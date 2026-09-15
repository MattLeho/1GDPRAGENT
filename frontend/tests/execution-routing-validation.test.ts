import { describe, expect, it } from 'vitest';
import {
  normalizeProcessingSettings,
  validateTaskRoute,
  type ProcessingSettings,
  type TaskRoute,
} from '@/lib/execution/router';

const route = (changes: Partial<TaskRoute> = {}): TaskRoute => ({
  task_key: 'schema.fingerprinting',
  engine_id: 'deterministic_json',
  provider: null,
  model: null,
  execution_location: 'local',
  fallback_chain: [],
  enabled: true,
  max_concurrency: 1,
  batch_size: 1,
  timeout_ms: 60_000,
  configuration: {},
  ...changes,
});

describe('execution route validation', () => {
  it('accepts a valid route and rejects unsafe numeric or location fields', () => {
    expect(() => validateTaskRoute(route())).not.toThrow();
    expect(() => validateTaskRoute(route({ max_concurrency: 0 }))).toThrow('Max concurrency');
    expect(() => validateTaskRoute(route({ batch_size: Number.NaN }))).toThrow('Batch size');
    expect(() => validateTaskRoute(route({ timeout_ms: 999 }))).toThrow('Timeout');
    expect(() => validateTaskRoute(route({ execution_location: 'external' }))).toThrow('execution location');
  });

  it('rejects duplicate, primary, or malformed fallbacks', () => {
    expect(() => validateTaskRoute(route({ fallback_chain: [
      { engine_id: 'deterministic_json' },
      { engine_id: 'deterministic_json' },
    ] }))).toThrow('unique');
    expect(() => validateTaskRoute(route({ fallback_chain: [{ engine_id: 'deterministic_json' }] }))).toThrow('Primary engine');
  });

  it('normalizes a unique known-external allowlist and rejects invalid entries', () => {
    const base: ProcessingSettings = {
      processing_mode: 'controlled_cloud',
      external_fallback_enabled: false,
      approved_external_engines: ['openai_generation', 'openai_generation'],
    };
    expect(normalizeProcessingSettings(base).approved_external_engines).toEqual(['openai_generation']);
    expect(() => normalizeProcessingSettings({ ...base, approved_external_engines: ['ollama_generation'] }))
      .toThrow('invalid');
  });
});
