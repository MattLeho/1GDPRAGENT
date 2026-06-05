import { NextRequest, NextResponse } from 'next/server';
import {
    AI_PROVIDER_IDS,
    getAICredential,
    normalizeAIProvider,
} from '@/lib/ai-credentials';
import type { AIProviderId } from '@/lib/ai-credentials';

interface ModelOption {
    id: string;
    name: string;
    provider: AIProviderId;
    contextWindow?: number;
    priceLabel: string;
    description?: string;
}

interface ModelFetchResult {
    models: ModelOption[];
    fallback?: boolean;
    message?: string;
}

const DEFAULT_DISCOVERY_TIMEOUT_MS = 8000;

const staticPrices: Record<string, string> = {
    'gpt-4.1': '$2.00/M input, $8.00/M output',
    'gpt-4.1-mini': '$0.40/M input, $1.60/M output',
    'gpt-4.1-nano': '$0.10/M input, $0.40/M output',
    'gpt-4o': '$2.50/M input, $10.00/M output',
    'gpt-4o-mini': '$0.15/M input, $0.60/M output',
    'gemini-3-flash-preview': 'Check Google pricing',
    'gemini-3-pro-preview': 'Check Google pricing',
};

const fallbackModels: Record<AIProviderId, ModelOption[]> = {
    google: [
        { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash Preview', provider: 'google', priceLabel: 'Check Google pricing' },
        { id: 'gemini-3-pro-preview', name: 'Gemini 3 Pro Preview', provider: 'google', priceLabel: 'Check Google pricing' },
    ],
    openai: [
        { id: 'gpt-4.1', name: 'GPT-4.1', provider: 'openai', priceLabel: staticPrices['gpt-4.1'] },
        { id: 'gpt-4.1-mini', name: 'GPT-4.1 Mini', provider: 'openai', priceLabel: staticPrices['gpt-4.1-mini'] },
        { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'openai', priceLabel: staticPrices['gpt-4o-mini'] },
    ],
    ollama: [
        { id: 'llama3.2', name: 'llama3.2', provider: 'ollama', priceLabel: 'Local/free' },
        { id: 'mistral', name: 'mistral', provider: 'ollama', priceLabel: 'Local/free' },
    ],
    openrouter: [
        { id: 'openai/gpt-4.1-mini', name: 'OpenAI GPT-4.1 Mini', provider: 'openrouter', priceLabel: 'Fetch OpenRouter pricing' },
        { id: 'google/gemini-2.5-flash', name: 'Google Gemini 2.5 Flash', provider: 'openrouter', priceLabel: 'Fetch OpenRouter pricing' },
    ],
    huggingface: [
        { id: 'mistralai/Mistral-7B-Instruct-v0.3', name: 'Mistral 7B Instruct', provider: 'huggingface', priceLabel: 'Varies by endpoint' },
        { id: 'meta-llama/Llama-3.1-8B-Instruct', name: 'Llama 3.1 8B Instruct', provider: 'huggingface', priceLabel: 'Varies by endpoint' },
    ],
    nvidia: [
        { id: 'meta/llama-3.1-8b-instruct', name: 'Llama 3.1 8B Instruct', provider: 'nvidia', priceLabel: 'Often free/credit-based' },
        { id: 'mistralai/mixtral-8x7b-instruct-v0.1', name: 'Mixtral 8x7B Instruct', provider: 'nvidia', priceLabel: 'Often free/credit-based' },
    ],
};

function getDiscoveryTimeoutMs(): number {
    const configured = Number(process.env.AI_MODEL_DISCOVERY_TIMEOUT_MS);
    if (!Number.isFinite(configured)) {
        return DEFAULT_DISCOVERY_TIMEOUT_MS;
    }

    return Math.min(Math.max(configured, 1000), 30000);
}

function withDiscoveryTimeout(init: RequestInit = {}): RequestInit {
    return {
        ...init,
        cache: 'no-store',
        signal: init.signal || AbortSignal.timeout(getDiscoveryTimeoutMs()),
    };
}

function normalizeModelOptions(models: ModelOption[], provider: AIProviderId): ModelOption[] {
    const seen = new Set<string>();

    return models
        .filter(model => model.id && model.name)
        .map(model => ({
            ...model,
            id: model.id.trim(),
            name: model.name.trim(),
            provider,
            priceLabel: model.priceLabel || 'Pricing unavailable',
        }))
        .filter(model => {
            if (!model.id || !model.name) {
                return false;
            }

            const key = model.id.toLowerCase();
            if (seen.has(key)) {
                return false;
            }

            seen.add(key);
            return true;
        });
}

function getOllamaBaseUrl(): string {
    return (process.env.OLLAMA_BASE_URL || 'http://localhost:11434')
        .trim()
        .replace(/\/+$/, '');
}

function formatOpenRouterPrice(value: string | undefined): string | null {
    if (!value) {
        return null;
    }

    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) {
        return null;
    }

    return `$${(numberValue * 1_000_000).toFixed(2)}/M`;
}

