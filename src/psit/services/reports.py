from datetime import date

from psit.domain.errors import NotFoundError
from psit.domain.models import Actor, Report

from . import audit


class IntakeService:
    def __init__(self, uow):
        self.uow = uow

    def create(self, data: dict, actor: Actor, request_id: str) -> Report:
        now = audit.utcnow()
        with self.uow.begin() as tx:
            ref = tx.reports.next_reference_id(now.year)
            report = tx.reports.add(reference_id=ref, data=data, created_by=actor.actor_id, now=now)
            tx.history.add(reference_id=ref, from_status=None, to_status="NEW", now=now, actor_id=actor.actor_id,
                           actor_role=actor.role, approval_id=None, request_id=request_id)
            audit.record(tx, actor, "REPORT_CREATED", "REPORT", ref, request_id, "SUCCESS",
                         {"report_type": data["report_type"], "intake_channel": data["intake_channel"]})
        return report

    def get(self, reference_id: str) -> tuple[Report, list, int | None]:
        with self.uow.begin() as tx:
            r = tx.reports.get(reference_id)
            if r is None:
                raise NotFoundError(f"Report {reference_id} not found")
            pending = tx.approvals.pending_for_report(reference_id)
            return r, tx.history.for_report(reference_id), (pending.id if pending else None)

    def list(self, *, status=None, report_type=None, channel=None, product=None,
             date_from: date | None = None, date_to: date | None = None, limit=50, offset=0):
        with self.uow.begin() as tx:
            return tx.reports.search(status=status, report_type=report_type, channel=channel, product=product,
                                     date_from=date_from, date_to=date_to, limit=limit, offset=offset)

    def stats(self) -> dict:
        with self.uow.begin() as tx:
            return tx.reports.stats()
