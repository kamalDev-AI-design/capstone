"""FAISS exact index (IndexFlatIP over L2-normalized vectors). A derived artifact; SQLite is the authority."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np


class IndexMismatchError(Exception):
    """Index missing/inconsistent with manifest or model; a rebuild is required."""


def _sha(path_a: Path, path_b: Path) -> str:
    h = hashlib.sha256()
    h.update(path_a.read_bytes())
    h.update(path_b.read_bytes())
    return h.hexdigest()


class VectorIndex:
    def __init__(self, ids: list[str], index, dim: int):
        self.ids, self.index, self.dim = ids, index, dim

    def search(self, qvec: np.ndarray, k: int) -> list[tuple[str, float]]:
        if not self.ids:
            return []
        scores, rows = self.index.search(np.ascontiguousarray(qvec, dtype="float32"), min(k, len(self.ids)))
        return [(self.ids[r], float(s)) for r, s in zip(rows[0], scores[0]) if r >= 0]


def write_index(directory: Path, ids: list[str], vectors: np.ndarray, dim: int) -> str:
    """Build into temp files, then atomically replace; the previous index is retained as *.prev."""
    import faiss
    if vectors.ndim != 2 or vectors.shape[1] != dim:
        raise IndexMismatchError(f"Vector dimension {vectors.shape} does not match expected {dim}")
    directory.mkdir(parents=True, exist_ok=True)
    idx_tmp, ids_tmp = directory / "index.tmp", directory / "ids.tmp.json"
    index = faiss.IndexFlatIP(dim)
    if len(ids):
        index.add(np.ascontiguousarray(vectors, dtype="float32"))
    faiss.write_index(index, str(idx_tmp))
    ids_tmp.write_text(json.dumps(ids), encoding="utf-8")
    checksum = _sha(idx_tmp, ids_tmp)
    final_idx, final_ids = directory / "index.faiss", directory / "ids.json"
    if final_idx.exists():
        os.replace(final_idx, directory / "index.prev.faiss")
        os.replace(final_ids, directory / "ids.prev.json")
    os.replace(idx_tmp, final_idx)
    os.replace(ids_tmp, final_ids)
    return checksum


def load_index(directory: Path, expected_dim: int, expected_checksum: str | None) -> VectorIndex:
    import faiss
    idx_path, ids_path = directory / "index.faiss", directory / "ids.json"
    if not idx_path.exists() or not ids_path.exists():
        raise IndexMismatchError("Vector index files are missing; rebuild required.")
    if expected_checksum and _sha(idx_path, ids_path) != expected_checksum:
        raise IndexMismatchError("Vector index checksum differs from manifest; rebuild required.")
    index = faiss.read_index(str(idx_path))
    if index.d != expected_dim:
        raise IndexMismatchError(f"Index dimension {index.d} != model dimension {expected_dim}; rebuild required.")
    return VectorIndex(json.loads(ids_path.read_text(encoding="utf-8")), index, index.d)
