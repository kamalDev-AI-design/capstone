from psit.domain.enums import ActorRole, ReportStatus
from psit.domain.errors import ConflictError, DomainError, NotFoundError, VersionConflictError
from psit.domain.models import Actor, Approval
from psit.domain.workflow import assert_can_approve, assert_can_request_closure

from . import audit


class ApprovalService:
    """Human-in-the-loop closure: request -> persisted human approval -> version check -> transition."""

    def __init__(self, uow):
        self.uow = uow

    def request_closure(self, reference_id: str, note: str | None, actor: Actor, request_id: str) -> Approval:
        now = audit.utcnow()
        error: DomainError | None = None
        approval = None
        with self.uow.begin() as tx:
            report = tx.reports.get(reference_id)
            if report is None:
                raise NotFoundError(f"Report {reference_id} not found")
            try:
                assert_can_request_closure(report.status)
            except DomainError as e:
                error = e
                audit.record(tx, actor, "CLOSURE_REQUESTED", "REPORT", reference_id, request_id, "DENIED",
                             {"status": report.status.value, "reason": e.code})
            else:
                approval = tx.approvals.pending_for_report(reference_id)  # idempotent re-request
                if approval is None:
                    approval = tx.approvals.add_pending(reference_id=reference_id, requested_by=actor.actor_id,
                                                        now=now, version=report.record_version, note=note)
                    audit.record(tx, actor, "CLOSURE_REQUESTED", "REPORT", reference_id, request_id, "SUCCESS",
                                 {"approval_id": approval.id, "report_version": report.record_version})
        if error:
            raise error
        return approval

    def approve(self, approval_id: int, note: str | None, actor: Actor, request_id: str) -> Approval:
        now = audit.utcnow()
        error: DomainError | None = None
        with self.uow.begin() as tx:
            approval = tx.approvals.get(approval_id)
            if approval is None:
                raise NotFoundError(f"Approval {approval_id} not found")
            ref = approval.reference_id
            report = tx.reports.get(ref)
            try:
                if approval.status != "PENDING":
                    raise ConflictError(f"Approval {approval_id} is already {approval.status}.")
                assert_can_approve(ActorRole(actor.role), actor.actor_id, approval.requested_by)
                if report.status != ReportStatus.IN_REVIEW or report.record_version != approval.report_version_at_request:
                    raise VersionConflictError("Report changed since the closure request; request closure again.")
            except DomainError as e:
                error = e
                audit.record(tx, actor, "CLOSURE_APPROVED", "REPORT", ref, request_id, "DENIED",
                             {"approval_id": approval_id, "reason": e.code})
            else:
                approved = tx.approvals.mark_approved(approval_id, actor.actor_id, now, note)
                audit.record(tx, actor, "CLOSURE_APPROVED", "REPORT", ref, request_id, "SUCCESS",
                             {"approval_id": approval_id, "requested_by": approval.requested_by})
                updated = tx.reports.set_status(ref, ReportStatus.CLOSED.value, now)
                tx.history.add(reference_id=ref, from_status=report.status.value, to_status="CLOSED", now=now,
                               actor_id=actor.actor_id, actor_role=actor.role, approval_id=approval_id,
                               request_id=request_id)
                audit.record(tx, actor, "STATUS_CHANGED", "REPORT", ref, request_id, "SUCCESS",
                             {"from": "IN_REVIEW", "to": "CLOSED", "approval_id": approval_id,
                              "record_version": updated.record_version})
        if error:
            raise error
        return approved

    def list(self, status: str | None):
        with self.uow.begin() as tx:
            return tx.approvals.list(status)
