import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const dashboardAction = readFileSync(resolve(process.cwd(), 'lib/actions/dashboard.ts'), 'utf8');
const requestRepository = readFileSync(resolve(process.cwd(), 'lib/requests/repository.ts'), 'utf8');
const dashboardPersistence = `${dashboardAction}\n${requestRepository}`;
const presentationFiles = [
    'app/dashboard/home/page.tsx',
    'components/dashboard/StatsOverview.tsx',
    'components/dashboard/PrivacyScoreCard.tsx',
    'components/dashboard/ComplianceGauge.tsx',
    'components/dashboard/TopDataHolders.tsx',
].map((file) => readFileSync(resolve(process.cwd(), file), 'utf8')).join('\n');

describe('R2 dashboard metric semantics', () => {
    it('does not derive response duration or deadline outcomes from operational dates or a fixed day limit', () => {
        expect(dashboardPersistence).not.toMatch(/updated_at\s*-\s*created_at/i);
        expect(dashboardPersistence).not.toMatch(/interval\s+['"]30\s+days?['"]/i);
        expect(dashboardPersistence).not.toMatch(/status\s*=\s*['"]completed['"][\s\S]{0,160}(met|on.?time|deadline)/i);
        expect(requestRepository).toMatch(/response_received_at\s*-\s*controller_received_at/);
        expect(requestRepository).toContain('response_received_at IS NOT NULL');
        expect(requestRepository).toContain('controller_received_at IS NOT NULL');
    });

    it('uses explicit profile-scoped request, artefact, workflow, and lifecycle evidence', () => {
        expect(requestRepository).toContain('FROM requests');
        expect(requestRepository).toContain('WHERE profile_id = $1');
        expect(requestRepository).toMatch(/rd\.profile_id\s*=\s*\$1/);
        expect(requestRepository).toMatch(/r\.profile_id\s*=\s*\$1/);
        expect(requestRepository).toMatch(/wl\.status\s*=\s*'failed'/);
        expect(requestRepository).toMatch(/COALESCE\([\s\S]*extension_deadline_at[\s\S]*deadline_at\)\s+IS NULL/);
        expect(requestRepository).toMatch(/extension_notified_at\s+IS NOT NULL\s+AND\s+extension_deadline_at\s+IS NOT NULL/);
        expect(requestRepository).toContain('GROUP BY status');
    });

    it('retires unsupported score, risk, success, and deadline-limit claims from the Home UI', () => {
        expect(presentationFiles).not.toMatch(/privacy score/i);
        expect(presentationFiles).not.toMatch(/company compliance/i);
        expect(presentationFiles).not.toMatch(/request success/i);
        expect(presentationFiles).not.toMatch(/risk level/i);
        expect(presentationFiles).not.toMatch(/data points?/i);
        expect(presentationFiles).not.toMatch(/30-day|30 day|gdpr max|met deadline|missed deadline/i);
    });

    it('labels local state and evidence-backed screening without asserting a legal conclusion', () => {
        expect(presentationFiles).toContain('Locally completed');
        expect(presentationFiles).toContain('Workflow state only');
        expect(presentationFiles).toContain('Responses recorded');
        expect(presentationFiles).toContain('Known upcoming explicit deadlines');
        expect(presentationFiles).toContain('unknown deadline');
        expect(presentationFiles).toContain('Evidence-backed response-duration screening');
        expect(presentationFiles).toContain('does not determine legal timeliness');
        expect(presentationFiles).toContain('Received artefacts by company');
    });
});
