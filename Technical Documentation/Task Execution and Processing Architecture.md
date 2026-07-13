# Task Execution and Processing Architecture

Task 2 replaces broad model purposes with a concrete task router. `frontend/lib/execution/registry.ts` is the canonical `TaskDefinition` and `EngineDefinition` registry. Routes are persisted in `task_routes`; absent rows resolve to the documented defaults in code.

## Execution sequence

1. Resolve the `TaskDefinition` and persisted/default `TaskRoute`.
2. Reject unknown or unsupported engine/task combinations.
3. Resolve `strict_local`, `local_first`, or `controlled_cloud` policy.
4. Create or attach an `AnalysisRun` (`task2-router-v1`).
5. Create an `ExecutionRecord` before invocation, including source artefact IDs.
6. Invoke exactly the selected adapter. Provider identity is taken from the engine registry, not inferred or defaulted to Google.
7. Complete or fail the audit record with sizes and structured error details.
8. For transcription, persist language, segments, word timestamps, confidence metadata, engine/model, run, source artefact, and derivation version in `transcript_artifacts`.

`strict_local` blocks every external personal-data invocation. `local_first` tries a compatible local engine first and permits an external fallback only when the route explicitly names it and the user enables external fallback. `controlled_cloud` permits only engine IDs present in `approved_external_engines`; an empty list permits none. Every attempted candidate, including a privacy-policy block, is auditable. Unknown provider names fail closed and are never normalised to Google.

## Task 3 semantic residue

Task 3 does not introduce another provider registry. `frontend/lib/execution/task3.ts` maps schema interpretation, semantic adjudication, topic labelling, media-boundary roles, and later narrative explanation to existing Task 2 task keys. Model-facing samples are mechanically bounded (256 samples, 256 KiB, 1,024 provenance artefacts, and a 2,048-character purpose) before `executeTask` is called.

Schema interpretation returns an unapproved proposal. Feature adjudication returns candidates or abstention, not accepted facts. Private benchmark cases must be synthetic or explicitly user-approved and use the same route; their `ExecutionRecord` supplies actual provider, model, and local/external execution metadata.

## Engines

Deterministic adapters: JSON, tabular, EXIF, and temporal. Local adapters: Parakeet, Whisper, Tesseract OCR, and Ollama generation. Remote generation adapters: Google, OpenAI, OpenRouter, Hugging Face, and NVIDIA. Optional local dependencies are never reported healthy unless detected. Remote health checks call a provider discovery/identity endpoint; a stored key alone is reported only as configured until probed.

Local audio is normalised with FFmpeg when available. Parakeet and Whisper are optional alternatives, not architectural dependencies. A general LLM is not a speech-recognition fallback. Summary and other semantic tasks receive transcript text, never original audio.

Task 1 remains authoritative for acquisition and provenance. Uploads are registered through `EvidenceLedger` as `ContentBlob`/`SourceArtifact` occurrences before ASR, and graph projection remains owned by `GraphProjectionService`.
