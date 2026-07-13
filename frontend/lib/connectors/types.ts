export type ConnectorMode='snapshot_import'|'incremental_poll'|'event_stream'|'webhook_push'|'folder_watch';
export type ConnectorStatus='connected'|'paused'|'degraded'|'authentication_required'|'error'|'disconnected';
export type PermissionAccess='read'|'write'|'delete'|'not_read';

export interface ConnectorPermission {
  key:string; access:PermissionAccess; data_class:string; description:string;
  required:boolean; enabled_by_default:boolean;
}

export interface SourceConnectorDefinition {
  key:string; version:string; display_name:string; provider:string; connector_type:string;
  modes:ConnectorMode[]; data_classes:string[]; permissions:ConnectorPermission[];
  supports_backfill:boolean; supports_incremental:boolean;
  supports_source_delete:boolean; supports_remote_delete_request:boolean;
  configuration_schema:Record<string,unknown>;
}

export interface ConnectorInstance {
  id:string; definition_key:string; definition_version:string; profile_id:string|null;
  account_key:string; display_name:string; status:ConnectorStatus;
  enabled_permissions:string[]; configuration:Record<string,unknown>; credential_id:string|null;
  last_sync_at:string|null; next_sync_at:string|null; created_at:string; updated_at:string;
}

export interface ConnectorSyncRun {
  id:string; connector_instance_id:string; analysis_run_id:string; kind:'sync'|'backfill';
  status:'pending'|'running'|'completed'|'failed'|'cancelled';
  cursor_before:Record<string,unknown>; cursor_after:Record<string,unknown>;
  artefacts_discovered:number; events_produced:number; duplicates_skipped:number; errors:number;
  started_at:string; completed_at:string|null;
}

