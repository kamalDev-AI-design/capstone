"""Pydantic v2 API contracts shared by the API and any UI client (Streamlit now, React later via OpenAPI)."""
import re
from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from psit.domain.enums import (
    ApprovalStatus,
    IntakeChannel,
    ReporterType,
    ReportStatus,
    ReportType,
)

LOT_PATTERN = r"^LOT-\d{5}$"
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<![\w-])\+?\d[\d\s().-]{8,}\d(?![\w-])")


def contains_pii_pattern(text: str) -> bool:
    if _EMAIL.search(text):
        return True
    return any(sum(c.isdigit() for c in m.group()) >= 10 for m in _PHONE.finditer(text))


def _no_pii(v: str) -> str:
    if contains_pii_pattern(v):
        raise ValueError("Free text appears to contain an email address or telephone number; synthetic data only.")
    return v


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _ReportCommon(StrictModel):
    product_name: str = Field(min_length=1, max_length=200)
    lot_number: str = Field(pattern=LOT_PATTERN, examples=["LOT-88392"])
    date_received: date
    reporter_type: ReporterType
    intake_channel: IntakeChannel
    description: str = Field(min_length=1, max_length=4000)

    @field_validator("description", "product_name")
    @classmethod
    def _pii(cls, v: str) -> str:
        return _no_pii(v)

    @field_validator("date_received")
    @classmethod
    def _not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("date_received cannot be in the future")
        return v


class ProductQualityComplaintCreate(_ReportCommon):
    report_type: Literal[ReportType.PRODUCT_QUALITY_COMPLAINT]


class AdverseEventCreate(_ReportCommon):
    report_type: Literal[ReportType.SUSPECTED_ADVERSE_EVENT]
    event_description: str = Field(min_length=1, max_length=4000)
    event_onset_date: date

    @field_validator("event_description")
    @classmethod
    def _pii2(cls, v: str) -> str:
        return _no_pii(v)

    @field_validator("event_onset_date")
    @classmethod
    def _onset_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("event_onset_date cannot be in the future")
        return v


ReportCreate = Annotated[
    Union[ProductQualityComplaintCreate, AdverseEventCreate], Field(discriminator="report_type")
]


class ReportOut(StrictModel):
    reference_id: str
    report_type: ReportType
    status: ReportStatus
    product_name: str
    lot_number: str
    date_received: date
    reporter_type: ReporterType
    intake_channel: str
    description: str
    event_description: str | None = None
    event_onset_date: date | None = None
    synthetic: bool
    record_version: int
    created_by: str
    created_at: datetime
    updated_at: datetime


class ReportList(StrictModel):
    items: list[ReportOut]
    total: int


class ReportStats(StrictModel):
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_channel: dict[str, int]
    pending_approvals: int


class StatusHistoryOut(StrictModel):
    from_status: str | None
    to_status: str
    changed_at: datetime
    actor_id: str
    actor_role: str
    approval_id: int | None
    request_id: str


class ReportDetail(ReportOut):
    history: list[StatusHistoryOut]
    pending_approval_id: int | None = None


class TransitionRequest(StrictModel):
    target_status: ReportStatus


class TransitionResult(StrictModel):
    reference_id: str
    status: ReportStatus
    changed: bool
    message: str


class ClosureRequestIn(StrictModel):
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def _pii(cls, v: str | None) -> str | None:
        return _no_pii(v) if v else v


class ApproveIn(StrictModel):
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def _pii(cls, v: str | None) -> str | None:
        return _no_pii(v) if v else v


class ApprovalOut(StrictModel):
    approval_id: int
    reference_id: str
    status: ApprovalStatus
    requested_by: str
    requested_at: datetime
    report_version_at_request: int
    request_note: str | None
    decided_by: str | None
    decided_at: datetime | None
    decision_note: str | None


class AuditEventOut(StrictModel):
    event_id: str
    timestamp_utc: str
    actor_id: str
    actor_role: str
    action_type: str
    entity_type: str
    entity_id: str
    request_id: str
    outcome: str
    details: dict
    previous_event_hash: str
    payload_hash: str
    event_hash: str
    application_version: str


class AuditEventList(StrictModel):
    items: list[AuditEventOut]
    total: int


class AuditVerifyResult(StrictModel):
    valid: bool
    events_checked: int
    first_invalid_event_id: str | None = None
    message: str


class HealthOut(StrictModel):
    status: Literal["ok"]
    version: str
    database: Literal["ok", "error"]


class ErrorBody(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ErrorBody
