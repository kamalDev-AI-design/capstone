import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, Query

from psit.contracts.reports import AuditEventList, AuditEventOut, AuditVerifyResult

from ..deps import get_actor, get_request_id, get_svc

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=AuditEventList)
def events(entity_id: str | None = Query(None, max_length=80), limit: int = Query(100, ge=1, le=500),
           offset: int = Query(0, ge=0), svc=Depends(get_svc), actor=Depends(get_actor)):
    items, total = svc.audit.list(entity_id, limit, offset)
    out = []
    for e in items:
        d = asdict(e)
        d.pop("id")
        d["details"] = json.loads(d["details"])
        out.append(AuditEventOut(**d))
    return AuditEventList(items=out, total=total)


@router.get("/verify", response_model=AuditVerifyResult)
def verify(svc=Depends(get_svc), actor=Depends(get_actor), rid=Depends(get_request_id)):
    return AuditVerifyResult(**svc.audit.verify(actor, rid))
