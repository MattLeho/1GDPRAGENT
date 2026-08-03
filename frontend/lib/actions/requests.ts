'use server';

import { requireServerSessionAuthority } from '@/lib/api-session';
import { RequestService } from '@/lib/requests/service';
import type { CanonicalRequestState, Request, RequestEvent } from '@/lib/requests/types';

export type { Request, RequestEvent } from '@/lib/requests/types';

const requests = new RequestService();

export async function getRequests(search?: string, filter?: string, sort?: string): Promise<Request[]> {
    const { profileId } = await requireServerSessionAuthority();
    return requests.list(profileId, {
        search,
        status: filter && filter !== 'all' ? normaliseInputState(filter) : undefined,
        sort: sort === 'name' ? 'company_asc' : 'created_desc',
    });
}

export async function getRequestCounts(): Promise<{ total: number; pending: number; completed: number; action_required: number }> {
    const { profileId } = await requireServerSessionAuthority();
    const counts = await requests.counts(profileId);
    const by = counts.by_state;
    return {
        total: counts.total,
        pending: (by.scheduled ?? 0) + (by.awaiting_response ?? 0) + (by.processing_response ?? 0) + (by.processing ?? 0),
        completed: by.completed ?? 0,
        action_required: (by.ready_for_review ?? 0) + (by.identity_action_required ?? 0) +
            (by.clarification_action_required ?? 0) + (by.action_required ?? 0),
    };
}

export interface ManualRequestInput {
    company_name: string;
    domain?: string;
    status: 'draft' | 'scheduled' | 'processing' | 'action_required' | 'completed';
    request_type: string;
    notes?: string;
    date_started?: Date;
    progress?: number;
}

export async function createManualRequest(input: ManualRequestInput): Promise<{ success: boolean; requestId?: string; error?: string }> {
    try {
        const { profileId, userId } = await requireServerSessionAuthority();
        const status = normaliseInputState(input.status);
        const created = await requests.create(profileId, {
            company_name: input.company_name,
            domain: input.domain || `${input.company_name.toLowerCase().replace(/\s+/g, '')}.com`,
            status,
            request_type: input.request_type,
            progress: input.progress ?? getProgressFromStatus(status),
            notes: input.notes || null,
            // date_started is creation/import context, not evidence of completion.
            completed_at: null,
        });
        await requests.appendEvent(profileId, {
            request_id: created.id,
            event_type: 'created',
            description: 'Request added manually',
            occurred_at: input.date_started || new Date(),
            actor: `user:${userId}`,
            reason: 'Manual request creation',
        });
        const { revalidatePath } = await import('next/cache');
        revalidatePath('/dashboard/requests');
        revalidatePath('/dashboard/home');
        return { success: true, requestId: created.id };
    } catch (error) {
        console.error('Failed to create manual request:', error);
        return { success: false, error: error instanceof Error ? error.message : 'Unknown error' };
    }
}

function normaliseInputState(status: string): CanonicalRequestState {
    if (status === 'processing') return 'processing_response';
    if (status === 'action_required') return 'ready_for_review';
    if (['draft','scheduled','completed','ready_for_review','sent','awaiting_response','identity_action_required','clarification_action_required','response_received','processing_response','closed_incomplete','cancelled'].includes(status)) {
        return status as CanonicalRequestState;
    }
    throw new TypeError(`Unknown request state: ${status}`);
}

function getProgressFromStatus(status: CanonicalRequestState): number {
    if (status === 'draft') return 0;
    if (status === 'ready_for_review' || status === 'scheduled') return 10;
    if (status === 'sent' || status === 'awaiting_response') return 20;
    if (status === 'identity_action_required' || status === 'clarification_action_required') return 40;
    if (status === 'response_received' || status === 'processing_response') return 70;
    if (status === 'completed') return 100;
    return 0;
}

export async function getRequestEvents(requestId: string): Promise<RequestEvent[]> {
    const { profileId } = await requireServerSessionAuthority();
    return requests.events(profileId, requestId);
}

export async function addRequestEvent(event: {
    request_id: string;
    event_type: string;
    event_description?: string;
    event_date?: Date;
}): Promise<{ success: boolean; id?: string }> {
    try {
        const { profileId, userId } = await requireServerSessionAuthority();
        const created = await requests.appendEvent(profileId, {
            request_id: event.request_id,
            event_type: event.event_type,
            description: event.event_description || null,
            occurred_at: event.event_date || new Date(),
            actor: `user:${userId}`,
            reason: event.event_description || event.event_type,
        });
        return created ? { success: true, id: created.id } : { success: false };
    } catch (error) {
        console.error('Failed to add request event:', error);
        return { success: false };
    }
}
