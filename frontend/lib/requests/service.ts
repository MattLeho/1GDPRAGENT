import { screenRequestDeadline, type DeadlineInputField, type DeadlineScreeningResult } from './deadline';
import { RequestRepository } from './repository';
import {
    CANONICAL_REQUEST_STATES,
    type AppendRequestEventInput,
    type CanonicalRequestState,
    type CreateRequestInput,
    type Request,
    type RequestListOptions,
    type TransitionRequestCommand,
} from './types';

function requireText(value: string, field: string): string {
    const trimmed = value.trim();
    if (!trimmed) throw new TypeError(`${field} is required`);
    return trimmed;
}

function requireCanonicalState(state: string): asserts state is CanonicalRequestState {
    if (!(CANONICAL_REQUEST_STATES as readonly string[]).includes(state)) {
        throw new TypeError(`Unknown canonical request state: ${state}`);
    }
}

export class RequestService {
    constructor(readonly repository: RequestRepository = new RequestRepository()) {}

    list(profileId: string, options?: RequestListOptions) {
        return this.repository.list(requireText(profileId, 'profileId'), options);
    }

    get(profileId: string, requestId: string) {
        return this.repository.get(requireText(profileId, 'profileId'), requireText(requestId, 'requestId'));
    }

    history(profileId: string, domain: string, excludeRequestId?: string) {
        return this.repository.history(requireText(profileId, 'profileId'), requireText(domain, 'domain'), excludeRequestId);
    }

    counts(profileId: string) {
        return this.repository.counts(requireText(profileId, 'profileId'));
    }

    contactedCompanyNames(profileId: string, companyNames: string[]) {
        return this.repository.contactedCompanyNames(requireText(profileId, 'profileId'), companyNames);
    }

    create(profileId: string, input: CreateRequestInput) {
        requireText(input.company_name, 'company_name');
        requireText(input.request_type, 'request_type');
        if (input.status) requireCanonicalState(input.status);
        return this.repository.create(requireText(profileId, 'profileId'), {
            ...input,
            company_name: input.company_name.trim(),
            request_type: input.request_type.trim(),
            progress: Math.min(100, Math.max(0, Math.trunc(input.progress ?? 0))),
        });
    }

    updateProgress(profileId: string, requestId: string, progress: number) {
        if (!Number.isFinite(progress)) throw new TypeError('progress must be finite');
        return this.repository.updateProgress(
            requireText(profileId, 'profileId'),
            requireText(requestId, 'requestId'),
            Math.min(100, Math.max(0, Math.trunc(progress))),
        );
    }

    updateNotes(profileId: string, requestId: string, notes: string | null) {
        return this.repository.updateNotes(
            requireText(profileId, 'profileId'), requireText(requestId, 'requestId'), notes,
        );
    }

    transition(profileId: string, command: TransitionRequestCommand) {
        requireCanonicalState(command.next_state);
        const actor = requireText(command.actor, 'actor');
        const reason = requireText(command.reason, 'reason');
        requireText(command.request_id, 'request_id');
        const scopedProfileId = requireText(profileId, 'profileId');
        const extensionFields = [command.extension_notified_at, command.extension_deadline_at, command.extension_reason];
        const hasAnyExtension = extensionFields.some(value => value !== undefined && value !== null && value !== '');
        const hasCompleteExtension = command.extension_notified_at != null
            && command.extension_deadline_at != null
            && Boolean(command.extension_reason?.trim());
        if (hasAnyExtension && !hasCompleteExtension) {
            throw new TypeError('Extension notice, deadline, and reason are all required');
        }
        const normalised = {
            ...command,
            actor,
            reason,
            extension_reason: command.extension_reason?.trim(),
        };
        return hasCompleteExtension
            ? this.transitionWithValidatedExtension(scopedProfileId, normalised)
            : this.repository.transition(scopedProfileId, normalised);
    }

