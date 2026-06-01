/**
 * RLM Agent Orchestrator
 *
 * Core agent implementing the RLM (Recursive Language Model) agentic loop
 * with Gemini native function calling.
 *
 * Architecture:
 * 1. Build system prompt with GDPR expertise + request context
 * 2. Send user message + tool declarations to Gemini
 * 3. If model returns functionCalls → execute tools → send results back
 * 4. Repeat until model returns final text (max iterations)
 * 5. Return structured response
 *
 * Adapted from:
 * - RLM Paper: context-as-environment, recursive decomposition, selective retrieval
 * - RAG-Anything: hybrid retrieval, knowledge graph index, modality-aware ranking
 */

import { GoogleGenAI, Content, Part, FunctionCall } from '@google/genai';
import { allToolDeclarations } from './rlm/declarations';
import { executeTool } from './rlm/tools';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
    toolCalls?: { name: string; args: Record<string, unknown>; result: string }[];
}

export interface RLMResponse {
    content: string;
    toolsUsed: string[];
    iterations: number;
    error?: string;
}

interface ToolExecutionResult {
    name: string;
    args: Record<string, unknown>;
    result: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const MAX_ITERATIONS = 10;
const DEFAULT_MODEL = 'gemini-3.1-pro-preview';

const SYSTEM_PROMPT = `You are an expert GDPR Data Protection Assistant embedded in a privacy request management platform. You help users understand, process, and respond to GDPR data access requests (SARs), erasure requests, portability requests, and more.

## Your Capabilities
You have access to tools that let you:
1. **Search the Knowledge Graph** — query the Neo4j database for entities, relationships, personas, accounts, and connections discovered from uploaded documents.
2. **Search Documents** — find relevant content in uploaded files including extracted text, AI summaries, and transcripts.
3. **Look Up Privacy Policy** — get details about the current request, company, compliance status, and policy analysis.
4. **Get GDPR References** — retrieve specific GDPR articles, regulations, deadlines, and legal requirements.
5. **Decompose Complex Queries** — break down multi-part questions into simpler sub-queries for thorough analysis.

## Behavior Guidelines
- **Always use tools when relevant** — don't guess about document contents or request details, retrieve them.
- **Cite sources** — when referencing document content or GDPR articles, indicate where the information came from.
- **Be precise about legal matters** — when discussing GDPR obligations, cite specific articles and include response deadlines.
- **Be helpful but accurate** — if you can't find information, say so rather than fabricating answers.
- **Use decompose_query** when a question has multiple parts that need different types of information.
- **Respond in a professional, clear manner** suitable for data protection officers and compliance teams.
- **Structure longer responses** with headings and bullet points for readability.`;

// ─────────────────────────────────────────────────────────────────────────────
// Agent Class
// ─────────────────────────────────────────────────────────────────────────────

export class RLMAgent {
    private client: GoogleGenAI;
    private model: string;

    constructor() {
        const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
        if (!apiKey) {
            throw new Error('GEMINI_API_KEY or GOOGLE_API_KEY must be set');
        }
        this.client = new GoogleGenAI({ apiKey });
        this.model = process.env.GEMINI_MODEL_PRO || DEFAULT_MODEL;
    }

