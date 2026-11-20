from datetime import date, datetime
from typing import Literal

from pydantic import Field

from psit.domain.enums import ReportStatus, ReportType

from .reports import StrictModel

SourceType = Literal["SOP", "HISTORICAL_REPORT"]


class KnowledgeSearchRequest(StrictModel):
    query: str = Field(min_length=2, max_length=500)
    source_types: list[SourceType] | None = None
    status: ReportStatus | None = None
    report_type: ReportType | None = None
    date_from: date | None = None
    date_to: date | None = None
    include_superseded: bool = False


class Citation(StrictModel):
    n: int
    source_type: SourceType
    source_id: str
    chunk_id: str
    relevance: float
    exact_id_match: bool = False
    title: str | None = None
    # SOP-specific
    version: str | None = None
    section: str | None = None
    page: int | None = None
    superseded: bool | None = None
    # report-specific
    status: str | None = None
    report_type: str | None = None
    snippet: str | None = None


class TraceRow(StrictModel):
    chunk_id: str
    source_type: SourceType
    bm25_rank: int | None
    dense_rank: int | None
    rrf_rank: int
    rrf_score: float
    rerank_rank: int
    rerank_score: float
    exact_id: bool
    dense_score: float | None = None
    selected: bool


class KnowledgeAnswer(StrictModel):
    route: str
    answer: str
    abstained: bool
    abstain_reason: str | None = None
    blocked: bool = False
    block_category: str | None = None
    scope_statement: str
    citations: list[Citation] = []
    trace: list[TraceRow] = []
    timings_ms: dict[str, float] = {}
    counts: dict[str, int] = {}
    index_stale: bool = False
    answer_mode: str = "extractive"
    llm_notice: str | None = None


class DocumentVersionOut(StrictModel):
    doc_key: str
    title: str
    version: str
    active: bool
    effective_date: date | None
    filename: str
    file_type: str
    page_count: int | None
    sha256: str
    chunk_count: int
    ingested_at: datetime


class IngestionRunOut(StrictModel):
    id: int
    filename: str
    status: str
    message: str
    chunk_count: int
    started_at: datetime


class DocumentOverview(StrictModel):
    versions: list[DocumentVersionOut]
    runs: list[IngestionRunOut]


class IngestResult(StrictModel):
    status: Literal["INGESTED", "DUPLICATE", "QUARANTINED", "REJECTED"]
    message: str
    filename: str
    doc_key: str | None = None
    chunk_count: int = 0


class ManifestOut(StrictModel):
    index_version: int
    embedding_model: str
    embedding_dimension: int
    document_count: int
    chunk_count: int
    last_successful_build: datetime | None
    checksum: str | None
    status: str


class IndexStatus(StrictModel):
    built: bool
    stale: bool
    profile: str
    active_model: str
    reranker: str
    manifest: ManifestOut | None
    pending_reports: int
