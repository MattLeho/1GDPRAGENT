export type RetentionClass=
  |'KEEP_LEGAL_OR_REGULATORY'|'KEEP_FINANCIAL'|'KEEP_IDENTITY_OR_SECURITY'
  |'KEEP_PROJECT_RECORD'|'KEEP_ACTIVE_CONVERSATION'|'KEEP_PERSONAL_SIGNIFICANCE'
  |'LOW_VALUE_BULK'|'SPAM'|'UNSURE';
export type RetentionAction='local_purge'|'source_delete'|'controller_erasure_candidate'|'review_only';
export type DeletionItemGroup='eligible'|'protected'|'uncertain';
export type DeletionStage='candidate'|'review'|'quarantine'|'eligible_for_delete'|'executed'|'cancelled';

export interface RetentionDecision {
  id:string; source_artifact_id:string; classification:RetentionClass;
  deterministic_evidence:Record<string,unknown>; semantic_adjudication:Record<string,unknown>|null;
  confidence:number; policy_id:string; policy_version:number; analysis_run_id:string;
  review_status:'pending'|'approved'|'rejected'; created_at:string;
}

export interface DeletionPlanItem {
  id:string; source_artifact_id:string; retention_decision_id:string;
  group:DeletionItemGroup; action:RetentionAction; reasons:string[];
  source_delete_capability:boolean; stage:DeletionStage;
  quarantine_at:string|null; grace_expires_at:string|null;
}

export interface DeletionPlan {
  id:string; policy_id:string; policy_version:number; analysis_run_id:string;
  dry_run:boolean; items:DeletionPlanItem[]; created_at:string;
}

