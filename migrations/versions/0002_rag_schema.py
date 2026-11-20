"""RAG schema: documents, versions, chunks, FTS5, manifests, ingestion runs, settings

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("doc_key", sa.String(40), nullable=False, unique=True),   # e.g. SOP-QC-001
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("effective_date", sa.Date),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("page_count", sa.Integer),
        sa.Column("ingested_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("document_id", "version", name="uq_doc_version"),
    )
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False),  # INGESTED | DUPLICATE | QUARANTINED | REJECTED
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("document_version_id", sa.Integer, sa.ForeignKey("document_versions.id")),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "chunks",
        sa.Column("chunk_id", sa.String(80), primary_key=True),
        sa.Column("parent_id", sa.String(80), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),    # SOP | HISTORICAL_REPORT
        sa.Column("source_id", sa.String(40), nullable=False),      # sop_id or reference_id
        sa.Column("document_version_id", sa.Integer, sa.ForeignKey("document_versions.id")),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("section_path", sa.String(300)),
        sa.Column("page_number", sa.Integer),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("meta", sa.Text, nullable=False),                 # JSON metadata (version, dates, product, ...)
        sa.Column("embedding_model", sa.String(80)),
        sa.Column("embedding_version", sa.String(40)),
        sa.Column("indexed_at", sa.DateTime),
    )
    op.create_index("ix_chunks_source", "chunks", ["source_type", "source_id"])
    # Sparse index: '-' and '_' are token characters so REF-2026-0001 / LOT-88392 / SOP-QC-001 stay single tokens.
    op.execute(
        "CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id UNINDEXED, text, tokenize=\"unicode61 tokenchars '-_'\")"
    )
    op.create_table(
        "embedding_manifests",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("index_version", sa.Integer, nullable=False),
        sa.Column("embedding_model", sa.String(80), nullable=False),
        sa.Column("embedding_dimension", sa.Integer, nullable=False),
        sa.Column("document_count", sa.Integer, nullable=False),
        sa.Column("chunk_count", sa.Integer, nullable=False),
        sa.Column("last_successful_build", sa.DateTime),
        sa.Column("checksum", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False),  # BUILDING | ACTIVE | FAILED | SUPERSEDED
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(60), primary_key=True),
        sa.Column("value", sa.String(300), nullable=False),
    )


def downgrade() -> None:
    op.execute("DROP TABLE chunks_fts")
    for t in ("app_settings", "embedding_manifests", "chunks", "ingestion_runs", "document_versions", "documents"):
        op.drop_table(t)
