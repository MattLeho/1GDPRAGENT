import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  protectedApi: vi.fn(),
  resetHandlers: [] as Array<() => void>,
}));

vi.mock('../lib/api-client', () => ({
  protectedApi: apiMocks.protectedApi,
  registerProtectedStateReset: (reset: () => void) => {
    apiMocks.resetHandlers.push(reset);
    return () => undefined;
  },
}));

import { getProfileInitials, resetProfileState, useProfileStore, type UserProfile } from '../lib/stores/profile-store';

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

const originalProfile: UserProfile = {
  id: 'user-1',
  username: 'Original User',
  email: 'original@example.com',
  profilePictureUrl: '/avatars/original.png',
};

beforeEach(() => {
  resetProfileState();
  apiMocks.protectedApi.mockReset();
});

describe('shared profile state', () => {
  it('deduplicates the initial load and preserves its cancellation signal', async () => {
    const response = deferred<{ success: boolean; profile: UserProfile }>();
    const controller = new AbortController();
    apiMocks.protectedApi.mockReturnValueOnce(response.promise);

    const first = useProfileStore.getState().loadProfile(controller.signal);
    const second = useProfileStore.getState().loadProfile();

    expect(first).toBe(second);
    expect(apiMocks.protectedApi).toHaveBeenCalledTimes(1);
    expect(apiMocks.protectedApi).toHaveBeenCalledWith('/api/settings/profile', { signal: controller.signal });

    response.resolve({ success: true, profile: originalProfile });
    await expect(first).resolves.toEqual(originalProfile);
    expect(useProfileStore.getState()).toMatchObject({ profile: originalProfile, status: 'ready' });
  });

  it('publishes a successful save to existing subscribers without a remount', async () => {
    apiMocks.protectedApi
      .mockResolvedValueOnce({ success: true, profile: originalProfile })
      .mockResolvedValueOnce({
        success: true,
        profile: {
          ...originalProfile,
          username: 'Updated Person',
          email: 'updated@example.com',
          profilePictureUrl: '/avatars/updated.png',
        },
      });
    await useProfileStore.getState().loadProfile();
    const visibleProfiles: Array<UserProfile | null> = [];
    const unsubscribe = useProfileStore.subscribe((state) => visibleProfiles.push(state.profile));

    await useProfileStore.getState().saveProfile(new FormData());

    expect(visibleProfiles.at(-1)).toMatchObject({
      username: 'Updated Person',
      email: 'updated@example.com',
      profilePictureUrl: '/avatars/updated.png',
    });
    expect(getProfileInitials(visibleProfiles.at(-1)?.username)).toBe('UP');
    unsubscribe();
  });

  it('clears profile, avatar, and identity through the registered authentication reset', async () => {
    apiMocks.protectedApi.mockResolvedValueOnce({ success: true, profile: originalProfile });
    await useProfileStore.getState().loadProfile();

    expect(apiMocks.resetHandlers).toHaveLength(1);
    apiMocks.resetHandlers[0]();

    expect(useProfileStore.getState()).toMatchObject({ profile: null, status: 'idle', isSaving: false });
    expect(getProfileInitials(useProfileStore.getState().profile?.username)).toBe('');
  });

  it('does not let a stale load overwrite a newer successful save', async () => {
    const oldLoad = deferred<{ success: boolean; profile: UserProfile }>();
    const updatedProfile = { ...originalProfile, username: 'Newest Identity', profilePictureUrl: '/avatars/newest.png' };
    apiMocks.protectedApi
      .mockReturnValueOnce(oldLoad.promise)
      .mockResolvedValueOnce({ success: true, profile: updatedProfile });

    const loading = useProfileStore.getState().loadProfile();
    await useProfileStore.getState().saveProfile(new FormData());
    oldLoad.resolve({ success: true, profile: originalProfile });
    await loading;

    expect(useProfileStore.getState().profile).toEqual(updatedProfile);
    expect(getProfileInitials(useProfileStore.getState().profile?.username)).toBe('NI');
  });

  it('ignores a save response that arrives after logout reset', async () => {
    const save = deferred<{ success: boolean; profile: UserProfile }>();
    apiMocks.protectedApi.mockReturnValueOnce(save.promise);

    const saving = useProfileStore.getState().saveProfile(new FormData());
    resetProfileState();
    save.resolve({ success: true, profile: originalProfile });

    await expect(saving).resolves.toBeUndefined();
    expect(useProfileStore.getState()).toMatchObject({ profile: null, status: 'idle', isSaving: false });
  });
});
