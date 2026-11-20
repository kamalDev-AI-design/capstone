from pathlib import Path

from psit.domain.errors import ForbiddenError
from psit.domain.models import Actor
from psit.rag.chunking import chunk_sop, index_text
from psit.rag.normalize import document_hash, normalize, text_hash
from psit.rag.parsers import (
    DocumentQuarantined, DocumentRejected, extract_sop_metadata, parse_file, version_key,
)

from . import audit

MAX_BYTES = 10 * 1024 * 1024


def require_writer(actor: Actor) -> None:
    if actor.role not in ("INTAKE_OPERATOR", "REVIEWER"):
        raise ForbiddenError("Only a human INTAKE_OPERATOR or REVIEWER may ingest documents or rebuild the index.")


class IngestionService:
    def __init__(self, uow, runtime):
        self.uow, self.rt = uow, runtime

    def _finish(self, tx, actor, request_id, filename, status, message, sha=None, version_id=None, chunks=0, key=None):
        tx.rag.log_run(filename=filename[:255], sha256=sha, status=status, message=message[:500],
                       document_version_id=version_id, chunk_count=chunks, started_at=audit.utcnow())
        audit.record(tx, actor, f"DOCUMENT_{status}", "DOCUMENT", (key or filename)[:80], request_id,
                     "SUCCESS" if status == "INGESTED" else status, {"filename": filename[:120], "chunks": chunks})
        return {"status": status, "message": message, "filename": filename, "doc_key": key, "chunk_count": chunks}

    def ingest(self, filename: str, data: bytes, actor: Actor, request_id: str) -> dict:
        require_writer(actor)
        filename = Path(filename).name
        now = audit.utcnow()
        if len(data) > MAX_BYTES:
            with self.uow.begin() as tx:
                return self._finish(tx, actor, request_id, filename, "REJECTED", "File larger than 10 MB.")
        try:
            parsed = parse_file(filename, data)
            pages = [(n, normalize(t)) for n, t in parsed.pages]
            full = normalize("\n\n".join(t for _, t in pages))
            meta = extract_sop_metadata(full)
        except DocumentQuarantined as e:
            with self.uow.begin() as tx:
                return self._finish(tx, actor, request_id, filename, "QUARANTINED", str(e))
        except DocumentRejected as e:
            with self.uow.begin() as tx:
                return self._finish(tx, actor, request_id, filename, "REJECTED", str(e))

        sha = document_hash(full)
        drafts = chunk_sop(pages, meta, self.rt.embedder.count_tokens)   # embedder-compatible tokenizer
        with self.uow.begin() as tx:
            if tx.rag.version_by_hash(sha):
                return self._finish(tx, actor, request_id, filename, "DUPLICATE",
                                    "Identical document content already ingested; skipped.", sha, key=meta["sop_id"])
            doc = tx.rag.get_or_create_document(meta["sop_id"], "SOP", meta["sop_title"], now)
            existing = tx.rag.versions_of(doc.id)
            if any(v.version == meta["version"] for v in existing):
                return self._finish(tx, actor, request_id, filename, "REJECTED",
                                    f"{meta['sop_id']} v{meta['version']} already exists with different content; bump the version.",
                                    sha, key=meta["sop_id"])
            if not drafts:
                return self._finish(tx, actor, request_id, filename, "REJECTED", "No chunkable content found.",
                                    sha, key=meta["sop_id"])
            newest = all(version_key(meta["version"]) > version_key(v.version) for v in existing)
            ver = tx.rag.add_version(document_id=doc.id, version=meta["version"], sha256=sha,
                                     effective_date=meta["effective_date"], active=newest, filename=filename,
                                     file_type=filename.rsplit(".", 1)[-1].lower(), page_count=parsed.page_count,
                                     ingested_at=now)
            if newest:
                for v in existing:
                    if v.active:
                        tx.rag.set_version_active(v.id, False)       # supersede older versions
            rows, fts = [], []
            for d in drafts:
                m = {**d.meta, "active": newest}
                rows.append(dict(chunk_id=d.chunk_id, parent_id=d.parent_id, source_type="SOP", source_id=meta["sop_id"],
                                 document_version_id=ver.id, text=d.text, text_hash=text_hash(d.text),
                                 section_path=d.section_path, page_number=d.page_number, sequence=d.sequence,
                                 active=newest, meta=m))
                fts.append(index_text("SOP", m, d.section_path, d.text))
            tx.rag.add_chunks(rows, fts)
            msg = f"Ingested {meta['sop_id']} v{meta['version']} ({len(rows)} chunks)" + (
                "" if newest else " as superseded (older version).")
            return self._finish(tx, actor, request_id, filename, "INGESTED", msg, sha, ver.id, len(rows), meta["sop_id"])

    def overview(self) -> dict:
        with self.uow.begin() as tx:
            return {"versions": tx.rag.list_versions(), "runs": tx.rag.list_runs()}
