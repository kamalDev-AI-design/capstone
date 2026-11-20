"""Business audit: append-only, hash-chained (tamper-evident; SQLite is not absolutely immutable)."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from psit import __version__
from psit.domain.models import Actor, AuditEvent


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _hash_fields(e: dict | AuditEvent) -> str:
    g = (lambda k: e[k]) if isinstance(e, dict) else (lambda k: getattr(e, k))
    keys = ["event_id", "timestamp_utc", "actor_id", "actor_role", "action_type", "entity_type", "entity_id",
            "request_id", "outcome", "payload_hash", "previous_event_hash", "application_version"]
    return sha256(canonical({k: g(k) for k in keys}))


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def record(tx, actor: Actor, action_type: str, entity_type: str, entity_id: str, request_id: str,
           outcome: str, details: dict | None = None) -> AuditEvent:
    """Append an event inside the caller's transaction (so it commits/rolls back with the mutation)."""
    details_json = canonical(details or {})
    ev = {
        "event_id": f"EVT-{uuid.uuid4().hex[:16]}",
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "actor_id": actor.actor_id, "actor_role": actor.role, "action_type": action_type,
        "entity_type": entity_type, "entity_id": entity_id, "request_id": request_id, "outcome": outcome,
        "details": details_json, "payload_hash": sha256(details_json),
        "previous_event_hash": tx.audit.last_hash(), "application_version": __version__,
    }
    ev["event_hash"] = _hash_fields(ev)
    return tx.audit.append(ev)


def verify_chain(events: list[AuditEvent]) -> tuple[bool, str | None, str]:
    from psit.repositories.sql.repos import GENESIS_HASH  # constant only

    prev = GENESIS_HASH
    for e in events:
        if (e.previous_event_hash != prev or sha256(e.details) != e.payload_hash
                or _hash_fields(e) != e.event_hash):
            return False, e.event_id, f"Chain broken at event {e.event_id}"
        prev = e.event_hash
    return True, None, f"Chain intact ({len(events)} events)"


class AuditService:
    def __init__(self, uow):
        self.uow = uow

    def list(self, entity_id: str | None, limit: int, offset: int):
        with self.uow.begin() as tx:
            return tx.audit.list(entity_id=entity_id, limit=limit, offset=offset)

    def verify(self, actor: Actor, request_id: str) -> dict:
        with self.uow.begin() as tx:
            events = tx.audit.all_ascending()
            ok, bad, msg = verify_chain(events)
            record(tx, actor, "AUDIT_CHAIN_VERIFIED", "AUDIT", "chain", request_id,
                   "SUCCESS" if ok else "FAILURE", {"events_checked": len(events), "valid": ok})
        return {"valid": ok, "events_checked": len(events), "first_invalid_event_id": bad, "message": msg}
