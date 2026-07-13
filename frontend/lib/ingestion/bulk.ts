import { executeTask } from '@/lib/execution/router';

interface ReceivedFile {
    id: string;
    request_id?: string | null;
    file_path: string;
    file_name?: string;
    file_type?: string | null;
    category?: string | null;
}

interface SpecialistRequest {
    request_id: string;
    task_key: string;
    input_manifest: Record<string, unknown>;
}

export interface BulkResult {
    analysis_run_id: string;
    export_snapshot_id: string;
    artifact_id: string;
    ingestion_status: string;
    detected_format: string | null;
    extraction_unit_count: number;
    event_count: number;
    specialist_tasks: SpecialistRequest[];
    warnings: string[];
    specialist_results?: Array<Record<string, unknown>>;
}

const intelligenceUrl = () => process.env.INTELLIGENCE_SERVICE_URL || process.env.INTELLIGENCE_URL || 'http://intelligence:8000';

export function toIntelligencePath(filePath: string): string {
    return filePath.startsWith('/app/uploads/')
        ? filePath.replace('/app/uploads/', '/source-uploads/')
        : filePath;
}

export function requestedSpecialistTasks(action: string | undefined, file: ReceivedFile): string[] {
    const selected = action || file.category || '';
    if (['transcribe','audio','video'].includes(selected)) return ['speech.transcription'];
    if (selected === 'ocr' || selected === 'image') {
        return file.file_type === 'application/pdf' ? ['document.ocr'] : ['image.ocr'];
    }
    return [];
}

export async function processThroughBulkPipeline(file: ReceivedFile, action?: string): Promise<BulkResult> {
    const response = await fetch(`${intelligenceUrl()}/bulk-ingestion/process`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
            file_path:toIntelligencePath(file.file_path), request_id:file.request_id || null,
            received_data_id:file.id, declared_mime:file.file_type || null,
            original_path:file.file_name || undefined, source_type:'manual_import',
            requested_tasks:requestedSpecialistTasks(action,file),
        }), signal:AbortSignal.timeout(15 * 60_000),
    });
    if (!response.ok) throw new Error(`Local ingestion returned ${response.status}: ${await response.text()}`);
    const result = await response.json() as BulkResult;
    const specialistResults: Array<Record<string, unknown>> = [];
    for (const request of result.specialist_tasks || []) {
        const routed = await executeTask({
            taskKey:request.task_key, workflowKey:'file.ingestion',
            analysisRunId:result.analysis_run_id, sourceArtifactIds:[result.artifact_id],
            input:request.input_manifest,
        });
        const report = routed.ok
            ? { specialist_request_id:request.request_id, execution_record_id:routed.executionRecordId, status:'completed', output:routed.output }
            : { specialist_request_id:request.request_id, execution_record_id:routed.executionRecordId || null, status:routed.error.code === 'PRIVACY_POLICY_BLOCK' ? 'blocked' : 'failed', error:routed.error };
        const recorded = await fetch(`${intelligenceUrl()}/bulk-ingestion/specialist-results`, {
            method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(report),
            signal:AbortSignal.timeout(120_000),
        });
        if (!recorded.ok) throw new Error(`Specialist provenance registration returned ${recorded.status}: ${await recorded.text()}`);
        specialistResults.push({ task_key:request.task_key, ...report });
    }
    return { ...result, specialist_results:specialistResults };
}
