import { pool } from '@/lib/db';
import { DEFAULT_AI_PROVIDER, normalizeAIProvider } from '@/lib/ai-credentials';
import type { AIProviderId } from '@/lib/ai-credentials';

export type WorkflowBackend = 'built_in' | 'n8n' | 'hybrid';

export interface ModelPreferences {
    workflowBackend: WorkflowBackend;
    provider: AIProviderId;
    model: string;
}

interface ModelPreferencesInput {
    workflowBackend?: unknown;
    provider?: unknown;
    model?: unknown;
}

const DEFAULT_MODEL_BY_PROVIDER: Record<AIProviderId, string> = {
    google: 'gemini-3-flash-preview',
    openai: 'gpt-4.1-mini',
    ollama: 'llama3.2',
    openrouter: 'openai/gpt-4.1-mini',
    huggingface: 'mistralai/Mistral-7B-Instruct-v0.3',
    nvidia: 'meta/llama-3.1-8b-instruct',
};

const DEFAULT_PREFERENCES: ModelPreferences = {
    workflowBackend: 'built_in',
    provider: DEFAULT_AI_PROVIDER,
    model: DEFAULT_MODEL_BY_PROVIDER[DEFAULT_AI_PROVIDER],
};

async function ensurePreferencesTable() {
    await pool.query(`
        CREATE TABLE IF NOT EXISTS model_preferences (
            id INTEGER PRIMARY KEY DEFAULT 1,
            workflow_backend TEXT NOT NULL DEFAULT 'built_in',
            provider TEXT NOT NULL DEFAULT 'google',
            model TEXT NOT NULL DEFAULT 'gemini-3-flash-preview',
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT single_model_preferences_row CHECK (id = 1)
        )
    `);

    await pool.query(`
        INSERT INTO model_preferences (id, workflow_backend, provider, model)
        VALUES (1, $1, $2, $3)
        ON CONFLICT (id) DO NOTHING
    `, [
        DEFAULT_PREFERENCES.workflowBackend,
        DEFAULT_PREFERENCES.provider,
        DEFAULT_PREFERENCES.model,
    ]);
}

function normalizeWorkflowBackend(value: unknown): WorkflowBackend {
    if (value === 'n8n' || value === 'hybrid' || value === 'built_in') {
        return value;
    }

    return DEFAULT_PREFERENCES.workflowBackend;
}

function normalizeModel(value: unknown, provider: AIProviderId): string {
    if (typeof value !== 'string') {
        return DEFAULT_MODEL_BY_PROVIDER[provider];
    }

    const normalizedModel = value.trim();
    if (!normalizedModel || normalizedModel.length > 200) {
        return DEFAULT_MODEL_BY_PROVIDER[provider];
    }

    return normalizedModel;
}

export async function getModelPreferences(): Promise<ModelPreferences> {
    try {
        await ensurePreferencesTable();
        const result = await pool.query(`
            SELECT workflow_backend, provider, model
            FROM model_preferences
            WHERE id = 1
        `);

        const row = result.rows[0];
        if (!row) {
            return DEFAULT_PREFERENCES;
        }

        const provider = normalizeAIProvider(row.provider) || DEFAULT_PREFERENCES.provider;

        return {
            workflowBackend: normalizeWorkflowBackend(row.workflow_backend),
            provider,
            model: normalizeModel(row.model, provider),
        };
    } catch (error) {
        console.warn('[Model Preferences] Falling back to defaults:', error);
        return DEFAULT_PREFERENCES;
    }
}

export async function saveModelPreferences(preferences: ModelPreferencesInput): Promise<ModelPreferences> {
    await ensurePreferencesTable();

    const provider = normalizeAIProvider(preferences.provider) || DEFAULT_PREFERENCES.provider;
    const normalized: ModelPreferences = {
        workflowBackend: normalizeWorkflowBackend(preferences.workflowBackend),
        provider,
        model: normalizeModel(preferences.model, provider),
    };

    await pool.query(`
        INSERT INTO model_preferences (id, workflow_backend, provider, model, updated_at)
        VALUES (1, $1, $2, $3, NOW())
        ON CONFLICT (id) DO UPDATE SET
            workflow_backend = EXCLUDED.workflow_backend,
            provider = EXCLUDED.provider,
            model = EXCLUDED.model,
            updated_at = NOW()
    `, [normalized.workflowBackend, normalized.provider, normalized.model]);

    return normalized;
}
