from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 09: handoff

## What to build

写 wind.py。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: research-scout
- Risk: L1
- Write scope: wind.py
- Verify: python -c "print(1)"

## Acceptance

- [ ] wind.py 完成。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "09.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def test_handoff_describes_what_to_send_a_teammate(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "09", "--agent", "research-scout").returncode == 0

    result = run_dispatch(tmp_path, "handoff", "09", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["to"] == "research-scout"
    assert payload["work_order"].endswith("work-order.md")
    assert Path(payload["work_order"]).is_file()
    assert payload["execution_root"]
    assert "receipt.json" in payload["message"]
    assert payload["run_id"]


def test_handoff_can_target_another_agent(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "09", "--agent", "research-scout").returncode == 0

    payload = json.loads(run_dispatch(tmp_path, "handoff", "09", "--to", "implementer", "--json").stdout)

    assert payload["to"] == "implementer"


def test_handoff_without_a_run_fails(tmp_path: Path) -> None:
    repo(tmp_path)

    result = run_dispatch(tmp_path, "handoff", "09")

    assert result.returncode != 0
    assert "run" in (result.stdout + result.stderr).lower()
