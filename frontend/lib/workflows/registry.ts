import { pool } from '@/lib/db';

export type WorkflowExecutionMode = 'built_in' | 'n8n' | 'hybrid' | 'disabled';

export interface WorkflowDefinition {
    workflow_key: string;
    display_name: string;
    description: string;
    category: string;
    built_in_handler: string;
    n8n_webhook_key: string | null;
    supports_schedule: boolean;
    configuration_schema: Record<string, unknown>;
    required_task_keys: string[];
    required_connector_capabilities: string[];
}

export interface WorkflowPreference {
    workflow_key: string;
    execution_mode: WorkflowExecutionMode;
    enabled: boolean;
    configuration: Record<string, unknown>;
    fallback_order: Array<'built_in'|'n8n'>;
    schedule: Record<string, unknown> | null;
    updated_at?: string;
}

const schema = { type:'object',additionalProperties:true };
function workflow(workflow_key:string,display_name:string,description:string,category:string,built_in_handler:string,n8n_webhook_key:string|null,required_task_keys:string[]=[],required_connector_capabilities:string[]=[],supports_schedule=false):WorkflowDefinition {
    return { workflow_key,display_name,description,category,built_in_handler,n8n_webhook_key,supports_schedule,configuration_schema:schema,required_task_keys,required_connector_capabilities };
}

export const WORKFLOW_DEFINITIONS: readonly WorkflowDefinition[] = [
    workflow('policy.acquisition','Privacy-policy acquisition','Fetch a controller privacy policy.','Policy','frontend:/api/gdpr-agent/analyze-policy','analyzePolicy'),
    workflow('policy.analysis','Privacy-policy analysis','Extract and interpret controller policy claims.','Policy','frontend:/api/gdpr-agent/analyze-policy','analyzePolicy',['policy.extraction','policy.interpretation']),
    workflow('request.drafting','Request drafting','Draft a reviewed GDPR request.','Requests','frontend:/api/gdpr-agent/draft',null,['request.drafting']),
    workflow('email.sending','Email sending','Send with the configured server-side email connector.','Email','frontend:built-in-email-transport',null,[],['email.send']),
    workflow('email.connection_test','IMAP/SMTP connection testing','Test configured connectors without exposing secrets.','Email','frontend:built-in-email-test','testImap',[],['email.test']),
    workflow('inbox.monitoring','Inbox monitoring','Incrementally check for controller replies.','Email','frontend:built-in-inbox-monitor',null,[],['email.read'],true),
    workflow('response.classification','Response classification','Classify a matched controller reply.','Responses','frontend:task-router',null,['email.classification']),
    workflow('response.attachment_detection','Attachment and download detection','Detect attachments and protected download links.','Responses','frontend:built-in-response-detector',null),
    workflow('response.parsing','Response parsing','Parse response files into the canonical evidence pipeline.','Responses','frontend:/api/upload/process',null,['document.text_extraction','schema.fingerprinting']),
    workflow('file.ingestion','File ingestion','Create ContentBlob, SourceArtifact, EvidenceLocator, and candidates through the local bulk pipeline.','Evidence','python:/bulk-ingestion/process','ingestData',['schema.fingerprinting','schema.interpretation']),
    workflow('identity.ingestion','Identity ingestion','Create human-confirmed identity assertions.','Evidence','frontend:/api/graph/upsert-identity','ingestIdentity'),
    workflow('grounded.extraction','Grounded extraction','Persist Task-Router candidates only after exact source-location verification.','Evidence','python:/extract/policy-claims','ingestData',['schema.fingerprinting','schema.interpretation']),
    workflow('graph.projection','Graph projection','Project verified assertions through GraphProjectionService.','Graph','python:GraphProjectionService','ingestData',['graph.projection']),
    workflow('graph.query','Typed privacy query','Run one allow-listed read-only privacy tool with assertion and locator citations.','Graph','python:/query',null,['graph.explanation']),
    workflow('speech.transcription','Speech transcription','Route local ASR and persist transcript provenance.','Media','python:/execution/invoke',null,['speech.transcription']),
    workflow('vendor.ocr','Vendor OCR','Extract vendor candidates from selected media.','ONSIT','frontend:/api/onsit/extract-vendors','vendorExtract',['image.ocr']),
    workflow('policy.scanning','Privacy-policy scanning','Scan and analyse a policy URL.','Policy','frontend:/api/gdpr-agent/analyze-policy','policyScan',['policy.extraction','policy.interpretation']),
    workflow('makged.validation','MAKGED validation','Validate interpretation candidates before projection.','Graph','python:/validate','validateTriple',['semantic.adjudication']),
] as const;

