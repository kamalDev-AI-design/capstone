from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import Field

from psit.contracts.reports import StrictModel
from psit.domain.errors import ForbiddenError
from psit.rag.llm import MODEL_RE
from psit.services import audit

from ..deps import get_actor, get_request_id, get_svc

router = APIRouter(prefix="/settings", tags=["settings"])


class LlmSettings(StrictModel):
    provider: Literal["EXTRACTIVE", "OPENROUTER"]
    model: str
    key_configured: bool
    suggested_models: list[str]


class LlmSettingsUpdate(StrictModel):
    provider: Literal["EXTRACTIVE", "OPENROUTER"]
    model: str = Field(min_length=3, max_length=100, pattern=MODEL_RE.pattern)


@router.get("/llm", response_model=LlmSettings)
def get_llm(svc=Depends(get_svc), actor=Depends(get_actor)):
    return LlmSettings(**svc.llm.settings())


@router.put("/llm", response_model=LlmSettings)
def put_llm(body: LlmSettingsUpdate, svc=Depends(get_svc), actor=Depends(get_actor), rid=Depends(get_request_id)):
    if actor.role not in ("INTAKE_OPERATOR", "REVIEWER"):
        raise ForbiddenError("Only a human may change LLM settings.")
    with svc.uow.begin() as tx:
        tx.rag.set_setting("llm_provider", body.provider)
        tx.rag.set_setting("llm_model", body.model)
        audit.record(tx, actor, "SETTINGS_CHANGED", "SETTINGS", "llm", rid, "SUCCESS",
                     {"provider": body.provider, "model": body.model})
    return LlmSettings(**svc.llm.settings())
