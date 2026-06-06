import { getWorkflowModelPreference } from '@/lib/model-preferences';
import { executeTool } from './rlm/tools';
import {
    generateRLMResponse,
    providerSupportsToolCalling,
    RLMMessage,
    RLMProviderError,
    RLMToolCall,
} from './rlm/provider-adapters';

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
    id: string;
    name: string;
    args: Record<string, unknown>;
    result: string;
}

const MAX_ITERATIONS = 10;
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

export class RLMAgent {
    async chat(
        requestId: string,
        userMessage: string,
        conversationHistory: ChatMessage[] = [],
    ): Promise<RLMResponse> {
        const toolsUsed: string[] = [];
        let iterations = 0;

        try {
            const preferences = await getWorkflowModelPreference('rlm');
            const messages = this.buildMessages(conversationHistory, userMessage);
            const supportsTools = providerSupportsToolCalling(preferences.provider);

            if (!supportsTools) {
                return this.chatWithRetrievedContext(
                    requestId,
                    userMessage,
                    messages,
                    preferences.provider,
                    preferences.model,
                    toolsUsed,
                );
            }

            while (iterations < MAX_ITERATIONS) {
                iterations++;

                let modelResponse;
                try {
                    modelResponse = await generateRLMResponse({
                        provider: preferences.provider,
                        model: preferences.model,
                        systemPrompt: SYSTEM_PROMPT,
                        messages,
                        useTools: true,
                        temperature: 0.4,
                    });
                } catch (error) {
                    if (error instanceof RLMProviderError && error.retryWithoutTools) {
                        console.warn(`[RLM] ${preferences.provider}/${preferences.model} rejected tools; using retrieved-context fallback.`);
                        const fallbackResponse = await this.chatWithRetrievedContext(
                            requestId,
                            userMessage,
                            this.buildMessages(conversationHistory, userMessage),
                            preferences.provider,
                            preferences.model,
                            toolsUsed,
                        );
                        return {
                            ...fallbackResponse,
                            iterations: iterations + fallbackResponse.iterations - 1,
                        };
                    }

                    throw error;
                }

                if (modelResponse.toolCalls.length === 0) {
                    return {
                        content: modelResponse.content || 'No response generated.',
                        toolsUsed,
                        iterations,
                    };
                }

                const toolResults = await this.executeToolCalls(requestId, modelResponse.toolCalls);

                for (const result of toolResults) {
                    if (!toolsUsed.includes(result.name)) {
                        toolsUsed.push(result.name);
                    }
                }

                messages.push({
                    role: 'assistant',
                    content: modelResponse.content,
                    toolCalls: modelResponse.toolCalls,
                });

                for (const result of toolResults) {
                    messages.push({
                        role: 'tool',
                        toolCallId: result.id,
                        name: result.name,
                        content: result.result,
                    });
                }

                console.log(`[RLM] Iteration ${iterations}: executed ${toolResults.length} tool(s): ${toolResults.map(result => result.name).join(', ')}`);
            }

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

    private buildMessages(history: ChatMessage[], currentMessage: string): RLMMessage[] {
        const recentHistory = history.slice(-10).map(message => ({
            role: message.role === 'user' ? 'user' as const : 'assistant' as const,
            content: message.content,
        }));

        return [
            ...recentHistory,
            {
                role: 'user',
                content: currentMessage,
            },
        ];
    }

    private async executeToolCalls(
        requestId: string,
        toolCalls: RLMToolCall[],
    ): Promise<ToolExecutionResult[]> {
        return Promise.all(
            toolCalls.map(async (toolCall) => {
                try {
                    const result = await executeTool(requestId, toolCall.name, toolCall.args);
                    return { ...toolCall, result };
                } catch (err) {
                    const errorMsg = err instanceof Error ? err.message : 'Tool execution failed';
                    console.error(`[RLM] Tool "${toolCall.name}" failed:`, err);
                    return { ...toolCall, result: `Error: ${errorMsg}` };
                }
            }),
        );
    }

    private async chatWithRetrievedContext(
        requestId: string,
        userMessage: string,
        messages: RLMMessage[],
        provider: string,
        model: string,
        toolsUsed: string[],
    ): Promise<RLMResponse> {
        const contextResults = await this.collectFallbackContext(requestId, userMessage);

        for (const result of contextResults) {
            if (!toolsUsed.includes(result.name)) {
                toolsUsed.push(result.name);
            }
        }

        const currentMessage = messages[messages.length - 1];
        const messagesWithContext = [
            ...messages.slice(0, -1),
            {
                role: 'user' as const,
                content: `The selected model/provider does not expose compatible tool calling, so these platform tool results were retrieved before generation:\n\n${contextResults.map(result => `## ${result.name}\n${result.result}`).join('\n\n')}`,
            },
            currentMessage,
        ];

        const response = await generateRLMResponse({
            provider,
            model,
            systemPrompt: SYSTEM_PROMPT,
            messages: messagesWithContext,
            useTools: false,
            temperature: 0.4,
        });

        return {
            content: response.content || 'No response generated.',
            toolsUsed,
            iterations: 1,
        };
    }

    private async collectFallbackContext(
        requestId: string,
        userMessage: string,
    ): Promise<ToolExecutionResult[]> {
        const fallbackCalls: RLMToolCall[] = [
            {
                id: 'fallback_lookup_privacy_policy',
                name: 'lookup_privacy_policy',
                args: {},
            },
            {
                id: 'fallback_search_documents',
                name: 'search_documents',
                args: { query: userMessage },
            },
            {
                id: 'fallback_search_knowledge_graph',
                name: 'search_knowledge_graph',
                args: { query: userMessage },
            },
            {
                id: 'fallback_get_gdpr_reference',
                name: 'get_gdpr_reference',
                args: { topic: userMessage },
            },
        ];

        return this.executeToolCalls(requestId, fallbackCalls);
    }
}

let agentInstance: RLMAgent | null = null;

export function getRLMAgent(): RLMAgent {
    if (!agentInstance) {
        agentInstance = new RLMAgent();
    }
    return agentInstance;
}
