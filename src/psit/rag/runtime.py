"""Lazy holder for local models and the loaded FAISS index."""
from pathlib import Path

from .models import PROFILES, build_models
from .vector_index import IndexMismatchError, VectorIndex, load_index


class RagRuntime:
    def __init__(self, profile: str, index_dir: str, threshold: float | None = None, embedder=None, reranker=None):
        if profile not in PROFILES:
            raise ValueError(f"Unknown model profile {profile!r}; choose from {list(PROFILES)}")
        self.profile = PROFILES[profile]
        self.index_dir = Path(index_dir) / profile
        self.threshold = threshold if threshold is not None else self.profile.threshold
        self._embedder, self._reranker = embedder, reranker
        self._index: VectorIndex | None = None
        self._index_key: str | None = None

    def _models(self):
        if self._embedder is None or self._reranker is None:
            emb, rer = build_models(self.profile)
            self._embedder = self._embedder or emb
            self._reranker = self._reranker or rer

    @property
    def embedder(self):
        self._models()
        return self._embedder

    @property
    def reranker(self):
        self._models()
        return self._reranker

    def index_for(self, manifest) -> VectorIndex:
        if manifest.embedding_model != self.embedder.name or manifest.embedding_dimension != self.embedder.dim:
            raise IndexMismatchError(
                f"Index built with {manifest.embedding_model} ({manifest.embedding_dimension}d) but the active model is "
                f"{self.embedder.name} ({self.embedder.dim}d); rebuild required. Models are never mixed.")
        if self._index is None or self._index_key != manifest.checksum:
            self._index = load_index(self.index_dir, manifest.embedding_dimension, manifest.checksum)
            self._index_key = manifest.checksum
        return self._index

    def invalidate(self) -> None:
        self._index, self._index_key = None, None
