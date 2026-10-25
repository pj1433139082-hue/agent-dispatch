from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: w

## What to build

写 out.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] out.txt 存在。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    run_dir = tmp_path / ".dispatch" / "runs" / "01-run"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": "01-run", "state": "done", "created_at": "2026-10-24T00:00:00+00:00",
    }), encoding="utf-8")


def test_wrap_reports_runs_without_landing(tmp_path: Path) -> None:
    repo(tmp_path)

    result = run_dispatch(tmp_path, "wrap", "--json")

    payload = json.loads(result.stdout)
    assert payload["runs_total"] == 1
    assert payload["runs_landed"] == 0
    assert any("without landing.json" in issue for issue in payload["issues"])
    assert any("gc" in action for action in payload["actions"])


def test_wrap_is_happy_once_the_run_is_landed(tmp_path: Path) -> None:
    repo(tmp_path)
    landed = tmp_path / ".dispatch" / "runs" / "01-run" / "landing.json"
    landed.write_text(json.dumps({"status": "landed"}), encoding="utf-8")

    result = run_dispatch(tmp_path, "wrap", "--json")

    payload = json.loads(result.stdout)
    assert payload["runs_landed"] == 1
    assert not any("without landing.json" in issue for issue in payload["issues"])
