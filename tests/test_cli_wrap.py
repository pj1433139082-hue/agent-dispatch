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


def test_wrap_is_clean_on_a_fresh_repo(tmp_path: Path) -> None:
    repo(tmp_path)

    result = run_dispatch(tmp_path, "wrap")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Verdict: CLEAN" in result.stdout


def test_wrap_points_at_the_next_commands_when_work_is_open(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead", "--no-worktree").returncode == 0
    (tmp_path / "stray.md").write_text("x", encoding="utf-8")

    result = run_dispatch(tmp_path, "wrap", "--json")

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["clean"] is False
    assert any("active" in str(item) or "sweep" in str(item) or "commit" in str(item) for item in payload["actions"]) or payload["issues"]
    assert any("stray.md" in issue for issue in payload["issues"])
