"""core schema: reports, workflow, approvals, audit

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reference_counters",
        sa.Column("year", sa.Integer, primary_key=True),
        sa.Column("next_val", sa.Integer, nullable=False),
    )
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("reference_id", sa.String(16), nullable=False, unique=True),
        sa.Column("report_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("lot_number", sa.String(16), nullable=False),
        sa.Column("date_received", sa.Date, nullable=False),
        sa.Column("reporter_type", sa.String(40), nullable=False),
        sa.Column("intake_channel", sa.String(30), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("synthetic", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("record_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.CheckConstraint("status IN ('NEW','IN_REVIEW','CLOSED')", name="ck_reports_status"),
        sa.CheckConstraint("report_type IN ('SUSPECTED_ADVERSE_EVENT','PRODUCT_QUALITY_COMPLAINT')", name="ck_reports_type"),
    )
    op.create_index("ix_reports_status", "reports", ["status"])
    op.create_index("ix_reports_lot", "reports", ["lot_number"])
    op.create_table(
        "adverse_event_extensions",
        sa.Column("report_id", sa.Integer, sa.ForeignKey("reports.id"), primary_key=True),
        sa.Column("event_description", sa.Text, nullable=False),
        sa.Column("event_onset_date", sa.Date, nullable=False),
    )
    op.create_table(
        "review_approvals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.Integer, sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_by", sa.String(80), nullable=False),
        sa.Column("requested_at", sa.DateTime, nullable=False),
        sa.Column("report_version_at_request", sa.Integer, nullable=False),
        sa.Column("request_note", sa.String(500)),
        sa.Column("decided_by", sa.String(80)),
        sa.Column("decided_at", sa.DateTime),
        sa.Column("decision_note", sa.String(500)),
        sa.CheckConstraint("status IN ('PENDING','APPROVED')", name="ck_approvals_status"),
    )
    # At most one pending approval per report.
    op.create_index(
        "uq_one_pending_approval", "review_approvals", ["report_id"], unique=True,
        sqlite_where=sa.text("status = 'PENDING'"),
    )
    op.create_table(
        "status_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.Integer, sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("from_status", sa.String(20)),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("changed_at", sa.DateTime, nullable=False),
        sa.Column("actor_id", sa.String(80), nullable=False),
        sa.Column("actor_role", sa.String(30), nullable=False),
        sa.Column("approval_id", sa.Integer, sa.ForeignKey("review_approvals.id")),
        sa.Column("request_id", sa.String(64), nullable=False),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(40), nullable=False, unique=True),
        sa.Column("timestamp_utc", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.String(80), nullable=False),
        sa.Column("actor_role", sa.String(30), nullable=False),
        sa.Column("action_type", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(80), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("details", sa.Text, nullable=False),
        sa.Column("previous_event_hash", sa.String(64), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("application_version", sa.String(20), nullable=False),
    )
    op.create_index("ix_audit_entity", "audit_events", ["entity_id"])
    # Append-only semantics (tamper-evident, not absolute immutability).
    op.execute(
        "CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_events "
        "BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END"
    )
    op.execute(
        "CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_events "
        "BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END"
    )


def downgrade() -> None:
    for t in ("audit_events", "status_history", "review_approvals", "adverse_event_extensions", "reports", "reference_counters"):
        op.drop_table(t)
