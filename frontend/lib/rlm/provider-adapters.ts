import { Content, FunctionCall, GoogleGenAI, Part } from '@google/genai';
import { getAICredential } from '@/lib/ai-credentials';
import { allToolDeclarations } from './declarations';

export type RLMProvider = 'google' | 'openai' | 'openrouter' | 'ollama' | 'huggingface' | 'nvidia';

export interface RLMToolCall {
    id: string;
    name: string;
    args: Record<string, unknown>;
}

export interface RLMMessage {
    role: 'user' | 'assistant' | 'tool';
    content?: string;
    toolCalls?: RLMToolCall[];
    toolCallId?: string;
    name?: string;
}

export interface RLMGenerateRequest {
    provider: string;
    model: string;
    systemPrompt: string;
    messages: RLMMessage[];
    useTools: boolean;
    temperature?: number;
}

export interface RLMGenerateResponse {
    content: string;
    toolCalls: RLMToolCall[];
}

export class RLMProviderError extends Error {
    retryWithoutTools: boolean;

    constructor(message: string, retryWithoutTools = false) {
        super(message);
        this.name = 'RLMProviderError';
        this.retryWithoutTools = retryWithoutTools;
    }
}

const TOOL_CAPABLE_PROVIDERS = new Set<RLMProvider>([
    'google',
    'openai',
    'openrouter',
    'ollama',
    'nvidia',
]);

const OPENAI_COMPATIBLE_ENDPOINTS: Record<'openai' | 'openrouter' | 'nvidia', string> = {
    openai: 'https://api.openai.com/v1/chat/completions',
    openrouter: 'https://openrouter.ai/api/v1/chat/completions',
    nvidia: 'https://integrate.api.nvidia.com/v1/chat/completions',
};

export function normalizeRLMProvider(provider: string): RLMProvider {
    if (
        provider === 'google' ||
        provider === 'openai' ||
        provider === 'openrouter' ||
        provider === 'ollama' ||
        provider === 'huggingface' ||
        provider === 'nvidia'
    ) {
        return provider;
    }

    return 'google';
}

export function providerSupportsToolCalling(provider: string): boolean {
    return TOOL_CAPABLE_PROVIDERS.has(normalizeRLMProvider(provider));
}

export async function generateRLMResponse(request: RLMGenerateRequest): Promise<RLMGenerateResponse> {
    const provider = normalizeRLMProvider(request.provider);

    if (provider === 'google') {
        return generateGoogleResponse(request);
    }

    if (provider === 'openai' || provider === 'openrouter' || provider === 'nvidia') {
        return generateOpenAICompatibleResponse(provider, request);
    }

    if (provider === 'ollama') {
        return generateOllamaResponse(request);
    }

    return generateHuggingFaceResponse(request);
}

async function generateGoogleResponse(request: RLMGenerateRequest): Promise<RLMGenerateResponse> {
    const apiKey = await getAICredential('google');
    if (!apiKey) {
        throw new RLMProviderError('No Google AI API key configured.');
    }

    const ai = new GoogleGenAI({ apiKey });
    const response = await ai.models.generateContent({
        model: request.model,
        contents: toGoogleContents(request.messages),
        config: {
            systemInstruction: request.systemPrompt,
            tools: request.useTools ? [{ functionDeclarations: allToolDeclarations }] : undefined,
            temperature: request.temperature ?? 0.4,
        },
    });

    const parts = response.candidates?.[0]?.content?.parts || [];
    const toolCalls = parts
        .filter((part): part is Part & { functionCall: FunctionCall } => !!part.functionCall)
        .map((part, index) => ({
            id: `google_call_${Date.now()}_${index}`,
            name: part.functionCall.name || '',
            args: (part.functionCall.args || {}) as Record<string, unknown>,
        }))
        .filter(call => call.name);

    return {
        content: parts.filter(part => part.text).map(part => part.text).join(''),
        toolCalls,
    };
}

