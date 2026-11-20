import json

import httpx
import pytest
from fastapi.testclient import TestClient

from conftest import AGENT, OP
from psit.api.app import create_app
from psit.infra.config import Settings
from psit.rag.llm import validate_generated

from test_rag import SOPS  # noqa: F401

Q = "How many business days do I have to acknowledge a complaint?"
KEY = "sk-or-test-SECRET-123"


def make(tmp_path, handler):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'l.db'}", index_dir=str(tmp_path / "i"),
                              model_profile="test", auto_migrate=True))
    app.state.svc.llm._client = httpx.Client(transport=httpx.MockTransport(handler))
    c = TestClient(app)
    for n in ("SOP-QC-001_v2.0.md", "SOP-REV-003_v1.0.pdf"):
        c.post("/api/v1/documents?rebuild=false", files={"file": (n, (SOPS / n).read_bytes())}, headers=OP)
    c.post("/api/v1/knowledge/index/rebuild", headers=OP)
    return c


def enable(c, monkeypatch, key=KEY):
    if key:
        monkeypatch.setenv("OPENROUTER_API_KEY", key)
    else:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert c.put("/api/v1/settings/llm", json={"provider": "OPENROUTER", "model": "openai/gpt-4o-mini"}, headers=OP).status_code == 200


def ask(c):
    return c.post("/api/v1/knowledge/search", json={"query": Q}, headers=OP).json()


def ok_handler(seen):
    def h(req: httpx.Request):
        seen.append(req)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Acknowledge within 2 business days [1]."}}]})
    return h


def test_off_by_default_never_calls_network(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)           # key alone is not enough
    c = make(tmp_path, ok_handler(seen))
    r = ask(c)
    assert r["answer_mode"] == "extractive" and not seen
    s = c.get("/api/v1/settings/llm", headers=OP).json()
    assert s["provider"] == "EXTRACTIVE" and s["key_configured"] and KEY not in json.dumps(s)


def test_enabled_uses_openrouter_with_validated_citations(tmp_path, monkeypatch):
    seen = []
    c = make(tmp_path, ok_handler(seen))
    enable(c, monkeypatch)
    r = ask(c)
    assert r["answer_mode"] == "openrouter:openai/gpt-4o-mini" and "[1]" in r["answer"] and r["citations"]
    req = seen[0]
    body = json.loads(req.content)
    assert req.headers["authorization"] == f"Bearer {KEY}" and body["temperature"] == 0 and body["max_tokens"] <= 500
    assert "business days" in body["messages"][1]["content"]                      # only question + retrieved evidence
    ev = json.dumps(c.get("/api/v1/audit/events?limit=50", headers=OP).json())
    assert KEY not in ev                                                          # key never audited


def test_fallbacks(tmp_path, monkeypatch):
    c = make(tmp_path, lambda req: httpx.Response(500))
    enable(c, monkeypatch)
    r = ask(c)
    assert r["answer_mode"] == "extractive" and "unavailable" in r["llm_notice"] and r["citations"]
    bad = make(tmp_path / "b", lambda req: httpx.Response(200, json={"choices": [{"message": {"content": "Made up [9]."}}]})) \
        if (tmp_path / "b").mkdir() is None else None
    enable(bad, monkeypatch)
    r = ask(bad)
    assert r["answer_mode"] == "extractive" and "citation validation" in r["llm_notice"]
    nokey = make(tmp_path / "n", ok_handler([])) if (tmp_path / "n").mkdir() is None else None
    enable(nokey, monkeypatch, key=None)
    assert ask(nokey)["answer_mode"] == "extractive"


def test_insufficient_evidence_from_model_abstains(tmp_path, monkeypatch):
    c = make(tmp_path, lambda req: httpx.Response(200, json={"choices": [{"message": {"content": "INSUFFICIENT_EVIDENCE"}}]}))
    enable(c, monkeypatch)
    r = ask(c)
    assert r["abstained"] and not r["citations"]


def test_prohibited_question_never_reaches_provider(tmp_path, monkeypatch):
    seen = []
    c = make(tmp_path, ok_handler(seen))
    enable(c, monkeypatch)
    r = c.post("/api/v1/knowledge/search", json={"query": "Did the drug cause the headache?"}, headers=OP).json()
    assert r["blocked"] and not seen


def test_agent_cannot_change_settings_and_model_validated(tmp_path, monkeypatch):
    c = make(tmp_path, ok_handler([]))
    assert c.put("/api/v1/settings/llm", json={"provider": "OPENROUTER", "model": "openai/gpt-4o-mini"}, headers=AGENT).status_code == 403
    assert c.put("/api/v1/settings/llm", json={"provider": "OPENROUTER", "model": "bad model!"}, headers=OP).status_code == 422


def test_validate_generated():
    assert validate_generated("Fact [1] and [2].", 2) and not validate_generated("No cites.", 2) and not validate_generated("x [3]", 2)
