import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, protectedApi, resetAuthenticationFailureForTests } from '@/lib/api-client';
import { resetProfileState, useProfileStore } from '@/lib/stores/profile-store';

describe('R1 adversarial protected client and shared profile state', () => {
  const originalWindow = globalThis.window;

  beforeEach(() => {
    resetAuthenticationFailureForTests();
    resetProfileState();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    Object.defineProperty(globalThis, 'window', { configurable: true, value: originalWindow });
  });

  it('handles concurrent 401s with one state clear and one redirect', async () => {
    const assign = vi.fn();
    Object.defineProperty(globalThis, 'window', { configurable: true, value: { location: { assign } } });
    useProfileStore.setState({ profile: { username: 'Alice', email: 'alice@test' }, status: 'ready' });
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      error: { code: 'SESSION_INVALID', message: 'Expired session', reason: 'expired' },
    }), { status: 401, headers: { 'content-type': 'application/json' } })));

    const results = await Promise.allSettled([
      protectedApi('/api/graph'), protectedApi('/api/connectors'), protectedApi('/api/insights/summary'),
    ]);
    expect(results.every(result => result.status === 'rejected')).toBe(true);
    expect(useProfileStore.getState().profile).toBeNull();
    expect(assign).toHaveBeenCalledTimes(1);
    expect(assign).toHaveBeenCalledWith('/login?reason=expired');
  });

  it.each([
    ['GRAPH_AUTHORITY_REJECTED', 'Graph authorization failed'],
    ['CONNECTOR_AUTHORITY_REJECTED', 'Connector authorization failed'],
  ])('preserves %s instead of relabeling it as an infrastructure/empty-data failure', async (code, message) => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: { code, message } }), {
      status: 403, headers: { 'content-type': 'application/json' },
    })));
    await expect(protectedApi('/api/probe')).rejects.toMatchObject({ status: 403, code, message } satisfies Partial<ApiError>);
  });

  it('publishes a saved username/email/avatar immediately to header subscribers', async () => {
    const updated = { username: 'Alice Updated', email: 'new@test', profilePictureUrl: '/avatar/new.png' };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ success: true, profile: updated }), {
      status: 200, headers: { 'content-type': 'application/json' },
    })));
    const observed: string[] = [];
    const unsubscribe = useProfileStore.subscribe(state => {
      if (state.profile) observed.push(`${state.profile.username}|${state.profile.email}|${state.profile.profilePictureUrl}`);
    });
    await useProfileStore.getState().saveProfile(new FormData());
    unsubscribe();
    expect(useProfileStore.getState().profile).toEqual(updated);
    expect(observed).toContain('Alice Updated|new@test|/avatar/new.png');
  });

  it('logout-compatible reset clears cached identity and pending status', () => {
    useProfileStore.setState({ profile: { username: 'Alice', email: null }, status: 'ready', isSaving: true, error: 'stale' });
    resetProfileState();
    expect(useProfileStore.getState()).toMatchObject({ profile: null, status: 'idle', isSaving: false, error: null });
  });
});
