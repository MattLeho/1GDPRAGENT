import { pool } from '@/lib/db';
import { DEFAULT_AI_PROVIDER, normalizeAIProvider } from '@/lib/ai-credentials';
import type { AIProviderId } from '@/lib/ai-credentials';
import { resolveModelForProvider } from '@/lib/model-intents';

export type WorkflowBackend = 'built_in' | 'n8n' | 'hybrid';
export type ModelPurpose = 'default' | 'rlm' | 'drafting' | 'extraction' | 'graph' | 'policy';

export interface WorkflowModelPreference {
    provider: AIProviderId;
    model: string;
}

export interface ModelPreferences {
    workflowBackend: WorkflowBackend;
    provider: AIProviderId;
    model: string;
    workflowModels: Record<ModelPurpose, WorkflowModelPreference>;
}

interface ModelPreferencesInput {
    workflowBackend?: unknown;
    provider?: unknown;
    model?: unknown;
    workflowModels?: unknown;
}

const DEFAULT_MODEL_BY_PROVIDER: Record<AIProviderId, string> = {
    google: 'flash_latest',
    openai: 'gpt-4.1-mini',
    ollama: 'llama3.2',
    openrouter: 'openai/gpt-4.1-mini',
    huggingface: 'mistralai/Mistral-7B-Instruct-v0.3',
    nvidia: 'meta/llama-3.1-8b-instruct',
};

const DEFAULT_WORKFLOW_MODELS: Record<ModelPurpose, WorkflowModelPreference> = {
    default: { provider: DEFAULT_AI_PROVIDER, model: DEFAULT_MODEL_BY_PROVIDER[DEFAULT_AI_PROVIDER] },
    rlm: { provider: DEFAULT_AI_PROVIDER, model: DEFAULT_MODEL_BY_PROVIDER[DEFAULT_AI_PROVIDER] },
    drafting: { provider: DEFAULT_AI_PROVIDER, model: DEFAULT_MODEL_BY_PROVIDER[DEFAULT_AI_PROVIDER] },
    extraction: {
        provider: 'google',
        model: process.env.GEMINI_MODEL_EXTRACTION || process.env.GEMINI_MODEL_FLASH_LITE || 'flash_lite_latest',
    },
    graph: {
        provider: 'google',
        model: process.env.GEMINI_MODEL_GRAPH || process.env.GEMINI_MODEL_FLASH || 'flash_latest',
    },
    policy: {
        provider: 'google',
        model: process.env.GEMINI_MODEL_POLICY || process.env.GEMINI_MODEL_FLASH || 'flash_latest',
    },
};

const DEFAULT_PREFERENCES: ModelPreferences = {
    workflowBackend: 'built_in',
    provider: DEFAULT_AI_PROVIDER,
    model: DEFAULT_MODEL_BY_PROVIDER[DEFAULT_AI_PROVIDER],
    workflowModels: DEFAULT_WORKFLOW_MODELS,
};

async function ensurePreferencesTable() {
    await pool.query(`
        CREATE TABLE IF NOT EXISTS model_preferences (
            id INTEGER PRIMARY KEY DEFAULT 1,
            workflow_backend TEXT NOT NULL DEFAULT 'built_in',
            provider TEXT NOT NULL DEFAULT 'google',
            model TEXT NOT NULL DEFAULT 'flash_latest',
            workflow_models JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT single_model_preferences_row CHECK (id = 1)
        )
    `);

    await pool.query(`
        ALTER TABLE model_preferences
        ADD COLUMN IF NOT EXISTS workflow_models JSONB NOT NULL DEFAULT '{}'::jsonb
    `);

    await pool.query(`
        INSERT INTO model_preferences (id, workflow_backend, provider, model, workflow_models)
        VALUES (1, $1, $2, $3, $4::jsonb)
        ON CONFLICT (id) DO NOTHING
    `, [
        DEFAULT_PREFERENCES.workflowBackend,
        DEFAULT_PREFERENCES.provider,
        DEFAULT_PREFERENCES.model,
        JSON.stringify(DEFAULT_PREFERENCES.workflowModels),
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

function normalizeWorkflowModels(value: unknown): Record<ModelPurpose, WorkflowModelPreference> {
    const normalized: Record<ModelPurpose, WorkflowModelPreference> = { ...DEFAULT_WORKFLOW_MODELS };

    if (!value || typeof value !== 'object') {
        return normalized;
    }

    for (const purpose of Object.keys(DEFAULT_WORKFLOW_MODELS) as ModelPurpose[]) {
        const entry = (value as Record<string, unknown>)[purpose];
        if (!entry || typeof entry !== 'object') {
            continue;
        }

        const provider = normalizeAIProvider((entry as Record<string, unknown>).provider);
        if (!provider) {
            continue;
        }

        normalized[purpose] = {
            provider,
            model: normalizeModel((entry as Record<string, unknown>).model, provider),
        };
    }

    return normalized;
}

export async function getModelPreferences(): Promise<ModelPreferences> {
    try {
        await ensurePreferencesTable();
        const result = await pool.query(`
            SELECT workflow_backend, provider, model, workflow_models
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
            workflowModels: normalizeWorkflowModels(row.workflow_models),
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
        workflowModels: normalizeWorkflowModels(preferences.workflowModels),
    };

    await pool.query(`
        INSERT INTO model_preferences (id, workflow_backend, provider, model, workflow_models, updated_at)
        VALUES (1, $1, $2, $3, $4::jsonb, NOW())
        ON CONFLICT (id) DO UPDATE SET
            workflow_backend = EXCLUDED.workflow_backend,
            provider = EXCLUDED.provider,
            model = EXCLUDED.model,
            workflow_models = EXCLUDED.workflow_models,
            updated_at = NOW()
    `, [
        normalized.workflowBackend,
        normalized.provider,
        normalized.model,
        JSON.stringify(normalized.workflowModels),
    ]);

    return normalized;
}

export async function getWorkflowModelPreference(purpose: ModelPurpose): Promise<WorkflowModelPreference> {
    const preferences = await getModelPreferences();
    const preference = preferences.workflowModels[purpose] || preferences.workflowModels.default;

    return {
        ...preference,
        model: await resolveModelForProvider(preference.provider, preference.model),
    };
}
