"""Approved agent capabilities. Each tool has a strict typed contract; mutating tools check authorization.
The model can only *propose* a call; arguments are validated here and services enforce the invariants."""
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import Field, TypeAdapter

from psit.contracts.reports import ReportCreate, StrictModel
from psit.domain.enums import ActorRole, ReportStatus, ReportType
from psit.domain.errors import ForbiddenError, NotFoundError
from psit.domain.models import Actor


class GetReportCmd(StrictModel):
    reference_id: str = Field(pattern=r"^REF-\d{4}-\d{4}$")


class ListReportsCmd(StrictModel):
    status: ReportStatus | None = None
    report_type: ReportType | None = None
    limit: int = Field(default=10, ge=1, le=50)


class UpdateStatusCmd(StrictModel):
    reference_id: str = Field(pattern=r"^REF-\d{4}-\d{4}$")
    target_status: ReportStatus


class RequestClosureCmd(StrictModel):
    reference_id: str = Field(pattern=r"^REF-\d{4}-\d{4}$")
    note: str | None = Field(default=None, max_length=500)


class ApproveClosureCmd(StrictModel):
    approval_id: int = Field(ge=1)


class SearchCmd(StrictModel):
    query: str = Field(min_length=2, max_length=500)
    status: ReportStatus | None = None


class AuditHistoryCmd(StrictModel):
    entity_id: str = Field(min_length=3, max_length=80)


class NoArgs(StrictModel):
    pass


@dataclass
class ToolContext:
    actor: Actor
    request_id: str
    svc: Any


@dataclass
class Tool:
    name: str
    adapter: TypeAdapter
    fn: Callable[[ToolContext, Any], dict]
    mutating: bool = False


HUMAN_ROLES = {ActorRole.INTAKE_OPERATOR.value, ActorRole.REVIEWER.value}


def _create_report(ctx: ToolContext, cmd) -> dict:
    if ctx.actor.role not in HUMAN_ROLES:
        raise ForbiddenError("Only a human intake operator or reviewer may create reports through the assistant.")
    return {"kind": "created", "report": ctx.svc.intake.create(cmd.model_dump(mode="python"), ctx.actor, ctx.request_id)}


def _get_report(ctx, cmd) -> dict:
    r, hist, pending = ctx.svc.intake.get(cmd.reference_id)
    return {"kind": "report", "report": r, "history": hist, "pending_approval_id": pending}


def _list_reports(ctx, cmd) -> dict:
    items, total = ctx.svc.intake.list(status=cmd.status.value if cmd.status else None,
                                       report_type=cmd.report_type.value if cmd.report_type else None, limit=cmd.limit)
    return {"kind": "reports", "items": items, "total": total}


def _update_status(ctx, cmd) -> dict:
    return {"kind": "transition", **ctx.svc.workflow.transition(cmd.reference_id, cmd.target_status, ctx.actor, ctx.request_id)}


def _request_closure(ctx, cmd) -> dict:
    return {"kind": "closure_requested", "approval": ctx.svc.approvals.request_closure(cmd.reference_id, cmd.note, ctx.actor, ctx.request_id)}


def _approve_closure(ctx, cmd) -> dict:
    """The agent NEVER approves. It only validates the request and hands over to a human confirmation step."""
    if ctx.actor.role != ActorRole.REVIEWER.value:
        raise ForbiddenError("Only a human REVIEWER may approve closure; AI/agent and operators cannot.")
    a = next((x for x in ctx.svc.approvals.list("PENDING") if x.id == cmd.approval_id), None)
    if a is None:
        raise NotFoundError(f"No pending approval #{cmd.approval_id}.")
    return {"kind": "needs_confirmation", "approval": a}


def _knowledge(source_types):
    def run(ctx, cmd) -> dict:
        req = {"query": cmd.query, "source_types": source_types, "status": cmd.status.value if cmd.status else None}
        return {"kind": "knowledge", "answer": ctx.svc.knowledge.search(req, ctx.actor, ctx.request_id)}
    return run


def _audit_history(ctx, cmd) -> dict:
    items, total = ctx.svc.audit.list(cmd.entity_id, 15, 0)
    return {"kind": "audit", "events": items, "total": total}


def _verify(ctx, cmd) -> dict:
    return {"kind": "audit_verify", **ctx.svc.audit.verify(ctx.actor, ctx.request_id)}


def build_registry() -> dict[str, Tool]:
    t = [
        Tool("create_report", TypeAdapter(ReportCreate), _create_report, mutating=True),
        Tool("get_report", TypeAdapter(GetReportCmd), _get_report),
        Tool("list_reports", TypeAdapter(ListReportsCmd), _list_reports),
        Tool("update_report_status", TypeAdapter(UpdateStatusCmd), _update_status, mutating=True),
        Tool("request_closure", TypeAdapter(RequestClosureCmd), _request_closure, mutating=True),
        Tool("approve_closure", TypeAdapter(ApproveClosureCmd), _approve_closure, mutating=True),
        Tool("search_sops", TypeAdapter(SearchCmd), _knowledge(["SOP"])),
        Tool("search_historical_reports", TypeAdapter(SearchCmd), _knowledge(["HISTORICAL_REPORT"])),
        Tool("run_hybrid_rag", TypeAdapter(SearchCmd), _knowledge(None)),
        Tool("get_audit_history", TypeAdapter(AuditHistoryCmd), _audit_history),
        Tool("verify_audit_chain", TypeAdapter(NoArgs), _verify),
    ]
    return {x.name: x for x in t}
