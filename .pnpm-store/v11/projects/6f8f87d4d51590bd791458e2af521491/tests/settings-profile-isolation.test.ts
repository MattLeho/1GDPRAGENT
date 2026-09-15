import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';

const mocks = vi.hoisted(() => ({
  authority: { userId: 'user-a', profileId: 'profile-a' },
  query: vi.fn(),
  getTaskRoutes: vi.fn(),
  saveTaskRoute: vi.fn(),
  getProcessingSettings: vi.fn(),
  saveProcessingSettings: vi.fn(),
}));

vi.mock('@/lib/api-session', () => ({
  requireApiSession: vi.fn(async () => mocks.authority),
}));
vi.mock('@/lib/db', () => ({ pool: { query: mocks.query } }));
vi.mock('@/lib/execution/router', () => ({
  getTaskRoutes: mocks.getTaskRoutes,
  saveTaskRoute: mocks.saveTaskRoute,
  getProcessingSettings: mocks.getProcessingSettings,
  saveProcessingSettings: mocks.saveProcessingSettings,
}));
vi.mock('@/lib/execution/registry', () => ({
  TASK_DEFINITIONS: [], ENGINE_DEFINITIONS: [], validateRegistry: () => [],
}));

import { GET as getTaskRoutes, POST as saveTaskRoute } from '@/app/api/settings/task-routes/route';
import { GET as getProcessing, POST as saveProcessing } from '@/app/api/settings/processing/route';
import { GET as getExecutionAudit } from '@/app/api/settings/execution-audit/route';
import fs from 'node:fs';
import path from 'node:path';

function request(path: string, method = 'GET', body?: unknown) {
  return new NextRequest(`https://gdpr.test${path}`, {
    method,
    headers: { 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

describe('SETTINGS-002 profile isolation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.authority.profileId = 'profile-a';
    mocks.query.mockResolvedValue({ rows: [] });
    mocks.getTaskRoutes.mockResolvedValue([]);
    mocks.saveTaskRoute.mockResolvedValue({ task_key: 'schema.validate' });
    mocks.getProcessingSettings.mockResolvedValue({ processing_mode: 'local_first', external_fallback_enabled: false, approved_external_engines: [] });
    mocks.saveProcessingSettings.mockResolvedValue({ processing_mode: 'strict_local', external_fallback_enabled: false, approved_external_engines: [] });
  });

  it('keeps two authenticated profiles on distinct configuration reads', async () => {
    await getTaskRoutes(request('/api/settings/task-routes'));
    mocks.authority.profileId = 'profile-b';
    await getTaskRoutes(request('/api/settings/task-routes'));

    expect(mocks.getTaskRoutes).toHaveBeenNthCalledWith(1, 'profile-a');
    expect(mocks.getTaskRoutes).toHaveBeenNthCalledWith(2, 'profile-b');
  });

  it('passes canonical session authority into task-route and processing reads/writes', async () => {
    await getTaskRoutes(request('/api/settings/task-routes'));
    await saveTaskRoute(request('/api/settings/task-routes', 'POST', { task_key: 'schema.validate' }));
    await getProcessing(request('/api/settings/processing'));
    await saveProcessing(request('/api/settings/processing', 'POST', { processing_mode: 'strict_local' }));

    expect(mocks.getTaskRoutes).toHaveBeenCalledWith('profile-a');
    expect(mocks.saveTaskRoute).toHaveBeenCalledWith('profile-a', { task_key: 'schema.validate' });
    expect(mocks.getProcessingSettings).toHaveBeenCalledWith('profile-a');
    expect(mocks.saveProcessingSettings).toHaveBeenCalledWith('profile-a', { processing_mode: 'strict_local' });
  });

  it('filters external processing audit records by canonical profile', async () => {
    await getExecutionAudit(request('/api/settings/execution-audit'));

    expect(mocks.query).toHaveBeenCalledWith(
      expect.stringMatching(/WHERE profile_id=\$2[\s\S]*execution_location='external'/),
      [true, 'profile-a'],
    );
  });

  it('persists profile ownership in execution configuration, runs, and N8N settings', () => {
    const router = fs.readFileSync(path.join(process.cwd(), 'lib/execution/router.ts'), 'utf8');
    const migration = fs.readFileSync(path.join(process.cwd(), '../database/migrations/034_settings_profile_ownership.sql'), 'utf8');
    expect(router).toContain('INSERT INTO analysis_runs(profile_id');
    expect(router).toContain('(profile_id,analysis_run_id,task_key');
    expect(migration).toContain('task_routes_profile_task_key_uidx');
    expect(migration).toContain('processing_settings_profile_uidx');
    expect(migration).toContain('n8n_webhooks_profile_name_uidx');
    expect(migration).toContain('execution_records_profile_started_idx');
  });
});
