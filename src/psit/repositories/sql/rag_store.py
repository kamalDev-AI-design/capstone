"""Persistence for documents, chunks, FTS5 index, manifests and ingestion runs."""
import json
from datetime import datetime

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from psit.domain.models import Chunk

from .orm import ChunkRow, DocumentRow, DocumentVersionRow, IngestionRunRow, ManifestRow, SettingRow


def _chunk(r: ChunkRow) -> Chunk:
    return Chunk(r.chunk_id, r.parent_id, r.source_type, r.source_id, r.text, r.text_hash, r.section_path,
                 r.page_number, r.sequence, r.active, json.loads(r.meta))


class SqlRagStore:
    def __init__(self, s: Session):
        self.s = s

    # ---- documents / versions
    def version_by_hash(self, sha: str) -> DocumentVersionRow | None:
        return self.s.scalar(select(DocumentVersionRow).where(DocumentVersionRow.sha256 == sha))

    def get_or_create_document(self, doc_key: str, source_type: str, title: str, now: datetime) -> DocumentRow:
        d = self.s.scalar(select(DocumentRow).where(DocumentRow.doc_key == doc_key))
        if d is None:
            d = DocumentRow(doc_key=doc_key, source_type=source_type, title=title, created_at=now)
            self.s.add(d)
            self.s.flush()
        return d

    def versions_of(self, document_id: int) -> list[DocumentVersionRow]:
        return list(self.s.scalars(select(DocumentVersionRow).where(DocumentVersionRow.document_id == document_id)))

    def add_version(self, **kw) -> DocumentVersionRow:
        v = DocumentVersionRow(**kw)
        self.s.add(v)
        self.s.flush()
        return v

    def set_version_active(self, version_id: int, active: bool) -> None:
        self.s.execute(update(DocumentVersionRow).where(DocumentVersionRow.id == version_id).values(active=active))
        self.s.execute(update(ChunkRow).where(ChunkRow.document_version_id == version_id).values(active=active))

    def list_versions(self) -> list[dict]:
        q = (select(DocumentVersionRow, DocumentRow).join(DocumentRow, DocumentRow.id == DocumentVersionRow.document_id)
             .order_by(DocumentRow.doc_key, DocumentVersionRow.id.desc()))
        out = []
        for v, d in self.s.execute(q).all():
            n = self.s.scalar(select(func.count()).select_from(ChunkRow).where(ChunkRow.document_version_id == v.id))
            out.append({"doc_key": d.doc_key, "title": d.title, "version": v.version, "active": v.active,
                        "effective_date": v.effective_date, "filename": v.filename, "file_type": v.file_type,
                        "page_count": v.page_count, "sha256": v.sha256, "chunk_count": n or 0,
                        "ingested_at": v.ingested_at})
        return out

    def log_run(self, **kw) -> IngestionRunRow:
        r = IngestionRunRow(**kw)
        self.s.add(r)
        self.s.flush()
        return r

    def list_runs(self, limit: int = 50) -> list[IngestionRunRow]:
        return list(self.s.scalars(select(IngestionRunRow).order_by(IngestionRunRow.id.desc()).limit(limit)))

    # ---- chunks + FTS
    def add_chunks(self, rows: list[dict], fts_texts: list[str]) -> None:
        for r, ft in zip(rows, fts_texts):
            self.s.add(ChunkRow(**{**r, "meta": json.dumps(r["meta"], sort_keys=True)}))
            self.s.execute(text("INSERT INTO chunks_fts(chunk_id, text) VALUES (:c, :t)"), {"c": r["chunk_id"], "t": ft})
        self.s.flush()

    def delete_chunks_of_type(self, source_type: str) -> None:
        ids = self.s.scalars(select(ChunkRow.chunk_id).where(ChunkRow.source_type == source_type)).all()
        for i in range(0, len(ids), 500):
            batch = list(ids[i:i + 500])
            self.s.execute(text("DELETE FROM chunks_fts WHERE chunk_id IN (%s)" % ",".join(f":p{j}" for j in range(len(batch)))),
                           {f"p{j}": v for j, v in enumerate(batch)})
        self.s.execute(delete(ChunkRow).where(ChunkRow.source_type == source_type))

    def fts_search(self, match: str, limit: int, source_types: list[str] | None, include_inactive: bool) -> list[tuple[str, float]]:
        if not match:
            return []
        sql = ("SELECT f.chunk_id, bm25(chunks_fts) AS s FROM chunks_fts f JOIN chunks c ON c.chunk_id = f.chunk_id "
               "WHERE chunks_fts MATCH :m")
        params: dict = {"m": match, "n": limit}
        if not include_inactive:
            sql += " AND c.active = 1"
        if source_types:
            sql += " AND c.source_type IN (%s)" % ",".join(f":t{i}" for i in range(len(source_types)))
            params.update({f"t{i}": t for i, t in enumerate(source_types)})
        sql += " ORDER BY s LIMIT :n"
        return [(r[0], float(r[1])) for r in self.s.execute(text(sql), params)]

    def get_chunks(self, ids: list[str]) -> dict[str, Chunk]:
        out: dict[str, Chunk] = {}
        for i in range(0, len(ids), 500):
            rows = self.s.scalars(select(ChunkRow).where(ChunkRow.chunk_id.in_(ids[i:i + 500]))).all()
            out.update({r.chunk_id: _chunk(r) for r in rows})
        return out

    def all_chunks(self) -> list[Chunk]:
        return [_chunk(r) for r in self.s.scalars(select(ChunkRow).order_by(ChunkRow.chunk_id))]

    def mark_indexed(self, model: str, version: str, now: datetime) -> None:
        self.s.execute(update(ChunkRow).values(embedding_model=model, embedding_version=version, indexed_at=now))

    def counts(self) -> dict:
        n = lambda q: self.s.scalar(q) or 0
        return {
            "chunks": n(select(func.count()).select_from(ChunkRow)),
            "documents": n(select(func.count(func.distinct(ChunkRow.source_id)))),
            "report_sources": n(select(func.count(func.distinct(ChunkRow.source_id))).where(ChunkRow.source_type == "HISTORICAL_REPORT")),
        }

    # ---- manifests
    def active_manifest(self) -> ManifestRow | None:
        return self.s.scalar(select(ManifestRow).where(ManifestRow.status == "ACTIVE").order_by(ManifestRow.id.desc()))

    def latest_manifest(self) -> ManifestRow | None:
        return self.s.scalar(select(ManifestRow).order_by(ManifestRow.id.desc()))

    def add_manifest(self, **kw) -> ManifestRow:
        m = ManifestRow(**kw)
        self.s.add(m)
        self.s.flush()
        return m

    def supersede_active_manifests(self) -> None:
        self.s.execute(update(ManifestRow).where(ManifestRow.status == "ACTIVE").values(status="SUPERSEDED"))

    def next_index_version(self) -> int:
        return (self.s.scalar(select(func.max(ManifestRow.index_version))) or 0) + 1

    # ---- settings
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        r = self.s.get(SettingRow, key)
        return r.value if r else default

    def set_setting(self, key: str, value: str) -> None:
        r = self.s.get(SettingRow, key)
        if r:
            r.value = value
        else:
            self.s.add(SettingRow(key=key, value=value))
        self.s.flush()
