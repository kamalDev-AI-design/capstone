from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from psit.domain.enums import ReportStatus
from psit.domain.errors import NotFoundError
from psit.domain.models import Approval, AuditEvent, Report, StatusHistoryEntry

from .orm import (
    AdverseEventRow, ApprovalRow, AuditRow, HistoryRow, ReferenceCounter, ReportRow,
)

GENESIS_HASH = "0" * 64


def _report(r: ReportRow, ext: AdverseEventRow | None) -> Report:
    return Report(
        id=r.id, reference_id=r.reference_id, report_type=r.report_type, status=ReportStatus(r.status),
        product_name=r.product_name, lot_number=r.lot_number, date_received=r.date_received,
        reporter_type=r.reporter_type, intake_channel=r.intake_channel, description=r.description,
        event_description=ext.event_description if ext else None,
        event_onset_date=ext.event_onset_date if ext else None,
        synthetic=r.synthetic, record_version=r.record_version, created_by=r.created_by,
        created_at=r.created_at, updated_at=r.updated_at,
    )


class SqlReportRepository:
    def __init__(self, s: Session):
        self.s = s

    def _row(self, reference_id: str) -> ReportRow | None:
        return self.s.scalar(select(ReportRow).where(ReportRow.reference_id == reference_id))

    def _ext(self, report_id: int) -> AdverseEventRow | None:
        return self.s.get(AdverseEventRow, report_id)

    def next_reference_id(self, year: int) -> str:
        # Runs inside BEGIN IMMEDIATE, so increments are serialized; UNIQUE(reference_id) is the backstop.
        counter = self.s.get(ReferenceCounter, year)
        if counter is None:
            counter = ReferenceCounter(year=year, next_val=2)
            self.s.add(counter)
            seq = 1
        else:
            seq = counter.next_val
            counter.next_val = seq + 1
        self.s.flush()
        return f"REF-{year}-{seq:04d}"

    def add(self, *, reference_id: str, data: dict, created_by: str, now: datetime) -> Report:
        row = ReportRow(
            reference_id=reference_id, report_type=data["report_type"], status=ReportStatus.NEW.value,
            product_name=data["product_name"], lot_number=data["lot_number"], date_received=data["date_received"],
            reporter_type=data["reporter_type"], intake_channel=data["intake_channel"], description=data["description"],
            synthetic=True, record_version=1, created_by=created_by, created_at=now, updated_at=now,
        )
        self.s.add(row)
        self.s.flush()
        ext = None
        if data.get("event_description") is not None:
            ext = AdverseEventRow(report_id=row.id, event_description=data["event_description"],
                                  event_onset_date=data["event_onset_date"])
            self.s.add(ext)
            self.s.flush()
        return _report(row, ext)

    def get(self, reference_id: str) -> Report | None:
        r = self._row(reference_id)
        return _report(r, self._ext(r.id)) if r else None

    def search(self, *, status, report_type, channel, product, date_from, date_to, limit, offset):
        q = select(ReportRow)
        if status:
            q = q.where(ReportRow.status == status)
        if report_type:
            q = q.where(ReportRow.report_type == report_type)
        if channel:
            q = q.where(ReportRow.intake_channel == channel)
        if product:
            q = q.where(ReportRow.product_name.ilike(f"%{product}%"))
        if date_from:
            q = q.where(ReportRow.date_received >= date_from)
        if date_to:
            q = q.where(ReportRow.date_received <= date_to)
        total = self.s.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = self.s.scalars(q.order_by(ReportRow.id.desc()).limit(limit).offset(offset)).all()
        return [_report(r, self._ext(r.id)) for r in rows], total

    def set_status(self, reference_id: str, status: str, now: datetime) -> Report:
        r = self._row(reference_id)
        if r is None:
            raise NotFoundError(f"Report {reference_id} not found")
        r.status = status
        r.record_version += 1
        r.updated_at = now
        self.s.flush()
        return _report(r, self._ext(r.id))

    def stats(self) -> dict:
        def group(col):
            return {k: v for k, v in self.s.execute(select(col, func.count()).group_by(col)).all()}
        by_status = group(ReportRow.status)
        pending = self.s.scalar(select(func.count()).select_from(ApprovalRow).where(ApprovalRow.status == "PENDING")) or 0
        return {
            "total": sum(by_status.values()), "by_status": by_status, "by_type": group(ReportRow.report_type),
            "by_channel": group(ReportRow.intake_channel), "pending_approvals": pending,
        }


