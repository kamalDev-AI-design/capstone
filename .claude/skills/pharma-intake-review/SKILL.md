---
name: pharma-intake-review
description: Review changes to the Pharma Safety Intake & Triage Knowledge Agent (PSIT) for data minimization, validation, workflow integrity, human-in-the-loop enforcement, auditability, RAG grounding, citations, error handling, tests and security boundaries. Use when reviewing a diff, PR, or module in this repository.
---

# PSIT review skill

Review against the project rules in `CLAUDE.md`. For each dimension below report **PASS / CONCERN / FAIL** with `file:line` evidence, then list required fixes ordered by safety impact. Priority when rules conflict: Safety > Determinism > Auditability > Data minimization > Evidence grounding > Modularity > Maintainability > Performance > Convenience.

## 1. Data minimization & synthetic-data rule
- No real patient data, names, addresses, emails or phone numbers in code, fixtures, seeds, docs or logs.
- New schema fields do not capture patient identifiers; contracts use `extra="forbid"`; the PII guard (`contracts/reports.py`) still covers every free-text field.
- Audit payloads store hashes/metadata only (no prompts, retrieved contexts, report descriptions, keys, chain-of-thought).

## 2. Validation
- Mandatory fields, `^LOT-\d{5}$`, AE conditional fields enforced by Pydantic in `contracts/`, not in the UI or by an LLM.
- Agent tool arguments go through a typed `TypeAdapter` before any service call.

## 3. State-transition integrity
- Only `domain/workflow.py` decides transitions (NEW->IN_REVIEW; IN_REVIEW->CLOSED only via approval; NEW->CLOSED and CLOSED->* rejected; same-state no-op).
- Mutations are inside one `SqlUnitOfWork.begin()` transaction (status + history + audit commit or roll back together); optimistic `record_version` checked.

## 4. HITL enforcement
- Closure needs a persisted approval by a REVIEWER different from the requester; AGENT/OPERATOR can never approve.
- The assistant's `approve_closure` tool never mutates; no code path lets a model fabricate approval.
- Denied attempts are audited.

## 5. Auditability
- Every mutating path calls `audit.record` inside the same transaction; hash chain intact (`/audit/verify`); append-only triggers not weakened; no claim of absolute immutability.
- Observable events only: route, tool names, outcomes, error codes, circuit-breaker events.

## 6. RAG grounding & citations
- Four stages present and ordered: FTS5 BM25, dense (BGE/FAISS IndexFlatIP, normalized), RRF (k=60), cross-encoder rerank.
- Every result carries `source_type`; SOP and historical-report evidence stay distinct; stale/superseded SOPs excluded by default.
- Answers are extractive or evidence-constrained, cite `source_type/source_id/chunk_id` (+ version/section/page for SOPs), include the scope statement, and abstain when evidence is insufficient. Wording is "evidence-constrained", never "zero hallucination".
- Index consistency: manifest model/dimension checked, no silent mixing, atomic replace with retained previous index.
- Cloud LLM (OpenRouter) is optional, off by default, receives only question + retrieved synthetic evidence, output citation-validated with extractive fallback, key never logged.

## 7. Policy boundary
- Prohibited determinations (causality, seriousness, expectedness, listedness, reportability, treatment, regulatory submission, autonomous closure) are blocked deterministically *before* retrieval or any model call.

## 8. Error handling
- Failures return typed errors (no stack traces to UI); failed index rebuild keeps the previous index; provider failure falls back; circuit breaker halts after 2 identical invalid attempts (`CIRCUIT_BREAKER_TRIGGERED`).

## 9. Test coverage
- New behavior has pytest coverage (unit, Hypothesis where valuable, HTTPX API); rollback, HITL, breaker, routing and prohibited-request tests still pass.
- Eval claims come from `eval/run_eval.py` runs - never invented numbers.

## 10. Security & architecture boundaries
- Only `psit.ui` imports Streamlit; UI imports only `psit.contracts` + httpx and never touches SQL/FAISS/workflow (`tests/test_architecture.py`).
- No secrets in repo; `X-Actor-*` demo auth is documented as non-production; uploads are size/type-checked and parsed locally.

## Output format
1. Verdict table (10 rows). 2. Findings ranked by severity with file:line and a concrete failing scenario. 3. Missing tests. 4. Residual risks.
