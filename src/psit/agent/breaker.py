"""Circuit breaker for repeated identical invalid tool invocations (per request)."""
import hashlib
import json

CIRCUIT_BREAKER_TRIGGERED = "CIRCUIT_BREAKER_TRIGGERED"
MAX_IDENTICAL_INVALID = 2     # two identical invalid attempts are tolerated; the next one halts execution


def signature(tool_name: str, arguments: dict, validation_error: str) -> str:
    canon = json.dumps({"tool": tool_name, "args": arguments, "error": validation_error},
                       sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class CircuitBreaker:
    def __init__(self, counts: dict[str, int]):
        self.counts = counts      # shared with RequestMemory.invalid_counts

    def register_invalid(self, tool_name: str, arguments: dict, error: str) -> tuple[str, bool]:
        """Record an invalid attempt. Returns (signature, tripped). Tripped on the attempt after the allowed ones."""
        sig = signature(tool_name, arguments, error)
        prior = self.counts.get(sig, 0)
        self.counts[sig] = prior + 1
        return sig, prior >= MAX_IDENTICAL_INVALID
