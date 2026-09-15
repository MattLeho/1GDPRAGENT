import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const source = (relativePath: string) => fs.readFileSync(path.join(process.cwd(), relativePath), 'utf8');

describe('N8N settings UX and disclosure contract', () => {
  it('does not expose raw environment webhook URLs to authenticated clients', () => {
    const route = source('app/api/settings/n8n-webhooks/route.ts');
    expect(route).not.toContain('currentUrls: getEnvUrls()');
    expect(route).not.toContain('const envUrls = getEnvUrls()');
  });

  it('does not offer the nonexistent Test All action', () => {
    const component = source('components/settings/N8NWebhooksSection.tsx');
    expect(component).not.toContain('/api/settings/n8n-webhooks/test');
    expect(component).not.toContain('Test All');
  });

  it('provides named, touch-sized URL reveal controls and narrow reflow', () => {
    const component = source('components/settings/N8NWebhooksSection.tsx');
    expect(component).toContain('aria-label={isShown ?');
    expect(component).toContain('h-11 w-11');
    expect(component).toMatch(/flex flex-col gap-3[^\"]*sm:flex-row/);
  });

  it('scopes saved webhook reads and writes to the authenticated profile', () => {
    const route = source('app/api/settings/n8n-webhooks/route.ts');
    const utility = source('lib/n8n-webhooks.ts');
    const client = source('lib/n8n-client.ts');
    expect(route).toContain('WHERE profile_id = $1 AND is_active = true');
    expect(route).toContain('ON CONFLICT (profile_id, webhook_name)');
    expect(utility).toContain('profileId: string');
    expect(utility).toContain('profile_id = $2');
    expect(client).toContain('getWebhookUrl(webhookType, profileId)');
  });

  it('validates every override before using one transaction and reports load failure', () => {
    const route = source('app/api/settings/n8n-webhooks/route.ts');
    const component = source('components/settings/N8NWebhooksSection.tsx');
    expect(route).toContain('validateN8nWebhookUrl(url)');
    expect(route.indexOf('validateN8nWebhookUrl(url)')).toBeLessThan(route.indexOf("await client.query('BEGIN')"));
    expect(route).toContain("await client.query('ROLLBACK')");
    expect(route).toContain("{ status: 503 }");
    expect(component).toContain("toast.error('Could not load N8N webhook settings')");
  });
});
