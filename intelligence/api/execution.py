import subprocess
from typing import Any
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from execution.adapters import engine_health,invoke_engine
from api.security import require_internal_request

router=APIRouter(prefix="/execution",tags=["Task Execution"],dependencies=[Depends(require_internal_request)])
class InvokeBody(BaseModel):
    engine_id:str;task_key:str;input:Any;model:str|None=None;configuration:dict[str,Any]=Field(default_factory=dict)

@router.get("/engines/{engine_id}/health")
async def health(engine_id:str):return engine_health(engine_id)

@router.post("/invoke")
async def invoke(body:InvokeBody):
    try:return invoke_engine(body.engine_id,body.task_key,body.input,body.model,body.configuration)
    except (ValueError,RuntimeError) as exc:raise HTTPException(status_code=422,detail={"code":"LOCAL_ENGINE_ERROR","engine_id":body.engine_id,"message":str(exc)}) from exc
    except subprocess.TimeoutExpired as exc:raise HTTPException(status_code=504,detail={"code":"LOCAL_ENGINE_TIMEOUT","engine_id":body.engine_id,"message":str(exc)}) from exc
