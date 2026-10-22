from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_new_produces_a_lint_clean_ticket(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()

    created = run_dispatch(
        tmp_path, "new", "01", "--title", "hello",
        "--what", "写 greeting.txt", "--write-scope", "greeting.txt",
        "--verify", 'python -c "print(1)"',
    )
    assert created.returncode == 0, created.stderr

    linted = run_dispatch(tmp_path, "lint")
    assert linted.returncode == 0, linted.stdout + linted.stderr


def test_plan_separates_blocked_tickets_into_waves(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text("""# 01: a

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: a.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] a
""", encoding="utf-8")
    (tmp_path / "tickets" / "02.md").write_text("""# 02: b

## What to build

y

**Blocked by:** 01
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: b.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] b
""", encoding="utf-8")

    result = run_dispatch(tmp_path, "plan", "--json")

    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    waves = plan["waves"] if "waves" in plan else plan
    flat = json.dumps(waves, ensure_ascii=False)
    assert "01" in flat and "02" in flat


def test_personas_list_finds_the_bundled_roles(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "personas", "list", "--json")

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    names = json.dumps(rows, ensure_ascii=False)
    assert "dispatcher" in names


def test_export_codex_produces_a_work_order(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text("""# 01: a

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: a.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] a
""", encoding="utf-8")

    result = run_dispatch(tmp_path, "export", "--format", "codex", "--output", str(tmp_path / "codex.md"))

    assert result.returncode == 0, result.stderr
    assert "01" in (tmp_path / "codex.md").read_text(encoding="utf-8")
