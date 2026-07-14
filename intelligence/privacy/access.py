"""Evidence-backed Institutional Access; identifier overlap is never access."""
from __future__ import annotations
from dataclasses import dataclass
import json
from uuid import NAMESPACE_URL,UUID,uuid5
from db.postgres import PostgresClient,get_postgres_client
from .contracts import (
 Dataset,GraphEpistemicState,InstitutionalAccessEdge,
 InstitutionalAccessType,InstitutionalStorageClass,
)

@dataclass(frozen=True,slots=True)
class AccessEvidence:
    central_storage_assertion_ids:tuple[UUID,...]=()
    mutual_access_assertion_ids:tuple[UUID,...]=()
    independent_storage_assertion_ids:tuple[UUID,...]=()
    shared_identifier_assertion_ids:tuple[UUID,...]=()

def classify_storage(evidence:AccessEvidence)->InstitutionalStorageClass:
    if evidence.central_storage_assertion_ids:return InstitutionalStorageClass.CENTRALLY_STORED
    if evidence.mutual_access_assertion_ids:return InstitutionalStorageClass.FEDERATED_MUTUALLY_ACCESSIBLE
    if evidence.independent_storage_assertion_ids and evidence.shared_identifier_assertion_ids:
        return InstitutionalStorageClass.INDEPENDENTLY_STORED_LINKABLE
    return InstitutionalStorageClass.UNKNOWN

def create_access_edge(*,source_ref:str,target_ref:str,access_type:InstitutionalAccessType,
                       assertion_id:UUID|None,epistemic_state:GraphEpistemicState,
                       identifier_overlap_only:bool=False,jurisdiction:str|None=None,
                       legal_instrument:str|None=None,requirements:tuple[str,...]=(),
                       transparency:str|None=None)->InstitutionalAccessEdge:
    if identifier_overlap_only:
        raise ValueError("identifier overlap establishes linkability, not organisational access")
    if assertion_id is None: raise ValueError("Institutional Access edges require a supporting Assertion")
    if access_type is InstitutionalAccessType.HAS_LEGAL_GATEWAY_TO and not legal_instrument:
        raise ValueError("a legal gateway requires an evidenced legal instrument")
    stable=f"{source_ref}:{access_type.value}:{target_ref}:{assertion_id}"
    return InstitutionalAccessEdge(id=uuid5(NAMESPACE_URL,stable),source_ref=source_ref,target_ref=target_ref,
        access_type=access_type,epistemic_state=epistemic_state,jurisdiction=jurisdiction,
        legal_instrument=legal_instrument,requirements=requirements,transparency=transparency,
        assertion_id=assertion_id)

class AccessRepository:
    def __init__(self,postgres:PostgresClient|None=None):self.postgres=postgres or get_postgres_client()
    async def save_dataset(self,profile_id:UUID,value:Dataset)->None:
        await self.postgres.execute("""INSERT INTO privacy_datasets(id,profile_id,dataset_key,label,storage_class)
          VALUES($1,$2,$3,$4,$5) ON CONFLICT(profile_id,dataset_key) DO NOTHING""",
          value.id,profile_id,value.dataset_key,value.label,value.storage_class.value)
    async def save_edge(self,profile_id:UUID,value:InstitutionalAccessEdge)->None:
        await self.postgres.execute("""INSERT INTO institutional_access_edges(id,profile_id,source_ref,target_ref,
          access_type,epistemic_state,jurisdiction,legal_instrument,requirements,transparency,assertion_id)
          VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11)
          ON CONFLICT(profile_id,source_ref,target_ref,access_type,assertion_id) DO NOTHING""",
          value.id,profile_id,value.source_ref,value.target_ref,value.access_type.value,
          value.epistemic_state.value,value.jurisdiction,value.legal_instrument,
          json.dumps(value.requirements),value.transparency,value.assertion_id)
