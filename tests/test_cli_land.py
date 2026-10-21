from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ticket_text() -> str:
    return """# 01: A

**What to build:** Ship A.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/01.py
- Verify: python -c "print('ok')"

## Acceptance

- [ ] A works.
"""


def git(tmp_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def git_result(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )


def make_repo(tmp_path: Path) -> None:
    directory = tmp_path / "tickets"
    directory.mkdir()
    (directory / "01-a.md").write_text(ticket_text(), encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def only_run(tmp_path: Path) -> Path:
    return sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]


def execution_root(tmp_path: Path, run: dict) -> Path:
    value = str(run.get("execution_root", ""))
    if not value:
        return tmp_path
    path = Path(value)
    return path if path.is_absolute() else tmp_path / path


def prepare_landable(
    tmp_path: Path,
    *,
    review: bool = True,
    no_worktree: bool = False,
) -> tuple[Path, dict]:
    make_repo(tmp_path)
    args = ["render", "01", "--tickets", str(tmp_path / "tickets")]
    if no_worktree:
        args.append("--no-worktree")
    assert run_dispatch(tmp_path, *args).returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = only_run(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    (run_dir / "evidence").mkdir()
    (run_dir / "evidence" / "proof.txt").write_text("proof\n", encoding="utf-8")
    (run_dir / "receipt.json").write_text(
        json.dumps(
            {
                "ticket_id": "01",
                "run_id": run["run_id"],
                "status": "done",
                "summary": "implemented",
                "criteria": [
                    {
                        "id": 1,
                        "verdict": "pass",
                        "evidence": [{"kind": "file", "path": "evidence/proof.txt"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    worktree = execution_root(tmp_path, run)
    (worktree / "src").mkdir()
    (worktree / "src" / "01.py").write_text("print('done')\n", encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", "01").returncode == 0
    if review:
        reviewed = run_dispatch(
            tmp_path,
            "review",
            "01",
            "--reviewer",
            "reviewer-b",
            "--verdict",
            "pass",
        )
        assert reviewed.returncode == 0, reviewed.stderr
    return run_dir, run


def test_land_creates_an_integration_branch_without_touching_the_target(tmp_path: Path) -> None:
    run_dir, _ = prepare_landable(tmp_path)
    target = git(tmp_path, "branch", "--show-current")
    target_before = git(tmp_path, "rev-parse", target)

    result = run_dispatch(tmp_path, "land", "01")

    assert result.returncode == 0, result.stderr
    assert "Pushed: no" in result.stdout
    landing = json.loads((run_dir / "landing.json").read_text(encoding="utf-8"))
    assert landing["target_branch"] == target
    assert landing["target_commit"] == target_before
    assert landing["pushed"] is False
    assert landing["pr_url"] is None
    assert landing["integration_branch"].startswith("dispatch/land/")
    assert landing["landing_commit"] != landing["target_commit"]
    assert landing["run_commit"] != landing["target_commit"]
    assert git(tmp_path, "rev-parse", target) == target_before
    assert git(
        tmp_path, "show", landing["integration_branch"] + ":src/01.py"
    ).strip() == "print('done')"
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run["landing"]["integration_branch"] == landing["integration_branch"]
    ledger = tmp_path / ".dispatch" / "ledger" / "landings.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["ticket_id"] == "01"
    assert rows[-1]["integration_branch"] == landing["integration_branch"]
    assert rows[-1]["landing_hash"]
    landings_dir = tmp_path / ".dispatch" / "landings"
    assert not landings_dir.exists() or not any(landings_dir.iterdir())


def test_land_refuses_worktree_changes_after_review(tmp_path: Path) -> None:
    run_dir, run = prepare_landable(tmp_path)
    worktree = execution_root(tmp_path, run)
    (worktree / "src" / "01.py").write_text("print('changed')\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "land", "01")

    assert result.returncode == 1
    assert "changed after verification" in result.stderr.lower()
    assert not (run_dir / "landing.json").exists()


def test_land_is_refused_until_review_passes(tmp_path: Path) -> None:
    prepare_landable(tmp_path, review=False)

    result = run_dispatch(tmp_path, "land", "01")

    assert result.returncode == 1
    assert "review" in result.stderr.lower() or "done" in result.stderr.lower()


def test_land_requires_a_worktree_run(tmp_path: Path) -> None:
    prepare_landable(tmp_path, no_worktree=True)

    result = run_dispatch(tmp_path, "land", "01")

    assert result.returncode == 1
    assert "worktree" in result.stderr.lower()


def test_land_refuses_a_dirty_main_checkout(tmp_path: Path) -> None:
    prepare_landable(tmp_path)
    (tmp_path / "scratch.txt").write_text("not landed\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "land", "01")

    assert result.returncode == 1
    assert "main checkout" in result.stderr.lower()


def test_land_reports_a_conflict_and_leaves_the_target_alone(tmp_path: Path) -> None:
    run_dir, _ = prepare_landable(tmp_path)
    target = git(tmp_path, "branch", "--show-current")
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "01.py").write_text("print('target')\n", encoding="utf-8")
    git(tmp_path, "add", "src/01.py")
    git(tmp_path, "commit", "-q", "-m", "target changes")
    target_before = git(tmp_path, "rev-parse", target)

    result = run_dispatch(tmp_path, "land", "01", "--into", target)

    assert result.returncode == 1
    assert "merge" in result.stderr.lower() or "conflict" in result.stderr.lower()
    assert git(tmp_path, "rev-parse", target) == target_before
    assert git(tmp_path, "branch", "--list", "dispatch/land/*") == ""
    assert not (run_dir / "landing.json").exists()


def test_land_accepts_an_explicit_branch_and_json_output(tmp_path: Path) -> None:
    prepare_landable(tmp_path)

    result = run_dispatch(
        tmp_path,
        "land",
        "01",
        "--branch",
        "integration/demo",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record["integration_branch"] == "integration/demo"
    assert record["pushed"] is False
    assert git(tmp_path, "rev-parse", "--verify", "refs/heads/integration/demo")
