# PSIT Agent - Pharma Safety Intake & Triage Knowledge Agent

A local-first **training prototype** with **fictional data only**. Not a pharmacovigilance system, medical device, or regulatory decision engine.

## Run (Windows / bash)
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,ui]"
# terminal 1 - backend (OpenAPI docs at http://127.0.0.1:8000/docs)
.venv/Scripts/python -m uvicorn psit.api.app:create_app --factory --port 8000
# terminal 2 - UI
.venv/Scripts/python -m streamlit run src/psit/ui/app.py
.venv/Scripts/python -m pytest
```
Env vars: see `.env.example`. `PSIT_MODEL_PROFILE` = `fast` (BGE-small + MiniLM reranker, default), `full` (BGE-M3 + BGE-Reranker-v2-M3, ~4.5 GB first download) or `test` (deterministic stand-ins, used by pytest only). Models run locally; first use downloads weights from Hugging Face once. The OpenRouter key is optional, off by default, and arrives with the LLM-provider stage.
Install RAG extras: `.venv/Scripts/python -m pip install -e ".[rag]"`. Generate fictional SOP files: `python data/synthetic/generate_sops.py`.

## Demo walkthrough (milestone A)
1. Dashboard -> **Load fictional demo data**.
2. **New Intake** -> *Fill sample data* -> submit; try `LOT-1` to see server-side validation.
3. Open a NEW report -> *Move to IN_REVIEW*. Expand *Demo: attempt prohibited transitions* -> force CLOSED (rejected).
4. As Olivia Operator, *Request closure*. Switch persona to the AI agent and click *Try to approve anyway* (403).
5. Switch to Rafael Reviewer -> **Approvals** -> Approve. Report becomes CLOSED.
6. **Audit Trail** -> *Verify hash chain*.

## Demo walkthrough (milestone B - knowledge)
1. Dashboard -> *Load fictional demo data* (36 reports).
2. **Documents & Index** -> upload everything in `data/synthetic/sops/` -> see INGESTED / DUPLICATE (copy) / QUARANTINED (image-only PDF) / REJECTED (no metadata, .xlsx) and SOP-QC-001 v1.0 marked SUPERSEDED.
3. **Knowledge Assistant** -> try the example chips: SOP question, `LOT-88392` exact lookup, paraphrase search, a prohibited causality question (scope boundary), an unanswerable question (abstains). Expand *Retrieval trace* to see BM25 / dense / RRF / rerank ranks.

## Demo walkthrough (milestone C - agent)
1. **Assistant** page -> try the suggested prompts: `show REF-2026-0004`, `move REF-2026-0004 to in review`, `request closure for REF-2026-0004`, an SOP question, `similar complaints about cracked seals`.
2. As Rafael Reviewer: `approve approval #1` -> the assistant refuses to approve and shows a **confirmation button**; only your click records the human approval.
3. As the AI persona, any mutating request is rejected. Ask `Did the drug cause the headache?` -> scope-boundary response, no retrieval.
4. **Settings** -> optional OpenRouter: set `OPENROUTER_API_KEY` in the *backend* environment, restart the API, toggle on. Off by default; falls back to extractive on any failure.
5. Circuit breaker: covered by `tests/test_agent.py` (third identical invalid tool call halts with `CIRCUIT_BREAKER_TRIGGERED`).

## Evaluation
`python eval/run_eval.py --profile fast --calibrate` - see [eval/README.md](eval/README.md) for measured results and caveats.

## Governance
`CLAUDE.md` (dev rules), `.claude/skills/pharma-intake-review/SKILL.md` (review checklist), and a `PostToolUse` hook (`.claude/hooks/log_edit.py`) that logs edit metadata only (never file contents) to `.claude/dev_audit.jsonl`.

## Documentation
The project wiki is in [docs/PSIT_Wiki.pdf](docs/PSIT_Wiki.pdf) (overview, personas and permissions, workflow, pages, RAG, agent, audit, API, evaluation, known gaps). Regenerate it after changes with `.venv/Scripts/python -m pip install -e ".[docs]"` then `.venv/Scripts/python docs/build_wiki.py`.

## Architecture
`ui (Streamlit, HTTP only) -> api (FastAPI /api/v1) -> services -> domain + repository interfaces -> SQLAlchemy/SQLite`.
Streamlit imports only `psit.contracts` and `httpx` (enforced by `tests/test_architecture.py`), so a React client can replace it using the generated OpenAPI spec.
Demo auth uses `X-Actor-Id` / `X-Actor-Role` headers - **not production authentication**.
