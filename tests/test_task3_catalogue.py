import asyncio

from ingestion.catalogue import record_ingestion_status,sync_format_support_registry
from ingestion.registry import FORMAT_SUPPORT_REGISTRY


class FakePostgres:
    def __init__(self): self.calls=[]
    async def execute(self,query,*args): self.calls.append((query,args)); return []


def test_support_registry_sync_is_code_owned_and_complete():
    postgres=FakePostgres(); count=asyncio.run(sync_format_support_registry(postgres))
    assert count==len(FORMAT_SUPPORT_REGISTRY)==len(postgres.calls)
    assert {call[1][0] for call in postgres.calls}=={record.format_key for record in FORMAT_SUPPORT_REGISTRY}


def test_ingestion_status_keeps_unsupported_visible():
    postgres=FakePostgres(); asyncio.run(record_ingestion_status(postgres,artifact_id="a",analysis_run_id="r",status="unsupported",support_status="UNSUPPORTED",detected_format="unknown_binary",next_action="review",warnings=("no parser",)))
    args=postgres.calls[0][1]
    assert args[2]=="unsupported" and args[3]=="UNSUPPORTED" and args[8]=="review"
