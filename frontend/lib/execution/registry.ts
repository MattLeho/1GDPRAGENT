export type EngineType = 'deterministic' | 'local_model' | 'remote_model' | 'local_service' | 'remote_service';
export type ExecutionLocation = 'local' | 'external' | 'automatic';
export type ProcessingMode = 'strict_local' | 'local_first' | 'controlled_cloud';
export type TaskCategory = 'speech' | 'images' | 'documents' | 'schema' | 'semantic' | 'temporal' | 'graph' | 'policy_requests' | 'email' | 'media';

export interface TaskDefinition {
    task_key: string;
    display_name: string;
    description: string;
    task_category: TaskCategory;
    privacy_class: 'personal' | 'sensitive' | 'metadata';
    input_modality: string;
    output_schema: Record<string, unknown>;
    deterministic: boolean;
    default_engine_id: string;
    supported_engine_types: EngineType[];
    supports_local: boolean;
    supports_external: boolean;
    allows_external_in_strict_local: boolean;
    configuration_schema: Record<string, unknown>;
}

export interface EngineDefinition {
    engine_id: string;
    display_name: string;
    engine_type: EngineType;
    provider: string;
    execution_location: Exclude<ExecutionLocation, 'automatic'>;
    capabilities: string[];
    supports_model_discovery: boolean;
    adapter: 'deterministic' | 'generation' | 'intelligence_service';
}

const textOutput = { type: 'object', required: ['text'], properties: { text: { type: 'string' } } };
const jsonOutput = { type: 'object' };
const configSchema = { type: 'object', additionalProperties: true };

function task(
    task_key: string, display_name: string, description: string, task_category: TaskCategory,
    privacy_class: TaskDefinition['privacy_class'], input_modality: string,
    default_engine_id: string, supported_engine_types: EngineType[],
    output_schema: Record<string, unknown> = jsonOutput,
): TaskDefinition {
    return {
        task_key, display_name, description, task_category, privacy_class, input_modality,
        output_schema, deterministic: supported_engine_types.length === 1 && supported_engine_types[0] === 'deterministic',
        default_engine_id, supported_engine_types,
        supports_local: supported_engine_types.some(type => type === 'deterministic' || type.startsWith('local_')),
        supports_external: supported_engine_types.some(type => type.startsWith('remote_')),
        allows_external_in_strict_local: false,
        configuration_schema: configSchema,
    };
}

export const TASK_DEFINITIONS: readonly TaskDefinition[] = [
    task('speech.transcription','Speech transcription','Timestamped speech-to-text only.','speech','sensitive','audio','parakeet_local',['local_model'],textOutput),
    task('speech.translation','Speech translation','Translate timestamped speech without semantic interpretation.','speech','sensitive','audio','whisper_local',['local_model'],textOutput),
    task('speech.diarisation','Speaker diarisation','Separate speakers in timestamped speech.','speech','sensitive','audio','parakeet_local',['local_model','local_service']),
    task('image.metadata','Image metadata','Read deterministic file and EXIF metadata.','images','metadata','image','deterministic_exif',['deterministic']),
    task('image.origin_classification','Image origin classification','Classify camera, screenshot, downloaded, edited, generated, or unknown origin.','images','personal','image','local_ocr',['local_service','local_model','remote_model']),
    task('image.ocr','Image OCR','Extract visible text from an image.','images','sensitive','image','local_ocr',['local_service','local_model','remote_model'],textOutput),
    task('image.caption','Image caption','Describe selected image content.','images','sensitive','image','ollama_generation',['local_model','remote_model'],textOutput),
    task('image.landmark_candidate','Landmark candidate','Propose, but do not assert, a landmark match.','images','sensitive','image','ollama_generation',['local_model','remote_model']),
    task('document.text_extraction','Document text extraction','Extract embedded text without interpretation.','documents','sensitive','document','deterministic_json',['deterministic','local_service'],textOutput),
    task('document.ocr','Document OCR','OCR scanned document pages.','documents','sensitive','document','local_ocr',['local_service','local_model','remote_model'],textOutput),
    task('document.structure','Document structure','Recover headings, tables, and reading order.','documents','sensitive','document','deterministic_json',['deterministic','local_model','remote_model']),
    task('schema.fingerprinting','Schema fingerprinting','Deterministically identify known JSON/tabular shapes.','schema','metadata','structured','deterministic_json',['deterministic']),
    task('schema.interpretation','Unknown-schema interpretation','Interpret only unresolved schema residue.','schema','sensitive','text','ollama_generation',['local_model','remote_model']),
    task('semantic.adjudication','Semantic adjudication','Adjudicate ambiguous extracted candidates.','semantic','sensitive','text','ollama_generation',['local_model','remote_model']),
    task('semantic.topic_labelling','Topic labelling','Label user-originated engagement signals.','semantic','sensitive','text','ollama_generation',['local_model','remote_model']),
    task('semantic.context_correlation','Context correlation','Describe possible contextual relations without causal claims.','semantic','sensitive','text','ollama_generation',['local_model','remote_model']),
    task('temporal.change_detection','Temporal change detection','Detect changes in event series deterministically.','temporal','personal','structured','deterministic_temporal',['deterministic']),
    task('temporal.episode_labelling','Temporal episode labelling','Label detected temporal episodes.','temporal','personal','text','ollama_generation',['local_model','remote_model']),
    task('graph.projection','Graph projection','Project verified assertions through GraphProjectionService.','graph','sensitive','assertions','deterministic_json',['deterministic','local_service']),
    task('graph.explanation','Graph explanation','Explain grounded graph query results.','graph','sensitive','text','ollama_generation',['local_model','remote_model'],textOutput),
    task('policy.extraction','Policy extraction','Extract policy clauses and controller details.','policy_requests','personal','document','deterministic_json',['deterministic','local_model','remote_model']),
    task('policy.interpretation','Policy interpretation','Interpret extracted policy clauses.','policy_requests','personal','text','ollama_generation',['local_model','remote_model']),
    task('request.drafting','Request drafting','Draft a GDPR request from reviewed facts.','policy_requests','sensitive','text','ollama_generation',['local_model','remote_model'],textOutput),
    task('email.classification','Email classification','Classify a controller response.','email','sensitive','text','ollama_generation',['local_model','remote_model']),
    task('email.retention_adjudication','Email retention adjudication','Adjudicate uncertain retention candidates; never deletes.','email','sensitive','text','ollama_generation',['local_model','remote_model']),
    task('media.summary','Transcript or media summary','Summarise extracted text; never receives original audio by default.','media','sensitive','text','ollama_generation',['local_model','remote_model'],textOutput),
] as const;

