import sys, time, tempfile, json
from pathlib import Path
from fastapi.testclient import TestClient
from psit.api.app import create_app
from psit.infra.config import Settings

profile = sys.argv[1] if len(sys.argv) > 1 else "fast"
tmp = Path(tempfile.mkdtemp())
app = create_app(Settings(database_url=f"sqlite:///{tmp/'s.db'}", index_dir=str(tmp/'idx'), model_profile=profile))
c = TestClient(app)
H = {"X-Actor-Id": "operator.demo", "X-Actor-Role": "INTAKE_OPERATOR"}
print("seeded", c.post("/api/v1/admin/seed", headers=H).json())
sops = Path("data/synthetic/sops")
t = time.time()
for n in ["SOP-QC-001_v1.0.md","SOP-QC-001_v2.0.md","SOP-AE-002_v1.0.docx","SOP-REV-003_v1.0.pdf","SOP-LOT-004_v1.0.md","SOP-CALL-006_v1.0.txt","SOP-DOC-005_v1.0.md"]:
    r = c.post("/api/v1/documents?rebuild=false", files={"file": (n, (sops/n).read_bytes())}, headers=H)
    print(n, r.json()["status"], r.json().get("chunk_count"))
print("ingest s", round(time.time()-t,1)); t = time.time()
st = c.post("/api/v1/knowledge/index/rebuild", headers=H).json()
print("rebuild s", round(time.time()-t,1), st["manifest"])
qs = ["How quickly must a complaint be acknowledged?", "LOT-88392", "tablets turning to powder", "Can the AI approve closure?",
      "What is the capital of France?", "what does the SOP say about quarantine hold", "queasy after dose"]
for q in qs:
    t = time.time(); r = c.post("/api/v1/knowledge/search", json={"query": q}, headers=H).json()
    top = [(x["source_id"], x["relevance"]) for x in r["citations"][:3]]
    best = max((x["rerank_score"] for x in r["trace"]), default=None)
    print(f"{q!r:55} abst={r['abstained']} best_rerank={best} cites={top} {round(time.time()-t,2)}s")
