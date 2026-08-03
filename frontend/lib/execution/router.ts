import { pool } from '@/lib/db';
import { getAICredential } from '@/lib/ai-credentials';
import { generateRLMResponse } from '@/lib/rlm/provider-adapters';
import { resolveModelForProvider } from '@/lib/model-intents';
import { intelligenceAuthorityHeaders } from '@/lib/api-session';
import {
    ENGINES_BY_ID, ENGINE_DEFINITIONS, TASKS_BY_KEY, type EngineDefinition,
    type ExecutionLocation, type ProcessingMode,
} from './registry';

export interface FallbackRoute {
    engine_id: string;
    provider?: string;
    model?: string;
    execution_location?: ExecutionLocation;
}

export interface TaskRoute {
    task_key: string;
    engine_id: string;
    provider: string | null;
    model: string | null;
    execution_location: ExecutionLocation;
    fallback_chain: FallbackRoute[];
    enabled: boolean;
    max_concurrency: number;
    batch_size: number;
    timeout_ms: number;
    configuration: Record<string, unknown>;
    updated_at?: string;
}

export interface TaskInvocation {
    taskKey: string;
    input: unknown;
    workflowKey?: string;
    analysisRunId?: string;
    sourceArtifactIds?: string[];
    configuration?: Record<string, unknown>;
    /** Canonical session-derived profile authority for local Intelligence calls. */
    profileId?: string;
}

export interface EngineError {
    code: string;
    message: string;
    retryable: boolean;
    engine_id: string;
}

export type TaskResult =
    | { ok: true; output: unknown; executionRecordId: string; engineId: string; model: string | null }
    | { ok: false; error: EngineError; executionRecordId?: string };

interface ProcessingSettings {
    processing_mode: ProcessingMode;
    external_fallback_enabled: boolean;
    approved_external_engines: string[];
}

const DEFAULT_MODEL: Record<string, string> = {
    ollama: 'llama3.2', google: 'flash_latest', openai: 'gpt-4.1-mini',
    openrouter: 'openai/gpt-4.1-mini', huggingface: 'mistralai/Mistral-7B-Instruct-v0.3',
    nvidia: 'meta/llama-3.1-8b-instruct', nvidia_parakeet: 'nvidia/parakeet-tdt-0.6b-v3',
    openai_whisper: 'whisper',
};

function defaultRoute(taskKey: string): TaskRoute {
    const definition = TASKS_BY_KEY.get(taskKey);
    if (!definition) throw new Error(`Unknown task: ${taskKey}`);
    const engine = ENGINES_BY_ID.get(definition.default_engine_id)!;
    return {
        task_key: taskKey, engine_id: engine.engine_id, provider: engine.provider,
        model: DEFAULT_MODEL[engine.provider] || null, execution_location: engine.execution_location,
        fallback_chain: taskKey === 'speech.transcription'
            ? [{ engine_id: 'whisper_local', provider: 'openai_whisper', model: 'whisper', execution_location: 'local' }]
            : [],
        enabled: true, max_concurrency: 1, batch_size: 1, timeout_ms: 60_000, configuration: {},
    };
}

export async function getTaskRoutes(): Promise<TaskRoute[]> {
    const persisted = await pool.query('SELECT * FROM task_routes');
    const byKey = new Map(persisted.rows.map(row => [row.task_key, normalizeRoute(row)]));
    return [...TASKS_BY_KEY.keys()].map(key => byKey.get(key) || defaultRoute(key));
}

export async function getTaskRoute(taskKey: string): Promise<TaskRoute> {
    if (!TASKS_BY_KEY.has(taskKey)) throw new Error(`Unknown task: ${taskKey}`);
    const result = await pool.query('SELECT * FROM task_routes WHERE task_key=$1', [taskKey]);
    return result.rows[0] ? normalizeRoute(result.rows[0]) : defaultRoute(taskKey);
}

function normalizeRoute(row: Record<string, unknown>): TaskRoute {
    return {
        task_key: String(row.task_key), engine_id: String(row.engine_id),
        provider: row.provider ? String(row.provider) : null, model: row.model ? String(row.model) : null,
        execution_location: row.execution_location as ExecutionLocation,
        fallback_chain: Array.isArray(row.fallback_chain) ? row.fallback_chain as FallbackRoute[] : [],
        enabled: row.enabled !== false, max_concurrency: Number(row.max_concurrency || 1),
        batch_size: Number(row.batch_size || 1), timeout_ms: Number(row.timeout_ms || 60_000),
        configuration: (row.configuration || {}) as Record<string, unknown>,
        updated_at: row.updated_at ? String(row.updated_at) : undefined,
    };
}

