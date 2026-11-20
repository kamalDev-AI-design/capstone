import uuid

from fastapi import HTTPException, Request

from psit.domain.enums import ActorRole
from psit.domain.models import Actor


def get_svc(request: Request):
    return request.app.state.svc


def get_actor(request: Request) -> Actor:
    """Prototype auth: demo persona headers. NOT production authentication."""
    actor_id = request.headers.get("X-Actor-Id")
    role = request.headers.get("X-Actor-Role")
    if not actor_id or not role:
        raise HTTPException(401, {"error": {"code": "UNAUTHENTICATED", "message": "X-Actor-Id and X-Actor-Role headers required (demo auth)."}})
    try:
        ActorRole(role)
    except ValueError:
        raise HTTPException(401, {"error": {"code": "UNAUTHENTICATED", "message": f"Unknown role {role!r}."}})
    if len(actor_id) > 80:
        raise HTTPException(401, {"error": {"code": "UNAUTHENTICATED", "message": "actor id too long"}})
    return Actor(actor_id=actor_id, role=role)


def get_request_id(request: Request) -> str:
    return (request.headers.get("X-Request-Id") or uuid.uuid4().hex)[:64]
