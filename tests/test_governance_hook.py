import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "log_edit.py"


def run(payload, tmp_path):
    out = tmp_path / "audit.jsonl"
    subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), text=True, check=True,
                   env={"PSIT_DEV_AUDIT_PATH": str(out), "CLAUDE_PROJECT_DIR": str(ROOT), "PATH": ""})
    return out


def test_hook_logs_edit_metadata_but_never_contents(tmp_path):
    secret = "SECRET-FILE-CONTENT-123"
    out = run({"tool_name": "Write", "session_id": "s1",
               "tool_input": {"file_path": str(ROOT / "src" / "psit" / "x.py"), "content": secret},
               "tool_response": {"output": secret}}, tmp_path)
    line = out.read_text(encoding="utf-8")
    rec = json.loads(line)
    assert rec["tool"] == "Write" and rec["file"] == "src/psit/x.py" and len(rec["path_sha256"]) == 16
    assert secret not in line


def test_hook_ignores_other_tools_and_bad_input(tmp_path):
    out = run({"tool_name": "Bash", "tool_input": {"command": "ls"}}, tmp_path)
    assert not out.exists()
    r = subprocess.run([sys.executable, str(HOOK)], input="not json", text=True)
    assert r.returncode == 0


def test_settings_registers_posttooluse_hook():
    cfg = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    entry = cfg["hooks"]["PostToolUse"][0]
    assert "Edit" in entry["matcher"] and "log_edit.py" in entry["hooks"][0]["command"]
