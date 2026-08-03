'use client';

import { create } from 'zustand';
import { protectedApi, registerProtectedStateReset, shouldSuppressProtectedRequestError } from '@/lib/api-client';

export interface UserProfile {
    id?: string;
    username: string;
    email: string | null;
    profilePictureUrl?: string | null;
    createdAt?: string;
    updatedAt?: string;
}

interface ProfileResponse {
    success: boolean;
    profile?: UserProfile;
    error?: string;
}

type ProfileStatus = 'idle' | 'loading' | 'ready' | 'error';

interface ProfileState {
    profile: UserProfile | null;
    status: ProfileStatus;
    isSaving: boolean;
    error: string | null;
    loadProfile: (signal?: AbortSignal) => Promise<UserProfile>;
    saveProfile: (formData: FormData, signal?: AbortSignal) => Promise<UserProfile | undefined>;
    reset: () => void;
}

const initialState = {
    profile: null,
    status: 'idle' as const,
    isSaving: false,
    error: null,
};

let stateVersion = 0;
let inFlightLoad: Promise<UserProfile> | null = null;

function responseProfile(payload: ProfileResponse): UserProfile {
    if (!payload.success || !payload.profile) {
        throw new Error(payload.error || 'Profile response did not include a profile');
    }
    return payload.profile;
}

function errorMessage(error: unknown): string {
    return error instanceof Error ? error.message : 'Failed to load profile';
}

export const useProfileStore = create<ProfileState>((set, get) => ({
    ...initialState,

    loadProfile: (signal) => {
        const cached = get().profile;
        if (cached) return Promise.resolve(cached);
        if (inFlightLoad) return inFlightLoad;

        const requestVersion = stateVersion;
        set({ status: 'loading', error: null });
        const request = protectedApi<ProfileResponse>('/api/settings/profile', { signal })
            .then(responseProfile)
            .then((profile) => {
                if (stateVersion === requestVersion) {
                    set({ profile, status: 'ready', error: null });
                }
                return profile;
            })
            .catch((error: unknown) => {
                if (stateVersion === requestVersion && !shouldSuppressProtectedRequestError(error)) {
                    set({ status: 'error', error: errorMessage(error) });
                } else if (stateVersion === requestVersion) {
                    set({ status: 'idle' });
                }
                throw error;
            })
            .finally(() => {
                if (inFlightLoad === request) inFlightLoad = null;
            });

        inFlightLoad = request;
        return request;
    },

    saveProfile: (formData, signal) => {
        const requestVersion = ++stateVersion;
        inFlightLoad = null;
        set({ isSaving: true, error: null });

        return protectedApi<ProfileResponse>('/api/settings/profile', {
            method: 'POST',
            body: formData,
            signal,
        })
            .then(responseProfile)
            .then((profile) => {
                if (stateVersion !== requestVersion) return undefined;
                set({ profile, status: 'ready', isSaving: false, error: null });
                return profile;
            })
            .catch((error: unknown) => {
                if (stateVersion === requestVersion) {
                    set({ isSaving: false, error: shouldSuppressProtectedRequestError(error) ? null : errorMessage(error) });
                }
                throw error;
            });
    },

    reset: () => {
        stateVersion += 1;
        inFlightLoad = null;
        set(initialState);
    },
}));

/** Used by the central authentication transition on 401 and by the logout flow. */
export function resetProfileState(): void {
    useProfileStore.getState().reset();
}

export function getProfileInitials(username: string | null | undefined): string {
    if (!username?.trim()) return '';
    return username
        .trim()
        .split(/\s+/)
        .map((word) => word.charAt(0).toUpperCase())
        .slice(0, 2)
        .join('');
}

registerProtectedStateReset(resetProfileState);
