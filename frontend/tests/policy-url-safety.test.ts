import { describe, expect, it, vi } from 'vitest';
import { assertPublicHttpUrl, type HostResolver } from '@/lib/security/public-url';
import fs from 'node:fs';
import path from 'node:path';

const publicResolver: HostResolver = vi.fn(async () => [
  { address: '93.184.216.34', family: 4 },
]);

describe('public URL acquisition guard', () => {
  it.each([
    'file:///etc/passwd',
    'ftp://example.com/policy',
    'http://user:secret@example.com/policy',
    'http://localhost:8000/health',
    'http://intelligence:8000/health',
    'http://127.0.0.1/policy',
    'http://169.254.169.254/latest/meta-data',
    'http://10.0.0.2/policy',
    'http://[::1]/policy',
  ])('rejects unsafe URL %s', async (url) => {
    await expect(assertPublicHttpUrl(url, publicResolver)).rejects.toThrow();
  });

  it('rejects a hostname when DNS returns a private address', async () => {
    const resolver: HostResolver = vi.fn(async () => [{ address: '192.168.1.20', family: 4 }]);
    await expect(assertPublicHttpUrl('https://policy.example.test/privacy', resolver))
      .rejects.toThrow(/public address/i);
  });

  it('accepts an HTTPS URL only when every resolved address is public', async () => {
    const url = await assertPublicHttpUrl('https://example.com/privacy', publicResolver);
    expect(url.href).toBe('https://example.com/privacy');
    expect(publicResolver).toHaveBeenCalledWith('example.com');
  });

  it('keeps redirects manual and uses the validated URL in the policy route', () => {
    const source = fs.readFileSync(
      path.join(process.cwd(), 'app/api/gdpr-agent/analyze-policy/route.ts'),
      'utf8',
    );
    expect(source).toContain("redirect:'manual'");
    expect(source).toContain('Policy URL: ${safeUrl.href}');
    expect(source).not.toContain('Policy URL: ${url}');
    expect(source).toContain('error instanceof PublicUrlValidationError?400:500');
  });
});