class SqlHistoryRepository:
    def __init__(self, s: Session):
        self.s = s

    def add(self, *, reference_id, from_status, to_status, now, actor_id, actor_role, approval_id, request_id):
        rid = self.s.scalar(select(ReportRow.id).where(ReportRow.reference_id == reference_id))
        self.s.add(HistoryRow(report_id=rid, from_status=from_status, to_status=to_status, changed_at=now,
                              actor_id=actor_id, actor_role=actor_role, approval_id=approval_id, request_id=request_id))
        self.s.flush()

    def for_report(self, reference_id: str) -> list[StatusHistoryEntry]:
        q = (select(HistoryRow, ReportRow.reference_id).join(ReportRow, ReportRow.id == HistoryRow.report_id)
             .where(ReportRow.reference_id == reference_id).order_by(HistoryRow.id))
        return [StatusHistoryEntry(h.id, ref, h.from_status, h.to_status, h.changed_at, h.actor_id,
                                   h.actor_role, h.approval_id, h.request_id) for h, ref in self.s.execute(q).all()]


class SqlApprovalRepository:
    def __init__(self, s: Session):
        self.s = s

    def _dto(self, a: ApprovalRow) -> Approval:
        ref = self.s.scalar(select(ReportRow.reference_id).where(ReportRow.id == a.report_id))
        return Approval(a.id, ref, a.status, a.requested_by, a.requested_at, a.report_version_at_request,
                        a.request_note, a.decided_by, a.decided_at, a.decision_note)

    def add_pending(self, *, reference_id, requested_by, now, version, note):
        rid = self.s.scalar(select(ReportRow.id).where(ReportRow.reference_id == reference_id))
        a = ApprovalRow(report_id=rid, status="PENDING", requested_by=requested_by, requested_at=now,
                        report_version_at_request=version, request_note=note)
        self.s.add(a)
        self.s.flush()
        return self._dto(a)

    def get(self, approval_id: int):
        a = self.s.get(ApprovalRow, approval_id)
        return self._dto(a) if a else None

    def pending_for_report(self, reference_id: str):
        a = self.s.scalar(select(ApprovalRow).join(ReportRow, ReportRow.id == ApprovalRow.report_id)
                          .where(ReportRow.reference_id == reference_id, ApprovalRow.status == "PENDING"))
        return self._dto(a) if a else None

    def list(self, status: str | None):
        q = select(ApprovalRow).order_by(ApprovalRow.id.desc())
        if status:
            q = q.where(ApprovalRow.status == status)
        return [self._dto(a) for a in self.s.scalars(q).all()]

    def mark_approved(self, approval_id, decided_by, now, note):
        a = self.s.get(ApprovalRow, approval_id)
        a.status, a.decided_by, a.decided_at, a.decision_note = "APPROVED", decided_by, now, note
        self.s.flush()
        return self._dto(a)


def _audit(a: AuditRow) -> AuditEvent:
    return AuditEvent(a.id, a.event_id, a.timestamp_utc, a.actor_id, a.actor_role, a.action_type, a.entity_type,
                      a.entity_id, a.request_id, a.outcome, a.details, a.previous_event_hash, a.payload_hash,
                      a.event_hash, a.application_version)


class SqlAuditRepository:
    def __init__(self, s: Session):
        self.s = s

    def last_hash(self) -> str:
        return self.s.scalar(select(AuditRow.event_hash).order_by(AuditRow.id.desc()).limit(1)) or GENESIS_HASH

    def append(self, event: dict) -> AuditEvent:
        row = AuditRow(**event)
        self.s.add(row)
        self.s.flush()
        return _audit(row)

    def list(self, *, entity_id, limit, offset):
        q = select(AuditRow)
        if entity_id:
            q = q.where(AuditRow.entity_id == entity_id)
        total = self.s.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = self.s.scalars(q.order_by(AuditRow.id.desc()).limit(limit).offset(offset)).all()
        return [_audit(r) for r in rows], total

    def all_ascending(self):
        return [_audit(r) for r in self.s.scalars(select(AuditRow).order_by(AuditRow.id)).all()]
