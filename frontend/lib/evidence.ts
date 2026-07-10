import { z } from 'zod'

export const locatorSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('json_pointer'), pointer: z.string().regex(/^(|\/.*)$/) }).strict(),
  z.object({ type: z.literal('csv_row'), row: z.number().int().positive() }).strict(),
  z.object({ type: z.literal('csv_cell'), row: z.number().int().positive(), column: z.union([z.string(), z.number().int().nonnegative()]) }).strict(),
  z.object({ type: z.literal('text_span'), byte_start: z.number().int().nonnegative(), byte_end: z.number().int().positive(), line_start: z.number().int().positive().optional(), line_end: z.number().int().positive().optional() }).strict().refine(v => v.byte_end > v.byte_start),
  z.object({ type: z.literal('html_dom_span'), selector: z.string().min(1), text_start: z.number().int().nonnegative().optional(), text_end: z.number().int().positive().optional() }).strict(),
  z.object({ type: z.literal('media_time_range'), start_ms: z.number().int().nonnegative(), end_ms: z.number().int().positive() }).strict().refine(v => v.end_ms > v.start_ms),
  z.object({ type: z.literal('image_region'), x: z.number().nonnegative(), y: z.number().nonnegative(), width: z.number().positive(), height: z.number().positive() }).strict(),
  z.object({ type: z.literal('archive_member'), member_path: z.string().min(1) }).strict(),
])

export type EvidenceLocatorValue = z.infer<typeof locatorSchema>
export type AssertionDataClass = 'declared' | 'observed' | 'derived' | 'inferred'
export type AssertionStatus = 'candidate' | 'accepted' | 'rejected' | 'superseded'
export type EpistemicBasis = 'source_explicit' | 'controller_assigned' | 'deterministic_derivation' | 'model_hypothesis' | 'human_confirmed'

export interface AnalysisRun {
  id: string; run_type: string; profile_id: string | null; request_id: string | null
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  pipeline_version: string; configuration: Record<string, unknown>; started_at: string | null
  completed_at: string | null; error: string | null; created_at: string
}
export interface ExportSnapshot {
  id: string; profile_id: string | null; request_id: string | null; controller_key: string | null
  source_type: 'controller_export' | 'takeout_export' | 'dsar_response' | 'manual_import'
  exported_at: string | null; ingested_at: string; analysis_run_id: string; metadata: Record<string, unknown>
}
export interface ContentBlob { id: string; sha256: string; byte_size: number; storage_uri: string; first_ingested_at: string }
export interface SourceArtifact {
  id: string; export_snapshot_id: string; parent_artifact_id: string | null; content_blob_id: string
  original_path: string; archive_member_path: string | null; file_name: string; declared_mime: string | null
  detected_mime: string | null; extension: string | null; file_type_status: 'declared'|'detected'|'matched'|'mismatch'|'unknown'
  canonical_hash: string | null; structure_fingerprint_id: string | null; source_organisation: string | null
  source_product: string | null; source_service: string | null; created_at: string
}
export interface EvidenceLocator {
  id: string; artifact_id: string; locator_type: EvidenceLocatorValue['type']
  locator: Omit<EvidenceLocatorValue, 'type'>; raw_hash: string; verified: boolean
  verification_method: 'mechanical_resolution'|'exact_quote_match'|'structured_value_match'|'human_verified'
  verification_error: string | null; created_at: string
}
export interface Assertion {
  id: string; subject_type: string; subject_ref: string; predicate: string; object_type: 'node_ref'|'literal'|'json'|'unknown'
  object_ref: string | null; object_value: unknown; assertion_type: 'fact'|'relationship'|'classification'|'hypothesis'
  data_class: AssertionDataClass; status: AssertionStatus; epistemic_basis: EpistemicBasis; confidence: number | null
  valid_from: string | null; valid_to: string | null; temporal_precision: 'exact'|'day'|'month'|'year'|'range'|'unknown'
  controller_observed_from: string | null; controller_observed_to: string | null; exported_at: string | null
  ingested_at: string; system_asserted_at: string; superseded_at: string | null
  derivation_method: string; derivation_version: string; analysis_run_id: string; supersedes_assertion_id: string | null
}
