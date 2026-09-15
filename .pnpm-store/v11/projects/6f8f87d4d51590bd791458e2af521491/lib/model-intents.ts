import { getAICredential } from '@/lib/ai-credentials';

export type ModelIntent = 'flash_lite_latest' | 'flash_latest' | 'pro_latest';

export const MODEL_INTENT_LABELS: Record<ModelIntent, string> = {
    flash_lite_latest: 'Latest Flash Lite',
    flash_latest: 'Latest Flash',
    pro_latest: 'Latest Pro',
};

export const MODEL_INTENT_FALLBACKS: Record<ModelIntent, string> = {
    flash_lite_latest: 'gemini-3.1-flash-lite',
    flash_latest: 'gemini-3.1-flash',
    pro_latest: 'gemini-3.1-pro',
};

const MODEL_DISCOVERY_TIMEOUT_MS = 6000;

export function isModelIntent(model: string): model is ModelIntent {
    return model === 'flash_lite_latest' || model === 'flash_latest' || model === 'pro_latest';
}

function parseVersionScore(modelId: string): number {
    const versionMatch = modelId.match(/gemini-(\d+(?:\.\d+)?)/i);
    if (!versionMatch) {
        return 0;
    }

    const version = Number(versionMatch[1]);
    return Number.isFinite(version) ? version : 0;
}

function pickLatestModel(models: string[], intent: ModelIntent): string | null {
    const candidates = models.filter(model => {
        const normalized = model.toLowerCase();
        if (normalized.includes('preview') || normalized.includes('experimental')) {
            return false;
        }

        if (intent === 'flash_lite_latest') {
            return normalized.includes('flash-lite');
        }

        if (intent === 'flash_latest') {
            return normalized.includes('flash') && !normalized.includes('flash-lite');
        }

        return normalized.includes('pro');
    });

    return candidates.sort((a, b) => parseVersionScore(b) - parseVersionScore(a) || b.localeCompare(a))[0] || null;
}

export async function resolveGoogleModelIntent(model: string): Promise<string> {
    if (!isModelIntent(model)) {
        return model;
    }

    try {
        const apiKey = await getAICredential('google');
        if (!apiKey) {
            return MODEL_INTENT_FALLBACKS[model];
        }

        const url = new URL('https://generativelanguage.googleapis.com/v1beta/models');
        url.searchParams.set('key', apiKey);

        const response = await fetch(url, {
            cache: 'no-store',
            signal: AbortSignal.timeout(MODEL_DISCOVERY_TIMEOUT_MS),
        });

        if (!response.ok) {
            return MODEL_INTENT_FALLBACKS[model];
        }

        const data = await response.json();
        const models = (data.models || [])
            .filter((entry: { name?: string; supportedGenerationMethods?: string[] }) =>
                entry.name && entry.supportedGenerationMethods?.includes('generateContent'))
            .map((entry: { name: string }) => entry.name.replace('models/', ''));

        return pickLatestModel(models, model) || MODEL_INTENT_FALLBACKS[model];
    } catch {
        return MODEL_INTENT_FALLBACKS[model];
    }
}

export async function resolveModelForProvider(provider: string, model: string): Promise<string> {
    if (provider === 'google') {
        return resolveGoogleModelIntent(model);
    }

    return model;
}
