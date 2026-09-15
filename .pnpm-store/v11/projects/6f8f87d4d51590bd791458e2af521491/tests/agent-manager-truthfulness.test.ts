import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const source = fs.readFileSync(path.join(process.cwd(), 'components/dashboard/AgentManager.tsx'), 'utf8');

describe('Agent Manager truthfulness contract', () => {
    it('uses contextual workflow links instead of incompatible generic POST requests', () => {
        expect(source).toContain("href: '/requests/new'");
        expect(source).toContain("href: '/dashboard/onsit'");
        expect(source).toContain("href: '/dashboard/import'");
        expect(source).not.toContain("method: 'POST'");
        expect(source).not.toContain("source: 'agent_manager'");
    });

    it('does not present local animation as persisted agent state or scheduling', () => {
        expect(source).toContain('Workflow shortcuts');
        expect(source).toContain('Recurring execution is not configured from this panel.');
        expect(source).not.toContain('All Idle');
        expect(source).not.toContain('SCHEDULE_OPTIONS');
        expect(source).not.toContain('lastRun');
        expect(source).not.toContain('animate-ping');
    });

    it('keeps every shortcut labelled and responsive', () => {
        expect(source).toContain('sm:flex-row');
        expect(source).toContain('min-h-11');
        expect(source).toContain('{workflow.action}');
    });
});