export function validateTaskRoute(route: TaskRoute): void {
    const task = TASKS_BY_KEY.get(route.task_key);
    const engine = ENGINES_BY_ID.get(route.engine_id);
    if (!task) throw new Error(`Unknown task: ${route.task_key}`);
    if (!engine) throw new Error(`Unknown engine: ${route.engine_id}`);
    if (!task.supported_engine_types.includes(engine.engine_type) || !engine.capabilities.includes(task.task_key)) {
        throw new Error(`Engine ${engine.engine_id} does not support ${task.task_key}`);
    }
    if (route.provider && route.provider !== engine.provider) {
        throw new Error(`Provider ${route.provider} does not match engine ${engine.engine_id}`);
    }
    for (const fallback of route.fallback_chain) {
        const fallbackEngine = ENGINES_BY_ID.get(fallback.engine_id);
        if (!fallbackEngine || !task.supported_engine_types.includes(fallbackEngine.engine_type) || !fallbackEngine.capabilities.includes(task.task_key)) {
            throw new Error(`Fallback engine ${fallback.engine_id} does not support ${task.task_key}`);
        }
        if (fallback.provider && fallback.provider !== fallbackEngine.provider) {
            throw new Error(`Fallback provider does not match engine ${fallback.engine_id}`);
        }
    }
}

export async function saveTaskRoute(route: TaskRoute): Promise<TaskRoute> {
    validateTaskRoute(route);
    const result = await pool.query(`INSERT INTO task_routes
        (task_key,engine_id,provider,model,execution_location,fallback_chain,enabled,max_concurrency,batch_size,timeout_ms,configuration,updated_at)
        VALUES($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10,$11::jsonb,NOW())
        ON CONFLICT(task_key) DO UPDATE SET engine_id=EXCLUDED.engine_id,provider=EXCLUDED.provider,
        model=EXCLUDED.model,execution_location=EXCLUDED.execution_location,fallback_chain=EXCLUDED.fallback_chain,
        enabled=EXCLUDED.enabled,max_concurrency=EXCLUDED.max_concurrency,batch_size=EXCLUDED.batch_size,
        timeout_ms=EXCLUDED.timeout_ms,configuration=EXCLUDED.configuration,updated_at=NOW() RETURNING *`,
    [route.task_key,route.engine_id,route.provider,route.model,route.execution_location,JSON.stringify(route.fallback_chain),route.enabled,route.max_concurrency,route.batch_size,route.timeout_ms,JSON.stringify(route.configuration)]);
    return normalizeRoute(result.rows[0]);
}

export async function getProcessingSettings(): Promise<ProcessingSettings> {
    const result = await pool.query('SELECT processing_mode,external_fallback_enabled,approved_external_engines FROM processing_settings WHERE id=1');
    const row = result.rows[0] || {};
    return {
        processing_mode: row.processing_mode || 'local_first',
        external_fallback_enabled: row.external_fallback_enabled === true,
        approved_external_engines: Array.isArray(row.approved_external_engines) ? row.approved_external_engines : [],
    };
}

export async function saveProcessingSettings(settings: ProcessingSettings): Promise<ProcessingSettings> {
    if (!['strict_local','local_first','controlled_cloud'].includes(settings.processing_mode)) throw new Error('Invalid processing mode');
    await pool.query(`INSERT INTO processing_settings(id,processing_mode,external_fallback_enabled,approved_external_engines,updated_at)
        VALUES(1,$1,$2,$3::jsonb,NOW()) ON CONFLICT(id) DO UPDATE SET processing_mode=EXCLUDED.processing_mode,
        external_fallback_enabled=EXCLUDED.external_fallback_enabled,approved_external_engines=EXCLUDED.approved_external_engines,updated_at=NOW()`,
    [settings.processing_mode,settings.external_fallback_enabled,JSON.stringify(settings.approved_external_engines)]);
    return settings;
}

async function ensureAnalysisRun(invocation: TaskInvocation): Promise<string> {
    if (invocation.analysisRunId) return invocation.analysisRunId;
    const result = await pool.query(`INSERT INTO analysis_runs(run_type,status,pipeline_version,configuration,started_at)
        VALUES('task_execution','running','task2-router-v1',$1::jsonb,NOW()) RETURNING id`,
    [JSON.stringify({ task_key: invocation.taskKey, workflow_key: invocation.workflowKey || null })]);
    return result.rows[0].id;
}

