import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { validateConnectorDraft } from '@/lib/connectors/configuration';

const source = (relativePath: string) => fs.readFileSync(path.join(process.cwd(), relativePath), 'utf8');

describe('Source Connectors settings contract', () => {
  it('retains queued task identity and reads profile-scoped connector health', () => {
    const component = source('components/settings/SourceConnectorsSection.tsx');
    const client = source('lib/connectors/client.ts');
    expect(client).toContain('SyncQueuedResult');
    expect(client).toContain('fetchConnectorHealth');
    expect(component).toContain('result.task_id');
    expect(component).toContain('Sync queued');
    expect(component).not.toContain('Sync scheduled');
    expect(component).toContain('aria-live="polite"');
    expect(component).toContain('Retry source connectors');
  });

  it('labels fields, preserves compact touch targets, and discloses server-visible paths', () => {
    const component = source('components/settings/SourceConnectorsSection.tsx');
    expect(component).toContain('<Label htmlFor={id}>');
    expect(component).toContain('min-h-11 sm:min-h-9');
    expect(component).toContain('visible inside the Intelligence runtime');
    expect(component).toContain('/source-uploads/');
    expect(component).not.toContain('placeholder="C:\\Users\\You');
  });

  it('rejects incomplete or relative connector configuration before creation', () => {
    expect(() => validateConnectorDraft('email.imap', { path: '', host: '', account: '' }))
      .toThrow('Email account and IMAP host are required');
    expect(() => validateConnectorDraft('filesystem.scoped', { path: 'relative/folder', host: '', account: '' }))
      .toThrow('absolute path');
    expect(validateConnectorDraft('filesystem.scoped', { path: '/source-uploads/mail', host: '', account: 'default' }))
      .toEqual({ roots: ['/source-uploads/mail'] });
  });

  it('returns a stable proxy error without exposing internal exception details', () => {
    const route = source('app/api/connectors/[[...path]]/route.ts');
    expect(route).toContain("{detail:'Connector service is unavailable'}");
    expect(route).not.toContain('error:error instanceof Error');
  });

  it('keeps the selected settings section in the URL for reload and back navigation', () => {
    const page = source('app/dashboard/settings/page.tsx');
    expect(page).toContain("searchParams.get('section')");
    expect(page).toContain("window.addEventListener('popstate', syncSection)");
    expect(page).toContain("url.searchParams.set('section', value)");
  });
});
