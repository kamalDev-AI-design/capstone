"""Four-stage hybrid retrieval -> evidence -> cited / abstaining answer. Deterministic policy runs first."""
import hashlib
import time

from psit.agent import policy
from psit.domain.models import Actor, Chunk
from psit.rag.chunking import index_text
from psit.rag.context import ABSTAIN_MESSAGE, SCOPE_STATEMENT, Candidate, build_context, citation_for, extractive_answer
from psit.rag.fusion import IDENT_RE, extract_identifiers, fts_match_query, rrf
from psit.rag.models import STOP, content_tokens

from . import audit

BM25_K, DENSE_K, RERANK_K, OVERFETCH = 30, 30, 25, 150


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)


class KnowledgeService:
    def __init__(self, uow, runtime, llm=None):
        self.uow, self.rt, self.llm = uow, runtime, llm

    def _base(self, route: str, **kw) -> dict:
        return {"route": route, "answer": "", "abstained": False, "abstain_reason": None, "blocked": False,
                "block_category": None, "scope_statement": SCOPE_STATEMENT, "citations": [], "trace": [],
                "timings_ms": {}, "index_stale": False, "answer_mode": "extractive", **kw}

    def search(self, req: dict, actor: Actor, request_id: str) -> dict:
        t_all = time.perf_counter()
        query: str = req["query"]
        qhash = hashlib.sha256(query.encode()).hexdigest()[:16]

        decision = policy.check(query)
        if decision.blocked:
            with self.uow.begin() as tx:
                audit.record(tx, actor, "POLICY_BLOCKED", "KNOWLEDGE", "search", request_id, "BLOCKED",
                             {"category": decision.category, "query_hash": qhash})
            return self._base("PROHIBITED_REQUEST", answer=decision.message, blocked=True,
                              block_category=decision.category, scope_statement=decision.message)

        with self.uow.begin() as tx:
            manifest = tx.rag.active_manifest()
            counts = tx.rag.counts()
            n_reports = tx.reports.stats()["total"]
        stale = manifest is None or n_reports != counts["report_sources"]
        if manifest is None:
            return self._base("HYBRID_KNOWLEDGE_LOOKUP", abstained=True, abstain_reason="INDEX_NOT_BUILT",
                              answer="The knowledge index has not been built yet. Ingest documents and rebuild the index.",
                              index_stale=True)
        index = self.rt.index_for(manifest)        # raises IndexMismatchError -> 409 (never mixes models)
        emb, timings = self.rt.embedder, {}
        source_types = req.get("source_types") or None
        include_old = bool(req.get("include_superseded"))

        # Allowed report refs by live status/date/type filters (SQLite is the authority)
        allowed_refs = None
        if any(req.get(k) for k in ("status", "report_type", "date_from", "date_to")):
            with self.uow.begin() as tx:
                items, _ = tx.reports.search(status=req.get("status"), report_type=req.get("report_type"), channel=None,
                                             product=None, date_from=req.get("date_from"), date_to=req.get("date_to"),
                                             limit=200, offset=0)
                allowed_refs = {r.reference_id for r in items}

        # Stage 1 - sparse (FTS5 BM25)
        t0 = time.perf_counter()
        with self.uow.begin() as tx:
            bm_hits = tx.rag.fts_search(fts_match_query(query, STOP), OVERFETCH, source_types, include_old)
        timings["bm25"] = _ms(t0)
        # Stage 2 - dense (FAISS IndexFlatIP over normalized vectors)
        t0 = time.perf_counter()
        qv = emb.encode([emb.query_prefix + query])
        dense_hits = index.search(qv, OVERFETCH)
        timings["dense"] = _ms(t0)

        with self.uow.begin() as tx:
            chunks = tx.rag.get_chunks(list({c for c, _ in bm_hits} | {c for c, _ in dense_hits}))

        def ok(c: Chunk | None) -> bool:
            if c is None:
                return False
            if not include_old and not c.active:
                return False
            if source_types and c.source_type not in source_types:
                return False
            if allowed_refs is not None and c.source_type == "HISTORICAL_REPORT" and c.source_id not in allowed_refs:
                return False
            return True

        bm_ids = [c for c, _ in bm_hits if ok(chunks.get(c))][:BM25_K]
        dn_ids = [c for c, _ in dense_hits if ok(chunks.get(c))][:DENSE_K]

        # Stage 3 - RRF (k=60); BM25 weight raised for exact structured identifiers
        t0 = time.perf_counter()
        idents = extract_identifiers(query)
        fused = rrf({"bm25": bm_ids, "dense": dn_ids}, {"bm25": 1.25 if idents else 1.0, "dense": 1.0})
        timings["fusion"] = _ms(t0)
        top = fused[:RERANK_K]

        # Stage 4 - cross-encoder rerank
        t0 = time.perf_counter()
        cands = []
        for rank, f in enumerate(top, 1):
            ch = chunks[f["chunk_id"]]
            cands.append(Candidate(chunk=ch, rrf_score=f["rrf_score"], ranks=f["ranks"], rrf_rank=rank))
        dscore = dict(dense_hits)
        for c in cands:
            c.dense_score = dscore.get(c.chunk.chunk_id)
        texts = [index_text(c.chunk.source_type, c.chunk.meta, c.chunk.section_path, c.chunk.text) for c in cands]
        scores = self.rt.reranker.score(query, texts) if cands else []
        for c, s, t in zip(cands, scores, texts):
            c.rerank_score = s
            c.exact_id = any(i in t.upper() for i in idents)
        for r, c in enumerate(sorted(cands, key=lambda x: -x.rerank_score), 1):
            c.rerank_rank = r
        timings["rerank"] = _ms(t0)

        pure_ident = bool(idents) and not content_tokens(IDENT_RE.sub(" ", query))   # identifier-only query: exact matches or nothing
        evidence = build_context(cands, self.rt.threshold, exact_only=pure_ident)
        selected = {c.chunk.chunk_id for c in evidence}
        trace = [{"chunk_id": c.chunk.chunk_id, "source_type": c.chunk.source_type, "bm25_rank": c.ranks.get("bm25"),
                  "dense_rank": c.ranks.get("dense"), "rrf_rank": c.rrf_rank, "rrf_score": round(c.rrf_score, 5),
                  "rerank_rank": c.rerank_rank, "rerank_score": round(c.rerank_score, 3), "exact_id": c.exact_id,
                  "dense_score": None if c.dense_score is None else round(c.dense_score, 3),
                  "selected": c.chunk.chunk_id in selected}
                 for c in sorted(cands, key=lambda x: x.rerank_rank)[:req.get("trace_limit", 12)]]
        route = "HYBRID_KNOWLEDGE_LOOKUP"
        resp = self._base(route, trace=trace, index_stale=stale, timings_ms=timings,
                          counts={"bm25": len(bm_ids), "dense": len(dn_ids), "fused": len(fused), "reranked": len(cands),
                                  "evidence": len(evidence)})
        if not evidence:
            resp.update(abstained=True, abstain_reason="INSUFFICIENT_EVIDENCE", answer=ABSTAIN_MESSAGE)
        else:
            answer, citations = extractive_answer(query, evidence)
            # live workflow status for report citations (chunk metadata can lag behind SQLite)
            with self.uow.begin() as tx:
                for c in citations:
                    if c["source_type"] == "HISTORICAL_REPORT":
                        r = tx.reports.get(c["source_id"])
                        c["status"] = r.status.value if r else c.get("status")
            resp.update(answer=answer, citations=citations)
            if self.llm is not None:
                resp.update(self.llm.refine(query, evidence, resp))
        timings["total"] = _ms(t_all)
        with self.uow.begin() as tx:
            audit.record(tx, actor, "KNOWLEDGE_SEARCH_COMPLETED", "KNOWLEDGE", "search", request_id,
                         "ABSTAINED" if resp["abstained"] else "SUCCESS",
                         {"query_hash": qhash, "route": route, "chunks": [c.chunk.chunk_id for c in evidence],
                          "mode": resp["answer_mode"], "total_ms": timings["total"]})
        return resp