    private async transitionWithValidatedExtension(profileId: string, command: TransitionRequestCommand) {
        const current = await this.repository.get(profileId, command.request_id);
        if (!current) return null;
        const screening = screenRequestDeadline({
            request_type: current.request_type,
            sent_at: current.sent_at,
            controller_received_at: current.controller_received_at,
            identity_requested_at: current.identity_requested_at,
            identity_verified_at: current.identity_verified_at,
            clarification_requested_at: current.clarification_requested_at,
            clarification_resolved_at: current.clarification_resolved_at,
            response_received_at: current.response_received_at,
            completed_at: current.completed_at,
            extension_notified_at: command.extension_notified_at,
            extension_deadline_at: command.extension_deadline_at,
            extension_reason: command.extension_reason,
            evaluationAt: command.transitioned_at,
        });
        if (screening.human_review_required || !screening.deadline_at) {
            throw new TypeError('Extension evidence is invalid or requires human review');
        }
        return this.repository.transition(profileId, { ...command, deadline_at: screening.deadline_at });
    }

    events(profileId: string, requestId: string) {
        return this.repository.events(requireText(profileId, 'profileId'), requireText(requestId, 'requestId'));
    }

    appendEvent(profileId: string, event: AppendRequestEventInput) {
        return this.repository.appendEvent(requireText(profileId, 'profileId'), {
            ...event,
            request_id: requireText(event.request_id, 'request_id'),
            event_type: requireText(event.event_type, 'event_type'),
            actor: requireText(event.actor, 'actor'),
            reason: requireText(event.reason, 'reason'),
        });
    }

    messages(profileId: string, requestId: string) {
        return this.repository.messages(requireText(profileId, 'profileId'), requireText(requestId, 'requestId'));
    }

    appendMessage(profileId: string, requestId: string, sender: string, content: string) {
        return this.repository.appendMessage(
            requireText(profileId, 'profileId'), requireText(requestId, 'requestId'),
            requireText(sender, 'sender'), requireText(content, 'content'),
        );
    }

    chat(profileId: string, requestId: string) {
        return this.repository.chat(requireText(profileId, 'profileId'), requireText(requestId, 'requestId'));
    }

    appendChatMessage(profileId: string, requestId: string, sender: string, message: string) {
        return this.repository.appendChatMessage(
            requireText(profileId, 'profileId'), requireText(requestId, 'requestId'),
            requireText(sender, 'sender'), requireText(message, 'message'),
        );
    }

    receivedData(profileId: string, requestId: string) {
        return this.repository.receivedData(requireText(profileId, 'profileId'), requireText(requestId, 'requestId'));
    }

    addReceivedData(profileId:string,requestId:string,input:{file_name:string;file_size_mb:number;file_path?:string|null}){
        return this.repository.addReceivedData(requireText(profileId,'profileId'),requireText(requestId,'requestId'),input);
    }

    registerReceivedDataBatch(profileId: string, requestId: string | null, files: Parameters<RequestRepository['registerReceivedDataBatch']>[2]) {
        return this.repository.registerReceivedDataBatch(requireText(profileId, 'profileId'), requestId, files);
    }

    listReceivedData(profileId: string, filter: { fileId?: string | null; requestId?: string | null } = {}) {
        return this.repository.listReceivedData(requireText(profileId, 'profileId'), filter);
    }

    pendingReceivedData(profileId: string) {
        return this.repository.pendingReceivedData(requireText(profileId, 'profileId'));
    }

    receivedDataVolume(profileId: string, requestId: string) {
        return this.repository.receivedDataVolume(requireText(profileId, 'profileId'), requireText(requestId, 'requestId'));
    }

    receivedDataStatusCounts(profileId: string, requestId: string) {
        return this.repository.receivedDataStatusCounts(requireText(profileId, 'profileId'), requireText(requestId, 'requestId'));
    }

    searchReceivedData(profileId: string, requestId: string, options: Parameters<RequestRepository['searchReceivedData']>[2] = {}) {
        return this.repository.searchReceivedData(requireText(profileId, 'profileId'), requireText(requestId, 'requestId'), options);
    }

    updateReceivedData(profileId: string, fileId: string, input: Record<string, unknown>) {
        return this.repository.updateReceivedData(requireText(profileId, 'profileId'), requireText(fileId, 'fileId'), input);
    }

    requestDetails(profileId:string,requestId:string){
        return this.repository.requestDetails(requireText(profileId,'profileId'),requireText(requestId,'requestId'));
    }

    addRequestDetail(profileId:string,requestId:string,fieldKey:string,encryptedValue:string){
        return this.repository.addRequestDetail(requireText(profileId,'profileId'),requireText(requestId,'requestId'),requireText(fieldKey,'fieldKey'),requireText(encryptedValue,'encryptedValue'));
    }

    reviewItems(profileId:string){return this.repository.reviewItems(requireText(profileId,'profileId'));}

