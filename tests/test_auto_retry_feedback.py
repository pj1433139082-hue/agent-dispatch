from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: retry

## What to build

写 out.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('out.txt').exists() else 1)"

## Acceptance

- [ ] out.txt 存在。
"""

EXECUTOR = """import json, os, pathlib
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
attempt = os.environ.get("DISPATCH_ATTEMPT", "1")
auto = run / "auto"
auto.mkdir(parents=True, exist_ok=True)
(auto / ("seen-" + attempt + ".txt")).write_text(os.environ.get("DISPATCH_FEEDBACK", ""), encoding="utf-8")
if attempt == "1":
    raise SystemExit(1)
pathlib.Path("out.txt").write_text("done", encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
    "ticket_id": "01", "run_id": os.environ["DISPATCH_RUN_ID"], "status": "done", "summary": "done",
    "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
}), encoding="utf-8")
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_auto_feeds_previous_failure_into_the_next_attempt(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "exec.py").write_text(EXECUTOR, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)

    result = run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py", "--max-attempts", "2")

    assert result.returncode == 0, result.stdout + result.stderr
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    auto = json.loads((run_dir / "auto.json").read_text(encoding="utf-8"))
    assert len(auto["attempts"]) == 2, auto
    feedback = list((run_dir / "auto").glob("feedback-*.md"))
    assert feedback, "第一次失败应该留下 feedback 文件"
    assert "findings" in feedback[0].read_text(encoding="utf-8").lower()
    seen = (run_dir / "auto" / "seen-2.txt").read_text(encoding="utf-8")
    assert "feedback" in seen.lower(), repr(seen)
