'use server';

import { revalidatePath } from 'next/cache';
import { Request } from './requests';
import { requireServerSessionAuthority } from '@/lib/api-session';
import { RequestService } from '@/lib/requests/service';
import type { CanonicalRequestState } from '@/lib/requests/types';

const requests = new RequestService();

export interface RequestAccountDetail {
    id: string;
    request_id: string;
    field_key: string;
    field_value_encrypted: string;
}

/**
 * Gets a single request by ID
 */
export async function getRequestById(id: string): Promise<Request | null> {
    const { profileId } = await requireServerSessionAuthority();
    return requests.get(profileId,id);
}

/**
 * Updates request status
 */
export async function updateRequestStatus(
    id: string,
    status: 'draft' | 'scheduled' | 'processing' | 'action_required' | 'completed'
): Promise<{ success: boolean }> {
    try {
        const { profileId,userId } = await requireServerSessionAuthority();
        const nextState = status === 'processing' ? 'processing_response'
            : status === 'action_required' ? 'ready_for_review' : status as CanonicalRequestState;
        await requests.transition(profileId,{request_id:id,next_state:nextState,actor:`user:${userId}`,
            reason:'Request state changed in request details',transitioned_at:new Date(),
            completed_at:nextState==='completed'?new Date():null});
        revalidatePath('/dashboard/requests');
        revalidatePath(`/dashboard/requests/${id}`);
        revalidatePath('/dashboard/home');
        return { success: true };
    } catch (error) {
        console.error('Failed to update request status:', error);
        return { success: false };
    }
}

/**
 * Gets encrypted account details attached to a request
 */
export async function getRequestAccountDetails(requestId: string): Promise<RequestAccountDetail[]> {
    const { profileId } = await requireServerSessionAuthority();
    return requests.requestDetails(profileId,requestId) as Promise<unknown> as Promise<RequestAccountDetail[]>;
}

/**
 * Updates request progress
 */
export async function updateRequestProgress(
    id: string,
    progress: number
): Promise<{ success: boolean }> {
    try {
        const { profileId } = await requireServerSessionAuthority();
        if(!await requests.updateProgress(profileId,id,progress))return {success:false};
        return { success: true };
    } catch (error) {
        console.error('Failed to update request progress:', error);
        return { success: false };
    }
}

/**
 * Updates request notes
 */
export async function updateRequestNotes(
    id: string,
    notes: string
): Promise<{ success: boolean }> {
    try {
        const { profileId } = await requireServerSessionAuthority();
        if(!await requests.updateNotes(profileId,id,notes))return {success:false};
        return { success: true };
    } catch (error) {
        console.error('Failed to update notes:', error);
        return { success: false };
    }
}

/**
 * Cancels a request while retaining its audit record and evidence.
 */
export async function deleteRequest(id: string): Promise<{ success: boolean }> {
    try {
        const { profileId, userId } = await requireServerSessionAuthority();
        if(!await requests.cancel(profileId,id,`user:${userId}`))return {success:false};
        return { success: true };
    } catch (error) {
        console.error('Failed to cancel request:', error);
        return { success: false };
    }
}

/**
 * Gets requests history for a company (previous requests to same domain)
 */
export async function getRequestHistory(domain: string, excludeId?: string): Promise<Request[]> {
    const { profileId } = await requireServerSessionAuthority();
    return requests.history(profileId,domain,excludeId);
}

/** Returns a conservative legal-deadline screening, never a compliance conclusion. */
export async function getRequestDeadlineScreening(id: string) {
    const { profileId } = await requireServerSessionAuthority();
    const request = await requests.get(profileId, id);
    return request ? requests.screenDeadline(profileId, request, new Date()) : null;
}
