"""Builds docs/PSIT_Wiki.pdf (the project wiki). Run: python docs/build_wiki.py
Content mirrors the implemented code; eval numbers are copied from eval/README.md (real local runs)."""
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

OUT = Path(__file__).parent / "PSIT_Wiki.pdf"
TEAL, NAVY, GREY, LIGHT = colors.HexColor("#0f766e"), colors.HexColor("#0b1220"), colors.HexColor("#475569"), colors.HexColor("#f1f5f9")

ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.6, leading=13.6, spaceAfter=5)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.4, leading=11, textColor=GREY)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.4, leading=10.8, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=17, textColor=TEAL, spaceBefore=4, spaceAfter=8)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12, textColor=NAVY, spaceBefore=9, spaceAfter=4)
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=2.5)
CODE = ParagraphStyle("code", parent=BODY, fontName="Courier", fontSize=8.2, leading=10.6, backColor=LIGHT, borderPadding=5,
                      spaceBefore=3, spaceAfter=8, leftIndent=4)
TITLE = ParagraphStyle("title", parent=BODY, fontName="Helvetica-Bold", fontSize=30, leading=36, textColor=TEAL, alignment=TA_CENTER)
TOCTITLE = ParagraphStyle("toctitle", parent=H1)
SUB = ParagraphStyle("sub", parent=BODY, fontSize=13, leading=18, textColor=GREY, alignment=TA_CENTER)


