import re
from concurrent.futures import ThreadPoolExecutor

from hypothesis import given, strategies as st
from sqlalchemy import text

from conftest import AE, AGENT, OP, PQC, REV, REV2
from psit.contracts.reports import LOT_PATTERN, ProductQualityComplaintCreate


def mk(client, body=PQC):
    r = client.post("/api/v1/reports", json=body, headers=OP)
    assert r.status_code == 201, r.text
    return r.json()["reference_id"]


def test_create_two_reports_unique_refs(client):
    a, b = mk(client), mk(client, AE)
    assert re.fullmatch(r"REF-\d{4}-\d{4}", a) and a != b
    assert client.get("/api/v1/reports", headers=OP).json()["total"] == 2


def test_validation(client):
    bad = {**PQC, "lot_number": "LOT-1"}
    assert client.post("/api/v1/reports", json=bad, headers=OP).status_code == 422
    no_ae = {k: v for k, v in AE.items() if k != "event_onset_date"}
    assert client.post("/api/v1/reports", json=no_ae, headers=OP).status_code == 422
    assert client.post("/api/v1/reports", json={**PQC, "patient_name": "X"}, headers=OP).status_code == 422
    assert client.post("/api/v1/reports", json={**PQC, "description": "call me at +1 415 555 0134"}, headers=OP).status_code == 422
    assert client.post("/api/v1/reports", json={**PQC, "description": "mail a.b@example.com"}, headers=OP).status_code == 422
    assert client.post("/api/v1/reports", json=PQC).status_code == 401


@given(st.text(max_size=12))
def test_lot_property(s):
    from pydantic import ValidationError
    try:
        ProductQualityComplaintCreate(**{**PQC, "lot_number": s})
        assert re.fullmatch(LOT_PATTERN, s.strip())
    except ValidationError:
        assert not re.fullmatch(LOT_PATTERN, s.strip())


def test_concurrent_reference_uniqueness(client):
    with ThreadPoolExecutor(10) as ex:
        refs = list(ex.map(lambda _: mk(client), range(30)))
    assert len(set(refs)) == 30


def test_transitions_and_hitl(client):
    ref = mk(client)
    t = lambda tgt, h=OP: client.post(f"/api/v1/reports/{ref}/transitions", json={"target_status": tgt}, headers=h)
    assert t("CLOSED").status_code == 409                       # NEW -> CLOSED rejected
    assert t("NEW").json()["changed"] is False                   # same-state no-op
    assert t("IN_REVIEW").json()["changed"] is True
    assert t("IN_REVIEW").json()["changed"] is False
    assert t("CLOSED").json()["error"]["code"] == "APPROVAL_REQUIRED"   # direct close blocked
    cr = client.post(f"/api/v1/reports/{ref}/closure-requests", json={}, headers=OP)
    assert cr.status_code == 201
    aid = cr.json()["approval_id"]
    ap = lambda h: client.post(f"/api/v1/closure-requests/{aid}/approve", json={}, headers=h)
    assert ap(AGENT).status_code == 403     # AI cannot approve
    assert ap(OP).status_code == 403        # operator cannot approve
    assert client.get(f"/api/v1/reports/{ref}", headers=OP).json()["status"] == "IN_REVIEW"
    assert ap(REV).status_code == 200
    d = client.get(f"/api/v1/reports/{ref}", headers=OP).json()
    assert d["status"] == "CLOSED" and d["history"][-1]["approval_id"] == aid
    assert t("IN_REVIEW").status_code == 409                     # CLOSED is terminal
    assert ap(REV2).status_code == 409                           # already approved


def test_requester_cannot_self_approve(client):
    ref = mk(client)
    client.post(f"/api/v1/reports/{ref}/transitions", json={"target_status": "IN_REVIEW"}, headers=OP)
    aid = client.post(f"/api/v1/reports/{ref}/closure-requests", json={}, headers=REV).json()["approval_id"]
    assert client.post(f"/api/v1/closure-requests/{aid}/approve", json={}, headers=REV).status_code == 403
    assert client.post(f"/api/v1/closure-requests/{aid}/approve", json={}, headers=REV2).status_code == 200


def test_closure_request_requires_in_review(client):
    ref = mk(client)
    assert client.post(f"/api/v1/reports/{ref}/closure-requests", json={}, headers=OP).status_code == 409


def test_audit_chain_and_tamper(client, app):
    ref = mk(client)
    client.post(f"/api/v1/reports/{ref}/transitions", json={"target_status": "CLOSED"}, headers=OP)
    v = client.get("/api/v1/audit/verify", headers=OP).json()
    assert v["valid"] and v["events_checked"] >= 2
    events = client.get(f"/api/v1/audit/events?entity_id={ref}", headers=OP).json()["items"]
    assert {e["outcome"] for e in events} >= {"SUCCESS", "DENIED"}
    with app.state.svc.engine.begin() as c:   # simulate privileged tampering (bypass append-only trigger)
        c.execute(text("DROP TRIGGER audit_no_update"))
        c.execute(text("UPDATE audit_events SET outcome='TAMPERED' WHERE id=1"))
    bad = client.get("/api/v1/audit/verify", headers=OP).json()
    assert bad["valid"] is False and bad["first_invalid_event_id"]


def test_audit_append_only_trigger(app):
    import pytest
    from sqlalchemy.exc import DatabaseError
    mk_client = None  # noqa
    with pytest.raises(DatabaseError):
        with app.state.svc.engine.begin() as c:
            c.execute(text("INSERT INTO audit_events (event_id,timestamp_utc,actor_id,actor_role,action_type,entity_type,entity_id,request_id,outcome,details,previous_event_hash,payload_hash,event_hash,application_version) VALUES ('e','t','a','r','x','y','z','q','o','{}','p','h','h','v')"))
            c.execute(text("DELETE FROM audit_events"))


def test_transaction_rollback(client, app, monkeypatch):
    from psit.services import approval as ap_mod
    ref = mk(client)
    client.post(f"/api/v1/reports/{ref}/transitions", json={"target_status": "IN_REVIEW"}, headers=OP)
    aid = client.post(f"/api/v1/reports/{ref}/closure-requests", json={}, headers=OP).json()["approval_id"]
    real = ap_mod.audit.record
    def boom(tx, actor, action, *a, **k):
        if action == "STATUS_CHANGED":
            raise RuntimeError("injected failure")
        return real(tx, actor, action, *a, **k)
    monkeypatch.setattr(ap_mod.audit, "record", boom)
    from fastapi.testclient import TestClient
    c2 = TestClient(app, raise_server_exceptions=False)
    assert c2.post(f"/api/v1/closure-requests/{aid}/approve", json={}, headers=REV).status_code == 500
    monkeypatch.undo()
    assert client.get(f"/api/v1/reports/{ref}", headers=OP).json()["status"] == "IN_REVIEW"   # rolled back
    assert client.get("/api/v1/closure-requests?status=PENDING", headers=OP).json()[0]["approval_id"] == aid


def test_filters_and_stats(client):
    mk(client); mk(client, AE)
    r = client.get("/api/v1/reports?report_type=SUSPECTED_ADVERSE_EVENT&intake_channel=TELEPHONE", headers=OP).json()
    assert r["total"] == 1 and r["items"][0]["event_onset_date"] == "2026-01-09"
    s = client.get("/api/v1/reports/stats", headers=OP).json()
    assert s["total"] == 2 and s["by_status"]["NEW"] == 2
    assert client.get("/api/v1/health").json()["database"] == "ok"
    assert "/api/v1/reports/{reference_id}/transitions" in client.get("/openapi.json").json()["paths"]
