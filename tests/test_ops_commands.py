from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: A

**What to build:** Ship A.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/01.py
- Verify: {verify}

## Acceptance

- [ ] A works.
"""


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )


def git(tmp_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=tmp_path, text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


def test_review_window_detects_changes_and_blocks_sign(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "select", "demo", "--mode", "team").returncode == 0
    directory = tmp_path / "docs" / "selection" / "demo"
    for name, persona in (("01-oss.md", "builtin:oss-scout"), ("02-sources.md", "builtin:search-scout"), ("03-adversary.md", "builtin:adversary")):
        (directory / name).write_text("# 证据\n\nPersona: " + persona + "\n\n结论：建议采用\n", encoding="utf-8")
    assert run_dispatch(tmp_path, "review-window", "demo", "--open").returncode == 0
    (directory / "02-sources.md").write_text("# 证据\n\nPersona: builtin:search-scout\n\n结论：改了\n", encoding="utf-8")

    closed = run_dispatch(tmp_path, "review-window", "demo", "--close")
    assert closed.returncode == 1
    assert "02-sources.md" in closed.stdout + closed.stderr

    signed = run_dispatch(tmp_path, "sign", "demo", "--by", "lead", "--via", "card")
    assert signed.returncode == 1
    assert "评审窗口" in (signed.stdout + signed.stderr)


def test_review_window_clean_close_allows_sign(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "select", "demo", "--mode", "team").returncode == 0
    directory = tmp_path / "docs" / "selection" / "demo"
    for name, persona in (("01-oss.md", "builtin:oss-scout"), ("02-sources.md", "builtin:search-scout"), ("03-adversary.md", "builtin:adversary")):
        (directory / name).write_text("# 证据\n\nPersona: " + persona + "\n\n结论：建议采用\n", encoding="utf-8")
    assert run_dispatch(tmp_path, "review-window", "demo", "--open").returncode == 0
    assert run_dispatch(tmp_path, "review-window", "demo", "--close").returncode == 0

    signed = run_dispatch(tmp_path, "sign", "demo", "--by", "lead", "--via", "card")

    assert signed.returncode == 0, signed.stdout + signed.stderr


def _repo(tmp_path: Path, verify: str) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01-a.md").write_text(TICKET.format(verify=verify), encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(json.dumps({"persona_policy": "off", "require_brief": False}), encoding="utf-8")
    git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text(".dispatch/\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")


def test_mutate_reports_killed_for_a_strong_verify(tmp_path: Path) -> None:
    _repo(tmp_path, 'python -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'src/01.py\').is_file() else 1)"')
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets")).returncode == 0

    result = run_dispatch(tmp_path, "mutate", "01")

    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads(next((tmp_path / ".dispatch" / "runs").glob("*/mutation.json")).read_text(encoding="utf-8"))
    assert record["status"] == "killed"


def test_mutate_reports_weak_when_verify_passes_on_the_base_commit(tmp_path: Path) -> None:
    _repo(tmp_path, 'python -c "print(1)"')
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets")).returncode == 0

    result = run_dispatch(tmp_path, "mutate", "01")

    assert result.returncode == 1
    record = json.loads(next((tmp_path / ".dispatch" / "runs").glob("*/mutation.json")).read_text(encoding="utf-8"))
    assert record["status"] == "weak"


def test_integrate_merges_branches_and_runs_verify_all(tmp_path: Path) -> None:
    _repo(tmp_path, 'python -c "print(1)"')
    base = git(tmp_path, "rev-parse", "--abbrev-ref", "HEAD")
    git(tmp_path, "checkout", "-b", "feat/a")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "a")
    git(tmp_path, "checkout", base)
    git(tmp_path, "checkout", "-b", "feat/b")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "b")
    git(tmp_path, "checkout", base)

    result = run_dispatch(
        tmp_path, "integrate", "--branch", "integration/all", "--from", "feat/a", "--from", "feat/b",
        "--verify-all", 'python -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'a.txt\').is_file() and pathlib.Path(\'b.txt\').is_file() else 1)"',
    )

    assert result.returncode == 0, result.stdout + result.stderr
    files = git(tmp_path, "ls-tree", "--name-only", "integration/all").split()
    assert "a.txt" in files and "b.txt" in files
    record = json.loads(sorted((tmp_path / ".dispatch" / "landings").glob("integrate-*.json"))[0].read_text(encoding="utf-8"))
    assert record["status"] == "integrated"
    assert record["verify_all_status"] == "pass"
