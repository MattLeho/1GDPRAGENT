import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const source = (relativePath: string) => fs.readFileSync(path.join(process.cwd(), relativePath), 'utf8');

describe('new-request identity handoff contract', () => {
    it('carries the entered name, email, phone, and account details into submission state', () => {
        const builder = source('components/wizard/IdentityBuilder.tsx');
        const store = source('lib/stores/request-store.ts');
        expect(builder).toContain('contactName: data.name');
        expect(builder).toContain('contactEmail: data.email');
        expect(builder).toContain("{ fieldKey: 'full_name', value: data.name }");
        expect(store).toContain('contactName: string');
        expect(store).toContain('value: string');
        expect(builder).not.toContain('user-session-key');
        expect(builder).not.toContain('Address Placeholder');
    });

    it('validates identity and encrypts request details only on the server', () => {
        const submit = source('lib/actions/requests/submit.ts');
        expect(submit).toContain('A valid request identity name and email are required.');
        expect(submit).toContain('encryptCredential(detail.value)');
        expect(submit).not.toContain('not-provided@example.local');
        expect(submit).not.toContain("|| 'GDPR requester'");
    });

    it('does not block request creation when optional graph linking is unavailable', () => {
        const builder = source('components/wizard/IdentityBuilder.tsx');
        const catchIndex = builder.indexOf('catch (e)');
        expect(builder).toContain('Identity is ready, but graph linking is unavailable');
        expect(builder.indexOf('nextStep()', catchIndex)).toBeGreaterThan(builder.indexOf('catch (e)'));
    });

    it('describes creation and delivery separately and clears busy state on failure', () => {
        const scope = source('components/wizard/ScopeSelector.tsx');
        expect(scope).toContain('Delivery occurs only when a configured workflow succeeds');
        expect(scope).toContain('Create Request');
        expect(scope).toContain('finally');
        expect(scope).not.toContain('You are about to send a formal GDPR request.');
    });

    it('keeps the retired cosmetic-encryption selector out of the active codebase', () => {
        expect(fs.existsSync(path.join(process.cwd(), 'components/wizard/IdentitySelector.tsx'))).toBe(false);
    });

    it('runs policy analysis only from the explicit Analyze action', () => {
        const analyzer = source('components/wizard/UrlAnalyzer.tsx');
        const route = source('app/api/n8n/analyze-policy/route.ts');
        expect(analyzer).not.toContain('useEffect');
        expect(analyzer).not.toContain('checkingCache');
        expect(analyzer).not.toContain('forceNew');
        expect(analyzer.match(/fetch\('\/api\/n8n\/analyze-policy'/g)).toHaveLength(1);
        expect(analyzer).toContain('Analysis runs only when you press Analyze');
        expect(route).toContain('await assertPublicHttpUrl(url)');
        expect(route).toContain('PublicUrlValidationError');
    });

    it('keeps scope and timeframe choices in wizard state across Back and Next', () => {
        const scope = source('components/wizard/ScopeSelector.tsx');
        const store = source('lib/stores/request-store.ts');
        expect(store).toContain('wantAccess: boolean');
        expect(store).toContain('wantDeletion: boolean');
        expect(store).toContain('allData: boolean');
        expect(scope).not.toContain('useState(true)');
        expect(scope).toContain('id="request-access"');
        expect(scope).toContain('htmlFor="request-deletion"');
    });

    it('reports policy persistence separately from request creation or delivery', () => {
        const submit = source('lib/actions/requests/submit.ts');
        expect(submit).toContain('let policyPersisted = !payload.analysis');
        expect(submit).toContain('policyPersisted = true');
        expect(submit).toContain('The policy analysis could not be stored; review the request before relying on it.');
        expect(submit).toContain('policyPersisted,');
    });
});
