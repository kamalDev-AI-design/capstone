"""Embedding / reranking model adapters. All inference is local."""
import hashlib
import re
from dataclasses import dataclass

import numpy as np

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
STOP = set("a an the of to in on for and or is are was were be been what which who how does do did with by at from as it its this that these those about say says should can could would will".split())


def content_tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text) if w.lower() not in STOP and len(w) > 1]


# ---------------------------------------------------------------- embedders
class HashingEmbedder:
    """Deterministic lexical 'embedder' for unit tests only (profile=test). Never used in demo profiles."""
    name, version, dim, query_prefix = "hashing-test", "1", 256, ""

    def count_tokens(self, text: str) -> int:
        return len(_WORD.findall(text))

    def encode(self, texts: list[str], batch: int = 32) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype="float32")
        for i, t in enumerate(texts):
            toks = content_tokens(t)
            for w in toks + [a + "_" + b for a, b in zip(toks, toks[1:])]:
                h = int(hashlib.md5(w.encode()).hexdigest(), 16)
                out[i, h % self.dim] += 1.0 if (h >> 100) & 1 else -1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.maximum(norms, 1e-9)


class SentenceTransformerEmbedder:
    def __init__(self, name: str, dim: int, query_prefix: str = "", version: str = "1"):
        self.name, self.dim, self.query_prefix, self.version = name, dim, query_prefix, version
        self._m = None

    def _model(self):
        if self._m is None:
            from sentence_transformers import SentenceTransformer
            self._m = SentenceTransformer(self.name)
            self._m.max_seq_length = min(512, self._m.max_seq_length or 512)
            got = self._m.get_sentence_embedding_dimension()
            if got != self.dim:
                raise RuntimeError(f"{self.name} produced dimension {got}, expected {self.dim}")
        return self._m

    def count_tokens(self, text: str) -> int:
        return len(self._model().tokenizer.encode(text, add_special_tokens=False))

    def encode(self, texts: list[str], batch: int = 16) -> np.ndarray:
        v = self._model().encode(texts, batch_size=batch, normalize_embeddings=True, convert_to_numpy=True,
                                 show_progress_bar=False)
        return np.ascontiguousarray(v, dtype="float32")


# ---------------------------------------------------------------- rerankers
class OverlapReranker:
    """Deterministic stand-in for tests (profile=test)."""
    name = "overlap-test"

    def score(self, query: str, texts: list[str]) -> list[float]:
        q = set(content_tokens(query))
        if not q:
            return [0.0] * len(texts)
        return [len(q & set(content_tokens(t))) / len(q) for t in texts]


class CrossEncoderReranker:
    def __init__(self, name: str):
        self.name = name
        self._m = None

    def score(self, query: str, texts: list[str]) -> list[float]:
        if self._m is None:
            from sentence_transformers import CrossEncoder
            self._m = CrossEncoder(self.name, max_length=512)
        import torch
        s = self._m.predict([(query, t) for t in texts], activation_fn=torch.nn.Sigmoid(), batch_size=16,
                            show_progress_bar=False)
        return [float(x) for x in np.atleast_1d(s)]


@dataclass(frozen=True)
class Profile:
    name: str
    embed_model: str
    dim: int
    rerank_model: str
    threshold: float
    query_prefix: str = ""


PROFILES = {
    "full": Profile("full", "BAAI/bge-m3", 1024, "BAAI/bge-reranker-v2-m3", 0.40),
    "fast": Profile("fast", "BAAI/bge-small-en-v1.5", 384, "cross-encoder/ms-marco-MiniLM-L-6-v2", 0.40,
                    "Represent this sentence for searching relevant passages: "),
    "test": Profile("test", "hashing-test", 256, "overlap-test", 0.30),
}


def build_models(profile: Profile):
    if profile.name == "test":
        return HashingEmbedder(), OverlapReranker()
    return (SentenceTransformerEmbedder(profile.embed_model, profile.dim, profile.query_prefix),
            CrossEncoderReranker(profile.rerank_model))
