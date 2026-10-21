from __future__ import annotations

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
    runs = sorted((tmp_path / ".dispatch" / "runs").iterdir())
    assert len(runs) == 1
    return runs[0]


def execution_root(tmp_path: Path, run: dict) -> Path:
    value = str(run.get("execution_root", ""))
    if not value:
        return tmp_path
    path = Path(value)
    return path if path.is_absolute() else tmp_path / path


def python_command(script: Path) -> str:
    return f'"{sys.executable}" "{script}"'


def write_executor(tmp_path: Path, *, fail_first: bool = False, always_fail: bool = False) -> str:
    tools = tmp_path / ".dispatch" / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    script = tools / "executor.py"
    script.write_text(
        f"""import json
import os
import pathlib
import sys

attempt = int(os.environ["DISPATCH_ATTEMPT"])
if {always_fail!r}:
    sys.exit(3)
if {fail_first!r} and attempt == 1:
    sys.exit(3)

run_dir = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
root = pathlib.Path(os.environ["DISPATCH_EXECUTION_ROOT"])
(root / "src").mkdir(exist_ok=True)
(root / "src" / "01.py").write_text("print('done')\\n", encoding="utf-8")
(run_dir / "evidence").mkdir(exist_ok=True)
(run_dir / "evidence" / "proof.txt").write_text("proof\\n", encoding="utf-8")
receipt = {{
    "ticket_id": "01",
    "run_id": os.environ["DISPATCH_RUN_ID"],
    "status": "done",
    "summary": "implemented",
    "evidence": ["evidence/proof.txt"],
}}
(run_dir / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
print("executor ok")
""",
        encoding="utf-8",
    )
    return python_command(script)


def write_reviewer(tmp_path: Path, verdict: str = "pass") -> str:
    tools = tmp_path / ".dispatch" / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    script = tools / "reviewer.py"
    script.write_text(
        f"""import json
import os
import pathlib

result = pathlib.Path(os.environ["DISPATCH_REVIEW_RESULT"])
result.write_text(json.dumps({{"verdict": {verdict!r}, "notes": "reviewed"}}), encoding="utf-8")
print("reviewer ok")
""",
        encoding="utf-8",
    )
    return python_command(script)


def make_repo(tmp_path: Path) -> None:
    directory = tmp_path / "tickets"
    directory.mkdir()
    (directory / "01-a.md").write_text(ticket_text(), encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")


def read_auto(run_dir: Path) -> dict:
    return json.loads((run_dir / "auto.json").read_text(encoding="utf-8"))


def read_state(tmp_path: Path) -> dict:
    return json.loads((tmp_path / ".dispatch" / "state.json").read_text(encoding="utf-8"))


def test_auto_runs_executor_and_stops_at_review(tmp_path: Path) -> None:
    make_repo(tmp_path)
    executor = write_executor(tmp_path)

    result = run_dispatch(tmp_path, "auto", "01", "--executor", executor)

    assert result.returncode == 0, result.stderr
    assert "review" in result.stdout.lower()
    run_dir = only_run(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    auto = read_auto(run_dir)
    assert auto["status"] == "review"
    assert len(auto["attempts"]) == 1
    assert auto["attempts"][0]["verify_status"] == "passed"
    assert read_state(tmp_path)["tickets"]["01"]["state"] == "review"
    assert run["state"] == "review"
    assert (execution_root(tmp_path, run) / "src" / "01.py").read_text(encoding="utf-8") == "print('done')\n"
    assert json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))["status"] == "passed"


def test_auto_retries_after_a_failed_attempt(tmp_path: Path) -> None:
    make_repo(tmp_path)
    executor = write_executor(tmp_path, fail_first=True)

    result = run_dispatch(
        tmp_path,
        "auto",
        "01",
        "--executor",
        executor,
        "--max-attempts",
        "2",
    )

    assert result.returncode == 0, result.stderr
    auto = read_auto(only_run(tmp_path))
    assert auto["status"] == "review"
    assert [attempt["attempt"] for attempt in auto["attempts"]] == [1, 2]
    assert auto["attempts"][0]["verify_status"] == "failed"
    assert auto["attempts"][1]["verify_status"] == "passed"
    assert read_state(tmp_path)["tickets"]["01"]["state"] == "review"


