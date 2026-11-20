"""Stage 3: weighted Reciprocal Rank Fusion + structured-identifier detection."""
import re

IDENT_RE = re.compile(r"\b(REF-\d{4}-\d{4}|LOT-\d{5}|SOP-[A-Z]{2,6}-\d{3})\b", re.I)
RRF_K = 60


def extract_identifiers(query: str) -> list[str]:
    return list(dict.fromkeys(m.upper() for m in IDENT_RE.findall(query)))


def rrf(ranked: dict[str, list[str]], weights: dict[str, float], k: int = RRF_K) -> list[dict]:
    """ranked: {'bm25': [ids best-first], 'dense': [...]}. Dedupes by chunk_id; raw scores are never compared."""
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for name, ids in ranked.items():
        w = weights.get(name, 1.0)
        for r, cid in enumerate(ids, 1):
            scores[cid] = scores.get(cid, 0.0) + w / (k + r)
            ranks.setdefault(cid, {})[name] = r
    return [{"chunk_id": c, "rrf_score": s, "ranks": ranks[c]} for c, s in sorted(scores.items(), key=lambda x: -x[1])]


def fts_match_query(query: str, stop: set[str]) -> str:
    ids = extract_identifiers(query)
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", query)
             if w.lower() not in stop and len(w) > 1]
    terms = list(dict.fromkeys(ids + words))
    return " OR ".join('"' + t.replace('"', "") + '"' for t in terms)
