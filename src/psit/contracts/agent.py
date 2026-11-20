from pydantic import Field

from .knowledge import KnowledgeAnswer
from .reports import ReportOut, StrictModel


class AgentRequest(StrictModel):
    message: str = Field(min_length=1, max_length=1000)


class ToolCallOut(StrictModel):
    tool: str
    status: str
    error_code: str | None = None
    summary: str = ""


class PendingConfirmation(StrictModel):
    approval_id: int
    reference_id: str


class AgentResponse(StrictModel):
    route: str
    outcome: str
    message: str
    tool_calls: list[ToolCallOut] = []
    circuit_breaker: bool = False
    knowledge: KnowledgeAnswer | None = None
    report: ReportOut | None = None
    reports: list[ReportOut] | None = None
    pending_confirmation: PendingConfirmation | None = None
