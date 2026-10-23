from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: health

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
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


def test_stage_reports_health_alongside_the_pipeline(tmp_path: Path) -> None:
    repo(tmp_path)

    payload = json.loads(run_dispatch(tmp_path, "stage", "demo", "--json").stdout)

    assert "health" in payload
    assert isinstance(payload["health"]["issues"], list)


def test_stage_health_flags_a_failed_ticket(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--no-worktree").returncode == 0
    state = {"version": 1, "tickets": {"01": {"run_id": "01-x", "state": "failed", "updated_at": "2026-10-23T00:00:00+00:00"}}}
    (tmp_path / ".dispatch").mkdir(exist_ok=True)
    (tmp_path / ".dispatch" / "state.json").write_text(json.dumps(state), encoding="utf-8")

    payload = json.loads(run_dispatch(tmp_path, "stage", "demo", "--json").stdout)

    assert payload["health"]["ok"] is False
    assert any("retry" in issue for issue in payload["health"]["issues"])


def test_doctor_warns_about_host_installed_packages(tmp_path: Path) -> None:
    repo(tmp_path)
    package = tmp_path / ".agents" / "skills" / "some-skill"
    package.mkdir(parents=True)
    (package / "SKILL.md").write_text("# skill", encoding="utf-8")

    result = run_dispatch(tmp_path, "doctor", "--json")

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stdout
    assert any(".agents/skills" in warning for warning in payload["warnings"])