function formatOpenRouterPriceLabel(promptPrice: string | null, completionPrice: string | null): string {
    if (!promptPrice && !completionPrice) {
        return 'No pricing listed';
    }

    if (promptPrice === '$0.00/M' && completionPrice === '$0.00/M') {
        return 'Free';
    }

    if (promptPrice && completionPrice) {
        return `${promptPrice} input, ${completionPrice} output`;
    }

    return promptPrice ? `${promptPrice} input` : `${completionPrice} output`;
}

async function fetchGoogleModels(): Promise<ModelFetchResult> {
    const apiKey = await getAICredential('google');
    if (!apiKey) {
        return {
            models: fallbackModels.google,
            fallback: true,
            message: 'Google API key is not configured; showing recommended fallback models.',
        };
    }

    const url = new URL('https://generativelanguage.googleapis.com/v1beta/models');
    url.searchParams.set('key', apiKey);

    const response = await fetch(url, withDiscoveryTimeout());
    if (!response.ok) {
        throw new Error(`Google returned ${response.status}`);
    }

    const data = await response.json();
    const models = (data.models || [])
        .filter((model: { name?: string; supportedGenerationMethods?: string[] }) => model.supportedGenerationMethods?.includes('generateContent'))
        .map((model: { name: string; displayName?: string; description?: string; inputTokenLimit?: number }) => {
            const id = model.name.replace('models/', '');
            return {
                id,
                name: model.displayName || id,
                provider: 'google' as const,
                contextWindow: model.inputTokenLimit,
                priceLabel: staticPrices[id] || 'Check Google pricing',
                description: model.description,
            };
        });

    return { models };
}

async function fetchOpenAIModels(): Promise<ModelFetchResult> {
    const apiKey = await getAICredential('openai');
    if (!apiKey) {
        return {
            models: fallbackModels.openai,
            fallback: true,
            message: 'OpenAI API key is not configured; showing recommended fallback models.',
        };
    }

    const response = await fetch('https://api.openai.com/v1/models', {
        headers: { Authorization: `Bearer ${apiKey}` },
        ...withDiscoveryTimeout(),
    });
    if (!response.ok) {
        throw new Error(`OpenAI returned ${response.status}`);
    }

    const data = await response.json();
    const models = (data.data || [])
        .filter((model: { id?: string }) => model.id && /gpt|o\d|chat/i.test(model.id))
        .map((model: { id: string }) => ({
            id: model.id,
            name: model.id,
            provider: 'openai' as const,
            priceLabel: staticPrices[model.id] || 'Check OpenAI pricing',
        }));

    return { models };
}

async function fetchOllamaModels(): Promise<ModelFetchResult> {
    const response = await fetch(`${getOllamaBaseUrl()}/api/tags`, withDiscoveryTimeout());
    if (!response.ok) {
        throw new Error(`Ollama returned ${response.status}`);
    }

    const data = await response.json();
    const models = (data.models || []).map((model: { name: string; details?: { parameter_size?: string } }) => ({
        id: model.name,
        name: model.name,
        provider: 'ollama' as const,
        priceLabel: 'Local/free',
        description: model.details?.parameter_size,
    }));

    return { models };
}