    /**
     * Main chat method — implements the RLM agentic loop.
     *
     * @param requestId - The GDPR request ID for scoping tool calls
     * @param userMessage - The user's message
     * @param conversationHistory - Previous messages for context
     */
    async chat(
        requestId: string,
        userMessage: string,
        conversationHistory: ChatMessage[] = [],
    ): Promise<RLMResponse> {
        const toolsUsed: string[] = [];
        let iterations = 0;

        try {
            // Build initial contents array from conversation history
            const contents: Content[] = this.buildContents(conversationHistory, userMessage);

            // Agentic loop — keep calling Gemini until it returns text (not tools)
            while (iterations < MAX_ITERATIONS) {
                iterations++;

                const response = await this.client.models.generateContent({
                    model: this.model,
                    contents,
                    config: {
                        systemInstruction: SYSTEM_PROMPT,
                        tools: [{ functionDeclarations: allToolDeclarations }],
                        temperature: 0.4,
                    },
                });

                // Get the response parts
                const candidate = response.candidates?.[0];
                if (!candidate?.content?.parts) {
                    return {
                        content: 'I apologize, but I was unable to generate a response. Please try rephrasing your question.',
                        toolsUsed,
                        iterations,
                        error: 'No candidate response from model',
                    };
                }

                const parts = candidate.content.parts;

                // Check if the model wants to call functions
                const functionCalls = parts.filter(
                    (p): p is Part & { functionCall: FunctionCall } => !!p.functionCall,
                );

                if (functionCalls.length === 0) {
                    // Model returned text — we're done
                    const textContent = parts
                        .filter(p => p.text)
                        .map(p => p.text)
                        .join('');

                    return {
                        content: textContent || 'No response generated.',
                        toolsUsed,
                        iterations,
                    };
                }

                // Execute all function calls in parallel
                const toolResults = await this.executeToolCalls(
                    requestId,
                    functionCalls,
                );

                // Track which tools were used
                for (const result of toolResults) {
                    if (!toolsUsed.includes(result.name)) {
                        toolsUsed.push(result.name);
                    }
                }

                // Append model's response (with function calls) to contents
                contents.push({
                    role: 'model',
                    parts: functionCalls.map(fc => ({ functionCall: fc.functionCall })),
                });

                // Append function responses
                contents.push({
                    role: 'user',
                    parts: toolResults.map(tr => ({
                        functionResponse: {
                            name: tr.name,
                            response: { result: tr.result },
                        },
                    })),
                });

                console.log(`[RLM] Iteration ${iterations}: executed ${toolResults.length} tool(s): ${toolResults.map(t => t.name).join(', ')}`);
            }

            // Max iterations reached — force a text response
            return {
                content: 'I gathered information using multiple tools but reached my processing limit. Please ask a more specific question for a detailed answer.',
                toolsUsed,
                iterations,
                error: 'Max iterations reached',
            };
        } catch (err) {
            console.error('[RLM] Agent error:', err);
            const message = err instanceof Error ? err.message : 'Unknown error';
            return {
                content: `I encountered an error while processing your request: ${message}. Please try again.`,
                toolsUsed,
                iterations,
                error: message,
            };
        }
    }

    /**
     * Build Gemini contents array from conversation history.
     */
    private buildContents(history: ChatMessage[], currentMessage: string): Content[] {
        const contents: Content[] = [];

        // Add conversation history (last 10 messages for context window management)
        const recentHistory = history.slice(-10);
        for (const msg of recentHistory) {
            contents.push({
                role: msg.role === 'user' ? 'user' : 'model',
                parts: [{ text: msg.content }],
            });
        }

        // Add current user message
        contents.push({
            role: 'user',
            parts: [{ text: currentMessage }],
        });

        return contents;
    }

    /**
     * Execute tool calls in parallel and return results.
     */
    private async executeToolCalls(
        requestId: string,
        functionCalls: (Part & { functionCall: FunctionCall })[],
    ): Promise<ToolExecutionResult[]> {
        const results = await Promise.all(
            functionCalls.map(async (fc) => {
                const name = fc.functionCall.name!;
                const args = (fc.functionCall.args || {}) as Record<string, unknown>;

                try {
                    const result = await executeTool(requestId, name, args);
                    return { name, args, result };
                } catch (err) {
                    const errorMsg = err instanceof Error ? err.message : 'Tool execution failed';
                    console.error(`[RLM] Tool "${name}" failed:`, err);
                    return { name, args, result: `Error: ${errorMsg}` };
                }
            }),
        );

        return results;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Singleton for reuse across API calls
// ─────────────────────────────────────────────────────────────────────────────

let agentInstance: RLMAgent | null = null;

export function getRLMAgent(): RLMAgent {
    if (!agentInstance) {
        agentInstance = new RLMAgent();
    }
    return agentInstance;
}