export async function executeTask(invocation: TaskInvocation): Promise<TaskResult> {
    const task = TASKS_BY_KEY.get(invocation.taskKey);
    if (!task) return { ok:false,error:{code:'UNKNOWN_TASK',message:`Unknown task: ${invocation.taskKey}`,retryable:false,engine_id:'none'} };
    const route = await getTaskRoute(invocation.taskKey);
    if (!route.enabled) return { ok:false,error:{code:'TASK_DISABLED',message:`${invocation.taskKey} is disabled`,retryable:false,engine_id:route.engine_id} };
    try { validateTaskRoute(route); } catch (error) {
        return { ok:false,error:{code:'INVALID_ROUTE',message:error instanceof Error ? error.message : String(error),retryable:false,engine_id:route.engine_id} };
    }
    const privacy = await getProcessingSettings();
    const runId = await ensureAnalysisRun(invocation);
    const primary = ENGINES_BY_ID.get(route.engine_id)!;
    const candidates: Array<{ engine: EngineDefinition; model: string | null }> = [];
    if (privacy.processing_mode === 'local_first' && primary.execution_location === 'external') {
        const local = ENGINE_DEFINITIONS.find(engine => engine.execution_location === 'local' && engine.capabilities.includes(task.task_key) && task.supported_engine_types.includes(engine.engine_type));
        if (local) candidates.push({ engine: local, model: DEFAULT_MODEL[local.provider] || null });
        // Retain the configured external candidate so a denied attempt is
        // recorded as a privacy-policy block rather than disappearing as an
        // unaudited "no route" result.
        candidates.push({ engine: primary, model: route.model });
    } else {
        candidates.push({ engine: primary, model: route.model });
    }
    for (const fallback of route.fallback_chain) {
        const engine = ENGINES_BY_ID.get(fallback.engine_id)!;
        if (!candidates.some(candidate => candidate.engine.engine_id === engine.engine_id)) candidates.push({ engine, model: fallback.model || DEFAULT_MODEL[engine.provider] || null });
    }
    if (primary.execution_location === 'external' && privacy.processing_mode === 'controlled_cloud' && !candidates.some(c => c.engine.engine_id === primary.engine_id)) {
        candidates.unshift({ engine: primary, model: route.model });
    }

    let last: TaskResult | undefined;
    for (const candidate of candidates) {
        const external = candidate.engine.execution_location === 'external';
        const explicitlyFallback = route.fallback_chain.some(fallback => fallback.engine_id === candidate.engine.engine_id);
        const blocked = external && (
            privacy.processing_mode === 'strict_local' ||
            (privacy.processing_mode === 'local_first' && (!privacy.external_fallback_enabled || !explicitlyFallback)) ||
            (privacy.processing_mode === 'controlled_cloud' && !privacy.approved_external_engines.includes(candidate.engine.engine_id))
        );
        if (blocked) {
            const recordId = await startExecutionRecord(invocation, runId, candidate.engine, candidate.model);
            await finishExecutionRecord(recordId,'blocked',0,{ code:'PRIVACY_POLICY_BLOCK', processing_mode:privacy.processing_mode });
            last = { ok:false,executionRecordId:recordId,error:{code:'PRIVACY_POLICY_BLOCK',message:`${privacy.processing_mode} blocked ${candidate.engine.engine_id}`,retryable:false,engine_id:candidate.engine.engine_id} };
            continue;
        }
        last = await invokeAndAudit(invocation, runId, candidate.engine, candidate.model, route.timeout_ms, { ...route.configuration, ...invocation.configuration });
        if (last.ok) {
            await pool.query("UPDATE analysis_runs SET status='completed',completed_at=NOW() WHERE id=$1 AND run_type='task_execution'", [runId]);
            return last;
        }
    }
    await pool.query("UPDATE analysis_runs SET status='failed',completed_at=NOW(),error=$2 WHERE id=$1 AND run_type='task_execution'", [runId,last && !last.ok ? last.error.message : 'No executable route']);
    return last || { ok:false,error:{code:'NO_EXECUTABLE_ROUTE',message:'No executable route passed privacy policy',retryable:false,engine_id:route.engine_id} };
}

async function startExecutionRecord(invocation: TaskInvocation, runId: string, engine: EngineDefinition, model: string | null): Promise<string> {
    const result = await pool.query(`INSERT INTO execution_records
        (analysis_run_id,task_key,workflow_key,engine_id,provider,model,execution_location,source_artifact_ids,status,input_size)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8::uuid[],'running',$9) RETURNING id`,
    [runId,invocation.taskKey,invocation.workflowKey || null,engine.engine_id,engine.provider,model,engine.execution_location,invocation.sourceArtifactIds || [],byteSize(invocation.input)]);
    return result.rows[0].id;
}

