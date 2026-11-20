"""SQLAlchemy models. Internal to the persistence layer; never exposed outside repositories/sql."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ReferenceCounter(Base):
    __tablename__ = "reference_counters"
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_val: Mapped[int] = mapped_column(Integer)


class ReportRow(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reference_id: Mapped[str] = mapped_column(String(16), unique=True)
    report_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    product_name: Mapped[str] = mapped_column(String(200))
    lot_number: Mapped[str] = mapped_column(String(16))
    date_received: Mapped[date] = mapped_column(Date)
    reporter_type: Mapped[str] = mapped_column(String(40))
    intake_channel: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    record_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class AdverseEventRow(Base):
    __tablename__ = "adverse_event_extensions"
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), primary_key=True)
    event_description: Mapped[str] = mapped_column(Text)
    event_onset_date: Mapped[date] = mapped_column(Date)


class ApprovalRow(Base):
    __tablename__ = "review_approvals"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"))
    status: Mapped[str] = mapped_column(String(20))
    requested_by: Mapped[str] = mapped_column(String(80))
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    report_version_at_request: Mapped[int] = mapped_column(Integer)
    request_note: Mapped[str | None] = mapped_column(String(500))
    decided_by: Mapped[str | None] = mapped_column(String(80))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    decision_note: Mapped[str | None] = mapped_column(String(500))


class HistoryRow(Base):
    __tablename__ = "status_history"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    changed_at: Mapped[datetime] = mapped_column(DateTime)
    actor_id: Mapped[str] = mapped_column(String(80))
    actor_role: Mapped[str] = mapped_column(String(30))
    approval_id: Mapped[int | None] = mapped_column(ForeignKey("review_approvals.id"))
    request_id: Mapped[str] = mapped_column(String(64))


class AuditRow(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(40), unique=True)
    timestamp_utc: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[str] = mapped_column(String(80))
    actor_role: Mapped[str] = mapped_column(String(30))
    action_type: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(80))
    request_id: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(30))
    details: Mapped[str] = mapped_column(Text)
    previous_event_hash: Mapped[str] = mapped_column(String(64))
    payload_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64))
    application_version: Mapped[str] = mapped_column(String(20))


class DocumentRow(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_key: Mapped[str] = mapped_column(String(40), unique=True)
    source_type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class DocumentVersionRow(Base):
    __tablename__ = "document_versions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    version: Mapped[str] = mapped_column(String(20))
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    effective_date: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    page_count: Mapped[int | None] = mapped_column(Integer)
    ingested_at: Mapped[datetime] = mapped_column(DateTime)


class IngestionRunRow(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(500))
    document_version_id: Mapped[int | None] = mapped_column(ForeignKey("document_versions.id"))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime)


class ChunkRow(Base):
    __tablename__ = "chunks"
    chunk_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    parent_id: Mapped[str] = mapped_column(String(80))
    source_type: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[str] = mapped_column(String(40))
    document_version_id: Mapped[int | None] = mapped_column(ForeignKey("document_versions.id"))
    text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(String(64))
    section_path: Mapped[str | None] = mapped_column(String(300))
    page_number: Mapped[int | None] = mapped_column(Integer)
    sequence: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[str] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(String(80))
    embedding_version: Mapped[str | None] = mapped_column(String(40))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime)


class ManifestRow(Base):
    __tablename__ = "embedding_manifests"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index_version: Mapped[int] = mapped_column(Integer)
    embedding_model: Mapped[str] = mapped_column(String(80))
    embedding_dimension: Mapped[int] = mapped_column(Integer)
    document_count: Mapped[int] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer)
    last_successful_build: Mapped[datetime | None] = mapped_column(DateTime)
    checksum: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))


class SettingRow(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(300))
