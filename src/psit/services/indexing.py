import time

import numpy as np

from psit.domain.models import Actor
from psit.rag.chunking import chunk_report, index_text
from psit.rag.normalize import text_hash
from psit.rag.vector_index import write_index

from . import audit
from .ingestion import require_writer


class IndexService:
    """Rebuilds the derived search artifacts (report projections, FTS5 rows, FAISS index + manifest)."""

    def __init__(self, uow, runtime):
        self.uow, self.rt = uow, runtime

    def rebuild(self, actor: Actor, request_id: str) -> dict:
        require_writer(actor)
        emb, t0 = self.rt.embedder, time.perf_counter()
        # Phase 1: refresh report projections (SQLite is the authority)
        with self.uow.begin() as tx:
            tx.rag.delete_chunks_of_type("HISTORICAL_REPORT")
            offset, rows, fts = 0, [], []
            while True:
                reports, total = tx.reports.search(status=None, report_type=None, channel=None, product=None,
                                                   date_from=None, date_to=None, limit=200, offset=offset)
                for r in reports:
                    for d in chunk_report(r, emb.count_tokens):
                        rows.append(dict(chunk_id=d.chunk_id, parent_id=d.parent_id, source_type="HISTORICAL_REPORT",
                                         source_id=r.reference_id, document_version_id=None, text=d.text,
                                         text_hash=text_hash(d.text), section_path=None, page_number=None,
                                         sequence=d.sequence, active=True, meta=d.meta))
                        fts.append(index_text("HISTORICAL_REPORT", d.meta, None, d.text))
                offset += 200
                if offset >= total:
                    break
            tx.rag.add_chunks(rows, fts)
            chunks = tx.rag.all_chunks()
            doc_count = tx.rag.counts()["documents"]
        # Phase 2: embed + atomically replace the index (outside any DB transaction)
        try:
            texts = [index_text(c.source_type, c.meta, c.section_path, c.text) for c in chunks]
            vectors = emb.encode(texts) if texts else np.zeros((0, emb.dim), dtype="float32")
            checksum = write_index(self.rt.index_dir, [c.chunk_id for c in chunks], vectors, emb.dim)
        except Exception as e:
            with self.uow.begin() as tx:
                tx.rag.add_manifest(index_version=tx.rag.next_index_version(), embedding_model=emb.name,
                                    embedding_dimension=emb.dim, document_count=doc_count, chunk_count=len(chunks),
                                    last_successful_build=None, checksum=None, status="FAILED")
                audit.record(tx, actor, "INDEX_REBUILT", "INDEX", "faiss", request_id, "FAILURE",
                             {"error": type(e).__name__})
            raise
        # Phase 3: publish manifest
        now = audit.utcnow()
        with self.uow.begin() as tx:
            tx.rag.supersede_active_manifests()
            m = tx.rag.add_manifest(index_version=tx.rag.next_index_version(), embedding_model=emb.name,
                                    embedding_dimension=emb.dim, document_count=doc_count, chunk_count=len(chunks),
                                    last_successful_build=now, checksum=checksum, status="ACTIVE")
            tx.rag.mark_indexed(emb.name, emb.version, now)
            audit.record(tx, actor, "INDEX_REBUILT", "INDEX", "faiss", request_id, "SUCCESS",
                         {"index_version": m.index_version, "chunks": len(chunks), "model": emb.name,
                          "seconds": round(time.perf_counter() - t0, 2)})
        self.rt.invalidate()
        return self.status()

    def status(self) -> dict:
        with self.uow.begin() as tx:
            latest, active = tx.rag.latest_manifest(), tx.rag.active_manifest()
            counts = tx.rag.counts()
            n_reports = tx.reports.stats()["total"]
        stale = active is None or n_reports != counts["report_sources"] or active.chunk_count != counts["chunks"]
        return {
            "built": active is not None, "stale": stale, "profile": self.rt.profile.name,
            "active_model": self.rt.profile.embed_model, "reranker": self.rt.profile.rerank_model,
            "manifest": None if latest is None else {
                "index_version": latest.index_version, "embedding_model": latest.embedding_model,
                "embedding_dimension": latest.embedding_dimension, "document_count": latest.document_count,
                "chunk_count": latest.chunk_count, "last_successful_build": latest.last_successful_build,
                "checksum": latest.checksum, "status": latest.status},
            "pending_reports": max(0, n_reports - counts["report_sources"]),
        }