    getOwnedReceivedData(profileId: string, receivedDataId: string) {
        return this.repository.getOwnedReceivedData(
            requireText(profileId, 'profileId'), requireText(receivedDataId, 'receivedDataId'),
        );
    }

    context(profileId: string, requestId: string) {
        return this.repository.context(requireText(profileId, 'profileId'), requireText(requestId, 'requestId'));
    }

    dashboard(profileId: string) {
        return this.repository.dashboard(requireText(profileId, 'profileId'));
    }

    activity(profileId: string, requestId: string) {
        return this.repository.activity(requireText(profileId, 'profileId'), requireText(requestId, 'requestId'));
    }

    startWorkflowLog(profileId: string, params: { requestId: string; workflowName: string; workflowType: string; details?: Record<string, unknown> }) {
        return this.repository.startWorkflowLog(requireText(profileId, 'profileId'), params);
    }

    finishWorkflowLog(profileId: string, logId: string, input: { status: 'completed' | 'error'; details: Record<string, unknown>; errorMessage?: string | null }) {
        return this.repository.finishWorkflowLog(requireText(profileId, 'profileId'), requireText(logId, 'logId'), input);
    }

    recordOutboundMessage(profileId: string, input: Parameters<RequestRepository['recordOutboundMessage']>[1], connection?: Parameters<RequestRepository['recordOutboundMessage']>[2]) {
        return this.repository.recordOutboundMessage(requireText(profileId, 'profileId'), input, connection);
    }

    createEmailDraft(profileId:string,input:Parameters<RequestRepository['createEmailDraft']>[1]){return this.repository.createEmailDraft(requireText(profileId,'profileId'),input);}
    reviewEmailDraft(profileId:string,draftId:string,reviewedBy:string){return this.repository.reviewEmailDraft(requireText(profileId,'profileId'),requireText(draftId,'draftId'),requireText(reviewedBy,'reviewedBy'));}
    getReviewedEmailDraft(profileId:string,draftId:string){return this.repository.getReviewedEmailDraft(requireText(profileId,'profileId'),requireText(draftId,'draftId'));}
    markEmailDraftSent(profileId:string,draftId:string,messageId:string,connection:Parameters<RequestRepository['markEmailDraftSent']>[3]){return this.repository.markEmailDraftSent(requireText(profileId,'profileId'),requireText(draftId,'draftId'),requireText(messageId,'messageId'),connection);}
    markEmailDraftFailed(profileId:string,draftId:string,error:Record<string,unknown>){return this.repository.markEmailDraftFailed(requireText(profileId,'profileId'),requireText(draftId,'draftId'),error);}

    getThread(profileId: string, lookup: { threadId?: string | null; company?: string | null }) {
        return this.repository.getThread(requireText(profileId, 'profileId'), lookup);
    }

    updateThread(profileId: string, userId: string, input: Parameters<RequestRepository['updateThread']>[2]) {
        return this.repository.updateThread(
            requireText(profileId, 'profileId'), requireText(userId, 'userId'), input,
        );
    }

    cancel(profileId: string, requestId: string, actor: string) {
        return this.repository.cancel(
            requireText(profileId, 'profileId'),
            requireText(requestId, 'requestId'),
            requireText(actor, 'actor'),
        );
    }

    screenDeadline(
        profileId: string,
        request: Request,
        evaluationAt: Date | string,
        disputedFields: readonly DeadlineInputField[] = [],
        publicHolidays?: readonly string[],
    ): DeadlineScreeningResult {
        const scopedProfileId = requireText(profileId, 'profileId');
        if (request.profile_id !== scopedProfileId) {
            throw new TypeError('Request does not belong to the canonical profile');
        }
        return screenRequestDeadline({
            request_type: request.request_type,
            sent_at: request.sent_at,
            controller_received_at: request.controller_received_at,
            identity_requested_at: request.identity_requested_at,
            identity_verified_at: request.identity_verified_at,
            clarification_requested_at: request.clarification_requested_at,
            clarification_resolved_at: request.clarification_resolved_at,
            response_received_at: request.response_received_at,
            completed_at: request.completed_at,
            extension_notified_at: request.extension_notified_at,
            extension_deadline_at: request.extension_deadline_at,
            extension_reason: request.extension_reason,
            evaluationAt,
            disputedFields,
            publicHolidays,
        });
    }
}
