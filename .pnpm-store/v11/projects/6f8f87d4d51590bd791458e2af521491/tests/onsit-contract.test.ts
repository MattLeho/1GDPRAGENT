import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';

const mocks = vi.hoisted(() => ({
  authority: { userId: 'user-a', profileId: 'profile-a' },
}));

vi.mock('@/lib/api-session', () => ({
  requireApiSession: vi.fn(async () => mocks.authority),
  intelligenceAuthorityHeaders: vi.fn(() => ({ 'x-gdpr-profile-id': 'profile-a' })),
}));

import { GET as getStatus } from '@/app/api/onsit/status/[taskId]/route';
import { GET as getFindings } from '@/app/api/onsit/findings/[id]/route';

const discoveryFormSource = readFileSync(resolve(process.cwd(), 'components/onsit/DiscoveryForm.tsx'), 'utf8');
const progressSource = readFileSync(resolve(process.cwd(), 'components/onsit/ProgressTracker.tsx'), 'utf8');
const pageSource = readFileSync(resolve(process.cwd(), 'app/dashboard/onsit/page.tsx'), 'utf8');
const discoverRouteSource = readFileSync(resolve(process.cwd(), 'app/api/onsit/discover/route.ts'), 'utf8');
const exportRouteSource = readFileSync(resolve(process.cwd(), 'app/api/onsit/export/route.ts'), 'utf8');

function request(path: string) {
  return new NextRequest(`https://gdpr.test${path}`);
}

describe('ONSIT UI/API contract', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('maps service fractional progress to a truthful UI percentage without invented steps', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      scan_id: 'scan-1', status: 'completed', progress: 1, findings_count: 2,
      started_at: '2026-09-10T12:00:00.000Z', completed_at: '2026-09-10T12:01:00.000Z',
    }), { status: 200, headers: { 'content-type': 'application/json' } })));

    const response = await getStatus(request('/api/onsit/status/scan-1'), {
      params: Promise.resolve({ taskId: 'scan-1' }),
    });
    const body = await response.json();

    expect(body).toMatchObject({
      taskId: 'scan-1', status: 'completed', progress: 100,
      currentStep: 'Discovery complete', findingsCount: 2, steps: [],
    });
  });

  it('normalizes the Python finding envelope into the card contract', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ findings: [{
      type: 'Finding',
      label: 'Email: person@example.com',
      source: null,
      data: {
        finding_type: 'Email', value: 'person@example.com', risk_level: 'medium',
        confidence: 0.8, discovered_at: '2026-09-10T12:00:00.000Z',
      },
    }] }), { status: 200, headers: { 'content-type': 'application/json' } })));

    const response = await getFindings(request('/api/onsit/findings/scan-1'), {
      params: Promise.resolve({ id: 'scan-1' }),
    });
    const body = await response.json();

    expect(body.findings[0]).toMatchObject({
      type: 'Email', title: 'Email: person@example.com',
      sourcePlatform: 'Unknown provider', riskLevel: 'medium', confidence: 0.8,
      discoveredAt: '2026-09-10T12:00:00.000Z',
    });
    expect(body.findings[0].id).toMatch(/^onsit-/);
  });

  it('validates discovery seeds and avoids unsupported operational claims', () => {
    expect(discoveryFormSource).toContain('resolver: zodResolver(discoveryFormSchema)');
    expect(discoveryFormSource).toContain('Add at least one email, username, phone number, or domain');
    expect(discoveryFormSource).not.toContain('500+');
    expect(progressSource).not.toContain('500+');
    expect(pageSource).not.toContain('500+');
    expect(pageSource).not.toContain('handleAddToGraph');
    expect(pageSource).not.toContain('handleBulkAddToGraph');
  });

  it('resumes a service-bound task from the URL and discloses the durability boundary', () => {
    expect(pageSource).toContain("new URLSearchParams(window.location.search).get('task')");
    expect(pageSource).toContain('router.replace(`/dashboard/onsit?task=');
    expect(pageSource).toContain('scan history is not yet durable across service restarts');
    expect(pageSource).toContain('Discovery finished, but findings could not be loaded');
    expect(discoverRouteSource).not.toContain("details: errorText");
  });

  it('never fabricates export findings and scopes graph exports to the active profile', () => {
    expect(exportRouteSource).toContain('n.profile_id = $profileId');
    expect(exportRouteSource).toContain('profileId: authority.profileId');
    expect(exportRouteSource).not.toContain('sampleFindings');
    expect(exportRouteSource).not.toContain('user@example.com');
    expect(exportRouteSource).toContain("{ status: 503 }");
  });
});
