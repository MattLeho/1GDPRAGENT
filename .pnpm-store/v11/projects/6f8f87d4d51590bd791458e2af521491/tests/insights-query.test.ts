import { describe, expect, it } from 'vitest';
import {
  defaultInsightSelection,
  parseInsightSelection,
  serializeInsightSelection,
} from '../lib/insights/query';

describe('Personal Insights temporal query contract', () => {
  const now = new Date('2026-08-15T16:30:00.000Z');

  it('produces a deterministic default when server and client share the same snapshot', () => {
    const server = parseInsightSelection(new URLSearchParams(), now);
    const client = parseInsightSelection(new URLSearchParams(), new Date(now.toISOString()));

    expect(server).toEqual(client);
    expect(server).toEqual(defaultInsightSelection(now));
  });

  it('round-trips explicit period values without consulting a runtime-local clock', () => {
    const selection = {
      mode: 'period' as const,
      granularity: 'quarter' as const,
      from: '2025-01-01T00:00:00.000Z',
      to: '2026-01-01T00:00:00.000Z',
    };

    expect(parseInsightSelection(serializeInsightSelection(selection), now)).toEqual(selection);
  });
});

