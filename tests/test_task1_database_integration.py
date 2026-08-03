from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime,timezone
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from migrate import migrate
from db.postgres import PostgresClient
from evidence.ledger import EvidenceLedger
from evidence.models import AssertionCreate,AssertionStatus,DataClass,EpistemicBasis,EvidenceLocatorCreate,LocatorType
from graph.projection import GraphProjectionService
from db.neo4j import get_neo4j_client


MIGRATIONS=Path("/database/migrations") if Path("/database/migrations").exists() else Path(__file__).resolve().parents[1]/"database"/"migrations"


@pytest_asyncio.fixture
async def migrated_database():
    base=os.environ["DATABASE_URL"]
    admin=await asyncpg.connect(base)
    name=f"task1_test_{uuid.uuid4().hex[:10]}"
    await admin.execute(f'CREATE DATABASE "{name}"')
    await admin.close()
    url=base.rsplit("/",1)[0]+"/"+name
    try:
        # Simulate populated legacy tables before canonical migrations.
        connection=await asyncpg.connect(url)
        await connection.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')
        await connection.execute("CREATE TABLE requests(id uuid primary key default gen_random_uuid(),company_name text not null,company_url text,domain text,status text default 'draft',request_type text default 'access',created_at timestamptz default now())")
        await connection.execute('CREATE TABLE received_data(id uuid primary key default gen_random_uuid(),request_id uuid references requests(id),file_name text not null,graph_ingested boolean default false,date_received timestamptz default now())')
        await connection.execute("CREATE TABLE data_artifacts(id uuid primary key default gen_random_uuid(),request_id uuid references requests(id),file_id uuid references received_data(id),artifact_type text not null,title text not null,payload jsonb not null default '{}'::jsonb,confidence numeric default 1,source_span text,created_at timestamptz default now(),updated_at timestamptz default now())")
        await connection.execute("CREATE TABLE request_chat_messages(id serial primary key,request_id uuid references requests(id),role varchar(20) not null,content text not null,timestamp timestamptz default now())")
        await connection.execute("CREATE TABLE n8n_webhooks(id serial primary key,webhook_name varchar(100) unique not null,webhook_url text not null,is_active boolean default true,created_at timestamptz default now(),updated_at timestamptz default now())")
        await connection.execute("CREATE TABLE user_profiles(id serial primary key,username varchar(255) unique not null,email varchar(255),password_hash text,profile_picture_url text,created_at timestamptz default now(),updated_at timestamptz default now())")
        request_id=await connection.fetchval("INSERT INTO requests(company_name) VALUES('Synthetic Controller') RETURNING id")
        file_id=await connection.fetchval("INSERT INTO received_data(request_id,file_name) VALUES($1,'synthetic.json') RETURNING id",request_id)
        await connection.execute("INSERT INTO data_artifacts(request_id,file_id,artifact_type,title,payload) VALUES($1,$2,'metric','Legacy fixture','{\"legacy\":true}')",request_id,file_id)
        await connection.execute("INSERT INTO request_chat_messages(request_id,role,content) VALUES($1,'user','synthetic message')",request_id)
        await connection.execute("INSERT INTO n8n_webhooks(webhook_name,webhook_url) VALUES('kgIngestor','http://example.invalid')")
        await connection.execute("INSERT INTO user_profiles(username,email,password_hash,profile_picture_url) VALUES('legacy-user','legacy@example.invalid','synthetic-hash','/synthetic.png')")
        await connection.close()
        await migrate(url,MIGRATIONS)
        yield url,request_id,file_id
    finally:
        admin=await asyncpg.connect(base)
        await admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=$1",name)
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
        await admin.close()