async function finishExecutionRecord(id: string, status: 'completed'|'failed'|'blocked', outputSize: number, error?: unknown): Promise<void> {
    await pool.query('UPDATE execution_records SET status=$2,completed_at=NOW(),output_size=$3,error=$4::jsonb WHERE id=$1',
        [id,status,outputSize,error ? JSON.stringify(error) : null]);
}

async function invokeAndAudit(invocation: TaskInvocation, runId: string, engine: EngineDefinition, model: string | null, timeoutMs: number, configuration: Record<string, unknown>): Promise<TaskResult> {
    const recordId = await startExecutionRecord(invocation,runId,engine,model);
    try {
        const output = await Promise.race([
            invokeEngine(engine,invocation.taskKey,invocation.input,model,configuration,invocation.profileId),
            new Promise((_,reject) => setTimeout(() => reject(new Error('Engine invocation timed out')),timeoutMs)),
        ]);
        await finishExecutionRecord(recordId,'completed',byteSize(output));
        if (invocation.taskKey === 'speech.transcription' && invocation.sourceArtifactIds?.[0]) {
            const transcript = output as { text?:unknown;language?:unknown;segments?:unknown;words?:unknown;confidence?:unknown;derivation_version?:unknown };
            if (typeof transcript.text === 'string') {
                await pool.query(`INSERT INTO transcript_artifacts(source_artifact_id,analysis_run_id,execution_record_id,engine_id,model,language,segments,words,confidence,transcript,derivation_version)
                    VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,$10,$11)`,
                [invocation.sourceArtifactIds[0],runId,recordId,engine.engine_id,model,typeof transcript.language==='string'?transcript.language:null,
                    JSON.stringify(transcript.segments||[]),JSON.stringify(transcript.words||[]),JSON.stringify(transcript.confidence||{}),transcript.text,
                    typeof transcript.derivation_version==='string'?transcript.derivation_version:'task2-asr-v1']);
            }
        }
        return { ok:true,output,executionRecordId:recordId,engineId:engine.engine_id,model };
    } catch (error) {
        const structured = { code:'ENGINE_INVOCATION_FAILED',message:error instanceof Error ? error.message : String(error),retryable:true,engine_id:engine.engine_id };
        await finishExecutionRecord(recordId,'failed',0,structured);
        return { ok:false,executionRecordId:recordId,error:structured };
    }
}

async function invokeEngine(engine: EngineDefinition, taskKey: string, input: unknown, model: string | null, configuration: Record<string, unknown>, profileId?: string): Promise<unknown> {
    if (engine.adapter === 'generation') {
        if (taskKey === 'speech.transcription' || taskKey === 'speech.translation') throw new Error('General generation engines cannot perform speech recognition');
        const text = typeof input === 'string' ? input : (input as { text?: unknown })?.text;
        if (typeof text !== 'string') throw new Error(`${taskKey} requires extracted text, not binary media`);
        const resolvedModel=await resolveModelForProvider(engine.provider,model || DEFAULT_MODEL[engine.provider]);
        const result = await generateRLMResponse({ provider:engine.provider,model:resolvedModel,
            systemPrompt:String(configuration.systemPrompt || `Perform only the registered task ${taskKey}. Return a grounded result.`),
            messages:[{role:'user',content:text}],useTools:false,temperature:Number(configuration.temperature ?? 0.2) });
        return { text:result.content };
    }
    if (engine.adapter === 'intelligence_service') {
        if (!profileId) throw new Error('Authenticated profile authority is required for Intelligence execution');
        const baseUrl = process.env.INTELLIGENCE_SERVICE_URL || 'http://intelligence:8000';
        const target = `${baseUrl}/execution/invoke`;
        const body=JSON.stringify({ engine_id:engine.engine_id,task_key:taskKey,input,model,configuration });
        const response = await fetch(target, { method:'POST',headers:intelligenceAuthorityHeaders(profileId,target,'POST','application/json',undefined,undefined,body),
            body,signal:AbortSignal.timeout(120_000) });
        if (!response.ok) throw new Error(`Local intelligence adapter returned ${response.status}: ${await response.text()}`);
        return response.json();
    }
    if (engine.engine_id === 'deterministic_json') {
        if (typeof input === 'string') return { data:JSON.parse(input) };
        return { data:input };
    }
    if (engine.engine_id === 'deterministic_tabular') {
        if (typeof input !== 'string') throw new Error('Tabular parser requires text');
        const [header,...rows] = input.trim().split(/\r?\n/).map(line => line.split(','));
        return { rows:rows.map(row => Object.fromEntries(header.map((key,index) => [key,row[index] ?? '']))) };
    }
    if (engine.engine_id === 'deterministic_temporal') {
        const points = Array.isArray(input) ? input as Array<{ timestamp:string; value:number }> : [];
        return { changes:points.slice(1).map((point,index) => ({ timestamp:point.timestamp,delta:point.value-points[index].value })).filter(change => change.delta !== 0) };
    }
    throw new Error(`No invocation adapter for ${engine.engine_id}`);
}

