from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from psit import __version__
from psit.domain.errors import DomainError
from psit.infra.config import Settings, get_settings
from psit.infra.db import make_engine, make_session_factory
from psit.infra.migrate import upgrade
from psit.repositories.sql import SqlUnitOfWork
from psit.services.approval import ApprovalService
from psit.services.audit import AuditService
from psit.services.reports import IntakeService
from psit.rag.runtime import RagRuntime
from psit.services.indexing import IndexService
from psit.services.ingestion import IngestionService
from psit.services.knowledge import KnowledgeService
from psit.services.workflow import WorkflowService

from psit.agent.orchestrator import AgentOrchestrator
from psit.rag.llm import LlmGate
from .routers import admin, agent, audit, closure, health, knowledge, reports
from .routers import settings as settings_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.auto_migrate:
        upgrade(settings.database_url)
    engine = make_engine(settings.database_url)
    uow = SqlUnitOfWork(make_session_factory(engine))

    runtime = RagRuntime(settings.model_profile, settings.index_dir, settings.rerank_threshold)
    app = FastAPI(title="Pharma Safety Intake & Triage Knowledge Agent", version=__version__,
                  description="Fictional training data only. Not a PV system, medical device or decision engine.")
    app.state.svc = SimpleNamespace(
        engine=engine, intake=IntakeService(uow), workflow=WorkflowService(uow),
        approvals=ApprovalService(uow), audit=AuditService(uow), settings=settings, runtime=runtime,
        ingestion=IngestionService(uow, runtime), index=IndexService(uow, runtime), uow=uow,
    )
    app.state.svc.llm = LlmGate(uow)
    app.state.svc.knowledge = KnowledgeService(uow, runtime, llm=app.state.svc.llm)

    app.state.svc.agent = AgentOrchestrator(app.state.svc, uow, classifier=app.state.svc.llm.classify)

    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError):
        return JSONResponse(status_code=exc.http_status, content={"error": {"code": exc.code, "message": exc.message}})

    for r in (health.router, reports.router, closure.router, audit.router, admin.router, knowledge.router, agent.router, settings_router.router):
        app.include_router(r, prefix="/api/v1")
    return app


def db_ok(engine) -> bool:
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
