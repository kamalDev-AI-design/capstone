"""PostToolUse governance hook: deterministically appends one metadata line per file-edit tool call to
.claude/dev_audit.jsonl. It stores NO file contents, diffs, prompts or tool output - only tool, path, a hash of
the path, and a timestamp. (Development governance; separate from the business audit_events chain.)"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

TRACKED = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0                                    # never block development on a malformed event
    tool = payload.get("tool_name", "")
    if tool not in TRACKED:
        return 0
    ti = payload.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".").resolve()
    rel = path
    try:
        rel = str(Path(path).resolve().relative_to(project)).replace("\\", "/")
    except Exception:
        pass
    record = {
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": tool,
        "file": rel,
        "path_sha256": hashlib.sha256(path.encode("utf-8")).hexdigest()[:16],
        "session_id": payload.get("session_id", ""),
    }
    out = Path(os.environ.get("PSIT_DEV_AUDIT_PATH") or project / ".claude" / "dev_audit.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
