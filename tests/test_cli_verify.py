from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ticket_text(verify: str = "python -c \"print('ok')\"") -> str:
    return f"""# 01: A

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


def prepare(tmp_path: Path, verify: str = "python -c \"print('ok')\"") -> Path:
    directory = tmp_path / "tickets"
    directory.mkdir()
    (directory / "01-a.md").write_text(ticket_text(verify), encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(directory)).returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    return directory


def only_run(tmp_path: Path) -> Path:
    return sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]


def execution_root(tmp_path: Path) -> Path:
    run = json.loads((only_run(tmp_path) / "run.json").read_text(encoding="utf-8"))
    value = str(run.get("execution_root", ""))
    if not value:
        return tmp_path
    path = Path(value)
    return path if path.is_absolute() else tmp_path / path


def write_receipt(
    tmp_path: Path,
    *,
    status: str = "done",
    evidence: list[str] | None = None,
    changed_files: list[str] | None = None,
) -> Path:
    run_dir = only_run(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    receipt = {
        "ticket_id": "01",
        "run_id": run["run_id"],
        "status": status,
        "summary": "implemented",
        "evidence": evidence if evidence is not None else ["evidence/proof.txt"],
    }
    if changed_files is not None:
        receipt["changed_files"] = changed_files
    (run_dir / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return run_dir


def add_evidence(run_dir: Path, name: str = "evidence/proof.txt") -> Path:
    path = run_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("proof\n", encoding="utf-8")
    return path


def read_verify(tmp_path: Path) -> dict:
    return json.loads((only_run(tmp_path) / "verify.json").read_text(encoding="utf-8"))


def test_passing_verification_moves_state_to_review(tmp_path: Path) -> None:
    prepare(tmp_path)
    run_dir = write_receipt(tmp_path)
    add_evidence(run_dir)
    (execution_root(tmp_path) / "src").mkdir()
    (execution_root(tmp_path) / "src" / "01.py").write_text("print('done')\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 0, result.stderr
    record = read_verify(tmp_path)
    assert record["status"] == "passed"
    assert record["changed_files"] == ["src/01.py"]
    assert record["commands"][0]["exit_code"] == 0
    assert record["commands"][0]["log_hash"]
    assert record["evidence"][0]["sha256"]
    state = json.loads((tmp_path / ".dispatch" / "state.json").read_text(encoding="utf-8"))
    assert state["tickets"]["01"]["state"] == "review"


def test_missing_receipt_fails_and_marks_failed(tmp_path: Path) -> None:
    prepare(tmp_path)

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1
    record = read_verify(tmp_path)
    assert record["status"] == "failed"
    assert any("receipt" in error.lower() for error in record["errors"])
    state = json.loads((tmp_path / ".dispatch" / "state.json").read_text(encoding="utf-8"))
    assert state["tickets"]["01"]["state"] == "failed"


def test_non_done_receipt_fails(tmp_path: Path) -> None:
    prepare(tmp_path)
    write_receipt(tmp_path, status="failed")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1
    assert any("status" in error.lower() for error in read_verify(tmp_path)["errors"])


def test_failed_command_fails(tmp_path: Path) -> None:
    prepare(tmp_path, "python -c \"import sys; sys.exit(3)\"")
    run_dir = write_receipt(tmp_path)
    add_evidence(run_dir)

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1
    record = read_verify(tmp_path)
    assert record["commands"][0]["exit_code"] == 3
    assert any("command" in error.lower() for error in record["errors"])


def test_out_of_scope_file_fails(tmp_path: Path) -> None:
    prepare(tmp_path)
    run_dir = write_receipt(tmp_path)
    add_evidence(run_dir)
    (execution_root(tmp_path) / "outside.txt").write_text("nope\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1
    record = read_verify(tmp_path)
    assert "outside.txt" in record["changed_files"]
    assert any("scope" in error.lower() for error in record["errors"])


def test_missing_evidence_fails(tmp_path: Path) -> None:
    prepare(tmp_path)
    write_receipt(tmp_path, evidence=["evidence/missing.txt"])

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1
    assert any("evidence" in error.lower() for error in read_verify(tmp_path)["errors"])


def test_ticket_changed_after_render_fails(tmp_path: Path) -> None:
    directory = prepare(tmp_path)
    run_dir = write_receipt(tmp_path)
    add_evidence(run_dir)
    with (directory / "01-a.md").open("a", encoding="utf-8") as handle:
        handle.write("\nchanged\n")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1
    assert any("ticket" in error.lower() for error in read_verify(tmp_path)["errors"])


def test_receipt_changed_files_claim_is_not_trusted(tmp_path: Path) -> None:
    prepare(tmp_path)
    run_dir = write_receipt(tmp_path, changed_files=[])
    add_evidence(run_dir)
    (tmp_path / "outside.txt").write_text("nope\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1
    assert "outside.txt" in read_verify(tmp_path)["changed_files"]