@pytest.mark.asyncio
async def test_migrations_are_idempotent_and_preserve_legacy_rows(migrated_database):
    url,request_id,file_id=migrated_database
    await migrate(url,MIGRATIONS)
    connection=await asyncpg.connect(url)
    assert await connection.fetchval("SELECT count(*) FROM requests WHERE id=$1",request_id)==1
    assert await connection.fetchval("SELECT count(*) FROM received_data WHERE id=$1",file_id)==1
    assert await connection.fetchval("SELECT count(*) FROM data_artifacts WHERE file_id=$1 AND title='Legacy fixture' AND analysis_run_id IS NOT NULL AND artifact_version=1",file_id)==1
    assert await connection.fetchval("SELECT count(*) FROM request_chat_messages WHERE request_id=$1 AND sender='user' AND message='synthetic message'",request_id)==1
    assert await connection.fetchval("SELECT count(*) FROM n8n_webhooks WHERE webhook_name='kgIngestor' AND webhook_url='http://example.invalid'")==1
    assert await connection.fetchval("SELECT count(*) FROM user_profiles WHERE username='legacy-user' AND legacy_integer_id=1 AND profile_picture_url='/synthetic.png'")==1
    assert await connection.fetchval("SELECT count(*) FROM gdpr_schema_migrations")>=11
    await connection.close()


@pytest.mark.asyncio
async def test_blob_dedup_preserves_two_source_occurrences(migrated_database):
    url,request_id,_=migrated_database; client=PostgresClient(url); ledger=EvidenceLedger(client)
    run=await ledger.create_analysis_run("fixture","1",request_id=request_id)
    one=await ledger.create_export_snapshot(run,"dsar_response",request_id=request_id,controller_key="synthetic")
    two=await ledger.create_export_snapshot(run,"dsar_response",request_id=request_id,controller_key="synthetic")
    blob1,artifact1=await ledger.record_source_artifact(one,b"same bytes",storage_uri="fixture://one",original_path="one/a.txt",file_name="a.txt")
    blob2,artifact2=await ledger.record_source_artifact(two,b"same bytes",storage_uri="fixture://two",original_path="two/a.txt",file_name="a.txt")
    assert blob1==blob2 and artifact1!=artifact2
    rows=await client.execute("SELECT (SELECT count(*) FROM content_blobs) blobs,(SELECT count(*) FROM source_artifacts) artifacts")
    assert rows[0]["blobs"]==1 and rows[0]["artifacts"]==2
    await client.close()


