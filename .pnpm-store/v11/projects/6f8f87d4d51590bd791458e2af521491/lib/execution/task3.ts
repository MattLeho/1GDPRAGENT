import { executeTask, type TaskResult } from './router';

export const TASK3_ROLE_TASKS = {
    schema_interpretation:'schema.interpretation',
    semantic_adjudication:'semantic.adjudication',
    topic_labelling:'semantic.topic_labelling',
    image_caption:'image.caption',
    landmark_candidate:'image.landmark_candidate',
    media_summary:'media.summary',
    narrative_explanation:'graph.explanation',
} as const;

export const TASK3_LEGACY_ROLE_ALIASES: Record<string, keyof typeof TASK3_ROLE_TASKS> = {
    schemaInterpretation:'schema_interpretation',
    semanticAdjudication:'semantic_adjudication',
    topicLabelling:'topic_labelling',
};

export type Task3TextTask = 'schema.interpretation'|'semantic.adjudication'|'semantic.topic_labelling';

export interface Task3BoundedBundle {
    task_key: Task3TextTask;
    analysis_run_id: string;
    source_artifact_ids: string[];
    purpose: string;
    samples: Array<Record<string, unknown>>;
    maximum_sample_bytes: number;
    omitted_record_count: number;
    fingerprint_id?: string | null;
}

const TASK_PROMPTS: Record<Task3TextTask, string> = {
    'schema.interpretation':'Propose one constrained DeclarativeParserSpec from supplied structure samples. Return JSON only. Never return code. This is an unapproved proposal.',
    'semantic.adjudication':'Adjudicate only the supplied ambiguous candidates. Return JSON only with candidate results and abstention when evidence is insufficient. Do not promote candidates to facts.',
    'semantic.topic_labelling':'Label only the supplied engagement-signal summaries. Return JSON only with topic candidates and abstain when evidence is insufficient.',
};

export function validateTask3Bundle(bundle: Task3BoundedBundle): void {
    if (!Object.hasOwn(TASK_PROMPTS, bundle.task_key)) throw new Error(`Unsupported Task 3 bundle task: ${bundle.task_key}`);
    if (!bundle.analysis_run_id || !bundle.purpose || !Array.isArray(bundle.samples) || !Array.isArray(bundle.source_artifact_ids)) throw new Error('Incomplete Task 3 bundle');
    if (bundle.purpose.length > 2048 || bundle.samples.length > 256 || bundle.source_artifact_ids.length > 1024) throw new Error('Task 3 bundle exceeds structural limits');
    if (!Number.isInteger(bundle.maximum_sample_bytes) || bundle.maximum_sample_bytes < 1 || bundle.maximum_sample_bytes > 262_144) throw new Error('Invalid Task 3 bundle byte limit');
    const actualBytes = Buffer.byteLength(JSON.stringify(bundle.samples));
    if (actualBytes > bundle.maximum_sample_bytes) throw new Error('Task 3 bundle exceeds its byte limit');
    if (!Number.isInteger(bundle.omitted_record_count) || bundle.omitted_record_count < 0) throw new Error('Invalid omitted record count');
}

export async function executeTask3Bundle(bundle: Task3BoundedBundle, profileId: string): Promise<TaskResult> {
    validateTask3Bundle(bundle);
    const result = await executeTask({
        taskKey:bundle.task_key, workflowKey:'file.ingestion',
        analysisRunId:bundle.analysis_run_id, sourceArtifactIds:bundle.source_artifact_ids,
        input:{ text:JSON.stringify({
            purpose:bundle.purpose, samples:bundle.samples,
            omitted_record_count:bundle.omitted_record_count,
            fingerprint_id:bundle.fingerprint_id || null,
        }) },
        configuration:{ systemPrompt:TASK_PROMPTS[bundle.task_key], temperature:0 },
        profileId,
    });
    if (!result.ok) return result;
    const raw = result.output as { text?:unknown };
    if (typeof raw?.text !== 'string') return { ...result, output:{ structured_output_valid:false, raw_output:result.output } };
    const candidate = raw.text.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
    try {
        const parsed = JSON.parse(candidate);
        return { ...result, output:parsed };
    } catch {
        return { ...result, output:{ structured_output_valid:false, raw_text:raw.text } };
    }
}