function toGoogleContents(messages: RLMMessage[]): Content[] {
    const contents: Content[] = [];
    let pendingToolResponses: Part[] = [];

    const flushToolResponses = () => {
        if (pendingToolResponses.length > 0) {
            contents.push({
                role: 'user',
                parts: pendingToolResponses,
            });
            pendingToolResponses = [];
        }
    };

    for (const message of messages) {
        if (message.role === 'tool') {
            pendingToolResponses.push({
                functionResponse: {
                    name: message.name || message.toolCallId || 'tool',
                    response: { result: message.content || '' },
                },
            });
            continue;
        }

        flushToolResponses();

        if (message.role === 'assistant' && message.toolCalls?.length) {
            contents.push({
                role: 'model',
                parts: message.toolCalls.map(call => ({
                    functionCall: {
                        name: call.name,
                        args: call.args,
                    },
                })),
            });
            continue;
        }

        contents.push({
            role: message.role === 'user' ? 'user' : 'model',
            parts: [{ text: message.content || '' }],
        });
    }

    flushToolResponses();
    return contents;
}

async function generateOpenAICompatibleResponse(
    provider: 'openai' | 'openrouter' | 'nvidia',
    request: RLMGenerateRequest,
): Promise<RLMGenerateResponse> {
    const apiKey = await getAICredential(provider);
    if (!apiKey) {
        throw new RLMProviderError(`No ${provider} API key configured.`);
    }

    const response = await postJson(
        OPENAI_COMPATIBLE_ENDPOINTS[provider],
        {
            model: request.model,
            messages: toOpenAICompatibleMessages(request.systemPrompt, request.messages),
            tools: request.useTools ? toOpenAICompatibleTools() : undefined,
            tool_choice: request.useTools ? 'auto' : undefined,
            temperature: request.temperature ?? 0.4,
        },
        {
            Authorization: `Bearer ${apiKey}`,
            ...(provider === 'openrouter'
                ? {
                    'HTTP-Referer': process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
                    'X-Title': '1GDPRAGENT',
                }
                : {}),
        },
        request.useTools,
    );

    const message = response.choices?.[0]?.message || {};
    const toolCalls = (message.tool_calls || []).map((toolCall: {
        id?: string;
        function?: { name?: string; arguments?: string | Record<string, unknown> };
    }, index: number) => ({
        id: toolCall.id || `${provider}_call_${Date.now()}_${index}`,
        name: toolCall.function?.name || '',
        args: parseToolArguments(toolCall.function?.arguments),
    })).filter((call: RLMToolCall) => call.name);

    return {
        content: message.content || '',
        toolCalls,
    };
}

function toOpenAICompatibleMessages(systemPrompt: string, messages: RLMMessage[]) {
    return [
        { role: 'system', content: systemPrompt },
        ...messages.map(message => {
            if (message.role === 'tool') {
                return {
                    role: 'tool',
                    tool_call_id: message.toolCallId,
                    name: message.name,
                    content: message.content || '',
                };
            }

            if (message.role === 'assistant' && message.toolCalls?.length) {
                return {
                    role: 'assistant',
                    content: message.content || null,
                    tool_calls: message.toolCalls.map(call => ({
                        id: call.id,
                        type: 'function',
                        function: {
                            name: call.name,
                            arguments: JSON.stringify(call.args),
                        },
                    })),
                };
            }

            return {
                role: message.role,
                content: message.content || '',
            };
        }),
    ];
}

function toOpenAICompatibleTools() {
    return allToolDeclarations.map(declaration => ({
        type: 'function',
        function: {
            name: declaration.name,
            description: declaration.description,
            parameters: toJsonSchema(declaration.parameters),
        },
    }));
}

function toJsonSchema(value: unknown): unknown {
    if (Array.isArray(value)) {
        return value.map(item => toJsonSchema(item));
    }

    if (!value || typeof value !== 'object') {
        return value;
    }

    const converted: Record<string, unknown> = {};
    for (const [key, entry] of Object.entries(value)) {
        converted[key] = key === 'type' && typeof entry === 'string'
            ? entry.toLowerCase()
            : toJsonSchema(entry);
    }

    return converted;
}

