from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, Query

from psit.contracts.reports import (
    ReportCreate, ReportDetail, ReportList, ReportOut, ReportStats, StatusHistoryOut,
    TransitionRequest, TransitionResult,
)
from psit.domain.enums import IntakeChannel, ReportStatus, ReportType

from ..deps import get_actor, get_request_id, get_svc

router = APIRouter(prefix="/reports", tags=["reports"])


def _out(r) -> ReportOut:
    d = asdict(r)
    d.pop("id")
    return ReportOut(**d)


@router.post("", response_model=ReportOut, status_code=201)
def create_report(body: ReportCreate, svc=Depends(get_svc), actor=Depends(get_actor), rid=Depends(get_request_id)):
    return _out(svc.intake.create(body.model_dump(mode="python"), actor, rid))


@router.get("", response_model=ReportList)
def list_reports(
    status: ReportStatus | None = None, report_type: ReportType | None = None,
    intake_channel: IntakeChannel | None = None, product: str | None = Query(None, max_length=100),
    date_from: date | None = None, date_to: date | None = None,
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    svc=Depends(get_svc), actor=Depends(get_actor),
):
    items, total = svc.intake.list(
        status=status.value if status else None, report_type=report_type.value if report_type else None,
        channel=intake_channel.value if intake_channel else None, product=product,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset)
    return ReportList(items=[_out(r) for r in items], total=total)


@router.get("/stats", response_model=ReportStats)
def stats(svc=Depends(get_svc), actor=Depends(get_actor)):
    return ReportStats(**svc.intake.stats())


@router.get("/{reference_id}", response_model=ReportDetail)
def get_report(reference_id: str, svc=Depends(get_svc), actor=Depends(get_actor)):
    r, history, pending_id = svc.intake.get(reference_id)
    hist = [StatusHistoryOut(**{k: v for k, v in asdict(h).items() if k not in ("id", "reference_id")}) for h in history]
    return ReportDetail(**_out(r).model_dump(), history=hist, pending_approval_id=pending_id)


@router.post("/{reference_id}/transitions", response_model=TransitionResult)
def transition(reference_id: str, body: TransitionRequest, svc=Depends(get_svc), actor=Depends(get_actor),
               rid=Depends(get_request_id)):
    return TransitionResult(**svc.workflow.transition(reference_id, body.target_status, actor, rid))
