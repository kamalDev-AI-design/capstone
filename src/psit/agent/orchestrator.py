"""Bounded agentic orchestration:
Policy -> Entity extraction -> Routing -> Typed command -> Pydantic validation -> Tool execution
-> Result validation -> Audit -> Response. The model never writes to the DB; services enforce invariants."""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from pydantic import ValidationError

from psit.domain.errors import DomainError, ForbiddenError
from psit.domain.models import Actor
from psit.services import audit

from . import policy
from .breaker import CIRCUIT_BREAKER_TRIGGERED, CircuitBreaker
from .extractor import extract
from .memory import RequestMemory, ToolEvent
from .router import Route, route as route_message
from .tools import ToolContext, build_registry

MAX_STEPS = 6
CLASSIFIER_ALLOWED = {Route.DIRECT_RESPONSE, Route.REPORT_LOOKUP, Route.SOP_LOOKUP, Route.HYBRID_KNOWLEDGE_LOOKUP,
                      Route.PROHIBITED_REQUEST}     # a model may never select a mutating route

HELP = ("I can help with: **intake** (e.g. `create a complaint product: Zentrafen 50mg Tablets, lot: LOT-88392, "
        "date: 2026-02-01, reporter: pharmacist, channel: email, description: cracked seal`), **lookups** "
        "(`show REF-2026-0001`, `list new reports`), **SOP / historical-report questions**, **status updates** "
        "(`move REF-2026-0004 to in review`), **closure requests** (`request closure for REF-2026-0003`) and **audit** "
        "(`verify audit chain`). I never approve closures, and I do not assess causality, seriousness, expectedness, "
        "reportability or treatment.")


class Proposer(Protocol):
    def next_call(self, mem: RequestMemory) -> dict | None: ...


class DeterministicProposer:
    """Maps a route + extracted entities to at most one typed tool call (no model involved)."""

    def __init__(self, route: Route, ent: dict, message: str):
        self.calls = self._plan(route, ent, message)

    @staticmethod
    def _plan(route: Route, ent: dict, message: str) -> list[dict]:
        ref = ent["refs"][0] if ent["refs"] else None
        if route == Route.NEW_INTAKE:
            args = {k: v for k, v in {"report_type": ent["report_type"], **ent["fields"]}.items() if k != "note" and v}
            return [{"tool": "create_report", "arguments": args}]
        if route == Route.STATUS_UPDATE:
            return [{"tool": "update_report_status", "arguments": {k: v for k, v in
                     {"reference_id": ref, "target_status": ent["status"] or "IN_REVIEW"}.items() if v}}]
        if route == Route.CLOSURE_APPROVAL:
            if re.search(r"\bapprov", message, re.I):
                return [{"tool": "approve_closure", "arguments": {k: v for k, v in {"approval_id": ent["approval_id"]}.items() if v}}]
            return [{"tool": "request_closure", "arguments": {k: v for k, v in
                     {"reference_id": ref, "note": ent["fields"].get("note")}.items() if v}}]
        if route == Route.REPORT_LOOKUP:
            if re.search(r"verify|chain", message, re.I):
                return [{"tool": "verify_audit_chain", "arguments": {}}]
            if re.search(r"\baudit\b", message, re.I):
                return [{"tool": "get_audit_history", "arguments": {"entity_id": ref or "audit"}}]
            if ref:
                return [{"tool": "get_report", "arguments": {"reference_id": ref}}]
            args = {"status": ent["status"], "report_type": ent["report_type"]}
            return [{"tool": "list_reports", "arguments": {k: v for k, v in args.items() if v}}]
        if route == Route.SOP_LOOKUP:
            return [{"tool": "search_sops", "arguments": {"query": message}}]
        if route == Route.HYBRID_KNOWLEDGE_LOOKUP:
            if re.search(r"\b(similar|previous|past|historical|earlier)\b", message, re.I) and not re.search(r"\bsop\b", message, re.I):
                return [{"tool": "search_historical_reports", "arguments": {"query": message}}]
            return [{"tool": "run_hybrid_rag", "arguments": {"query": message}}]
        return []

    def next_call(self, mem: RequestMemory) -> dict | None:
        return self.calls.pop(0) if self.calls else None


@dataclass
class AgentResult:
    route: str
    outcome: str     # OK | NEEDS_INPUT | BLOCKED | REJECTED | ABSTAINED | NEEDS_HUMAN_CONFIRMATION | CIRCUIT_BREAKER_TRIGGERED
    message: str
    tool_calls: list[dict] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    circuit_breaker: bool = False