async function generateOllamaResponse(request: RLMGenerateRequest): Promise<RLMGenerateResponse> {
    const baseUrl = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';
    const apiKey = await getAICredential('ollama');
    const response = await postJson(
        `${baseUrl}/api/chat`,
        {
            model: request.model,
            messages: toOllamaMessages(request.systemPrompt, request.messages),
            tools: request.useTools ? toOpenAICompatibleTools() : undefined,
            stream: false,
            options: {
                temperature: request.temperature ?? 0.4,
            },
        },
        apiKey ? { Authorization: `Bearer ${apiKey}` } : {},
        request.useTools,
    );

    const message = response.message || {};
    const toolCalls = (message.tool_calls || []).map((toolCall: {
        function?: { name?: string; arguments?: string | Record<string, unknown> };
    }, index: number) => ({
        id: `ollama_call_${Date.now()}_${index}`,
        name: toolCall.function?.name || '',
        args: parseToolArguments(toolCall.function?.arguments),
    })).filter((call: RLMToolCall) => call.name);

    return {
        content: message.content || '',
        toolCalls,
    };
}

function toOllamaMessages(systemPrompt: string, messages: RLMMessage[]) {
    return [
        { role: 'system', content: systemPrompt },
        ...messages.map(message => {
            if (message.role === 'tool') {
                return {
                    role: 'tool',
                    content: message.content || '',
                    tool_name: message.name,
                };
            }

            if (message.role === 'assistant' && message.toolCalls?.length) {
                return {
                    role: 'assistant',
                    content: message.content || '',
                    tool_calls: message.toolCalls.map(call => ({
                        function: {
                            name: call.name,
                            arguments: call.args,
                        },
                    })),
                };
            }

            return {
                role: message.role,
                content: message.content || '',
            };
        }),
    ];
}

async function generateHuggingFaceResponse(request: RLMGenerateRequest): Promise<RLMGenerateResponse> {
    const apiKey = await getAICredential('huggingface');
    if (!apiKey) {
        throw new RLMProviderError('No Hugging Face API key configured.');
    }

    const modelPath = request.model.split('/').map(encodeURIComponent).join('/');
    const response = await postJson(
        `https://api-inference.huggingface.co/models/${modelPath}`,
        {
            inputs: toPlainPrompt(request.systemPrompt, request.messages),
            parameters: {
                temperature: request.temperature ?? 0.4,
                max_new_tokens: 1200,
                return_full_text: false,
            },
        },
        { Authorization: `Bearer ${apiKey}` },
        false,
    );

    const first = Array.isArray(response) ? response[0] : response;
    return {
        content: first?.generated_text || first?.summary_text || '',
        toolCalls: [],
    };
}

function toPlainPrompt(systemPrompt: string, messages: RLMMessage[]): string {
    const lines = [`System: ${systemPrompt}`];

    for (const message of messages) {
        if (message.role === 'tool') {
            lines.push(`Tool result (${message.name || 'tool'}): ${message.content || ''}`);
        } else {
            lines.push(`${message.role === 'assistant' ? 'Assistant' : 'User'}: ${message.content || ''}`);
        }
    }

    lines.push('Assistant:');
    return lines.join('\n\n');
}

async function postJson(
    url: string,
    body: Record<string, unknown>,
    headers: Record<string, string>,
    retryWithoutTools: boolean,
) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...headers,
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(60_000),
    });

    if (!response.ok) {
        const text = await response.text().catch(() => '');
        const canRetry = retryWithoutTools && (response.status === 400 || response.status === 422);
        throw new RLMProviderError(`${url} returned ${response.status}: ${text || response.statusText}`, canRetry);
    }

    return response.json();
}

function parseToolArguments(args: string | Record<string, unknown> | undefined): Record<string, unknown> {
    if (!args) {
        return {};
    }

    if (typeof args === 'object') {
        return args;
    }

    try {
        const parsed = JSON.parse(args);
        return parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
        return {};
    }
}
