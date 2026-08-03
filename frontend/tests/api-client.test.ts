import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ApiError,
  logout,
  protectedApi,
  registerProtectedStateReset,
  resetAuthenticationFailureForTests,
  shouldSuppressProtectedRequestError,
} from '../lib/api-client';
import { useRequestStore } from '../lib/stores/request-store';

describe('protectedApi', () => {
  const originalWindow = globalThis.window;

  beforeEach(() => {
    resetAuthenticationFailureForTests();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    Object.defineProperty(globalThis, 'window', { configurable: true, value: originalWindow });
  });

  it('adds the mutation marker and parses a successful response', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(new Headers(init?.headers).get('x-gdpr-csrf')).toBe('1');
      expect(init?.credentials).toBe('same-origin');
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(protectedApi<{ ok: boolean }>('/api/example', { method: 'POST', body: '{}' })).resolves.toEqual({ ok: true });
  });

  it('clears protected state and redirects only once across repeated 401 responses', async () => {
    const assign = vi.fn();
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: { location: { assign } },
    });
    vi.stubGlobal('fetch', vi.fn(async () => new Response(
      JSON.stringify({ error: { code: 'SESSION_EXPIRED', message: 'Expired', reason: 'expired' } }),
      { status: 401, headers: { 'content-type': 'application/json' } },
    )));
    const reset = vi.fn();
    const unregister = registerProtectedStateReset(reset);

    await expect(protectedApi('/api/one')).rejects.toMatchObject({ status: 401, handled: true } satisfies Partial<ApiError>);
    await expect(protectedApi('/api/two')).rejects.toMatchObject({ status: 401, handled: true } satisfies Partial<ApiError>);
    expect(reset).toHaveBeenCalledTimes(1);
    expect(assign).toHaveBeenCalledTimes(1);
    expect(assign).toHaveBeenCalledWith('/login?reason=expired');
    expect(fetch).toHaveBeenCalledTimes(1);
    unregister();
  });

  it('preserves cancellation signals', async () => {
    const controller = new AbortController();
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      expect(init?.signal).toBeDefined();
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
    })));
    const request = protectedApi('/api/example', { signal: controller.signal });
    controller.abort();
    await expect(request).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('logout clears protected stores and navigates after the server clears the cookie', async () => {
    const assign = vi.fn();
    Object.defineProperty(globalThis, 'window', { configurable: true, value: { location: { assign } } });
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe('POST');
      expect(new Headers(init?.headers).get('x-gdpr-csrf')).toBe('1');
      return new Response(JSON.stringify({ success: true }), { status: 200, headers: { 'content-type': 'application/json' } });
    }));
    const reset = vi.fn();
    const unregister = registerProtectedStateReset(reset);

    await logout();
    expect(reset).toHaveBeenCalledTimes(1);
    expect(assign).toHaveBeenCalledWith('/login?reason=logged_out');
    unregister();
  });

  it('clears the production request store synchronously during a handled 401', async () => {
    const assign = vi.fn();
    Object.defineProperty(globalThis, 'window', { configurable: true, value: { location: { assign } } });
    useRequestStore.getState().setTargetUrl('https://personal.example');
    useRequestStore.getState().setNotes('personal notes');
    useRequestStore.getState().setAnalysisResult({ dpo_email: 'dpo@example.com', address: 'secret', data_collected: ['email'] });
    vi.stubGlobal('fetch', vi.fn(async () => new Response(
      JSON.stringify({ error: { code: 'SESSION_EXPIRED', reason: 'expired' } }),
      { status: 401, headers: { 'content-type': 'application/json' } },
    )));

    await expect(protectedApi('/api/private')).rejects.toSatisfy(shouldSuppressProtectedRequestError);
    expect(useRequestStore.getState()).toMatchObject({
      targetUrl: '',
      additionalNotes: '',
      analysisResult: null,
      selectedIdentity: null,
      graphData: [],
    });
  });

  it('suppresses centrally handled authentication and abort errors only', () => {
    expect(shouldSuppressProtectedRequestError(new ApiError(401, 'Expired', 'SESSION_EXPIRED', 'expired', true))).toBe(true);
    expect(shouldSuppressProtectedRequestError(new DOMException('Aborted', 'AbortError'))).toBe(true);
    expect(shouldSuppressProtectedRequestError(new ApiError(500, 'Failed'))).toBe(false);
    expect(shouldSuppressProtectedRequestError(new Error('Failed'))).toBe(false);
  });
});
