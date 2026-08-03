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
        return this.repository.transition(requireText(profileId, 'profileId'), {
            ...command,
            actor,
            reason,
        });
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

    delete(profileId: string, requestId: string) {
        return this.repository.delete(requireText(profileId, 'profileId'), requireText(requestId, 'requestId'));
    }

    screenDeadline(
        profileId: string,
        request: Request,
        evaluationAt: Date | string,
        disputedFields: readonly DeadlineInputField[] = [],
    ): DeadlineScreeningResult {
        const scopedProfileId = requireText(profileId, 'profileId');
        if (request.profile_id !== scopedProfileId) {
            throw new TypeError('Request does not belong to the canonical profile');
        }
        return screenRequestDeadline({
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
            evaluationAt,
            disputedFields,
        });
    }
}