def test_auto_fails_after_max_attempts(tmp_path: Path) -> None:
    make_repo(tmp_path)
    executor = write_executor(tmp_path, always_fail=True)

    result = run_dispatch(
        tmp_path,
        "auto",
        "01",
        "--executor",
        executor,
        "--max-attempts",
        "2",
    )

    assert result.returncode == 1
    auto = read_auto(only_run(tmp_path))
    assert auto["status"] == "failed"
    assert len(auto["attempts"]) == 2
    assert all(attempt["verify_status"] == "failed" for attempt in auto["attempts"])
    assert read_state(tmp_path)["tickets"]["01"]["state"] == "failed"


def test_auto_land_requires_a_reviewer_command(tmp_path: Path) -> None:
    make_repo(tmp_path)
    executor = write_executor(tmp_path)

    result = run_dispatch(
        tmp_path,
        "auto",
        "01",
        "--executor",
        executor,
        "--until",
        "land",
        "--reviewer",
        "reviewer-b",
    )

    assert result.returncode == 1
    assert "reviewer-command" in result.stderr.lower()
    assert not (tmp_path / ".dispatch" / "runs").exists()


def test_auto_land_runs_a_separate_reviewer_and_creates_an_integration_branch(tmp_path: Path) -> None:
    make_repo(tmp_path)
    executor = write_executor(tmp_path)
    reviewer = write_reviewer(tmp_path)
    target_before = git(tmp_path, "rev-parse", "HEAD")

    result = run_dispatch(
        tmp_path,
        "auto",
        "01",
        "--executor",
        executor,
        "--until",
        "land",
        "--reviewer",
        "reviewer-b",
        "--reviewer-command",
        reviewer,
    )

    assert result.returncode == 0, result.stderr
    run_dir = only_run(tmp_path)
    auto = read_auto(run_dir)
    landing = json.loads((run_dir / "landing.json").read_text(encoding="utf-8"))
    assert auto["status"] == "landed"
    assert auto["review"]["verdict"] == "pass"
    assert landing["pushed"] is False
    assert landing["pr_url"] is None
    assert git(tmp_path, "rev-parse", "HEAD") == target_before
    assert git(tmp_path, "show", landing["integration_branch"] + ":src/01.py").strip() == "print('done')"
    assert read_state(tmp_path)["tickets"]["01"]["state"] == "done"


def test_auto_land_records_a_failing_reviewer_verdict_without_landing(tmp_path: Path) -> None:
    make_repo(tmp_path)
    executor = write_executor(tmp_path)
    reviewer = write_reviewer(tmp_path, verdict="fail")

    result = run_dispatch(
        tmp_path,
        "auto",
        "01",
        "--executor",
        executor,
        "--until",
        "land",
        "--reviewer",
        "reviewer-b",
        "--reviewer-command",
        reviewer,
    )

    assert result.returncode == 1
    run_dir = only_run(tmp_path)
    auto = read_auto(run_dir)
    assert auto["status"] == "review-failed"
    assert not (run_dir / "landing.json").exists()
    assert read_state(tmp_path)["tickets"]["01"]["state"] == "failed"


def test_auto_reviewer_log_does_not_overwrite_executor_log(tmp_path: Path) -> None:
    make_repo(tmp_path)
    executor = write_executor(tmp_path)
    reviewer = write_reviewer(tmp_path)

    result = run_dispatch(
        tmp_path,
        "auto",
        "01",
        "--executor",
        executor,
        "--until",
        "land",
        "--reviewer",
        "reviewer-b",
        "--reviewer-command",
        reviewer,
    )

    assert result.returncode == 0, result.stderr
    run_dir = only_run(tmp_path)
    auto_dir = run_dir / "auto"
    assert "executor ok" in (auto_dir / "attempt-01.log").read_text(encoding="utf-8")
    assert "reviewer ok" in (auto_dir / "reviewer.log").read_text(encoding="utf-8")
