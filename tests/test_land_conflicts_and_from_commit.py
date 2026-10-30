from __future__ import annotations

import json
import os
import shutil
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
- Write scope: out.txt
- Verify: python -c "print('ok')"

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


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=cwd, text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


TICKET_WITH_TICKETS_SCOPE = TICKET.replace("- Write scope: out.txt", "- Write scope: out.txt\n- Write scope: tickets/01.md")


def prepare(tmp_path: Path, *, commit_ticket_in_worktree: bool = False, ticket: str = TICKET) -> tuple[Path, dict, Path]:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(ticket, encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(json.dumps({"persona_policy": "off"}), encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".dispatch/\n", encoding="utf-8")
    git(tmp_path, "init", "-q")
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    git(tmp_path, "add", ".gitkeep")
    git(tmp_path, "commit", "-q", "-m", "base")
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets")).returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "out.txt").write_text("ok\n", encoding="utf-8")
    if commit_ticket_in_worktree:
        (worktree / "tickets").mkdir(exist_ok=True)
        (worktree / "tickets" / "01.md").write_text(ticket + "\n<!-- worktree copy -->\n", encoding="utf-8")
        git(worktree, "add", "-A")
        git(worktree, "commit", "-q", "-m", "worktree changes")
    git(tmp_path, "add", "tickets/01.md", ".gitignore")
    git(tmp_path, "commit", "-q", "-m", "tickets")
    (run_dir / "evidence").mkdir()
    (run_dir / "evidence" / "proof.txt").write_text("proof\n", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "file", "path": "evidence/proof.txt"}]}],
    }), encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", "01").returncode == 0
    assert run_dispatch(tmp_path, "review", "01", "--reviewer", "lead", "--verdict", "pass").returncode == 0
    return run_dir, run, worktree


def test_land_survives_a_ticket_only_add_add_conflict(tmp_path: Path) -> None:
    run_dir, run, worktree = prepare(tmp_path, commit_ticket_in_worktree=True, ticket=TICKET_WITH_TICKETS_SCOPE)
    (tmp_path / "tickets" / "01.md").write_text(TICKET_WITH_TICKETS_SCOPE + "\n<!-- main copy -->\n", encoding="utf-8")
    git(tmp_path, "add", "tickets/01.md")
    git(tmp_path, "commit", "-q", "-m", "main copy of the ticket")
    import hashlib
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    run["ticket_hash"] = hashlib.sha256((tmp_path / "tickets" / "01.md").read_bytes()).hexdigest()
    (run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")

    result = run_dispatch(tmp_path, "land", "01")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (run_dir / "landing.json").is_file()


def test_resolve_ticket_conflicts_uses_the_target_version(tmp_path: Path) -> None:
    from agent_dispatch.landing import _resolve_ticket_conflicts

    git(tmp_path, "init", "-q")
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    git(tmp_path, "add", ".gitkeep")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "target")
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text("target version\n", encoding="utf-8")
    git(tmp_path, "add", "tickets/01.md")
    git(tmp_path, "commit", "-q", "-m", "target ticket")
    git(tmp_path, "checkout", "-q", "-b", "work", "HEAD~1")
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text("worktree version\n", encoding="utf-8")
    git(tmp_path, "add", "tickets/01.md")
    git(tmp_path, "commit", "-q", "-m", "worktree ticket")
    git(tmp_path, "checkout", "-q", "target")
    merged = subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "merge", "--no-ff", "--no-edit", "work"],
        cwd=tmp_path, text=True, capture_output=True, check=False,
    )
    assert merged.returncode != 0

    resolved = _resolve_ticket_conflicts(tmp_path, tmp_path)

    assert resolved == ["tickets/01.md"]
    committed = subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "commit", "--no-edit"],
        cwd=tmp_path, text=True, capture_output=True, check=False,
    )
    assert committed.returncode == 0, committed.stderr
    content = (tmp_path / "tickets" / "01.md").read_text(encoding="utf-8")
    assert content == "target version\n"


def test_land_from_commit_restores_a_missing_worktree(tmp_path: Path) -> None:
    run_dir, run, worktree = prepare(tmp_path, commit_ticket_in_worktree=False)
    git(worktree, "add", "-A")
    git(worktree, "commit", "-q", "-m", "the work")
    sha = git(worktree, "rev-parse", "HEAD")
    branch = str(run["worktree_branch"])
    subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-D", branch], cwd=tmp_path, check=True, capture_output=True)

    result = run_dispatch(tmp_path, "land", "01", "--from-commit", sha)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (run_dir / "landing.json").is_file()


def test_doctor_reports_python_writability_and_ignore_paths(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(json.dumps({"persona_policy": "off"}), encoding="utf-8")
    (tmp_path / ".agents" / "skills" / "demo").mkdir(parents=True)
    (tmp_path / ".agents" / "skills" / "demo" / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")

    first = run_dispatch(tmp_path, "doctor", "--json")
    payload = json.loads(first.stdout)
    assert any(check["name"] == "python-writable" and check["ok"] for check in payload["checks"])
    assert any("host-installed" in issue for issue in payload["warnings"])

    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "off", "ignore_paths": [".agents"]}), encoding="utf-8"
    )
    second = run_dispatch(tmp_path, "doctor", "--json")
    assert "host-installed" not in second.stdout
