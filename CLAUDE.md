# CLAUDE.md - Pharma Safety Intake & Triage Knowledge Agent

Persistent development rules. Business auditing (audit_events table) is separate from development governance (.claude/dev_audit.jsonl).

## Nature of the project
Training / engineering prototype. NOT a pharmacovigilance platform, medical device, clinical decision-support tool or regulatory engine.

## Data & privacy
- All data is synthetic and fictional. Never add real patient data, names, addresses, emails or phone numbers.
- Schemas use `extra="forbid"`; a deterministic PII guard rejects email/phone patterns in free text.
- Never log or store: chain-of-thought, full prompts, secrets/API keys, whole retrieved contexts.

## Scope boundaries (hard)
The system must never assess causality, seriousness, expectedness, listedness, reportability, recommend treatment/regulatory submissions, or autonomously close records. Such requests get the deterministic scope-boundary response (route PROHIBITED_REQUEST).

## Architecture rules
- API-first modular monolith: ui -> api -> services -> domain -> repository interfaces -> infrastructure.
- `domain` imports nothing from the project. Only `psit.ui` may import streamlit. `psit.ui` may import only `psit.contracts` and httpx (enforced by tests/test_architecture.py).
- Streamlit holds temporary UI state only; no SQL, no workflow changes, no reference-number generation, no FAISS, no authoritative validation.
- Deterministic code owns validation, authorization, IDs, workflow, approvals, transactions, audit, circuit breaker, policy. LLMs may only route ambiguous text, rerank, and summarize retrieved evidence.
- LLM never writes to the DB; it may propose typed commands that services validate.
- SQLite is the metadata authority; FAISS is a derived artifact tracked by embedding_manifests.

## Workflow / HITL
NEW -> IN_REVIEW allowed. IN_REVIEW -> CLOSED only through a persisted human approval by a REVIEWER different from the requester. NEW -> CLOSED and CLOSED -> * rejected. Same-state = idempotent no-op. AGENT role can never approve.

## RAG boundaries
BM25 (FTS5) + dense (BGE-M3/FAISS IndexFlatIP) -> RRF (k=60) -> cross-encoder rerank. Every result carries source_type; SOPs and historical reports stay distinct. Answers are evidence-constrained with citations; abstain when evidence is insufficient. Never claim "zero hallucination". Cloud LLM (OpenRouter) is optional, off by default, and receives only retrieved synthetic evidence.

## Testing & conventions
pytest + Hypothesis + HTTPX (+ Playwright e2e). Run `pytest` before declaring work done. Type-hinted Python 3.11+, Pydantic v2, SQLAlchemy 2 style. Report eval results only from real local runs.
