from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from .rag_store import SqlRagStore
from .repos import SqlApprovalRepository, SqlAuditRepository, SqlHistoryRepository, SqlReportRepository


@dataclass
class Tx:
    reports: SqlReportRepository
    history: SqlHistoryRepository
    approvals: SqlApprovalRepository
    audit: SqlAuditRepository
    rag: SqlRagStore


class SqlUnitOfWork:
    """One DB transaction (BEGIN IMMEDIATE). Commits on clean exit, rolls back on exception."""

    def __init__(self, session_factory: sessionmaker):
        self._sf = session_factory

    @contextmanager
    def begin(self) -> Iterator[Tx]:
        with self._sf() as session:
            with session.begin():
                yield Tx(SqlReportRepository(session), SqlHistoryRepository(session),
                         SqlApprovalRepository(session), SqlAuditRepository(session), SqlRagStore(session))
