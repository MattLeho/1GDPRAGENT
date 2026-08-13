from __future__ import annotations

import re
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
SOURCE_ROOTS=(ROOT/'frontend'/'app',ROOT/'frontend'/'lib',ROOT/'intelligence')
ALLOWED_REQUEST_SQL={
    (ROOT/'frontend/lib/requests/repository.ts').resolve(),
    (ROOT/'intelligence/request_domain/repository.py').resolve(),
}


def _sources():
    for root in SOURCE_ROOTS:
        for path in root.rglob('*'):
            if path.suffix in {'.ts','.tsx','.py'} and 'node_modules' not in path.parts:
                yield path,path.read_text(encoding='utf-8')


def test_canonical_code_does_not_depend_on_access_requests():
    offenders=[str(path.relative_to(ROOT)) for path,text in _sources() if 'access_requests' in text]
    assert offenders==[]


def test_all_request_domain_sql_is_confined_to_canonical_repositories():
    tables='requests|request_events|request_details|request_chat_messages|messages|received_data|workflow_logs|request_threads|data_artifacts|outbound_messages|email_transport_drafts'
    pattern=re.compile(rf'\b(?:FROM|JOIN|UPDATE|INTO|DELETE\s+FROM)\s+(?:{tables})\b',re.I)
    offenders=[str(path.relative_to(ROOT)) for path,text in _sources()
               if path.resolve() not in ALLOWED_REQUEST_SQL and pattern.search(text)]
    assert offenders==[]


def test_status_writes_and_deadline_antipatterns_are_absent():
    forbidden={
        'direct request status update':re.compile(r'UPDATE\s+requests\s+SET[^;]{0,500}\bstatus\s*=',re.I|re.S),
        'fixed 30 day deadline':re.compile(r"INTERVAL\s*'30 days'|setDate\([^\n]{0,100}\+\s*30",re.I),
        'operational response duration':re.compile(r'updated_at\s*-\s*created_at|updated_at\s+ELSE\s+NULL',re.I),
    }
    offenders=[]
    for path,text in _sources():
        if path.resolve() in ALLOWED_REQUEST_SQL: continue
        for label,pattern in forbidden.items():
            if pattern.search(text):offenders.append(f'{path.relative_to(ROOT)}: {label}')
    assert offenders==[]


def test_migration_defines_evidence_transition_and_read_only_compatibility():
    migration=(ROOT/'database/migrations/031_r2_request_lifecycle.sql').read_text(encoding='utf-8')
    for token in ('transition_request_state','previous_state','next_state','evidence_reference',
                  'request_events_append_only','access_requests_read_only','requests_set_updated_at'):
        assert token in migration


def test_legacy_n8n_request_sql_is_archived_and_not_selectable():
    import json
    for path in (ROOT/'agents').rglob('*.json'):
        document=json.loads(path.read_text(encoding='utf-8'))
        assert document.get('active') is False, f'{path.name} must remain archived'
    registry=(ROOT/'frontend/lib/workflows/registry.ts').read_text(encoding='utf-8')
    for retired in ("{id:'draftRequest'", "{id:'sendEmail'", "{id:'parseResponse'", "{id:'enhancedRag'"):
        assert retired not in registry