async function fetchOpenRouterModels(): Promise<ModelFetchResult> {
    const apiKey = await getAICredential('openrouter');
    const response = await fetch('https://openrouter.ai/api/v1/models', {
        headers: apiKey ? { Authorization: `Bearer ${apiKey}` } : undefined,
        ...withDiscoveryTimeout(),
    });
    if (!response.ok) {
        throw new Error(`OpenRouter returned ${response.status}`);
    }

    const data = await response.json();
    const models = (data.data || []).map((model: {
        id: string;
        name?: string;
        description?: string;
        context_length?: number;
        pricing?: { prompt?: string; completion?: string };
    }) => {
        const promptPrice = formatOpenRouterPrice(model.pricing?.prompt);
        const completionPrice = formatOpenRouterPrice(model.pricing?.completion);
        return {
            id: model.id,
            name: model.name || model.id,
            provider: 'openrouter' as const,
            contextWindow: model.context_length,
            priceLabel: formatOpenRouterPriceLabel(promptPrice, completionPrice),
            description: model.description,
        };
    });

    return { models };
}

async function fetchHuggingFaceModels(): Promise<ModelFetchResult> {
    const apiKey = await getAICredential('huggingface');
    const response = await fetch('https://huggingface.co/api/models?pipeline_tag=text-generation&sort=trending&limit=50', {
        headers: apiKey ? { Authorization: `Bearer ${apiKey}` } : undefined,
        ...withDiscoveryTimeout(),
    });
    if (!response.ok) {
        throw new Error(`Hugging Face returned ${response.status}`);
    }

    const data = await response.json();
    const models = (data || []).map((model: { id: string; downloads?: number; likes?: number }) => ({
        id: model.id,
        name: model.id,
        provider: 'huggingface' as const,
        priceLabel: 'Varies by endpoint',
        description: `${model.downloads || 0} downloads, ${model.likes || 0} likes`,
    }));

    return { models };
}

async function fetchNvidiaModels(): Promise<ModelFetchResult> {
    const apiKey = await getAICredential('nvidia');
    if (!apiKey) {
        return {
            models: fallbackModels.nvidia,
            fallback: true,
            message: 'NVIDIA API key is not configured; showing recommended fallback models.',
        };
    }

    const response = await fetch('https://integrate.api.nvidia.com/v1/models', {
        headers: { Authorization: `Bearer ${apiKey}` },
        ...withDiscoveryTimeout(),
    });
    if (!response.ok) {
        throw new Error(`NVIDIA returned ${response.status}`);
    }

    const data = await response.json();
    const models = (data.data || []).map((model: { id: string; owned_by?: string }) => ({
        id: model.id,
        name: model.id,
        provider: 'nvidia' as const,
        priceLabel: 'Often free/credit-based',
        description: model.owned_by,
    }));

    return { models };
}

export async function GET(request: NextRequest) {
    const provider = normalizeAIProvider(request.nextUrl.searchParams.get('provider') || 'google');
    if (!provider) {
        return NextResponse.json(
            {
                error: 'Unsupported AI provider',
                supportedProviders: AI_PROVIDER_IDS,
            },
            { status: 400 },
        );
    }

    const fetchers: Record<AIProviderId, () => Promise<ModelFetchResult>> = {
        google: fetchGoogleModels,
        openai: fetchOpenAIModels,
        ollama: fetchOllamaModels,
        openrouter: fetchOpenRouterModels,
        huggingface: fetchHuggingFaceModels,
        nvidia: fetchNvidiaModels,
    };

    try {
        const result = await fetchers[provider]();
        const models = normalizeModelOptions(result.models, provider);

        if (models.length === 0) {
            throw new Error('Provider returned no compatible models');
        }

        return NextResponse.json({
            provider,
            models,
            fallback: Boolean(result.fallback),
            message: result.message,
            supportedProviders: AI_PROVIDER_IDS,
        });
    } catch (error) {
        console.warn(`[AI Models] Falling back for ${provider}:`, error);
        return NextResponse.json({
            provider,
            models: fallbackModels[provider],
            fallback: true,
            message: error instanceof Error ? error.message : 'Failed to fetch provider models',
            supportedProviders: AI_PROVIDER_IDS,
        });
    }
}