const generationTasks = TASK_DEFINITIONS.filter(t => t.supported_engine_types.includes('local_model') || t.supported_engine_types.includes('remote_model')).map(t => t.task_key);
const asrTasks = ['speech.transcription','speech.translation','speech.diarisation'];

export const ENGINE_DEFINITIONS: readonly EngineDefinition[] = [
    { engine_id:'deterministic_json',display_name:'Deterministic JSON',engine_type:'deterministic',provider:'built_in',execution_location:'local',capabilities:['document.text_extraction','document.structure','schema.fingerprinting','graph.projection','policy.extraction'],supports_model_discovery:false,adapter:'deterministic' },
    { engine_id:'deterministic_tabular',display_name:'Deterministic tabular parser',engine_type:'deterministic',provider:'built_in',execution_location:'local',capabilities:['document.text_extraction','schema.fingerprinting'],supports_model_discovery:false,adapter:'deterministic' },
    { engine_id:'deterministic_exif',display_name:'Deterministic EXIF',engine_type:'deterministic',provider:'exiftool',execution_location:'local',capabilities:['image.metadata'],supports_model_discovery:false,adapter:'intelligence_service' },
    { engine_id:'deterministic_temporal',display_name:'Deterministic temporal analysis',engine_type:'deterministic',provider:'built_in',execution_location:'local',capabilities:['temporal.change_detection'],supports_model_discovery:false,adapter:'deterministic' },
    { engine_id:'parakeet_local',display_name:'Parakeet local',engine_type:'local_model',provider:'nvidia_parakeet',execution_location:'local',capabilities:asrTasks,supports_model_discovery:true,adapter:'intelligence_service' },
    { engine_id:'whisper_local',display_name:'Whisper local',engine_type:'local_model',provider:'openai_whisper',execution_location:'local',capabilities:['speech.transcription','speech.translation'],supports_model_discovery:true,adapter:'intelligence_service' },
    { engine_id:'local_ocr',display_name:'Local OCR',engine_type:'local_service',provider:'tesseract',execution_location:'local',capabilities:['image.ocr','image.origin_classification','document.ocr'],supports_model_discovery:false,adapter:'intelligence_service' },
    { engine_id:'ollama_generation',display_name:'Ollama',engine_type:'local_model',provider:'ollama',execution_location:'local',capabilities:generationTasks,supports_model_discovery:true,adapter:'generation' },
    ...(['google','openai','openrouter','huggingface','nvidia'] as const).map(provider => ({
        engine_id:`${provider}_generation`, display_name:`${provider[0].toUpperCase()}${provider.slice(1)} generation`,
        engine_type:'remote_model' as const, provider, execution_location:'external' as const,
        capabilities:generationTasks, supports_model_discovery:true, adapter:'generation' as const,
    })),
] as const;

export const TASKS_BY_KEY = new Map(TASK_DEFINITIONS.map(definition => [definition.task_key, definition]));
export const ENGINES_BY_ID = new Map(ENGINE_DEFINITIONS.map(definition => [definition.engine_id, definition]));

export function validateRegistry(): string[] {
    const errors: string[] = [];
    for (const taskDefinition of TASK_DEFINITIONS) {
        const engine = ENGINES_BY_ID.get(taskDefinition.default_engine_id);
        if (!engine) errors.push(`${taskDefinition.task_key}: missing default engine`);
        else if (!engine.capabilities.includes(taskDefinition.task_key)) errors.push(`${taskDefinition.task_key}: default engine lacks capability`);
    }
    return errors;
}
