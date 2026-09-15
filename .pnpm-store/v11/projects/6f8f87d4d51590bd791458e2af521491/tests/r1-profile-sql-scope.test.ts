import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const root = process.cwd();
const ownedProductionFiles = [
    'app/api/settings/profile/route.ts',
    'app/api/settings/profile/password/route.ts',
    'lib/connectors/email.ts',
    'lib/actions/dashboard.ts',
    'lib/actions/data.ts',
    'lib/actions/email-settings.ts',
    'lib/actions/messages.ts',
    'lib/actions/policy-analysis.ts',
    'lib/actions/policy.ts',
    'lib/actions/request-detail.ts',
    'lib/actions/requests.ts',
    'lib/actions/requests/submit.ts',
];

describe('R1 owned SQL authority invariants', () => {
    it('contains no first-user or first-profile query shortcut', () => {
        for (const relative of ownedProductionFiles) {
            const source = readFileSync(path.join(root, relative), 'utf8');
            expect(source, relative).not.toMatch(/FROM\s+(?:user_profiles|profiles)\b[\s\S]{0,160}?LIMIT\s+1/i);
            expect(source, relative).not.toMatch(/(?:first user|first profile)/i);
        }
    });

    it('derives server action authority instead of accepting caller profile IDs', () => {
        for (const relative of ownedProductionFiles.filter(file => file.startsWith('lib/actions/'))) {
            const source = readFileSync(path.join(root, relative), 'utf8');
            expect(source, relative).toContain('requireServerSessionAuthority');
            expect(source, relative).not.toMatch(/export\s+async\s+function\s+\w+\s*\(\s*profileId\b/);
        }
    });

    it('scopes connector roots and request roots by canonical profile', () => {
        const email = readFileSync(path.join(root, 'lib/connectors/email.ts'), 'utf8');
        expect(email).toMatch(/ON CONFLICT\(profile_id,connector_key,account_key\)/);
        expect(email).toMatch(/FROM email_settings WHERE profile_id=\$1/);
        expect(email).not.toMatch(/FROM email_settings[^;`]*ORDER BY[^;`]*LIMIT\s+1/i);

        for (const relative of ownedProductionFiles.filter(file => file.startsWith('lib/actions/'))) {
            const source = readFileSync(path.join(root, relative), 'utf8');
            if (/\b(?:FROM|UPDATE|DELETE FROM|INSERT INTO)\s+requests\b/i.test(source)) {
                expect(source, relative).toMatch(/profile_id/);
            }
        }
    });
});
