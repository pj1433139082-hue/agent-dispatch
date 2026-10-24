from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# {id}: lease

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: shared.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def make(tmp_path: Path, ids: list[str]) -> None:
    (tmp_path / "tickets").mkdir()
    for tid in ids:
        (tmp_path / "tickets" / (tid + ".md")).write_text(TICKET.format(id=tid), encoding="utf-8")
    (tmp_path / "shared.txt").write_text("x", encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    for tid in ids:
        assert run_dispatch(tmp_path, "render", tid, "--no-worktree").returncode == 0


def locks(root: Path) -> list[Path]:
    directory = root / ".dispatch" / "locks"
    return sorted(directory.glob("*.json")) if directory.exists() else []


def test_release_frees_the_leases_of_a_ticket(tmp_path: Path) -> None:
    make(tmp_path, ["01"])
    assert run_dispatch(tmp_path, "claim", "01").returncode == 0
    assert locks(tmp_path)

    released = run_dispatch(tmp_path, "release", "01")

    assert released.returncode == 0, released.stdout + released.stderr
    assert locks(tmp_path) == []


def test_release_is_idempotent(tmp_path: Path) -> None:
    make(tmp_path, ["01"])
    assert run_dispatch(tmp_path, "claim", "01").returncode == 0
    assert run_dispatch(tmp_path, "release", "01").returncode == 0

    again = run_dispatch(tmp_path, "release", "01")

    assert again.returncode == 0
    assert "0" in again.stdout


def test_releasing_one_ticket_lets_another_claim_the_file(tmp_path: Path) -> None:
    make(tmp_path, ["01", "02"])
    assert run_dispatch(tmp_path, "claim", "01").returncode == 0
    blocked = run_dispatch(tmp_path, "claim", "02")
    assert blocked.returncode == 3

    assert run_dispatch(tmp_path, "release", "01").returncode == 0
    allowed = run_dispatch(tmp_path, "claim", "02")

    assert allowed.returncode == 0, allowed.stdout + allowed.stderr


def test_release_without_a_run_is_a_no_op(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET.format(id="01"), encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)

    result = run_dispatch(tmp_path, "release", "01")

    assert result.returncode == 0
    assert "run" in (result.stdout + result.stderr).lower()
