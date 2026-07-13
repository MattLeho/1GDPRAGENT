from __future__ import annotations
import re
from pathlib import Path

ROOT=Path('/workspace') if Path('/workspace/docker-compose.yml').exists() else Path(__file__).resolve().parents[1]
def read(path:str)->str:return (ROOT/path).read_text(encoding="utf-8")

def test_task_and_engine_registries_are_canonical_and_validated():
    source=read("frontend/lib/execution/registry.ts")
    required={"speech.transcription","speech.translation","speech.diarisation","image.metadata","image.ocr","document.text_extraction","schema.fingerprinting","schema.interpretation","semantic.adjudication","temporal.change_detection","graph.projection","graph.explanation","policy.extraction","policy.interpretation","request.drafting","email.classification","media.summary"}
    assert required <= set(re.findall(r"task\('([^']+)'",source))
    engines=set(re.findall(r"engine_id:'([^']+)'",source))|{"google_generation","openai_generation","openrouter_generation","huggingface_generation","nvidia_generation"}
    assert {"deterministic_json","deterministic_tabular","deterministic_exif","deterministic_temporal","parakeet_local","whisper_local","local_ocr","ollama_generation"} <= engines
    assert "validateRegistry" in source and "default engine lacks capability" in source

def test_router_rejects_unsupported_combinations_and_enforces_privacy_modes():
    source=read("frontend/lib/execution/router.ts")
    assert "does not support" in source and "validateTaskRoute(route)" in source
    assert "privacy.processing_mode === 'strict_local'" in source
    assert "privacy.processing_mode === 'local_first'" in source
    assert "privacy.external_fallback_enabled" in source and "explicitlyFallback" in source
    assert "execution_records" in source and "PRIVACY_POLICY_BLOCK" in source

def test_provider_selection_cannot_silently_fall_back_to_google():
    router=read("frontend/lib/execution/router.ts")
    draft=read("frontend/app/api/gdpr-agent/draft/route.ts")
    graph=read("frontend/app/api/graph/chat/route.ts")
    assert "provider:engine.provider" in router
    assert "route.provider !== engine.provider" in router
    assert "GoogleGenAI" not in draft and "GoogleGenAI" not in graph
    assert "executeTask({taskKey:'request.drafting'" in draft
    assert "executeTask({taskKey:'graph.explanation'" in graph

def test_speech_uses_local_asr_and_summary_receives_text_only():
    registry=read("frontend/lib/execution/registry.ts")
    upload=read("frontend/lib/ingestion/bulk.ts")
    adapters=read("intelligence/execution/adapters.py")
    assert "speech.transcription','Speech transcription" in registry and "parakeet_local" in registry and "whisper_local" in registry
    assert "'speech.transcription'" in upload and "executeTask({" in upload and "input:request.input_manifest" in upload
    assert "base64" not in upload and "GoogleGenAI" not in upload
    assert "word_timestamps=True" in adapters and "ffmpeg" in adapters
    assert "transcript_artifacts" in read("frontend/lib/execution/router.ts")

def test_every_core_workflow_has_a_built_in_handler_and_preferences_are_per_workflow():
    source=read("frontend/lib/workflows/registry.ts")
    definitions=re.findall(r"workflow\('([^']+)'\s*,[^\n]+?,'([^']+)'\s*,(?:'[^']+'|null)",source)
    assert len(definitions)>=18 and all(handler for _,handler in definitions)
    assert "assertBuiltInParity" in source and "WHERE workflow_key=$1" in source
    assert "workflow_preferences" in read("database/migrations/010_task_execution_router.sql")
    assert "request.drafting" in read("frontend/lib/actions/requests/submit.ts") and "email.sending" in read("frontend/lib/actions/requests/submit.ts")

def test_n8n_registry_is_shared_and_optional():
    registry=read("frontend/lib/workflows/registry.ts")
    assert "N8N_WEBHOOK_MAPPINGS" in registry
    assert "N8N_WEBHOOK_MAPPINGS" in read("frontend/lib/n8n-webhooks.ts")
    assert "N8N_WEBHOOK_MAPPINGS" in read("frontend/app/api/settings/n8n-webhooks/route.ts")
    compose=read("docker-compose.yml")
    nextjs=re.search(r"(?ms)^  nextjs:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|^volumes:)",compose).group(1)
    assert "      n8n:" not in nextjs

def test_built_in_email_path_encrypts_server_side_and_never_returns_secrets():
    page=read("frontend/app/dashboard/settings/page.tsx")
    connector=read("frontend/lib/connectors/email.ts")
    actions=read("frontend/lib/actions/email-settings.ts")
    crypto=read("frontend/lib/secure-credentials.ts")
    assert "btoa(" not in page and "password_encrypted:" not in actions
    assert "aes-256-gcm" in crypto and "getAuthTag" in crypto and "setAuthTag" in crypto
    assert "credential_version=connector_credentials.credential_version+1" in connector
    assert "deleteEmailCredential" in connector and "sendBuiltInEmail" in connector and "monitorInboxBuiltIn" in connector
    public_query=connector.split("async function internalConnector")[0]
    assert "secret_ciphertext" not in public_query.split("getEmailConnector")[1]

def test_settings_information_architecture_and_external_audit_are_exposed():
    page=read("frontend/app/dashboard/settings/page.tsx")
    for label in ("Profile & Identity","Connectors","Processing & Models","Workflows","Data Retention","Privacy & Security","Advanced"):assert label in page
    tasks=read("frontend/components/settings/TaskRoutesSection.tsx")
    assert "Fallbacks:" in tasks and "Health" in tasks and "Advanced" in tasks
    privacy=read("frontend/components/settings/PrivacySecuritySection.tsx")
    assert "Which external models processed personal data?" in privacy
    assert "execution_location='external'" in read("frontend/app/api/settings/execution-audit/route.ts")

def test_task2_migration_extends_task1_provenance_instead_of_replacing_it():
    migration=read("database/migrations/010_task_execution_router.sql")
    assert "analysis_run_id UUID REFERENCES analysis_runs" in migration
    assert "source_artifact_ids UUID[]" in migration
    assert "source_artifact_id UUID NOT NULL REFERENCES source_artifacts" in migration
    assert "legacy" in migration.lower() and "needs_reentry" in migration
    evidence=read("intelligence/api/evidence.py")
    assert "ledger.record_source_artifact" in evidence and "ledger.create_export_snapshot" in evidence
