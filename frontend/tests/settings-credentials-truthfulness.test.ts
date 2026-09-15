import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const source = (relativePath: string) => fs.readFileSync(path.join(process.cwd(), relativePath), 'utf8');

describe('settings credential truthfulness', () => {
    it('stores new ONSIT keys with authenticated encryption and atomically reports persisted presence', () => {
        const route = source('app/api/settings/api-credentials/route.ts');
        expect(route).toContain("import { encryptCredential } from '@/lib/secure-credentials'");
        expect(route).not.toContain('obfuscate(');
        expect(route).toContain("await client.query('BEGIN')");
        expect(route).toContain("await client.query('ROLLBACK')");
        expect(route).toContain('Enter at least one API key');
        const legacyUtility = source('lib/credentials.ts');
        expect(legacyUtility).not.toContain('deobfuscate');
        expect(legacyUtility).not.toContain('getDriver');
    });

    it('stores AI provider credentials with authenticated encryption in one transaction', () => {
        const route = source('app/api/settings/ai-credentials/route.ts');
        const utility = source('lib/ai-credentials.ts');
        const section = source('components/settings/AICredentialsSection.tsx');

        expect(route).toContain("import { encryptCredential } from '@/lib/secure-credentials'");
        expect(route).not.toContain("createCipheriv('aes-256-cbc'");
        expect(route).toContain("await client.query('BEGIN')");
        expect(route).toContain("await client.query('ROLLBACK')");
        expect(route).toContain('Enter at least one provider credential');
        expect(route).toContain('{ status: 503 }');
        expect(utility).toContain('isCanonicalCiphertext(encryptedText)');
        expect(section).toContain('if (!r.ok)');
    });

    it('does not equate a stored ONSIT secret with active provider availability', () => {
        const section = source('components/settings/APICredentialsSection.tsx');
        expect(section).toContain('Stored status does not mean');
        expect(section).toContain('Current ONSIT workers do not yet consume these stored values');
        expect(section).not.toContain('Required for breaches');
        expect(section).toContain('Stored');
        expect(section).toContain('aria-label={`${isShown ?');
    });

    it('limits the legacy email card to credential storage and a real IMAP check', () => {
        const section = source('components/settings/EmailConnectorSection.tsx');
        expect(section).toContain('Automated inbox monitoring is configured separately through Source Connectors.');
        expect(section).toContain('No periodic inbox monitoring is started by this card.');
        expect(section).not.toContain('incremental every 15 minutes');
        expect(section).toContain('finally');
        expect(section).toContain('htmlFor={id}');
    });
});
