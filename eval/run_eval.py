"""Local retrieval/answer evaluation. Everything printed or saved is MEASURED by this run - nothing is invented.
Usage: python eval/run_eval.py [--profile fast|full|test] [--threshold 0.4] [--calibrate]
"""
import argparse
import json
import math
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from eval.gold import build_gold  # noqa: E402
from psit.agent.orchestrator import AgentOrchestrator  # noqa: E402
from psit.api.app import create_app  # noqa: E402
from psit.domain.models import Actor  # noqa: E402
from psit.infra.config import Settings  # noqa: E402

OP = Actor("eval.operator", "INTAKE_OPERATOR")
SOP_FILES = ["SOP-QC-001_v1.0.md", "SOP-QC-001_v2.0.md", "SOP-AE-002_v1.0.docx", "SOP-REV-003_v1.0.pdf",
             "SOP-LOT-004_v1.0.md", "SOP-CALL-006_v1.0.txt", "SOP-DOC-005_v1.0.md"]
TARGETS = {"exact_reference_top1": 1.0, "exact_lot_all_cited_relevant": 1.0, "recall_at_20": 0.95, "ndcg_at_10": 0.85,
           "citation_precision": 0.98, "correct_abstention": 0.95, "prohibited_blocked": 1.0,
           "stale_sop_returned": 0, "breaker_blocking": 1.0}


def src_of(chunk_id: str) -> str:
    return chunk_id.split(":")[0].split("@")[0]


def ranked_sources(trace: list[dict], k: int) -> list[str]:
    seen, out = set(), []
    for t in sorted(trace, key=lambda x: x["rerank_rank"]):
        s = src_of(t["chunk_id"])
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out[:k]


def ndcg(ranked: list[str], rel: set[str], k: int = 10) -> float:
    dcg = sum(1 / math.log2(i + 2) for i, s in enumerate(ranked[:k]) if s in rel)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(rel), k)))
    return dcg / ideal if ideal else 0.0


def mrr(ranked: list[str], rel: set[str], k: int = 10) -> float:
    return next((1 / (i + 1) for i, s in enumerate(ranked[:k]) if s in rel), 0.0)


def p95(xs: list[float]) -> float:
    return round(float(np.percentile(xs, 95)), 1) if xs else 0.0


def setup(profile: str, threshold: float | None):
    tmp = Path(tempfile.mkdtemp())
    app = create_app(Settings(database_url=f"sqlite:///{tmp / 'e.db'}", index_dir=str(tmp / "idx"), model_profile=profile,
                              rerank_threshold=threshold))
    svc = app.state.svc
    from psit.services.seed import load_demo_data
    load_demo_data(svc.intake, svc.workflow, svc.approvals)
    sops = ROOT / "data" / "synthetic" / "sops"
    for f in SOP_FILES:
        res = svc.ingestion.ingest(f, (sops / f).read_bytes(), OP, "eval")
        assert res["status"] == "INGESTED", res
    t = time.perf_counter()
    svc.index.rebuild(OP, "eval")
    return svc, round(time.perf_counter() - t, 1)


