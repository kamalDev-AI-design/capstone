from fastapi import APIRouter, Depends

from psit.contracts.agent import AgentRequest, AgentResponse
from psit.contracts.knowledge import KnowledgeAnswer

from ..deps import get_actor, get_request_id, get_svc
from .reports import _out

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/messages", response_model=AgentResponse)
def message(body: AgentRequest, svc=Depends(get_svc), actor=Depends(get_actor), rid=Depends(get_request_id)):
    r = svc.agent.run(body.message, actor, rid)
    d = r.data
    rep = (d.get("report") or d.get("created") or {}).get("report")
    return AgentResponse(
        route=r.route, outcome=r.outcome, message=r.message, tool_calls=r.tool_calls, circuit_breaker=r.circuit_breaker,
        knowledge=KnowledgeAnswer(**d["knowledge"]["answer"]) if "knowledge" in d else None,
        report=_out(rep) if rep else None,
        reports=[_out(x) for x in d["reports"]["items"]] if "reports" in d else None,
        pending_confirmation=d.get("pending_confirmation"))
