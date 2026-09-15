import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const source = (relativePath: string) => fs.readFileSync(path.join(process.cwd(), relativePath), 'utf8');

describe('task route settings UX contract', () => {
  it('keeps route edits local until an explicit save is confirmed', () => {
    const component = source('components/settings/TaskRoutesSection.tsx');
    expect(component).toContain('[savedRoutes, setSavedRoutes]');
    expect(component).toContain('Unsaved changes');
    expect(component).toContain('Save route');
    expect(component).toContain('setSavedRoutes');
    expect(component).not.toContain('onValueChange={value=>update(route');
  });

  it('exposes retryable load and health states with task-specific accessible names', () => {
    const component = source('components/settings/TaskRoutesSection.tsx');
    expect(component).toContain('Retry task routes');
    expect(component).toContain('protectedApi');
    expect(component).toContain('aria-live="polite"');
    expect(component).toContain('Check ${task.display_name} engine health');
    expect(component).toContain('min-h-11 sm:min-h-9');
  });

  it('validates bounded route execution fields and configuration before persistence', () => {
    const router = source('lib/execution/router.ts');
    expect(router).toContain('Number.isSafeInteger(route.max_concurrency)');
    expect(router).toContain('Number.isSafeInteger(route.batch_size)');
    expect(router).toContain('Number.isSafeInteger(route.timeout_ms)');
    expect(router).toContain("route.execution_location !== engine.execution_location");
    expect(router).toContain('new Set(route.fallback_chain.map');
  });
});
