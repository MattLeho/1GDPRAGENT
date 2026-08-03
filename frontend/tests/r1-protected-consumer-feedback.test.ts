import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { ApiError } from '../lib/api-client';
import { reportProtectedConsumerError } from '../lib/protected-consumer-feedback';

describe('protected feature error presentation', () => {
  it.each([
    'components/settings/RetentionSettingsSection.tsx',
    'components/settings/SourceConnectorsSection.tsx',
    'components/settings/IDDocumentsSection.tsx',
    'components/settings/N8NWebhooksSection.tsx',
    'components/settings/APICredentialsSection.tsx',
    'components/settings/AICredentialsSection.tsx',
    'components/requests/AddManualRequestDialog.tsx',
    'components/requests/RequestsGrid.tsx',
  ])('%s adopts the protected-request suppression boundary', (path) => {
    const source = readFileSync(resolve(process.cwd(), path), 'utf8');
    expect(source).toMatch(/shouldSuppressProtectedRequestError|reportProtectedConsumerError/);
  });

  it('does not emit feature errors for a handled 401 and concurrently aborted companion request', async () => {
    const featureToast = vi.fn();
    const consume = async (request: Promise<unknown>) => {
      try {
        await request;
      } catch (error) {
        reportProtectedConsumerError(error, featureToast);
      }
    };

    await Promise.all([
      consume(Promise.reject(new ApiError(401, 'Expired', 'SESSION_EXPIRED', 'expired', true))),
      consume(Promise.reject(new DOMException('Aborted', 'AbortError'))),
    ]);

    expect(featureToast).not.toHaveBeenCalled();
  });

  it('still reports an ordinary feature failure once', () => {
    const featureToast = vi.fn();
    reportProtectedConsumerError(new ApiError(500, 'Failed'), featureToast);
    expect(featureToast).toHaveBeenCalledTimes(1);
  });
});
