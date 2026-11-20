"""Context construction (diversified) and extractive, citation-bearing answers."""
import re
from dataclasses import dataclass, field

from psit.domain.models import Chunk

from .models import content_tokens

SCOPE_STATEMENT = (
    "This response summarizes fictional training evidence only. It does not assess causality, seriousness, "
    "expectedness, treatment, or regulatory reportability."
)
ABSTAIN_MESSAGE = ("I could not find sufficient evidence in the ingested fictional SOPs and historical reports to "
                   "answer this. No answer is given rather than guessing from outside knowledge.")


@dataclass
class Candidate:
    chunk: Chunk
    rrf_score: float = 0.0
    ranks: dict = field(default_factory=dict)
    rrf_rank: int = 0
    rerank_score: float = 0.0
    rerank_rank: int = 0
    exact_id: bool = False
    dense_score: float | None = None


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(content_tokens(a)), set(content_tokens(b))
    return len(sa & sb) / max(1, len(sa | sb))


def build_context(cands: list[Candidate], threshold: float, top_n: int = 5, max_chunks: int = 6,
                  per_parent: int = 2, exact_only: bool = False) -> list[Candidate]:
    """cands must be sorted by relevance. Keeps candidates above threshold (or exact-ID matches),
    max N per parent, and drops near-duplicates."""
    chosen: list[Candidate] = []
    per: dict[str, int] = {}
    for c in sorted(cands, key=lambda x: (not x.exact_id, -x.rerank_score)):
        if len(chosen) >= min(top_n, max_chunks):
            break
        if exact_only and not c.exact_id:
            continue            # pure identifier lookup: return only exact identifier matches
        if not (c.exact_id or c.rerank_score >= threshold):
            continue
        if per.get(c.chunk.parent_id, 0) >= per_parent:
            continue
        if any(c.chunk.text_hash == k.chunk.text_hash or _jaccard(c.chunk.text, k.chunk.text) > 0.9 for k in chosen):
            continue
        chosen.append(c)
        per[c.chunk.parent_id] = per.get(c.chunk.parent_id, 0) + 1
    return chosen


def _best_sentences(query: str, text: str, n: int = 2) -> str:
    from .chunking import split_sentences
    q = set(content_tokens(query))
    sents = [s for para in text.split("\n") for s in split_sentences(para)] or [text]
    scored = sorted(range(len(sents)), key=lambda i: (-len(q & set(content_tokens(sents[i]))), i))
    keep = sorted(i for i in scored[:n] if q & set(content_tokens(sents[i]))) or [0]
    return " ".join(sents[i] for i in keep)


def citation_for(n: int, c: Candidate) -> dict:
    ch, m = c.chunk, c.chunk.meta
    cit = {"n": n, "source_type": ch.source_type, "source_id": ch.source_id, "chunk_id": ch.chunk_id,
           "relevance": round(c.rerank_score, 3), "exact_id_match": c.exact_id}
    if ch.source_type == "SOP":
        cit.update(title=m.get("sop_title"), version=m.get("version"), section=ch.section_path,
                   page=ch.page_number, superseded=not ch.active)
    else:
        cit.update(title=f"{m.get('product_name')} · {m.get('lot_number')}", status=m.get("status"),
                   report_type=m.get("report_type"))
    return cit


def extractive_answer(query: str, evidence: list[Candidate]) -> tuple[str, list[dict]]:
    citations, sop_lines, rep_lines = [], [], []
    for n, c in enumerate(evidence, 1):
        citations.append({**citation_for(n, c), "snippet": c.chunk.text[:400]})
        line = f"- {_best_sentences(query, c.chunk.text)} [{n}]"
        (sop_lines if c.chunk.source_type == "SOP" else rep_lines).append(line)
    parts = []
    if sop_lines:
        parts.append("**From SOP documents (procedural authority):**\n" + "\n".join(sop_lines))
    if rep_lines:
        parts.append("**From historical fictional reports (precedent only, not procedure):**\n" + "\n".join(rep_lines))
    return "\n\n".join(parts), citations
