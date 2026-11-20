from dataclasses import asdict

from fastapi import APIRouter, Depends, Query

from psit.contracts.reports import ApprovalOut, ApproveIn, ClosureRequestIn

from ..deps import get_actor, get_request_id, get_svc

router = APIRouter(tags=["closure"])


def _out(a) -> ApprovalOut:
    d = asdict(a)
    d["approval_id"] = d.pop("id")
    return ApprovalOut(**d)


@router.post("/reports/{reference_id}/closure-requests", response_model=ApprovalOut, status_code=201)
def request_closure(reference_id: str, body: ClosureRequestIn, svc=Depends(get_svc), actor=Depends(get_actor),
                    rid=Depends(get_request_id)):
    return _out(svc.approvals.request_closure(reference_id, body.note, actor, rid))


@router.get("/closure-requests", response_model=list[ApprovalOut])
def list_closure_requests(status: str | None = Query(None, pattern="^(PENDING|APPROVED)$"),
                          svc=Depends(get_svc), actor=Depends(get_actor)):
    return [_out(a) for a in svc.approvals.list(status)]


@router.post("/closure-requests/{approval_id}/approve", response_model=ApprovalOut)
def approve(approval_id: int, body: ApproveIn, svc=Depends(get_svc), actor=Depends(get_actor),
            rid=Depends(get_request_id)):
    return _out(svc.approvals.approve(approval_id, body.note, actor, rid))