class Doc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=18 * mm,
                         title="PSIT Agent Wiki", author="PSIT Agent project",
                         subject="Pharma Safety Intake & Triage Knowledge Agent (fictional training prototype)")
        self.addPageTemplates([PageTemplate(id="p", frames=[Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")],
                                            onPage=self._footer)])

    def _footer(self, canv, doc):
        canv.saveState()
        canv.setFont("Helvetica", 7.8)
        canv.setFillColor(GREY)
        canv.drawString(20 * mm, 10 * mm, "PSIT Agent Wiki - fictional training data only; not a PV system, medical device or decision engine")
        canv.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {doc.page}")
        canv.restoreState()

    def afterFlowable(self, fl):
        if isinstance(fl, Paragraph) and fl.style.name in ("h1", "h2"):
            self.notify("TOCEntry", (0 if fl.style.name == "h1" else 1, fl.getPlainText(), self.page))


def P(t): return Paragraph(t, BODY)
def B(items): return [Paragraph(i, BUL, bulletText="•") for i in items]
def C(t): return Paragraph(t.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br/>").replace(" ", "&nbsp;"), CODE)


def T(rows, widths, header=True):
    data = [[Paragraph(str(c), CELLB if (header and i == 0) else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), TEAL)] + [("BACKGROUND", (0, i), (-1, i), LIGHT) for i in range(2, len(rows), 2)]
    t.setStyle(TableStyle(st))
    return [t, Spacer(1, 7)]


def build() -> None:
    s = []
    # ------------------------------------------------------------------ cover
    s += [Spacer(1, 55 * mm), Paragraph("PSIT Agent", TITLE), Spacer(1, 4 * mm),
          Paragraph("Pharma Safety Intake &amp; Triage Knowledge Agent", SUB),
          Paragraph("A Local Multi-Stage RAG and Human-Governed Agentic Workflow Prototype", SUB), Spacer(1, 14 * mm),
          Paragraph("Project Wiki", ParagraphStyle("c", parent=SUB, fontName="Helvetica-Bold", textColor=NAVY, fontSize=16)),
          Spacer(1, 30 * mm),
          Paragraph("All data is synthetic and fictional. This is a training and engineering prototype. It is not a pharmacovigilance "
                    "platform, a medical device, a clinical decision-support tool or a regulatory decision engine.", SUB),
          Spacer(1, 10 * mm), Paragraph(f"Generated {date.today().isoformat()} from the repository (docs/build_wiki.py)", SMALL), PageBreak()]
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("t0", fontName="Helvetica-Bold", fontSize=10.5, leading=15, leftIndent=0),
                       ParagraphStyle("t1", fontName="Helvetica", fontSize=9, leading=12.5, leftIndent=14, textColor=GREY)]
    s += [Paragraph("Contents", TOCTITLE), toc, PageBreak()]

    # ------------------------------------------------------------------ 1 overview
    s += [Paragraph("1. Overview", H1),
          P("PSIT Agent manages fictional pharmaceutical safety intake records and helps a human reviewer find relevant history. "
            "It supports two report types - <b>Suspected Adverse Event</b> and <b>Product Quality Complaint</b> - received through two "
            "intake channels, <b>Email</b> and <b>Telephone</b>. An operator types the (fictional) details into a web form; there is no live "
            "mailbox integration, call recording or speech-to-text."),
          Paragraph("Four responsibilities", H2)]
    s += B(["<b>Capture</b> fictional safety reports with strict server-side validation and a unique reference ID (REF-YYYY-NNNN).",
            "<b>Govern</b> a deterministic review workflow in which closing a report always needs a persisted human approval.",
            "<b>Retrieve</b> historical fictional reports and SOP knowledge with a four-stage hybrid RAG pipeline.",
            "<b>Assist</b> with evidence-constrained, cited answers - and abstain when evidence is insufficient."])
    s += [Paragraph("Guiding principle", H2),
          P("AI retrieves, routes, ranks and summarizes. Deterministic software validates and enforces. Humans authorize consequential "
            "actions. When requirements conflict the priority is: Safety, Determinism, Auditability, Data minimization, Evidence grounding, "
            "Modularity, Maintainability, Performance, Convenience.")]

    s += [Paragraph("Safety boundaries (hard rules)", H2),
          P("The application never assesses drug-event causality, seriousness, expectedness, listedness or regulatory reportability; never "
            "recommends treatment or regulatory submissions; never replaces a human safety reviewer or an enterprise safety database; and "
            "never autonomously closes a record. A deterministic policy check runs <i>before</i> any retrieval or model call and returns a "
            "fixed scope-boundary response: the prototype can retrieve relevant training evidence but cannot make clinical or regulatory "
            "determinations.")]

    # ------------------------------------------------------------------ 2 architecture
    s += [Paragraph("2. Architecture", H1),
          P("An API-first modular monolith. Dependencies point one way:"),
          C("UI (Streamlit)  ->  API (FastAPI /api/v1)  ->  Application Services\n"
            "                 ->  Domain  ->  Repository interfaces  ->  SQLite / FAISS"),
          *T([["Layer", "Package", "Responsibility"],
              ["Presentation", "psit.ui", "Streamlit pages, theme, HTTP client. Holds temporary UI state only (selected persona, draft form values, chat history)."],
              ["API", "psit.api, psit.contracts", "FastAPI routers under /api/v1; Pydantic v2 request/response contracts (extra fields rejected); OpenAPI generated automatically."],
              ["Services", "psit.services", "Intake, Workflow, Approval, Audit, Ingestion, Indexing, Knowledge services. Each mutation is one DB transaction."],
              ["Domain", "psit.domain", "Enums, errors, workflow rules. Imports nothing from the project, no I/O."],
              ["Agent", "psit.agent", "Policy, extractor, router, typed tools, circuit breaker, orchestrator, per-request memory."],
              ["RAG", "psit.rag", "Normalization, parsers, chunking, FTS5, embedders, FAISS index, RRF fusion, reranker, context builder, LLM gate."],
              ["Persistence", "psit.repositories", "Repository interfaces plus SQLAlchemy 2 implementation; ORM models never leave this layer."],
              ["Audit", "psit.services.audit", "Append-only, hash-chained business audit log."]], [28, 38, 104]),
          Paragraph("Why Streamlit is replaceable", H2),
          P("Streamlit may import only <font face='Courier'>psit.contracts</font> and httpx. It never queries SQLite, changes workflow "
            "status, generates reference numbers, runs FAISS or holds authoritative validation. A test (tests/test_architecture.py) enforces "
            "this, so a future React + TypeScript client can replace the UI by consuming the same OpenAPI contract without touching services, "
            "workflow, RAG, repositories or the schema."),
          Paragraph("Repository layout", H2),
          C("src/psit/{domain,contracts,repositories,services,rag,agent,api,infra,ui}\n"
            "migrations/      Alembic (0001 core schema, 0002 RAG schema)\n"
            "data/synthetic/  generate_sops.py -> fictional SOP files in 4 formats + negative cases\n"
            "eval/            gold.py, run_eval.py, results/ (measured only)\n"
            "tests/           pytest, Hypothesis, HTTPX, hook and architecture tests\n"
            ".claude/         review skill, PostToolUse hook, dev audit log\n"
            "docs/            this wiki (build_wiki.py -> PSIT_Wiki.pdf)"), PageBreak()]

    # ------------------------------------------------------------------ 3 personas
    s += [Paragraph("3. Sign-in personas and permissions", H1),
          P("Choose a persona in the sidebar under <b>Sign in as</b>. There is no password: the UI sends <font face='Courier'>X-Actor-Id</font> "
            "and <font face='Courier'>X-Actor-Role</font> headers and the backend enforces the permissions. <b>This is demo identification, "
            "not production authentication.</b>"),
          *T([["Persona", "Actor id", "Role", "Purpose"],
              ["Olivia Operator", "operator.demo", "INTAKE_OPERATOR", "Front-line intake: logs reports, starts reviews, requests closure, uploads SOPs."],
              ["Rafael Reviewer", "reviewer.demo", "REVIEWER", "Human safety reviewer: can approve closure requests made by someone else."],
              ["Rhea Reviewer-2", "reviewer.two", "REVIEWER", "Second reviewer so the four-eyes rule can be shown end to end."],
              ["PSIT Agent", "agent.psit", "AGENT", "Represents the AI. Exists to prove that the AI can never approve."]], [34, 30, 34, 72]),
          Paragraph("Permission matrix", H2),
          *T([["Capability", "Operator", "Reviewer", "AI agent"],
              ["View dashboard, reports, audit, search knowledge", "Yes", "Yes", "Yes"],
              ["Create a report (UI form)", "Yes", "Yes", "See note"],
              ["Create a report through the Assistant", "Yes", "Yes", "No (refused)"],
              ["Move NEW to IN_REVIEW", "Yes", "Yes", "Yes"],
              ["Request closure (IN_REVIEW reports)", "Yes", "Yes", "Yes"],
              ["Approve closure", "No", "Yes, not own request", "Never"],
              ["Upload / ingest SOPs, rebuild index", "Yes", "Yes", "No"],
              ["Change LLM settings", "Yes", "Yes", "No"]], [78, 24, 40, 28]),
          P("<b>Note:</b> the REST endpoint that creates reports does not yet check the role, so the AI persona can submit the form. Only the "
            "Assistant's create tool blocks it. Adding a role check to the endpoint is a recommended hardening step (see Known gaps).")]

    # ------------------------------------------------------------------ 4 workflow
    s += [Paragraph("4. Report workflow and human-in-the-loop closure", H1),
          C("NEW  -->  IN_REVIEW  -->  CLOSED\n"
            "      (allowed)        (only with persisted human approval)"),
          *T([["Transition", "Result"],
              ["NEW -> IN_REVIEW", "Allowed (operator, reviewer or agent)."],
              ["IN_REVIEW -> CLOSED", "Only through a closure request plus approval by a different human REVIEWER. A direct request returns APPROVAL_REQUIRED."],
              ["NEW -> CLOSED", "Rejected (INVALID_TRANSITION)."],
              ["CLOSED -> anything", "Rejected; closed records cannot be reopened in this prototype."],
              ["Same state -> same state", "Idempotent no-op: nothing is written to history or audit."]], [48, 122]),
          Paragraph("Closure sequence", H2)]
    s += B(["Request closure: the report must be IN_REVIEW; a PENDING approval is created storing the requester and the record version.",
            "Wait for a human. The approver must have the REVIEWER role and must differ from the requester (four-eyes).",
            "Verify the record version is unchanged (otherwise 409 VERSION_CONFLICT and a new request is needed).",
            "In one transaction: mark the approval APPROVED, set status CLOSED, write status history, write audit events.",
            "Denied attempts (wrong role, self-approval, stale version) are themselves audited."])
    s += [Paragraph("Reference IDs and validation", H2)]
    s += B(["IDs have the form <font face='Courier'>REF-YYYY-NNNN</font>, allocated from a per-year counter table inside a BEGIN IMMEDIATE "
            "transaction, with a UNIQUE constraint as a backstop (30 concurrent creates were tested to give 30 unique IDs).",
            "Lot numbers must match <font face='Courier'>^LOT-\\d{5}$</font>; mandatory fields are enforced by Pydantic on the server.",
            "Adverse events additionally require an event description and onset date. Dates cannot be in the future.",
            "Patient names, addresses, emails and phone numbers are not captured; email/phone patterns in free text are rejected."])
    s += [PageBreak()]

    # ------------------------------------------------------------------ 5 UI features
    s += [Paragraph("5. Application pages", H1)]
    pages = [
        ("Dashboard", ["KPI cards: total, new, in review, closed, pending approvals.", "Status donut and report-type bar charts.",
                       "Filters: status, type, channel, product text, received-from / received-to dates.",
                       "Select a row to open the report. When empty it offers 'Load fictional demo data'."]),
        ("New Intake", ["Choose Product Quality Complaint or Suspected Adverse Event; adverse events reveal event fields.",
                        "'Fill sample data' button for demos. Server-side validation errors are shown inline.",
                        "Success shows the generated REF number and a link to the new record."]),
        ("Report Detail", ["Status stepper, facts, description, event details and a status-history timeline (who, when, approval id).",
                           "Actions depend on status: Move to IN_REVIEW, Request closure, or (reviewers) Approve closure.",
                           "A demo panel tries prohibited transitions so you can see the backend reject them."]),
        ("Assistant", ["Chat with the bounded agent. Shows route, outcome and the tools that ran.",
                       "Prompts such as: show REF-2026-0004; list new reports; move REF-2026-0004 to in review; request closure for REF-...; "
                       "what does the SOP say about acknowledging a complaint; verify the audit chain.",
                       "'approve approval #n' never approves: a reviewer gets a confirmation button, and only that click records approval."]),
        ("Knowledge Assistant", ["Direct hybrid search with example chips and filters (source, report status, include superseded SOPs).",
                                 "Answer with numbered citations; SOP cards show version, section and page, report cards show live status.",
                                 "Retrieval trace: BM25 rank, dense rank, RRF rank/score and rerank score per chunk, plus stage timings."]),
        ("Documents & Index", ["Upload PDF, DOCX, Markdown or TXT; per-file result: INGESTED, DUPLICATE, QUARANTINED or REJECTED.",
                               "SOP versions table (ACTIVE / SUPERSEDED), ingestion run history, index manifest and a rebuild button."]),
        ("Approvals", ["Queue of pending closure requests with requester, time and record version.", "Reviewers approve; others see 'Reviewer only'.",
                       "Lists decided approvals."]),
        ("Audit Trail", ["Newest-first business events with action, outcome, entity, actor, details and hash prefixes.",
                         "'Verify hash chain' recomputes every hash and reports the first broken event, if any."]),
        ("Settings", ["Choose Local extractive (default) or OpenRouter answer generation; shows whether the key is detected in the backend.",
                      "The key itself is never shown or stored by the UI."])]
    for name, items in pages:
        s += [KeepTogether([Paragraph(name, H2)] + B(items))]
    s += [PageBreak()]

    # ------------------------------------------------------------------ 6 RAG
    s += [Paragraph("6. Knowledge, ingestion and hybrid RAG", H1),
          Paragraph("Two distinct corpora", H2),
          P("Retrieval runs over <b>SOP documents</b> (procedural authority) and <b>historical fictional reports</b> (precedent only). "
            "Every result carries <font face='Courier'>source_type</font> (SOP or HISTORICAL_REPORT) and the UI renders them differently, "
            "so a historical report is never presented with the authority of an SOP."),
          Paragraph("Document ingestion", H2)]
    s += B(["Local parsers only: pypdf for PDF, python-docx for DOCX, plain read for Markdown/TXT. No external document APIs.",
            "Conservative normalization (whitespace, safe Unicode); identifiers, dates, negations and section numbers are preserved.",
            "The document hash is a SHA-256 of normalized text, so identical content in a different format is detected as a duplicate.",
            "A SOP needs a header with <font face='Courier'>SOP-XXX-000</font>, <font face='Courier'>Version:</font> and "
            "<font face='Courier'>Effective Date:</font>; otherwise it is REJECTED. Image-only PDFs are QUARANTINED (no OCR available).",
            "Ingesting a newer version marks older versions superseded; superseded SOPs are excluded from answers unless requested."])
    s += [Paragraph("Chunking", H2),
          *T([["Corpus", "Strategy", "Target / overlap"],
              ["SOP", "Document > version > heading > procedure > paragraph > sentence-aware token boundary. Complete sections act as "
                      "parents; a procedure stays together with its immediate WARNING / NOTE / EXCEPTION paragraph.", "350 / 50 tokens"],
              ["Report", "Controlled text projection of the report (type, channel, reporter, description, event) - not arbitrary DB fields. "
                         "Parent is the whole report.", "220 / 30 tokens"]], [22, 112, 36]),
          P("Token counts use the embedding model's tokenizer. Each chunk is indexed with an identifying header (SOP id/version/section, or "
            "REF/product/lot) so identifiers match in every chunk.")]
    s += [Paragraph("Four retrieval stages", H2),
          *T([["Stage", "Method", "Details"],
              ["1 Sparse", "SQLite FTS5 BM25", "Tokenizer keeps '-' and '_' inside tokens so REF-2026-0001, LOT-88392 and SOP-QC-001 stay whole. Top 30."],
              ["2 Dense", "Embeddings + FAISS IndexFlatIP", "Normalized vectors, exact inner-product search. Top 30. Fast profile BGE-small (384d); full profile BGE-M3 (1024d)."],
              ["3 Fusion", "Reciprocal Rank Fusion", "k = 60, equal weights; BM25 weight 1.25 when the query contains a structured identifier. Dedupe by chunk id."],
              ["4 Rerank", "Cross-encoder", "Top 25 fused candidates reranked (MiniLM in fast profile, BGE-Reranker-v2-M3 in full)."]], [20, 46, 104]),
          Paragraph("Context and answers", H2)]
    s += B(["Context: relevance threshold 0.40 (experimental default), max 5 evidence chunks (hard cap 6), max 2 chunks per parent, "
            "near-duplicates dropped, SOP and report evidence kept separate.",
            "Exact identifier matches bypass the threshold; a pure identifier query (e.g. 'REF-2026-0004') returns only exact matches.",
            "Answers are <b>extractive</b> by default (best-matching sentences, each tagged [n]) with a scope statement, never presented as "
            "'zero hallucination' - the design is described as evidence-constrained.",
            "Citations expose source_type, source_id, chunk_id; SOP citations add version, section and page.",
            "If nothing clears the threshold the system abstains instead of answering from model knowledge.",
            "Filters (report status, type, dates, source types, include superseded) apply against live SQLite data."])
    s += [Paragraph("Index consistency", H2)]
    s += B(["SQLite is the metadata authority; FAISS is a derived artifact described by an embedding manifest (index version, model, dimension, "
            "document and chunk counts, last build, checksum, status).",
            "Model or dimension mismatch makes search refuse with INDEX_REBUILD_REQUIRED (HTTP 409) - vectors are never silently mixed.",
            "Rebuilds write to temporary files and replace the index atomically, retaining the previous index; a failed rebuild records a FAILED "
            "manifest and keeps serving the old index. The Documents page shows when the index is stale."])
    s += [PageBreak()]

    # ------------------------------------------------------------------ 7 agent
    s += [Paragraph("7. The bounded agent", H1),
          P("The Assistant is deliberately <b>not</b> an autonomous agent. It can only select approved capabilities, and the model never writes "
            "to the database: it may propose a typed command, and services validate and execute it."),
          C("Policy check -> Entity extraction -> Intent routing -> Typed command\n"
            "  -> Pydantic validation -> Tool execution -> Result validation -> Audit -> Response"),
          Paragraph("Routes", H2),
          *T([["Route", "Triggered by", "Tools"],
              ["DIRECT_RESPONSE", "Greetings / help", "none"],
              ["NEW_INTAKE", "'create/log a complaint ...' with key: value fields", "create_report"],
              ["REPORT_LOOKUP", "A REF id, 'list reports', audit requests", "get_report, list_reports, get_audit_history, verify_audit_chain"],
              ["SOP_LOOKUP", "Mentions SOP / procedure / policy", "search_sops"],
              ["HYBRID_KNOWLEDGE_LOOKUP", "Lot ids, 'similar / historical', general domain questions", "search_historical_reports, run_hybrid_rag"],
              ["STATUS_UPDATE", "'move REF-... to in review'", "update_report_status"],
              ["CLOSURE_APPROVAL", "'request closure ...', 'approve approval #n'", "request_closure, approve_closure (never mutates)"],
              ["PROHIBITED_REQUEST", "Causality, seriousness, expectedness, reportability, treatment, autonomous closure", "none (fixed scope-boundary reply)"]],
            [44, 70, 56]),
          Paragraph("Key safeguards", H2)]
    s += B(["Routing is deterministic regex first. An optional LLM classifier is consulted only for unmatched text and may never choose a mutating route.",
            "Every tool has a strict typed contract (Pydantic TypeAdapter); mutating tools check the actor's role; services write audit events.",
            "<b>Circuit breaker:</b> the tool name, arguments and validation error are canonicalized into a SHA-256 signature per request. "
            "Two identical invalid attempts are tolerated; the third halts execution and returns CIRCUIT_BREAKER_TRIGGERED, requiring manual correction.",
            "<b>Memory:</b> short-term = per-request route, tool calls, validated arguments, results, error codes and retry count (observable events only); "
            "long-term = the database. Chain-of-thought is never stored.",
            "Each request writes one AGENT_REQUEST_COMPLETED audit event (route, tools, outcome, message hash - not the message text)."])
    s += [Paragraph("Optional OpenRouter generation", H2)]
    s += B(["Off by default. Requires <font face='Courier'>OPENROUTER_API_KEY</font> in the backend environment <i>and</i> the Settings toggle.",
            "Receives only the question and the already-retrieved synthetic evidence; temperature 0, top_p 0.1, max 450 tokens, 20 s timeout.",
            "The generated text must cite valid evidence numbers; if the model returns INSUFFICIENT_EVIDENCE the system abstains; any failure "
            "falls back to the local extractive answer with a notice. The key is never logged, audited or returned.",
            "Prohibited questions are blocked before the provider can see them. Retrieval, embeddings and reranking always remain local."])
    s += [PageBreak()]

    # ------------------------------------------------------------------ 8 audit
    s += [Paragraph("8. Audit and governance", H1),
          Paragraph("Business audit log", H2),
          P("Every consequential action appends an event to <font face='Courier'>audit_events</font>: REPORT_CREATED, STATUS_TRANSITION_REQUESTED, "
            "STATUS_CHANGED, CLOSURE_REQUESTED, CLOSURE_APPROVED, KNOWLEDGE_SEARCH_COMPLETED, POLICY_BLOCKED, CIRCUIT_BREAKER_TRIGGERED, "
            "AGENT_REQUEST_COMPLETED, DOCUMENT_*, INDEX_REBUILT, SETTINGS_CHANGED and AUDIT_CHAIN_VERIFIED."),
          *T([["Field", "Purpose"],
              ["event_id, timestamp_utc, actor_id, actor_role", "Who and when"],
              ["action_type, entity_type, entity_id, request_id, outcome", "What happened (SUCCESS, DENIED, BLOCKED, ABSTAINED, FAILURE, HALTED)"],
              ["details (+ payload_hash)", "Minimal non-sensitive metadata; hash of the canonical JSON"],
              ["previous_event_hash, event_hash", "SHA-256 chain linking each event to the one before"],
              ["application_version", "Software version that wrote the event"]], [78, 92]),
          P("Database triggers block UPDATE and DELETE on the table, and verification recomputes every hash. This makes tampering "
            "<i>evident</i>; SQLite does not provide absolute immutability, and the project does not claim it. Audit records never store "
            "chain-of-thought, full prompts, passwords, tokens, whole retrieved contexts or unnecessary report text."),
          Paragraph("Development governance (separate from business audit)", H2)]
    s += B(["<b>CLAUDE.md</b>: persistent rules - synthetic data only, privacy, scope boundaries, architecture, testing, RAG and human-approval rules.",
            "<b>.claude/skills/pharma-intake-review/SKILL.md</b>: a ten-dimension review checklist (data minimization, validation, state-transition "
            "integrity, HITL, auditability, RAG grounding, citations, error handling, test coverage, security boundaries).",
            "<b>PostToolUse hook</b> (.claude/hooks/log_edit.py): deterministically appends tool, file path, path hash and timestamp to "
            ".claude/dev_audit.jsonl for every file edit. It stores no file contents. The model does not decide whether to log."])

    # ------------------------------------------------------------------ 9 data model
    s += [Paragraph("9. Data model", H1),
          *T([["Table", "Purpose"],
              ["reports", "Core record: reference_id (unique), type, status, product, lot, dates, reporter, channel, description, record_version, synthetic flag."],
              ["adverse_event_extensions", "Event description and onset date for adverse events (1:1 with reports)."],
              ["status_history", "Every status change: from/to, actor, approval id, request id."],
              ["review_approvals", "Closure requests and decisions; a partial unique index allows one PENDING approval per report."],
              ["audit_events", "Hash-chained append-only business audit log."],
              ["reference_counters", "Per-year counter used to generate REF ids safely."],
              ["documents / document_versions", "SOP identity and each ingested version (hash, effective date, active flag, file info)."],
              ["ingestion_runs", "Outcome of every upload attempt."],
              ["chunks / chunks_fts", "Searchable chunks with metadata, and the FTS5 virtual table for BM25."],
              ["embedding_manifests", "Index version, model, dimension, counts, checksum, status."],
              ["app_settings", "Key/value settings (LLM provider and model)."]], [48, 122]),
          P("SQLite runs with foreign keys enabled, WAL journaling and BEGIN IMMEDIATE write transactions. Schema changes are managed by Alembic migrations.")]

    # ------------------------------------------------------------------ 10 API
    s += [Paragraph("10. REST API (/api/v1)", H1),
          P("Interactive documentation: <font face='Courier'>http://127.0.0.1:8000/docs</font>. All business endpoints require the demo actor headers."),
          *T([["Method and path", "Purpose"],
              ["GET /health", "Liveness and database check (no headers needed)"],
              ["POST /reports", "Create a report (validated; returns REF id)"],
              ["GET /reports  |  /reports/stats  |  /reports/{reference_id}", "List with filters, dashboard counts, detail with history"],
              ["POST /reports/{reference_id}/transitions", "Request a status change (deterministic validation)"],
              ["POST /reports/{reference_id}/closure-requests", "Request closure (creates a pending approval)"],
              ["GET /closure-requests  |  POST /closure-requests/{id}/approve", "Approvals queue; human approval"],
              ["POST /knowledge/search", "Hybrid RAG with citations, abstention and trace"],
              ["GET /knowledge/index  |  POST /knowledge/index/rebuild", "Manifest and staleness; rebuild"],
              ["GET /documents  |  POST /documents", "SOP versions and ingestion runs; upload a file"],
              ["POST /agent/messages", "Send a message to the bounded agent"],
              ["GET /audit/events  |  GET /audit/verify", "Browse events; verify the hash chain"],
              ["GET /settings/llm  |  PUT /settings/llm", "Answer-generation mode"],
              ["POST /admin/seed", "Load fictional demo data (demo only)"]], [88, 82]),
          P("Errors use a uniform body <font face='Courier'>{\"error\": {\"code\", \"message\"}}</font> with codes such as VALIDATION_ERROR (422), "
            "INVALID_TRANSITION, APPROVAL_REQUIRED, VERSION_CONFLICT, CONFLICT (409), FORBIDDEN (403), NOT_FOUND (404) and INDEX_REBUILD_REQUIRED (409).")]

    # ------------------------------------------------------------------ 11 run
    s += [Paragraph("11. Running, configuring and testing", H1),
          C("python -m venv .venv\n"
            ".venv/Scripts/python -m pip install -e \".[dev,ui,rag]\"\n"
            "# backend (OpenAPI at http://127.0.0.1:8000/docs)\n"
            ".venv/Scripts/python -m uvicorn psit.api.app:create_app --factory --port 8000\n"
            "# UI\n"
            ".venv/Scripts/python -m streamlit run src/psit/ui/app.py --server.port 8501\n"
            ".venv/Scripts/python -m pytest"),
          *T([["Variable", "Meaning"],
              ["PSIT_DATABASE_URL", "SQLite URL (default sqlite:///data/psit.db). Migrations run automatically at startup."],
              ["PSIT_API_BASE_URL", "Where the UI finds the API (default http://127.0.0.1:8000/api/v1)."],
              ["PSIT_MODEL_PROFILE", "fast (BGE-small + MiniLM, default), full (BGE-M3 + BGE-Reranker-v2-M3, ~4.5 GB), test (deterministic stand-ins for pytest)."],
              ["PSIT_INDEX_DIR", "Where FAISS index files are written (default data/index)."],
              ["PSIT_RERANK_THRESHOLD", "Override the relevance threshold for the active profile."],
              ["OPENROUTER_API_KEY, PSIT_OPENROUTER_MODEL", "Optional cloud answer generation (also needs the Settings toggle)."]], [56, 114]),
          P("A <font face='Courier'>.env</font> file at the project root is read at startup (blank values ignored; real environment variables win). "
            "Never commit a real key."),
          Paragraph("Quick demo path", H2)]
    s += B(["Dashboard: load fictional demo data (36 reports). Documents &amp; Index: upload the files in data/synthetic/sops/ (generate them with "
            "data/synthetic/generate_sops.py) and rebuild the index.",
            "As Olivia: create a report, move it to IN_REVIEW, request closure; try 'Force to CLOSED' and see it rejected.",
            "As PSIT Agent: try to approve (refused). As Rafael: approve on the Approvals page. Audit Trail: verify the chain.",
            "Assistant: ask an SOP question, a lot lookup, a prohibited causality question and an unanswerable question."])
    s += [Paragraph("Automated tests", H2),
          P("58 pytest tests cover: report validation and Hypothesis properties on lot numbers, reference uniqueness under concurrency, "
            "conditional adverse-event fields, status transitions, HITL enforcement, transaction rollback, audit chain and tamper detection, "
            "ingestion outcomes, hybrid retrieval, citations, abstention and prohibited requests, index mismatch and failed rebuild, deterministic routing, "
            "circuit-breaker behaviour, the OpenRouter gate (mocked transport), the governance hook and the architecture import rules. "
            "Playwright end-to-end tests have not been written; the Streamlit pages were smoke-tested headlessly.")]

    # ------------------------------------------------------------------ 12 evaluation
    s += [Paragraph("12. Evaluation results (measured)", H1),
          P("Produced by <font face='Courier'>python eval/run_eval.py --profile fast --calibrate</font>: 105 synthetic queries over 36 fictional reports "
            "and 7 SOP files on CPU, 2026-11-05. Ground truth is derived from the seeded text. These are local results, not published benchmarks."),
          *T([["Metric", "Result", "Project target", "Met"],
              ["Exact reference lookup (top-1)", "1.00", "1.00", "Yes"],
              ["Exact lot lookup (all cited relevant)", "1.00", "1.00", "Yes"],
              ["Recall@20", "0.970", ">= 0.95", "Yes"],
              ["nDCG@10", "0.954", ">= 0.85", "Yes"],
              ["MRR@10", "0.966", "-", "-"],
              ["Citation precision", "0.988", ">= 0.98", "Yes"],
              ["Correct abstention", "1.00", ">= 0.95", "Yes"],
              ["Prohibited-request blocking", "1.00", "1.00", "Yes"],
              ["Stale SOP returned by default", "0", "0", "Yes"],
              ["Repeated invalid tool call blocking", "1.00", "1.00", "Yes"],
              ["False abstention on answerable queries", "0.272", "(none stated)", "Weak"],
              ["Mixed SOP + report returns both source types", "0.143", "(none stated)", "Weak"],
              ["p95 retrieval / end-to-end latency", "~489 ms / ~496 ms", "-", "-"]], [78, 36, 34, 22]),
          Paragraph("Threshold trade-off and honest limits", H2)]
    s += B(["With the small MS-MARCO reranker, true paraphrase matches often score near zero, so no single threshold meets every target. Lowering "
            "the rerank threshold from 0.40 to 0.002 cuts false abstention from 0.272 to 0.099 but reduces citation precision from 0.988 to 0.922.",
            "The default stays at 0.40 because abstaining is the safer failure mode. A dense-similarity second gate gave only a marginal gain and was not added.",
            "The full profile (BGE-M3 + BGE-Reranker-v2-M3) has <b>not</b> been evaluated: the reranker download failed because the disk was full.",
            "The gold set is small (12 unanswerable queries); calibration conclusions are indicative, not definitive."])

    # ------------------------------------------------------------------ 13 gaps / glossary
    s += [Paragraph("13. Known gaps and next steps", H1)]
    s += B(["Add a role check to POST /reports so the AI persona cannot create records through the REST API.",
            "Replace header-based demo identity with real authentication before any non-demo use.",
            "Free disk space (~3 GB), then evaluate and recalibrate the threshold with --profile full.",
            "Add Playwright end-to-end tests; optionally an llama.cpp local generation provider.",
            "Improve mixed SOP+report retrieval (for example, query decomposition) and paraphrase recall with the stronger reranker.",
            "Only move to approximate vector search (HNSW) if exact search is shown to be too slow."])
    s += [Paragraph("14. Glossary", H1),
          *T([["Term", "Meaning"],
              ["HITL", "Human in the loop: a person must authorize closing a report."],
              ["BM25 / FTS5", "Keyword ranking implemented by SQLite's full-text search."],
              ["Dense retrieval", "Semantic search using embedding vectors (BGE) in a FAISS index."],
              ["RRF", "Reciprocal Rank Fusion: merges ranked lists using ranks, not raw scores."],
              ["Cross-encoder", "A model that scores a (query, passage) pair together for precise reranking."],
              ["Extractive answer", "An answer assembled from sentences in the retrieved evidence rather than newly generated text."],
              ["Abstention", "Deliberately not answering because evidence is insufficient."],
              ["Circuit breaker", "Halts the agent after repeated identical invalid tool calls."],
              ["Hash chain", "Each audit event includes the hash of the previous one, so edits are detectable."],
              ["Superseded SOP", "An older SOP version replaced by a newer one; excluded from answers by default."],
              ["Quarantined document", "A file that cannot be processed locally (e.g. image-only PDF)."]], [38, 132])]

    Doc(OUT).multiBuild(s)
    print("wrote", OUT, f"({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build()