def _verr(e: ValidationError) -> str:
    parts = []
    for x in e.errors():
        if x["type"] == "union_tag_not_found":
            parts.append("report_type: required (say 'adverse event' or 'complaint')")
        else:
            parts.append(f"{x['loc'][-1] if x['loc'] else 'arguments'}: {x['msg']}")
    return "; ".join(parts)


class AgentOrchestrator:
    def __init__(self, svc: Any, uow: Any, classifier: Callable[[str], str] | None = None):
        self.svc, self.uow, self.classifier = svc, uow, classifier
        self.registry = build_registry()

    # ---- main entry
    def run(self, message: str, actor: Actor, request_id: str, proposer: Proposer | None = None) -> AgentResult:
        mem = RequestMemory(request_id=request_id)
        mhash = hashlib.sha256(message.encode()).hexdigest()[:16]

        decision = policy.check(message)                                     # 1. policy boundary (deterministic)
        if decision.blocked:
            mem.route = Route.PROHIBITED_REQUEST.value
            with self.uow.begin() as tx:
                audit.record(tx, actor, "POLICY_BLOCKED", "AGENT", "chat", request_id, "BLOCKED",
                             {"category": decision.category, "message_hash": mhash})
            return AgentResult(mem.route, "BLOCKED", decision.message, data={"block_category": decision.category})

        ent = extract(message)                                               # 2. entity extraction
        mem.entities = {k: v for k, v in ent.items() if k != "fields"}
        rt, ambiguous = route_message(message, ent)                          # 3. intent routing
        if ambiguous and self.classifier is not None:                        # model consulted only when ambiguous
            try:
                cand = Route(self.classifier(message))
                if cand in CLASSIFIER_ALLOWED:
                    rt = cand
            except Exception:
                pass
        mem.route = rt.value
        if rt == Route.DIRECT_RESPONSE:
            return self._finish(actor, mem, mhash, AgentResult(rt.value, "OK", HELP))
        if rt == Route.PROHIBITED_REQUEST:
            return AgentResult(rt.value, "BLOCKED", policy.SCOPE_BOUNDARY_RESPONSE)

        proposer = proposer or DeterministicProposer(rt, ent, message)
        breaker = CircuitBreaker(mem.invalid_counts)
        ctx = ToolContext(actor=actor, request_id=request_id, svc=self.svc)
        result = AgentResult(rt.value, "OK", "")
        for _ in range(MAX_STEPS):                                           # 4-6. command -> validate -> execute
            call = proposer.next_call(mem)
            if call is None:
                break
            ok, data, code, msg = self._execute(ctx, mem, call)
            result.tool_calls.append({"tool": call["tool"], "status": "OK" if ok else "FAILED", "error_code": code,
                                      "summary": (msg or "")[:200]})
            if ok:
                self._format(rt, data, result, actor)                        # 7. result validation + response
                continue
            sig, tripped = breaker.register_invalid(call["tool"], call.get("arguments", {}), f"{code}:{msg}")
            mem.retry_count += 1
            if tripped:
                with self.uow.begin() as tx:
                    audit.record(tx, actor, "CIRCUIT_BREAKER_TRIGGERED", "AGENT", "chat", request_id, "HALTED",
                                 {"tool": call["tool"], "signature": sig[:16], "attempts": mem.invalid_counts[sig]})
                result.outcome, result.circuit_breaker = CIRCUIT_BREAKER_TRIGGERED, True
                result.message = ("⛔ **CIRCUIT_BREAKER_TRIGGERED** - the same invalid tool call was attempted repeatedly. "
                                  "Automated execution is halted; please correct the request manually.")
                return self._finish(actor, mem, mhash, result)
            self._failure(rt, call, code, msg, result)
        if not result.message:
            result.message = "Nothing to do."
        return self._finish(actor, mem, mhash, result)

    # ---- execution
    def _execute(self, ctx: ToolContext, mem: RequestMemory, call: dict):
        name, args = call.get("tool"), call.get("arguments", {})
        tool = self.registry.get(name)
        if tool is None:
            mem.events.append(ToolEvent(str(name), args, "INVALID", "UNKNOWN_TOOL"))
            return False, None, "UNKNOWN_TOOL", f"Tool '{name}' is not an approved capability."
        try:
            cmd = tool.adapter.validate_python(args)
        except ValidationError as e:
            msg = _verr(e)
            mem.events.append(ToolEvent(name, args, "INVALID", "VALIDATION_ERROR", msg))
            return False, None, "VALIDATION_ERROR", msg
        try:
            data = tool.fn(ctx, cmd)
        except DomainError as e:
            mem.events.append(ToolEvent(name, args, "ERROR", e.code, e.message))
            return False, None, e.code, e.message
        mem.events.append(ToolEvent(name, args, "OK", None, data.get("kind", "")))
        return True, data, None, data.get("kind")

    # ---- responses
    def _failure(self, rt: Route, call: dict, code: str, msg: str, result: AgentResult) -> None:
        if code == "VALIDATION_ERROR":
            result.outcome = "NEEDS_INPUT"
            hint = ""
            if call["tool"] == "create_report":
                hint = ("\n\nExample: `create a complaint product: Zentrafen 50mg Tablets, lot: LOT-88392, date: 2026-02-01, "
                        "reporter: pharmacist, channel: email, description: cracked seal`. Adverse events also need "
                        "`event: ...` and `onset: YYYY-MM-DD`.")
            result.message = f"I need more information before I can run `{call['tool']}`: {msg}{hint}"
        elif code == "FORBIDDEN":
            result.outcome, result.message = "REJECTED", f"🚫 Not permitted: {msg}"
        else:
            result.outcome, result.message = "REJECTED", f"The backend rejected this action [{code}]: {msg}"

    def _format(self, rt: Route, d: dict, res: AgentResult, actor: Actor) -> None:
        k = d["kind"]
        res.data[k] = d
        if k == "knowledge":
            a = d["answer"]
            res.message = a["answer"]
            if a["blocked"]:
                res.outcome = "BLOCKED"
            elif a["abstained"]:
                res.outcome = "ABSTAINED"
        elif k == "report":
            r = d["report"]
            extra = f"\n- Pending closure approval: #{d['pending_approval_id']}" if d["pending_approval_id"] else ""
            res.message = (f"**{r.reference_id}** - {r.report_type.replace('_', ' ').title()} - status **{r.status.value}** "
                           f"(record v{r.record_version})\n- Product: {r.product_name}, {r.lot_number}\n- Received {r.date_received} "
                           f"via {r.intake_channel.title()} from {r.reporter_type.replace('_', ' ').title()}\n- {r.description}{extra}")
        elif k == "reports":
            lines = [f"- **{r.reference_id}** [{r.status.value}] {r.product_name} / {r.lot_number}: {r.description[:80]}" for r in d["items"]]
            res.message = f"{d['total']} matching report(s)" + (", showing up to 10:\n" + "\n".join(lines) if lines else ".")
        elif k == "created":
            res.message = f"✅ Created **{d['report'].reference_id}** with status NEW."
        elif k == "transition":
            res.message = f"{'✅' if d['changed'] else 'ℹ️'} {d['reference_id']}: {d['message']}"
        elif k == "closure_requested":
            a = d["approval"]
            res.message = (f"📨 Closure requested for **{a.reference_id}** (approval #{a.id}). A human reviewer other than the "
                           f"requester must approve it on the Approvals page. I cannot approve it.")
        elif k == "needs_confirmation":
            a = d["approval"]
            res.outcome = "NEEDS_HUMAN_CONFIRMATION"
            res.message = (f"Approval #{a.id} for **{a.reference_id}** is pending. Approvals are never executed by the assistant - "
                           f"use the confirmation button below or the Approvals page to record your human authorization.")
            res.data["pending_confirmation"] = {"approval_id": a.id, "reference_id": a.reference_id}
        elif k == "audit":
            lines = [f"- `{e.timestamp_utc[:19]}` {e.action_type} - {e.outcome} ({e.actor_id})" for e in d["events"]]
            res.message = f"{d['total']} audit event(s) for the entity (newest first):\n" + "\n".join(lines)
        elif k == "audit_verify":
            res.message = ("✅ " if d["valid"] else "❌ ") + d["message"]

    def _finish(self, actor: Actor, mem: RequestMemory, mhash: str, res: AgentResult) -> AgentResult:
        with self.uow.begin() as tx:
            audit.record(tx, actor, "AGENT_REQUEST_COMPLETED", "AGENT", "chat", mem.request_id, res.outcome,
                         {"route": mem.route, "message_hash": mhash, "retries": mem.retry_count,
                          "tools": [{"tool": e.tool, "status": e.status, "code": e.error_code} for e in mem.events]})
        return res
