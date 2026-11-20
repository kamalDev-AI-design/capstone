"""Short-term (per-request) memory: observable execution events only. No chain-of-thought is ever stored."""
from dataclasses import dataclass, field


@dataclass
class ToolEvent:
    tool: str
    args: dict
    status: str            # OK | INVALID | ERROR
    error_code: str | None = None
    summary: str = ""


@dataclass
class RequestMemory:
    request_id: str
    route: str | None = None
    entities: dict = field(default_factory=dict)
    events: list[ToolEvent] = field(default_factory=list)
    retry_count: int = 0
    invalid_counts: dict[str, int] = field(default_factory=dict)
