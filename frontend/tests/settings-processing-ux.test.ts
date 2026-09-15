import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const source = (relativePath: string) => fs.readFileSync(path.join(process.cwd(), relativePath), 'utf8');

describe('processing privacy settings UX contract', () => {
  it('keeps edits as a draft until the server confirms them', () => {
    const component = source('components/settings/PrivacySecuritySection.tsx');
    expect(component).toContain('[draft, setDraft]');
    expect(component).toContain('Save processing policy');
    expect(component).toContain('Changes not saved');
    expect(component).toContain('setSettings(data.settings)');
    expect(component).not.toContain('const save = async (next: Settings)');
  });

  it('provides labelled controls, visible async status, and a load retry', () => {
    const component = source('components/settings/PrivacySecuritySection.tsx');
    expect(component).toContain('htmlFor="processing-mode"');
    expect(component).toContain('id="processing-mode"');
    expect(component).toContain('htmlFor="external-fallback"');
    expect(component).toContain('id="external-fallback"');
    expect(component).toContain('aria-live="polite"');
    expect(component).toContain('Retry privacy settings');
    expect(component).toContain('min-h-11 sm:min-h-9');
    expect(component).toContain('Approved external engines');
    expect(component).toContain('ENGINE_DEFINITIONS.filter');
  });

  it('checks non-authentication response failures before consuming settings', () => {
    const component = source('components/settings/PrivacySecuritySection.tsx');
    expect(component).toContain('if (!response.ok) throw new Error');
  });

  it('requires a valid boolean and known external engine allowlist on the server', () => {
    const router = source('lib/execution/router.ts');
    expect(router).toContain("typeof settings.external_fallback_enabled !== 'boolean'");
    expect(router).toContain("engine.execution_location !== 'external'");
    expect(router).toContain('new Set(settings.approved_external_engines)');
  });
});
