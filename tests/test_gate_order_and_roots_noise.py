from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# {id}: gate

**What to build:** x
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: a
- Risk: {risk}
- Write scope: out.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo(tmp_path: Path, risk: str = "L2", config: dict | None = None) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET.format(id="01", risk=risk), encoding="utf-8")
    (tmp_path / "seed.txt").write_text("x", encoding="utf-8")
    if config is not None:
        (tmp_path / ".dispatch").mkdir(exist_ok=True)
        (tmp_path / ".dispatch" / "config.json").write_text(json.dumps(config), encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def test_persona_gate_runs_before_the_brief_gate(tmp_path: Path) -> None:
    repo(tmp_path, "L2", {"require_brief": True})

    result = run_dispatch(tmp_path, "render", "01", "--agent", "lead")

    assert result.returncode == 6
    assert "needs a persona" in result.stderr


def test_policy_l3_lets_l2_pass_the_persona_gate(tmp_path: Path) -> None:
    repo(tmp_path, "L2", {"persona_policy": "l3"})

    result = run_dispatch(tmp_path, "render", "01", "--agent", "lead")

    assert result.returncode == 0, result.stdout + result.stderr


def test_render_inside_a_nested_repo_gives_a_clean_error(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    inner = outer / "planning" / "dispatch"
    (inner / "tickets").mkdir(parents=True)
    (outer / "seed.txt").write_text("x", encoding="utf-8")
    (inner / "tickets" / "01.md").write_text(TICKET.format(id="01", risk="L1"), encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=outer, check=True, capture_output=True)

    result = run_dispatch(inner, "render", "01", "--agent", "lead")

    assert result.returncode == 7
    assert "RENDER" in result.stderr
    assert "Traceback" not in result.stderr


def test_roots_ignores_probe_roots_inside_dispatch_tmp(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    probe = tmp_path / ".dispatch" / "tmp" / "probe-root" / "tickets"
    probe.mkdir(parents=True)
    (probe / "01.md").write_text(TICKET.format(id="01", risk="L1"), encoding="utf-8")

    result = run_dispatch(tmp_path, "roots", "--json")

    payload = json.loads(result.stdout)
    assert all(".dispatch" not in item["root"] for item in payload["roots"])