def run(profile: str, threshold: float | None, calibrate: bool) -> dict:
    svc, build_s = setup(profile, threshold)
    reports, _ = svc.intake.list(limit=200)
    reports = sorted(reports, key=lambda r: r.reference_id)
    versions = svc.ingestion.overview()["versions"]
    active = {v["doc_key"]: v["version"] for v in versions if v["active"]}
    gold = build_gold(reports, active)
    out = {"profile": profile, "threshold": svc.runtime.threshold, "embedding_model": svc.runtime.profile.embed_model,
           "reranker": svc.runtime.profile.rerank_model, "index_build_seconds": build_s, "n_queries": len(gold),
           "n_reports": len(reports), "per_query": []}
    lat, e2e = [], []
    recs, ndcgs, mrrs, cprec, fails = [], [], [], [], []
    exact_ref, exact_lot, abst, false_abst, blocked, false_block = [], [], [], [], [], []
    stale, filt_ok, mixed_ok, sop_ok, calib = 0, [], [], [], []
    svc.knowledge.search({"query": "warm up", "source_types": None}, OP, "warm")          # exclude model load from latency

    for g in gold:
        req = {"query": g["query"], "trace_limit": 20, **g["filters"]}
        if "source_types" in g:
            req["source_types"] = g["source_types"]
        t0 = time.perf_counter()
        r = svc.knowledge.search(req, OP, g["id"])
        lat.append(r["timings_ms"].get("total", (time.perf_counter() - t0) * 1000))
        t1 = time.perf_counter()
        svc.agent.run(g["query"] if not g["filters"] else g["query"], OP, g["id"] + "-agent")
        e2e.append((time.perf_counter() - t1) * 1000)
        cites = [c["source_id"] for c in r["citations"]]
        rel = set(g["relevant"])
        stale += sum(1 for c in r["citations"] if c.get("superseded"))
        for sid, ver in g.get("check_active_versions", {}).items():
            stale += sum(1 for c in r["citations"] if c["source_id"] == sid and c.get("version") != ver)
        ok = None
        if g["expect"] == "blocked":
            ok = r["blocked"]
            blocked.append(ok)
        elif g["expect"] == "abstain":
            ok = r["abstained"] and not r["blocked"]
            abst.append(ok)
            best = max([t["rerank_score"] for t in r["trace"] if not t["exact_id"]], default=0.0)
            calib.append(("unans", best, max([t["dense_score"] or 0 for t in r["trace"]], default=0.0)))
        else:
            false_block.append(r["blocked"])
            false_abst.append(r["abstained"])
            rs = ranked_sources(r["trace"], 20)
            recs.append(len(rel & set(rs)) / len(rel))
            ndcgs.append(ndcg(rs, rel))
            mrrs.append(mrr(rs, rel))
            if cites:
                cprec.append(sum(c in rel for c in cites) / len(cites))
            best = max([t["rerank_score"] for t in r["trace"] if not t["exact_id"]], default=0.0)
            calib.append(("ans", best if not any(t["exact_id"] for t in r["trace"]) else 1.0,
                          1.0 if any(t["exact_id"] for t in r["trace"]) else max([t["dense_score"] or 0 for t in r["trace"]], default=0.0)))
            ok = bool(cites) and bool(set(cites) & rel)
            if "exact_ref" in g:
                v = bool(cites) and cites[0] == g["exact_ref"]
                exact_ref.append(v)
                ok = v
            if "exact_lot" in g:
                v = bool(cites) and all(c in rel for c in cites)
                exact_lot.append(v)
                ok = v
            if "expect_status" in g:
                v = all(c["status"] == g["expect_status"] for c in r["citations"] if c["source_type"] == "HISTORICAL_REPORT")
                filt_ok.append(v)
                ok = ok and v
            if "expect_range" in g:
                lo, hi = g["expect_range"]
                by = {x.reference_id: x for x in reports}
                v = all(lo <= by[c].date_received.isoformat() <= hi for c in cites)
                filt_ok.append(v)
                ok = ok and v
            if "expect_types" in g and g["category"] == "mixed_sop_report":
                v = set(g["expect_types"]) <= {c["source_type"] for c in r["citations"]}
                mixed_ok.append(v)
                ok = ok and v
            if g["category"] == "sop_question":
                sop_ok.append(bool(set(cites) & rel))
        if not ok:
            fails.append({"id": g["id"], "category": g["category"], "query": g["query"], "expect": g["expect"],
                          "got": "blocked" if r["blocked"] else ("abstained" if r["abstained"] else cites[:5]),
                          "relevant": sorted(rel)[:6]})
        out["per_query"].append({"id": g["id"], "category": g["category"], "ok": bool(ok), "cites": cites,
                                 "irrelevant_cites": [c for c in cites if c not in rel] if g["expect"] == "answer" else []})

    # circuit breaker: identical invalid calls must always trip on the 3rd attempt
    class Stubborn:
        def __init__(self, call): self.call = call
        def next_call(self, mem): return self.call
    trips = [svc.agent.run("show REF-2026-0001", OP, f"cb{i}", proposer=Stubborn({"tool": "get_report", "arguments": {"reference_id": f"BAD{i}"}})).circuit_breaker
             for i in range(10)]

    mean = lambda xs: round(float(np.mean(xs)), 4) if xs else None
    rate = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
    out["metrics"] = {
        "recall_at_20": mean(recs), "ndcg_at_10": mean(ndcgs), "mrr_at_10": mean(mrrs),
        "citation_precision": mean(cprec), "correct_abstention": rate(abst), "false_abstention_on_answerable": rate(false_abst),
        "prohibited_blocked": rate(blocked), "false_block_on_answerable": rate(false_block),
        "exact_reference_top1": rate(exact_ref), "exact_lot_all_cited_relevant": rate(exact_lot),
        "stale_sop_returned": stale, "breaker_blocking": rate(trips), "filter_compliance": rate(filt_ok),
        "mixed_both_source_types": rate(mixed_ok), "sop_question_hit": rate(sop_ok),
        "p95_retrieval_ms": p95(lat), "p95_end_to_end_ms": p95(e2e),
        "median_retrieval_ms": round(float(np.median(lat)), 1),
    }
    out["by_category"] = {}
    for c in sorted({q["category"] for q in out["per_query"]}):
        xs = [q["ok"] for q in out["per_query"] if q["category"] == c]
        out["by_category"][c] = {"n": len(xs), "pass_rate": rate(xs)}
    out["targets_met"] = {k: (out["metrics"][k] is not None and (out["metrics"][k] >= v if k != "stale_sop_returned" else out["metrics"][k] <= v))
                          for k, v in TARGETS.items()}
    out["failures"] = fails
    if calibrate:
        un = sorted(rs for k, rs, ds in calib if k == "unans")
        an = sorted(rs for k, rs, ds in calib if k == "ans")
        out["score_distribution"] = {"unanswerable_max": un[-1] if un else None, "unanswerable_p90": un[int(.9 * len(un))] if un else None,
                                    "answerable_p10": an[int(.1 * len(an))] if an else None, "answerable_median": an[len(an) // 2] if an else None}
        grid = []
        for t in (0.02, 0.05, 0.1, 0.2, 0.4):
            for d in (None, 0.5, 0.55, 0.6, 0.65, 0.7):
                keep = lambda rs, ds: rs >= t or (d is not None and ds >= d)
                ua = [not keep(rs, ds) for k, rs, ds in calib if k == "unans"]
                an = [keep(rs, ds) for k, rs, ds in calib if k == "ans"]
                grid.append({"rerank_threshold": t, "dense_threshold": d, "correct_abstention": rate(ua), "answerable_retained": rate(an)})
        out["threshold_calibration"] = grid
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="fast")
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--calibrate", action="store_true")
    a = ap.parse_args()
    res = run(a.profile, a.threshold, a.calibrate)
    res["run_at"] = datetime.now().isoformat(timespec="seconds")
    d = ROOT / "eval" / "results"
    d.mkdir(exist_ok=True)
    tag = f"{a.profile}_t{res['threshold']}"
    (d / f"{tag}.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    m = res["metrics"]
    print(f"\nprofile={a.profile} threshold={res['threshold']} queries={res['n_queries']} reports={res['n_reports']}")
    for k, v in m.items():
        t = TARGETS.get(k)
        flag = "" if t is None else ("  OK" if res["targets_met"][k] else f"  MISS (target {t})")
        print(f"  {k:34} {v}{flag}")
    print("by category:", {k: v["pass_rate"] for k, v in res["by_category"].items()})
    if res.get("threshold_calibration"):
        print("calibration (rerank_thr, dense_thr -> correct_abstention, answerable_retained):")
        for g in res["threshold_calibration"]:
            print(f"   r>={g['rerank_threshold']:<5} d>={g['dense_threshold']}: abst={g['correct_abstention']} kept={g['answerable_retained']}")
    print(f"{len(res['failures'])} failing queries (first 12):")
    for f in res["failures"][:12]:
        print("  ", f)
    print("saved", d / f"{tag}.json")


if __name__ == "__main__":
    main()
