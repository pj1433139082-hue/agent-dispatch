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


def run_data(tmp_path: Path) -> dict:
    return json.loads((only_run(tmp_path) / "run.json").read_text(encoding="utf-8"))


def execution_root(tmp_path: Path) -> Path:
    value = Path(str(run_data(tmp_path)["execution_root"]))
    return value if value.is_absolute() else tmp_path / value


def prepare(tmp_path: Path, *render_args: str) -> dict:
    make_repo(tmp_path)
    args = ["render", "01", "--tickets", str(tmp_path / "tickets"), *render_args]
    result = run_dispatch(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    return run_data(tmp_path)


def write_receipt(run: dict, criteria: list[dict]) -> Path:
    run_dir = only_run(Path(run["_root"])) if "_root" in run else None
    raise AssertionError("use write_receipt_at")


def write_receipt_at(run_dir: Path, run: dict, criteria: list[dict], status: str = "done") -> None:
    receipt = {
        "ticket_id": "01",
        "run_id": run["run_id"],
        "status": status,
        "summary": "implemented",
        "criteria": criteria,
    }
    (run_dir / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")


def test_render_creates_a_worktree_and_records_the_execution_root(tmp_path: Path) -> None:
    run = prepare(tmp_path)
    worktree = Path(str(run["worktree_path"]))
    if not worktree.is_absolute():
        worktree = tmp_path / worktree

    assert run["use_worktree"] is True
    assert worktree.is_dir()
    assert (worktree / "tickets" / "01-a.md").is_file()
    assert run["execution_root"] == run["worktree_path"]
    assert run["worktree_branch"] == f"dispatch/{run['run_id']}"
    branch = git(worktree, "branch", "--show-current")
    assert branch == run["worktree_branch"]

    work_order = (only_run(tmp_path) / "work-order.md").read_text(encoding="utf-8")
    assert "Execution root:" in work_order
    assert run["worktree_branch"] in work_order


def test_render_can_opt_out_of_a_worktree(tmp_path: Path) -> None:
    run = prepare(tmp_path, "--no-worktree")

    assert run["use_worktree"] is False
    assert run["execution_root"] == ""
    assert "worktree_path" not in run


def test_verification_runs_in_the_worktree_and_accepts_criteria_evidence(tmp_path: Path) -> None:
    run = prepare(tmp_path)
    worktree = execution_root(tmp_path)
    (worktree / "src").mkdir()
    (worktree / "src" / "01.py").write_text("print('done')\n", encoding="utf-8")
    run_dir = only_run(tmp_path)
    (run_dir / "evidence").mkdir()
    (run_dir / "evidence" / "proof.txt").write_text("proof\n", encoding="utf-8")
    write_receipt_at(
        run_dir,
        run,
        [
            {
                "id": 1,
                "verdict": "pass",
                "note": "acceptance met",
                "evidence": [
                    {"kind": "file", "path": "evidence/proof.txt"},
                    {"kind": "inline", "content": "print('done')", "sha256": hashlib.sha256(b"print('done')").hexdigest()},
                    {"kind": "absent", "path": "src/missing.py"},
                    {"kind": "command", "command": "python -c \"print('ok')\"", "exit_code": 0},
                    {"kind": "note", "note": "reviewed manually"},
                ],
            }
        ],
    )

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 0, result.stderr
    record = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))
    assert record["status"] == "passed"
    assert record["changed_files"] == ["src/01.py"]
    assert [item["kind"] for item in record["evidence"]] == [
        "file",
        "inline",
        "absent",
        "command",
        "note",
    ]


def test_main_checkout_pollution_is_refused(tmp_path: Path) -> None:
    run = prepare(tmp_path)
    run_dir = only_run(tmp_path)
    (run_dir / "evidence").mkdir()
    (run_dir / "evidence" / "proof.txt").write_text("proof\n", encoding="utf-8")
    write_receipt_at(
        run_dir,
        run,
        [{"id": 1, "verdict": "pass", "evidence": [{"kind": "file", "path": "evidence/proof.txt"}]}],
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "01.py").write_text("print('leaked')\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1
    record = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))
    assert any("main checkout" in error.lower() for error in record["errors"])


def test_criteria_with_attested_evidence_is_degraded(tmp_path: Path) -> None:
    run = prepare(tmp_path)
    run_dir = only_run(tmp_path)
    write_receipt_at(
        run_dir,
        run,
        [{"id": 1, "verdict": "pass", "evidence": [{"kind": "note", "note": "checked by hand"}]}],
    )

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 2, result.stderr
    record = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))
    assert record["status"] == "degraded"
    state = json.loads((tmp_path / ".dispatch" / "state.json").read_text(encoding="utf-8"))
    assert state["tickets"]["01"]["state"] == "review"


def test_criteria_fail_verdict_fails_verification(tmp_path: Path) -> None:
    run = prepare(tmp_path)
    run_dir = only_run(tmp_path)
    (run_dir / "evidence").mkdir()
    (run_dir / "evidence" / "proof.txt").write_text("proof\n", encoding="utf-8")
    write_receipt_at(
        run_dir,
        run,
        [{"id": 1, "verdict": "fail", "evidence": [{"kind": "file", "path": "evidence/proof.txt"}]}],
    )

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1
    assert json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))["status"] == "failed"


def test_inline_hash_mismatch_fails(tmp_path: Path) -> None:
    run = prepare(tmp_path)
    run_dir = only_run(tmp_path)
    write_receipt_at(
        run_dir,
        run,
        [
            {
                "id": 1,
                "verdict": "pass",
                "evidence": [{"kind": "inline", "content": "actual", "sha256": "0" * 64}],
            }
        ],
    )

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1
    assert any("hash" in error.lower() for error in json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))["errors"])


def test_absent_evidence_must_not_exist(tmp_path: Path) -> None:
    run = prepare(tmp_path)
    run_dir = only_run(tmp_path)
    (run_dir / "src").mkdir()
    (run_dir / "src" / "01.py").write_text("exists\n", encoding="utf-8")
    write_receipt_at(
        run_dir,
        run,
        [{"id": 1, "verdict": "pass", "evidence": [{"kind": "absent", "path": "src/01.py"}]}],
    )

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1
    assert any("absent" in error.lower() for error in json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))["errors"])


def test_every_acceptance_item_needs_exactly_one_criterion(tmp_path: Path) -> None:
    run = prepare(tmp_path)
    run_dir = only_run(tmp_path)
    write_receipt_at(run_dir, run, [{"id": 2, "verdict": "pass", "evidence": [{"kind": "note", "note": "x"}]}])

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1
    assert any("criteria" in error.lower() for error in json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))["errors"])
