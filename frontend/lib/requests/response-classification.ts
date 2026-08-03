import { RequestService } from './service';

export type ResponseClassification='substantive_response'|'partial_response'|'identity_required'|'clarification_required';

/** Applies a human/model classification only with an explicit received artefact reference. */
export async function applyResponseClassification(input:{profileId:string;requestId:string;classification:ResponseClassification;
    occurredAt:Date|string;actor:string;reason:string;evidenceReference:string},service=new RequestService()){
    if(!input.evidenceReference.trim())throw new TypeError('Response classification requires an evidence reference');
    if(input.classification==='identity_required')return service.transition(input.profileId,{request_id:input.requestId,
        next_state:'identity_action_required',actor:input.actor,reason:input.reason,evidence_reference:input.evidenceReference,
        transitioned_at:input.occurredAt,identity_requested_at:input.occurredAt});
    if(input.classification==='clarification_required')return service.transition(input.profileId,{request_id:input.requestId,
        next_state:'clarification_action_required',actor:input.actor,reason:input.reason,evidence_reference:input.evidenceReference,
        transitioned_at:input.occurredAt,clarification_requested_at:input.occurredAt});
    return service.transition(input.profileId,{request_id:input.requestId,next_state:'response_received',actor:input.actor,
        reason:input.reason,evidence_reference:input.evidenceReference,transitioned_at:input.occurredAt,
        response_received_at:input.occurredAt});
}
