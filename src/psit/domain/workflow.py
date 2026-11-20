"""Deterministic workflow rules. No LLM involvement, no I/O."""
from enum import StrEnum

from .enums import ActorRole, ReportStatus
from .errors import ApprovalRequiredError, ForbiddenError, InvalidTransitionError


class TransitionDecision(StrEnum):
    NOOP = "NOOP"
    ALLOWED = "ALLOWED"


# Direct (non-approval) transitions.
_DIRECT = {(ReportStatus.NEW, ReportStatus.IN_REVIEW)}
_ALL_ROLES = {ActorRole.INTAKE_OPERATOR, ActorRole.REVIEWER, ActorRole.AGENT}


def evaluate_direct_transition(current: ReportStatus, target: ReportStatus, role: ActorRole) -> TransitionDecision:
    if role not in _ALL_ROLES:
        raise ForbiddenError("Unknown role")
    if current == target:
        return TransitionDecision.NOOP
    if target == ReportStatus.CLOSED:
        if current == ReportStatus.IN_REVIEW:
            raise ApprovalRequiredError(
                "Closing requires a human-approved closure request (POST /reports/{id}/closure-requests)."
            )
        raise InvalidTransitionError(f"Transition {current} -> {target} is prohibited.")
    if (current, target) in _DIRECT:
        return TransitionDecision.ALLOWED
    raise InvalidTransitionError(f"Transition {current} -> {target} is prohibited.")


def assert_can_request_closure(current: ReportStatus) -> None:
    if current != ReportStatus.IN_REVIEW:
        raise InvalidTransitionError(
            f"Closure can only be requested for IN_REVIEW reports (current: {current})."
        )


def assert_can_approve(role: ActorRole, actor_id: str, requested_by: str) -> None:
    if role != ActorRole.REVIEWER:
        raise ForbiddenError("Only a human REVIEWER may approve closure; AI/agent and operators cannot.")
    if actor_id == requested_by:
        raise ForbiddenError("The approver must differ from the requester (four-eyes principle).")