@pytest.mark.asyncio
async def test_task2_routes_audit_and_per_workflow_preferences_extend_task1(migrated_database):
    url,request_id,_=migrated_database
    connection=await asyncpg.connect(url)
    tables={row["tablename"] for row in await connection.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
    assert {"task_routes","processing_settings","workflow_preferences","execution_records","connector_credentials","transcript_artifacts","outbound_messages","inbox_checkpoints"} <= tables
    await connection.execute("UPDATE workflow_preferences SET execution_mode='n8n',fallback_order='[\"n8n\"]' WHERE workflow_key='request.drafting'")
    await connection.execute("UPDATE workflow_preferences SET execution_mode='built_in',fallback_order='[\"built_in\"]' WHERE workflow_key='email.sending'")
    rows=await connection.fetch("SELECT workflow_key,execution_mode FROM workflow_preferences WHERE workflow_key IN ('request.drafting','email.sending') ORDER BY workflow_key")
    assert {row["workflow_key"]:row["execution_mode"] for row in rows}=={"email.sending":"built_in","request.drafting":"n8n"}
    run_id=await connection.fetchval("INSERT INTO analysis_runs(run_type,status,pipeline_version) VALUES('task2-test','running','task2-router-v1') RETURNING id")
    record_id=await connection.fetchval("INSERT INTO execution_records(analysis_run_id,task_key,engine_id,provider,model,execution_location,status) VALUES($1,'request.drafting','openai_generation','openai','fixture','external','completed') RETURNING id",run_id)
    assert await connection.fetchval("SELECT analysis_run_id=$2 AND execution_location='external' FROM execution_records WHERE id=$1",record_id,run_id)
    await connection.close()


async def _fixture_evidence(ledger,request_id):
    run=await ledger.create_analysis_run("fixture","1",request_id=request_id)
    snap=await ledger.create_export_snapshot(run,"manual_import",request_id=request_id)
    content=b"exact source evidence"
    _,artifact=await ledger.record_source_artifact(snap,content,storage_uri="fixture://source",original_path="source.txt",file_name="source.txt")
    locator=await ledger.create_locator(EvidenceLocatorCreate(artifact_id=artifact,locator_type=LocatorType.TEXT_SPAN,locator={"byte_start":0,"byte_end":len(content)},expected_text=content.decode()),content)
    return run,locator


def _assertion(run,**overrides):
    values=dict(subject_type="Subject",subject_ref="synthetic-subject",predicate="HAS_OBSERVED_SIGNAL",object_type="literal",object_value={"value":"synthetic"},assertion_type="hypothesis",data_class=DataClass.INFERRED,status=AssertionStatus.CANDIDATE,epistemic_basis=EpistemicBasis.MODEL_HYPOTHESIS,confidence=.8,ingested_at=datetime.now(timezone.utc),derivation_method="fixture",derivation_version="1",analysis_run_id=run)
    values.update(overrides); return AssertionCreate(**values)


@pytest.mark.asyncio
async def test_assertion_lifecycle_provenance_immutability_and_supersession(migrated_database):
    url,request_id,_=migrated_database; client=PostgresClient(url); ledger=EvidenceLedger(client); run,locator=await _fixture_evidence(ledger,request_id)
    candidate=await ledger.create_assertion(_assertion(run))
    with pytest.raises(asyncpg.PostgresError): await ledger.transition(candidate,AssertionStatus.ACCEPTED)
    grounded=await ledger.create_assertion(_assertion(run,evidence_locator_ids=(locator,)))
    await ledger.transition(grounded,AssertionStatus.ACCEPTED)
    with pytest.raises(asyncpg.PostgresError): await client.execute("UPDATE assertions SET predicate='CHANGED' WHERE id=$1",grounded)
    replacement=await ledger.supersede(grounded,_assertion(run,status=AssertionStatus.ACCEPTED,evidence_locator_ids=(locator,),object_value={"value":"replacement"}))
    rows=await client.execute("SELECT id,status,supersedes_assertion_id FROM assertions WHERE id=ANY($1::uuid[]) ORDER BY system_asserted_at",[grounded,replacement])
    assert {row["status"] for row in rows}=={"superseded","accepted"}
    assert any(row["supersedes_assertion_id"]==grounded for row in rows)
    await client.close()


@pytest.mark.asyncio
async def test_data_artifact_versions_are_retained_and_latest_view_is_current(migrated_database):
    url,request_id,file_id=migrated_database; connection=await asyncpg.connect(url)
    run1=await connection.fetchval("INSERT INTO analysis_runs(run_type,request_id,status,pipeline_version) VALUES('artifact',$1,'completed','1') RETURNING id",request_id)
    run2=await connection.fetchval("INSERT INTO analysis_runs(run_type,request_id,status,pipeline_version) VALUES('artifact',$1,'completed','2') RETURNING id",request_id)
    first=await connection.fetchval("INSERT INTO data_artifacts(request_id,file_id,artifact_type,title,payload,analysis_run_id,artifact_version,derivation_method,derivation_version) VALUES($1,$2,'metric','Fixture','{\"v\":1}',$3,1,'fixture','1') RETURNING id",request_id,file_id,run1)
    second=await connection.fetchval("INSERT INTO data_artifacts(request_id,file_id,artifact_type,title,payload,analysis_run_id,artifact_version,supersedes_artifact_id,derivation_method,derivation_version) VALUES($1,$2,'metric','Fixture','{\"v\":2}',$3,2,$4,'fixture','2') RETURNING id",request_id,file_id,run2,first)
    assert await connection.fetchval("SELECT count(*) FROM data_artifacts WHERE file_id=$1 AND title='Fixture'",file_id)==2
    assert await connection.fetchval("SELECT id FROM current_data_artifacts WHERE file_id=$1 AND title='Fixture'",file_id)==second
    with pytest.raises(asyncpg.PostgresError): await connection.execute("DELETE FROM data_artifacts WHERE id=$1",first)
    await connection.close()


@pytest.mark.asyncio
async def test_speculation_excluded_and_projection_idempotent_with_stable_ids(migrated_database):
    url,request_id,_=migrated_database; client=PostgresClient(url); ledger=EvidenceLedger(client)
    profile_id=(await client.execute("SELECT profile_id FROM requests WHERE id=$1",request_id))[0]["profile_id"]
    run=await ledger.create_analysis_run("fixture","1",request_id=request_id,profile_id=profile_id)
    candidate=await ledger.create_assertion(_assertion(run))
    service=GraphProjectionService(client,get_neo4j_client())
    with pytest.raises(ValueError): await service.project_assertion(candidate,profile_id)
    human=await ledger.create_assertion(_assertion(run,status=AssertionStatus.ACCEPTED,epistemic_basis=EpistemicBasis.HUMAN_CONFIRMED,data_class=DataClass.DECLARED,assertion_type="relationship",object_type="node_ref",object_ref="DataPoint:task1-fixture",object_value=None))
    first=await service.project_assertion(human,profile_id); second=await service.project_assertion(human,profile_id)
    assert first["subject_id"]==second["subject_id"] and first["object_id"]==second["object_id"]
    rows=await service.neo4j.query("MATCH (:GraphNode)-[r {assertion_id:$id}]->(:GraphNode) RETURN count(r) AS count",{"id":str(human)})
    assert rows[0]["count"]==1
    await service.neo4j.execute("MATCH (n:GraphNode) WHERE n.node_id IN $ids DETACH DELETE n",{"ids":[first["subject_id"],first["object_id"]]})
    await client.close()


@pytest.mark.asyncio
async def test_legacy_graph_backfill_stable_across_reloads(migrated_database):
    neo=get_neo4j_client(); marker=uuid.uuid4().hex
    await neo.execute("CREATE (:Task1LegacyFixture {name:$name})",{"name":marker})
    service=GraphProjectionService(PostgresClient(migrated_database[0]),neo)
    await service.backfill_legacy_node_ids(); first=(await neo.query("MATCH (n:Task1LegacyFixture {name:$name}) RETURN n.node_id AS id",{"name":marker}))[0]["id"]
    await service.backfill_legacy_node_ids(); second=(await neo.query("MATCH (n:Task1LegacyFixture {name:$name}) RETURN n.node_id AS id",{"name":marker}))[0]["id"]
    assert first==second
    await neo.execute("MATCH (n:Task1LegacyFixture {name:$name}) DETACH DELETE n",{"name":marker})


@pytest.mark.asyncio
async def test_subject_and_controller_profile_cannot_be_merged(migrated_database):
    url,request_id,_=migrated_database; client=PostgresClient(url); ledger=EvidenceLedger(client); neo=get_neo4j_client()
    profile_id=(await client.execute("SELECT profile_id FROM requests WHERE id=$1",request_id))[0]["profile_id"]
    run=await ledger.create_analysis_run("fixture","1",request_id=request_id,profile_id=profile_id)
    approval=await ledger.create_assertion(_assertion(run,status=AssertionStatus.ACCEPTED,epistemic_basis=EpistemicBasis.HUMAN_CONFIRMED,data_class=DataClass.DECLARED,assertion_type="relationship",object_type="node_ref",object_ref="Claim:merge-test",object_value=None))
    subject=str(uuid.uuid4()); controller=str(uuid.uuid4()); helper=str(uuid.uuid4())
    await neo.execute("CREATE (s:GraphNode:Subject {node_id:$subject}),(c:GraphNode:ControllerProfile {node_id:$controller}),(h:GraphNode:Claim {node_id:$helper}), (s)-[:FIXTURE {profile_id:$profile_id}]->(h), (c)-[:FIXTURE {profile_id:$profile_id}]->(h)",{"subject":subject,"controller":controller,"helper":helper,"profile_id":str(profile_id)})
    with pytest.raises(ValueError,match="different ontology types"):
        await GraphProjectionService(client,neo).merge_nodes(approval,subject,controller,profile_id)
    await neo.execute("MATCH (n:GraphNode) WHERE n.node_id IN $ids DETACH DELETE n",{"ids":[subject,controller,helper]})
    await client.close()
