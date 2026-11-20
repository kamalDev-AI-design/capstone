from psit.domain.enums import ActorRole, ReportStatus
from psit.domain.errors import DomainError, NotFoundError
from psit.domain.models import Actor
from psit.domain.workflow import TransitionDecision, evaluate_direct_transition

from . import audit


class WorkflowService:
    """Deterministic transition validation. The LLM never decides validity."""

    def __init__(self, uow):
        self.uow = uow

    def transition(self, reference_id: str, target: ReportStatus, actor: Actor, request_id: str) -> dict:
        now = audit.utcnow()
        error: DomainError | None = None
        with self.uow.begin() as tx:
            report = tx.reports.get(reference_id)
            if report is None:
                raise NotFoundError(f"Report {reference_id} not found")
            try:
                decision = evaluate_direct_transition(report.status, target, ActorRole(actor.role))
            except DomainError as e:
                error = e
                audit.record(tx, actor, "STATUS_TRANSITION_REQUESTED", "REPORT", reference_id, request_id, "DENIED",
                             {"from": report.status.value, "to": target.value, "reason": e.code})
            else:
                if decision == TransitionDecision.NOOP:
                    result = {"reference_id": reference_id, "status": report.status, "changed": False,
                              "message": f"Already {report.status.value}; no change."}
                else:
                    audit.record(tx, actor, "STATUS_TRANSITION_REQUESTED", "REPORT", reference_id, request_id,
                                 "ACCEPTED", {"from": report.status.value, "to": target.value})
                    updated = tx.reports.set_status(reference_id, target.value, now)
                    tx.history.add(reference_id=reference_id, from_status=report.status.value, to_status=target.value,
                                   now=now, actor_id=actor.actor_id, actor_role=actor.role, approval_id=None,
                                   request_id=request_id)
                    audit.record(tx, actor, "STATUS_CHANGED", "REPORT", reference_id, request_id, "SUCCESS",
                                 {"from": report.status.value, "to": target.value, "record_version": updated.record_version})
                    result = {"reference_id": reference_id, "status": updated.status, "changed": True,
                              "message": f"Status changed to {target.value}."}
        if error:
            raise error
        return result