/** Single source of truth for every shipped N8N webhook adapter. */
export const N8N_WEBHOOK_MAPPINGS = [
    {id:'analyzePolicy',envVar:'N8N_WEBHOOK_ANALYZE_POLICY'},
    {id:'testImap',envVar:'N8N_WEBHOOK_TEST_IMAP'},
    {id:'ingestData',envVar:'N8N_WEBHOOK_INGEST_DATA'},
    {id:'ingestIdentity',envVar:'N8N_WEBHOOK_INGEST_IDENTITY'},
    {id:'vendorExtract',envVar:'N8N_WEBHOOK_VENDOR_EXTRACT'},
    {id:'policyScan',envVar:'N8N_WEBHOOK_POLICY_SCAN'},
    {id:'validateTriple',envVar:'N8N_WEBHOOK_VALIDATE_TRIPLE'},
] as const;

export const WORKFLOWS_BY_KEY = new Map(WORKFLOW_DEFINITIONS.map(definition => [definition.workflow_key,definition]));

function defaultPreference(workflowKey:string):WorkflowPreference {
    return { workflow_key:workflowKey,execution_mode:'built_in',enabled:true,configuration:{},fallback_order:['built_in'],schedule:null };
}

function normalize(row:Record<string,unknown>, definition?: WorkflowDefinition):WorkflowPreference {
    const storedMode = row.execution_mode as WorkflowExecutionMode;
    const executionMode = !definition?.n8n_webhook_key && (storedMode === 'n8n' || storedMode === 'hybrid')
        ? 'built_in' : storedMode;
    return { workflow_key:String(row.workflow_key),execution_mode:executionMode,
        enabled:row.enabled !== false,configuration:(row.configuration || {}) as Record<string,unknown>,
        fallback_order:Array.isArray(row.fallback_order) ? row.fallback_order as Array<'built_in'|'n8n'> : ['built_in'],
        schedule:row.schedule ? row.schedule as Record<string,unknown> : null,updated_at:row.updated_at ? String(row.updated_at) : undefined };
}

export async function getWorkflowPreferences():Promise<WorkflowPreference[]> {
    const result=await pool.query('SELECT * FROM workflow_preferences');
    const stored=new Map(result.rows.map(row=>{
        const definition=WORKFLOWS_BY_KEY.get(String(row.workflow_key));
        return [row.workflow_key,normalize(row,definition)] as const;
    }));
    return WORKFLOW_DEFINITIONS.map(definition=>stored.get(definition.workflow_key)||defaultPreference(definition.workflow_key));
}

export async function getWorkflowPreference(workflowKey:string):Promise<WorkflowPreference> {
    if(!WORKFLOWS_BY_KEY.has(workflowKey)) throw new Error(`Unknown workflow: ${workflowKey}`);
    const result=await pool.query('SELECT * FROM workflow_preferences WHERE workflow_key=$1',[workflowKey]);
    return result.rows[0]?normalize(result.rows[0],WORKFLOWS_BY_KEY.get(workflowKey)):defaultPreference(workflowKey);
}

export async function saveWorkflowPreference(preference:WorkflowPreference):Promise<WorkflowPreference> {
    if(!WORKFLOWS_BY_KEY.has(preference.workflow_key)) throw new Error(`Unknown workflow: ${preference.workflow_key}`);
    if(!['built_in','n8n','hybrid','disabled'].includes(preference.execution_mode)) throw new Error('Invalid execution mode');
    const definition=WORKFLOWS_BY_KEY.get(preference.workflow_key)!;
    if((preference.execution_mode==='n8n'||preference.execution_mode==='hybrid')&&!definition.n8n_webhook_key) throw new Error(`${preference.workflow_key} has no N8N adapter`);
    const fallback=preference.execution_mode==='hybrid'?(preference.fallback_order.length?preference.fallback_order:['built_in','n8n']):preference.execution_mode==='n8n'?['n8n']:['built_in'];
    const result=await pool.query(`INSERT INTO workflow_preferences(workflow_key,execution_mode,enabled,configuration,fallback_order,schedule,updated_at)
        VALUES($1,$2,$3,$4::jsonb,$5::jsonb,$6::jsonb,NOW()) ON CONFLICT(workflow_key) DO UPDATE SET
        execution_mode=EXCLUDED.execution_mode,enabled=EXCLUDED.enabled,configuration=EXCLUDED.configuration,
        fallback_order=EXCLUDED.fallback_order,schedule=EXCLUDED.schedule,updated_at=NOW() RETURNING *`,
    [preference.workflow_key,preference.execution_mode,preference.enabled,JSON.stringify(preference.configuration),JSON.stringify(fallback),preference.schedule?JSON.stringify(preference.schedule):null]);
    return normalize(result.rows[0],definition);
}

export function assertBuiltInParity():string[] {
    return WORKFLOW_DEFINITIONS.filter(definition=>!definition.built_in_handler).map(definition=>definition.workflow_key);
}