export async function getEngineHealth(engineId: string, profileId?: string): Promise<{ status:'healthy'|'unavailable'|'unconfigured'|'unknown'; message:string; models:string[] }> {
    const engine = ENGINES_BY_ID.get(engineId);
    if (!engine) return { status:'unavailable',message:'Unknown engine',models:[] };
    if (engine.adapter === 'deterministic') return { status:'healthy',message:'Built-in deterministic adapter is available',models:[] };
    if (engine.adapter === 'intelligence_service') {
        if (!profileId) return { status:'unavailable',message:'Authenticated profile authority is required for Intelligence health checks',models:[] };
        try {
            const baseUrl = process.env.INTELLIGENCE_SERVICE_URL || 'http://intelligence:8000';
            const target = `${baseUrl}/execution/engines/${engineId}/health`;
            const response = await fetch(target,{headers:intelligenceAuthorityHeaders(profileId,target,'GET'),signal:AbortSignal.timeout(3000)});
            if (!response.ok) return { status:'unavailable',message:`Health check returned ${response.status}`,models:[] };
            return response.json();
        } catch (error) { return { status:'unavailable',message:error instanceof Error ? error.message : String(error),models:[] }; }
    }
    if (engine.provider === 'ollama') {
        try {
            const response = await fetch(`${process.env.OLLAMA_BASE_URL || 'http://localhost:11434'}/api/tags`,{signal:AbortSignal.timeout(3000)});
            const body = response.ok ? await response.json() : {};
            return response.ok ? { status:'healthy',message:'Ollama responded',models:(body.models || []).map((entry:{name:string}) => entry.name) }
                : { status:'unavailable',message:`Ollama returned ${response.status}`,models:[] };
        } catch (error) { return { status:'unavailable',message:error instanceof Error ? error.message : String(error),models:[] }; }
    }
    const credential=await getAICredential(engine.provider, profileId);
    if (!credential) return { status:'unconfigured',message:'No provider credential is configured',models:[] };
    const probes:Record<string,{url:string;headers:Record<string,string>}>= {
        google:{url:`https://generativelanguage.googleapis.com/v1beta/models?key=${encodeURIComponent(credential)}`,headers:{}},
        openai:{url:'https://api.openai.com/v1/models',headers:{Authorization:`Bearer ${credential}`}},
        openrouter:{url:'https://openrouter.ai/api/v1/models',headers:{Authorization:`Bearer ${credential}`}},
        nvidia:{url:'https://integrate.api.nvidia.com/v1/models',headers:{Authorization:`Bearer ${credential}`}},
        huggingface:{url:'https://huggingface.co/api/whoami-v2',headers:{Authorization:`Bearer ${credential}`}},
    };
    const probe=probes[engine.provider];
    if(!probe)return {status:'unknown',message:'No non-invasive health probe is defined',models:[]};
    try{
        const response=await fetch(probe.url,{headers:probe.headers,signal:AbortSignal.timeout(5000),cache:'no-store'});
        if(!response.ok)return{status:'unavailable',message:`Provider health probe returned ${response.status}`,models:[]};
        const body=await response.json();const entries=Array.isArray(body.data)?body.data:Array.isArray(body.models)?body.models:[];
        return{status:'healthy',message:'Provider model-discovery endpoint responded',models:entries.map((item:{id?:string;name?:string})=>item.id||item.name||'').filter(Boolean).slice(0,100)};
    }catch(error){return{status:'unavailable',message:error instanceof Error?error.message:String(error),models:[]};}
}

function byteSize(value: unknown): number { return Buffer.byteLength(typeof value === 'string' ? value : JSON.stringify(value ?? null),'utf8'); }
