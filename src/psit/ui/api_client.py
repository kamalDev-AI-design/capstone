"""HTTP client for the FastAPI backend. The ONLY way the UI touches business state."""
import os
import uuid
from typing import Any

import httpx

from psit.contracts.agent import AgentResponse
from psit.contracts.knowledge import DocumentOverview, IndexStatus, IngestResult, KnowledgeAnswer
from psit.contracts.reports import (
    ApprovalOut, AuditEventList, AuditVerifyResult, ReportDetail, ReportList, ReportStats, TransitionResult,
)

BASE_URL = os.getenv("PSIT_API_BASE_URL", "http://127.0.0.1:8000/api/v1")

PERSONAS = {
    "Olivia Operator (intake)": ("operator.demo", "INTAKE_OPERATOR"),
    "Rafael Reviewer (human reviewer)": ("reviewer.demo", "REVIEWER"),
    "Rhea Reviewer-2 (human reviewer)": ("reviewer.two", "REVIEWER"),
    "PSIT Agent (AI - cannot approve)": ("agent.psit", "AGENT"),
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, fields: list[str] | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.fields = status, code, message, fields or []


class BackendUnavailable(Exception):
    pass


class ApiClient:
    def __init__(self, actor_id: str, role: str, base_url: str = BASE_URL):
        self._c = httpx.Client(base_url=base_url, timeout=30,
                               headers={"X-Actor-Id": actor_id, "X-Actor-Role": role})

    def _call(self, method: str, path: str, **kw) -> Any:
        kw.setdefault("headers", {})["X-Request-Id"] = uuid.uuid4().hex
        try:
            r = self._c.request(method, path, **kw)
        except httpx.HTTPError as e:
            raise BackendUnavailable(str(e)) from e
        if r.status_code >= 400:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if r.status_code == 422 and isinstance(body.get("detail"), list):
                fields = [f"{d['loc'][-1]}: {d['msg']}" for d in body["detail"]]
                raise ApiError(422, "VALIDATION_ERROR", "Validation failed", fields)
            err = body.get("error") or (body.get("detail") or {}).get("error") or {}
            raise ApiError(r.status_code, err.get("code", "HTTP_ERROR"), err.get("message", r.text[:200]))
        return r.json()

    # --- system
    def health(self) -> dict:
        return self._call("GET", "/health")

    def seed_demo(self) -> int:
        return self._call("POST", "/admin/seed")["created"]

    # --- reports
    def create_report(self, payload: dict) -> dict:
        return self._call("POST", "/reports", json=payload)

    def list_reports(self, **params) -> ReportList:
        return ReportList.model_validate(self._call("GET", "/reports", params={k: v for k, v in params.items() if v not in (None, "")}))

    def stats(self) -> ReportStats:
        return ReportStats.model_validate(self._call("GET", "/reports/stats"))

    def get_report(self, ref: str) -> ReportDetail:
        return ReportDetail.model_validate(self._call("GET", f"/reports/{ref}"))

    def transition(self, ref: str, target: str) -> TransitionResult:
        return TransitionResult.model_validate(self._call("POST", f"/reports/{ref}/transitions", json={"target_status": target}))

    # --- closure / HITL
    def request_closure(self, ref: str, note: str | None = None) -> ApprovalOut:
        return ApprovalOut.model_validate(self._call("POST", f"/reports/{ref}/closure-requests", json={"note": note}))

    def list_closure_requests(self, status: str | None = None) -> list[ApprovalOut]:
        return [ApprovalOut.model_validate(a) for a in self._call("GET", "/closure-requests", params={"status": status} if status else None)]

    def approve(self, approval_id: int, note: str | None = None) -> ApprovalOut:
        return ApprovalOut.model_validate(self._call("POST", f"/closure-requests/{approval_id}/approve", json={"note": note}))

    # --- audit
    def audit_events(self, entity_id: str | None = None, limit: int = 200) -> AuditEventList:
        p = {"limit": limit, **({"entity_id": entity_id} if entity_id else {})}
        return AuditEventList.model_validate(self._call("GET", "/audit/events", params=p))

    def verify_audit(self) -> AuditVerifyResult:
        return AuditVerifyResult.model_validate(self._call("GET", "/audit/verify"))

    # --- knowledge / documents
    def knowledge_search(self, query: str, **filters) -> KnowledgeAnswer:
        body = {"query": query, **{k: v for k, v in filters.items() if v not in (None, "", [])}}
        return KnowledgeAnswer.model_validate(self._call("POST", "/knowledge/search", json=body, timeout=600))

    def index_status(self) -> IndexStatus:
        return IndexStatus.model_validate(self._call("GET", "/knowledge/index"))

    def rebuild_index(self) -> IndexStatus:
        return IndexStatus.model_validate(self._call("POST", "/knowledge/index/rebuild", timeout=1800))

    def documents(self) -> DocumentOverview:
        return DocumentOverview.model_validate(self._call("GET", "/documents"))

    def upload_document(self, filename: str, data: bytes, rebuild: bool = False) -> IngestResult:
        return IngestResult.model_validate(self._call("POST", "/documents", params={"rebuild": str(rebuild).lower()},
                                                      files={"file": (filename, data)}, timeout=1800))

    # --- agent / settings
    def agent_message(self, message: str) -> AgentResponse:
        return AgentResponse.model_validate(self._call("POST", "/agent/messages", json={"message": message}, timeout=600))

    def get_llm_settings(self) -> dict:
        return self._call("GET", "/settings/llm")

    def put_llm_settings(self, provider: str, model: str) -> dict:
        return self._call("PUT", "/settings/llm", json={"provider": provider, "model": model})
