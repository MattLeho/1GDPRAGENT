import { beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const mocks = vi.hoisted(() => ({
    authority: { profileId: 'profile-a', userId: 'user-a' },
    query: vi.fn(),
    safeQuery: vi.fn(),
    getRequest: vi.fn(),
}));

vi.mock('@/lib/api-session', () => ({
    requireServerSessionAuthority: vi.fn(async () => mocks.authority),
}));
vi.mock('@/lib/db', () => ({
    db: { query: mocks.query },
    safeQuery: mocks.safeQuery,
}));
vi.mock('@/lib/requests/service', () => ({
    RequestService: class { get = mocks.getRequest; },
}));
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

import { getRequestAnalysis, savePolicyAnalysis } from '@/lib/actions/policy-analysis';

const persistedRow = {
    id: 'policy-a', request_id: 'request-a', profile_id: 'profile-a', url: 'https://example.test/privacy',
    dpo_email: 'dpo@example.test', company_address: null, data_collected: [], retention_period: null,
    third_party_sharing: [], analysis_raw: {}, provenance: { source: 'policy-claims' },
    execution_record_id: 'execution-a', created_at: new Date('2026-09-11T12:00:00.000Z'),
};

describe('request-owned policy analyses', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mocks.authority.profileId = 'profile-a';
        mocks.getRequest.mockResolvedValue({ id: 'request-a', profile_id: 'profile-a' });
        mocks.query.mockResolvedValue({ rows: [persistedRow] });
        mocks.safeQuery.mockResolvedValue({ rows: [persistedRow], error: null });
    });

    it('persists against the session profile and exact owned request, not global URL identity', async () => {
        const saved = await savePolicyAnalysis({
            requestId: 'request-a', url: 'https://example.test/privacy', dpo_email: 'dpo@example.test',
            provenance: { source: 'policy-claims' }, executionRecordId: 'execution-a',
        });

        expect(saved).toMatchObject({ success: true, analysis: { request_id: 'request-a', execution_record_id: 'execution-a' } });
        expect(mocks.getRequest).toHaveBeenCalledWith('profile-a', 'request-a');
        const [sql, values] = mocks.query.mock.calls[0];
        expect(sql).toMatch(/profile_id,\s*request_id/i);
        expect(sql).toMatch(/ON CONFLICT\s*\(profile_id,\s*request_id,\s*url\)/i);
        expect(values).toContain('profile-a');
        expect(values).toContain('request-a');
    });

    it('reads only the exact request under the session profile', async () => {
        await expect(getRequestAnalysis('request-a')).resolves.toMatchObject({ id: 'policy-a', request_id: 'request-a' });

        const [sql, values] = mocks.safeQuery.mock.calls[0];
        expect(sql).toMatch(/request_id\s*=\s*\$1/i);
        expect(sql).toMatch(/profile_id\s*=\s*\$2/i);
        expect(values).toEqual(['request-a', 'profile-a']);
        expect(sql).not.toMatch(/ILIKE/);
    });

    it('does not write a foreign request even when the URL matches', async () => {
        mocks.getRequest.mockResolvedValue(null);

        await expect(savePolicyAnalysis({ requestId: 'request-b', url: 'https://example.test/privacy' }))
            .resolves.toMatchObject({ success: false, error: 'Request not found' });
        expect(mocks.query).not.toHaveBeenCalled();
    });

    it('keeps the same policy URL in separate profile/request ownership scopes', async () => {
        await savePolicyAnalysis({ requestId: 'request-a', url: 'https://example.test/privacy' });
        mocks.authority.profileId = 'profile-b';
        mocks.getRequest.mockResolvedValue({ id: 'request-b', profile_id: 'profile-b' });

        await savePolicyAnalysis({ requestId: 'request-b', url: 'https://example.test/privacy' });

        expect(mocks.query.mock.calls[0]?.[1]).toContain('profile-a');
        expect(mocks.query.mock.calls[0]?.[1]).toContain('request-a');
        expect(mocks.query.mock.calls[1]?.[1]).toContain('profile-b');
        expect(mocks.query.mock.calls[1]?.[1]).toContain('request-b');
    });

    it('keeps pre-request N8N analysis transient and profile-scopes the legacy lookup', () => {
        const n8nRoute = fs.readFileSync(path.join(process.cwd(), 'app/api/n8n/analyze-policy/route.ts'), 'utf8');
        const legacyAction = fs.readFileSync(path.join(process.cwd(), 'lib/actions/policy.ts'), 'utf8');
        const rlmTools = fs.readFileSync(path.join(process.cwd(), 'lib/rlm/tools.ts'), 'utf8');

        expect(n8nRoute).toMatch(/persisted:\s*false/);
        expect(n8nRoute).not.toMatch(/savePolicyAnalysis/);
        expect(legacyAction).toMatch(/WHERE profile_id = \$1/);
        expect(legacyAction).not.toMatch(/INSERT INTO policy_analyses/);
        expect(rlmTools).toMatch(/WHERE profile_id = \$1 AND request_id = \$2/);
        expect(rlmTools).not.toMatch(/WHERE domain = \$1/);
    });
});
