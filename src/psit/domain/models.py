"""Plain domain records returned by repositories (no ORM leakage)."""
from dataclasses import dataclass
from datetime import date, datetime

from .enums import ReportStatus


@dataclass(frozen=True)
class Report:
    id: int
    reference_id: str
    report_type: str
    status: ReportStatus
    product_name: str
    lot_number: str
    date_received: date
    reporter_type: str
    intake_channel: str
    description: str
    event_description: str | None
    event_onset_date: date | None
    synthetic: bool
    record_version: int
    created_by: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class StatusHistoryEntry:
    id: int
    reference_id: str
    from_status: str | None
    to_status: str
    changed_at: datetime
    actor_id: str
    actor_role: str
    approval_id: int | None
    request_id: str


@dataclass(frozen=True)
class Approval:
    id: int
    reference_id: str
    status: str
    requested_by: str
    requested_at: datetime
    report_version_at_request: int
    request_note: str | None
    decided_by: str | None
    decided_at: datetime | None
    decision_note: str | None


@dataclass(frozen=True)
class AuditEvent:
    id: int
    event_id: str
    timestamp_utc: str
    actor_id: str
    actor_role: str
    action_type: str
    entity_type: str
    entity_id: str
    request_id: str
    outcome: str
    details: str  # canonical JSON, minimal non-sensitive metadata
    previous_event_hash: str
    payload_hash: str
    event_hash: str
    application_version: str


@dataclass(frozen=True)
class Actor:
    actor_id: str
    role: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    parent_id: str
    source_type: str  # SOP | HISTORICAL_REPORT
    source_id: str
    text: str
    text_hash: str
    section_path: str | None
    page_number: int | None
    sequence: int
    active: bool
    meta: dict
