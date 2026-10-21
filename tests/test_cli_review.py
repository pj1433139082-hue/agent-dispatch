from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ticket_text(owner: str = "implementer") -> str:
    return f"""# 01: A

**What to build:** Ship A.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: {owner}
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


def read_state(tmp_path: Path) -> dict:
    return json.loads((tmp_path / ".dispatch" / "state.json").read_text(encoding="utf-8"))


def execution_root(tmp_path: Path, run: dict) -> Path:
    value = str(run.get("execution_root", ""))
    if not value:
        return tmp_path
    path = Path(value)
    return path if path.is_absolute() else tmp_path / path


def prepare_verified(tmp_path: Path, owner: str = "implementer", agent: str | None = None) -> Path:
    directory = tmp_path / "tickets"
    directory.mkdir()
    (directory / "01-a.md").write_text(ticket_text(owner), encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    render_args = ["render", "01", "--tickets", str(directory)]
    if agent is not None:
        render_args.extend(["--agent", agent])
    assert run_dispatch(tmp_path, *render_args).returncode == 0
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
    return run_dir


def test_review_is_refused_before_verification(tmp_path: Path) -> None:
    directory = tmp_path / "tickets"
    directory.mkdir()
    (directory / "01-a.md").write_text(ticket_text(), encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(directory)).returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0

    result = run_dispatch(tmp_path, "review", "01", "--reviewer", "reviewer", "--verdict", "pass")

    assert result.returncode == 1
    assert "review" in result.stderr.lower()
    assert not (only_run(tmp_path) / "review.json").exists()


def test_self_review_is_refused(tmp_path: Path) -> None:
    run_dir = prepare_verified(tmp_path)

    result = run_dispatch(
        tmp_path, "review", "01", "--reviewer", "implementer", "--verdict", "pass"
    )

    assert result.returncode == 1
    assert "self" in result.stderr.lower() or "owner" in result.stderr.lower()
    assert not (run_dir / "review.json").exists()


def test_claimed_agent_cannot_review_its_own_run(tmp_path: Path) -> None:
    prepare_verified(tmp_path, agent="agent-a")

    result = run_dispatch(tmp_path, "review", "01", "--reviewer", "agent-a", "--verdict", "pass")

    assert result.returncode == 1


def test_pass_moves_to_done_and_writes_review(tmp_path: Path) -> None:
    run_dir = prepare_verified(tmp_path)

    result = run_dispatch(
        tmp_path,
        "review",
        "01",
        "--reviewer",
        "reviewer",
        "--verdict",
        "pass",
        "--notes",
        "looks good",
    )

    assert result.returncode == 0, result.stderr
    record = json.loads((run_dir / "review.json").read_text(encoding="utf-8"))
    assert record["verdict"] == "pass"
    assert record["reviewer"] == "reviewer"
    assert record["notes"] == "looks good"
    assert read_state(tmp_path)["tickets"]["01"]["state"] == "done"
    ledger = tmp_path / ".dispatch" / "ledger" / "reviews.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["ticket_id"] == "01"
    assert rows[-1]["verdict"] == "pass"
    assert rows[-1]["review_hash"]


def test_fail_moves_to_failed(tmp_path: Path) -> None:
    run_dir = prepare_verified(tmp_path)

    result = run_dispatch(
        tmp_path, "review", "01", "--reviewer", "reviewer", "--verdict", "fail"
    )

    assert result.returncode == 0, result.stderr
    assert json.loads((run_dir / "review.json").read_text(encoding="utf-8"))["verdict"] == "fail"
    assert read_state(tmp_path)["tickets"]["01"]["state"] == "failed"


def test_empty_reviewer_is_refused(tmp_path: Path) -> None:
    prepare_verified(tmp_path)

    result = run_dispatch(tmp_path, "review", "01", "--reviewer", "", "--verdict", "pass")

    assert result.returncode == 1


def prepare_degraded(tmp_path: Path) -> Path:
    directory = tmp_path / "tickets"
    directory.mkdir()
    (directory / "01-a.md").write_text(ticket_text(), encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(directory)).returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = only_run(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
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
                        "evidence": [{"kind": "note", "note": "checked by hand"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    worktree = execution_root(tmp_path, run)
    (worktree / "src").mkdir()
    (worktree / "src" / "01.py").write_text("print('done')\n", encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", "01").returncode == 2
    return run_dir


def test_degraded_verification_needs_explicit_review_acceptance(tmp_path: Path) -> None:
    run_dir = prepare_degraded(tmp_path)

    refused = run_dispatch(
        tmp_path, "review", "01", "--reviewer", "reviewer", "--verdict", "pass"
    )
    assert refused.returncode == 1
    assert "degraded" in refused.stderr.lower()

    accepted = run_dispatch(
        tmp_path,
        "review",
        "01",
        "--reviewer",
        "reviewer",
        "--verdict",
        "pass",
        "--accept-degraded",
    )
    assert accepted.returncode == 0, accepted.stderr
    record = json.loads((run_dir / "review.json").read_text(encoding="utf-8"))
    assert record["verify_status"] == "degraded"
    assert record["accepted_degraded"] is True
    assert read_state(tmp_path)["tickets"]["01"]["state"] == "done"
