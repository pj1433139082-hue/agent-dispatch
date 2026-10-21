"""Automated ticket execution: executor, verify, optional review and landing."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .feedback import write_feedback
from .landing import LandingError, land_run
from .review import submit_review
from .state import ACTIVE_STATES, DispatchState, Run, current_commit
from .ticket import Ticket
from .verify import verify_run


class AutoError(Exception):
    """An auto run could not be started or completed safely."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_command(
    command: str,
    *,
    cwd: Path,
    log_path: Path,
    timeout: int,
    env: dict[str, str],
) -> dict[str, object]:
    timed_out = False
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        exit_code = -1
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        stderr = (stderr + "\n" if stderr else "") + f"[timeout after {timeout}s]"
    except (OSError, ValueError) as error:
        exit_code = -1
        stdout = ""
        stderr = f"[failed to start] {error}"

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"$ {command}\n\n[stdout]\n{stdout}\n[stderr]\n{stderr}",
        encoding="utf-8",
    )
    return {
        "exit_code": exit_code,
        "timed_out": timed_out,
        "log": log_path.name,
        "log_hash": _sha256(log_path),
    }


def _write_result(run: Run, result: dict[str, object]) -> None:
    result["updated_at"] = _now()
    (run.directory / "auto.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _execute(
    *,
    command: str,
    run: Run,
    attempt: int,
    timeout: int,
    extra_env: dict[str, str] | None = None,
    log_name: str = "",
) -> dict[str, object]:
    log_path = run.directory / "auto" / (log_name or f"attempt-{attempt:02d}.log")
    env = os.environ.copy()
    env.update(
        {
            "DISPATCH_TICKET_ID": str(run.data["ticket_id"]),
            "DISPATCH_RUN_ID": run.id,
            "DISPATCH_RUN_DIR": str(run.directory),
            "DISPATCH_EXECUTION_ROOT": str(run.execution_root),
            "DISPATCH_WORK_ORDER": str(run.directory / "work-order.md"),
            "DISPATCH_TICKET_PATH": str(run.ticket_path),
            "DISPATCH_ATTEMPT": str(attempt),
        }
    )
    if extra_env:
        env.update(extra_env)
    return _run_command(
        command,
        cwd=run.execution_root,
        log_path=log_path,
        timeout=timeout,
        env=env,
    )


def _read_review_result(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise AutoError(f"reviewer did not write {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AutoError(f"cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise AutoError(f"{path.name} must be a JSON object")
    verdict = str(value.get("verdict", "")).strip().lower()
    if verdict not in {"pass", "fail"}:
        raise AutoError(f"{path.name} verdict must be 'pass' or 'fail'")
    notes = value.get("notes", "")
    return {"verdict": verdict, "notes": str(notes) if notes is not None else ""}


def _review_and_land(
    *,
    root: Path,
    ticket: Ticket,
    run: Run,
    result: dict[str, object],
    reviewer: str,
    reviewer_command: str,
    timeout: int,
    human: bool,
    accept_degraded: bool,
) -> None:
    review_result_path = run.directory / "review-result.json"
    if review_result_path.exists():
        review_result_path.unlink()
    try:
        execution = _execute(
            command=reviewer_command,
            run=run,
            attempt=1,
            timeout=timeout,
            extra_env={
                "DISPATCH_REVIEWER": reviewer,
                "DISPATCH_VERIFY_JSON": str(run.directory / "verify.json"),
                "DISPATCH_REVIEW_RESULT": str(review_result_path),
            },
            log_name="reviewer.log",
        )
        execution["role"] = "reviewer"
        result["reviewer_execution"] = execution
        review = _read_review_result(review_result_path)
    except AutoError as error:
        result["status"] = "review-invalid"
        result["error"] = str(error)
        _write_result(run, result)
        return

    if review["verdict"] == "pass" and execution["exit_code"] != 0:
        result["status"] = "review-invalid"
        result["error"] = (
            f"reviewer wrote pass but exited {execution['exit_code']}; no review recorded"
        )
        _write_result(run, result)
        return

    record, errors = submit_review(
        root,
        ticket,
        run,
        reviewer=reviewer,
        verdict=str(review["verdict"]),
        notes=str(review.get("notes", "")),
        human=human,
        accept_degraded=accept_degraded,
    )
    if errors:
        result["status"] = "review-invalid"
        result["error"] = "; ".join(errors)
        _write_result(run, result)
        return
    result["review"] = record
    if record is not None and record.get("verdict") != "pass":
        result["status"] = "review-failed"
        _write_result(run, result)
        return

    try:
        landing = land_run(root, ticket.id)
    except LandingError as error:
        result["status"] = "land-failed"
        result["error"] = str(error)
        _write_result(run, result)
        return
    result["landing"] = landing
    result["status"] = "landed"
    _write_result(run, result)


def auto_run(
    root: Path,
    ticket: Ticket,
    *,
    executor: str,
    agent: str = "",
    max_attempts: int = 1,
    timeout: int = 1800,
    verify_timeout: int = 300,
    until: str = "review",
    reviewer: str = "",
    reviewer_command: str = "",
    accept_degraded: bool = False,
    human: bool = False,
) -> dict[str, object]:
    """Run a ticket through an external executor and the dispatch gates.

    The executor is an arbitrary shell command. It runs in the run worktree and
    receives DISPATCH_TICKET_ID, DISPATCH_RUN_ID, DISPATCH_RUN_DIR,
    DISPATCH_EXECUTION_ROOT and DISPATCH_WORK_ORDER in its environment. It must
    write receipt.json and evidence into DISPATCH_RUN_DIR.

    With --until review (the default), the command stops once verification has
    passed. With --until land, a separate reviewer command must write
    review-result.json with a pass/fail verdict; only then is a local
    integration branch created. The target branch is never pushed or merged.
    """
    root = Path(root).resolve()
    executor = executor.strip()
    until = until.strip().lower()
    if not executor:
        raise AutoError("executor command is required")
    if until not in {"review", "land"}:
        raise AutoError("until must be 'review' or 'land'")
    if max_attempts < 1:
        raise AutoError("max-attempts must be at least 1")
    if timeout <= 0 or verify_timeout <= 0:
        raise AutoError("timeouts must be positive")
    if until == "land":
        if not reviewer.strip():
            raise AutoError("--until land requires --reviewer")
        if not reviewer_command.strip():
            raise AutoError("--until land requires --reviewer-command")
    if not current_commit(root):
        raise AutoError("auto requires a git repository with at least one commit")

    store = DispatchState(root)
    existing = store.ticket(ticket.id)
    if existing:
        state = str(existing.get("state", ""))
        if state == "done":
            raise AutoError(f"ticket {ticket.id} is already done")
        if state in ACTIVE_STATES:
            raise AutoError(f"ticket {ticket.id} already has an active run")
    missing = sorted(dep for dep in ticket.depends_on if dep not in store.done_ids())
    if missing:
        raise AutoError(
            f"ticket {ticket.id} is blocked by unfinished tickets: {', '.join(missing)}"
        )

    try:
        run = Run.create(root, ticket, claimed_by=agent, use_worktree=True)
    except ValueError as error:
        raise AutoError(str(error)) from error
    if not run.data.get("use_worktree"):
        raise AutoError("auto requires a worktree run; render inside a git repository")
    store.set_ticket(ticket.id, run.id, "claimed")
    run.set_state("running")
    store.set_ticket(ticket.id, run.id, "running")

    result: dict[str, object] = {
        "version": 1,
        "ticket_id": ticket.id,
        "run_id": run.id,
        "executor": executor,
        "until": until,
        "max_attempts": max_attempts,
        "status": "running",
        "verify_status": "",
        "attempts": [],
        "review": None,
        "landing": None,
        "run_directory": str(run.directory),
        "created_at": _now(),
    }
    _write_result(run, result)

    attempts = result["attempts"]
    assert isinstance(attempts, list)
    verify_status = ""
    last_errors: list[str] = []
    while len(attempts) < max_attempts:
        attempt_number = len(attempts) + 1
        if attempt_number > 1:
            run.set_state("running")
            store.set_ticket(ticket.id, run.id, "running")
        feedback_path = ""
        if attempt_number > 1 and last_errors:
            written = write_feedback(
                run.directory,
                attempt_number - 1,
                last_errors,
                log_name="attempt-" + str(attempt_number - 1).zfill(2) + ".log",
            )
            feedback_path = str(written)
        execution = _execute(
            command=executor,
            run=run,
            attempt=attempt_number,
            timeout=timeout,
            extra_env={"DISPATCH_FEEDBACK": feedback_path} if feedback_path else None,
        )
        record, passed = verify_run(root, ticket, run, timeout=verify_timeout)
        verify_status = str(record.get("status", "failed"))
        errors = [str(error) for error in record.get("errors", [])]
        attempts.append(
            {
                "attempt": attempt_number,
                "executor": {
                    "exit_code": execution["exit_code"],
                    "timed_out": execution["timed_out"],
                    "log": str((run.directory / "auto" / f"attempt-{attempt_number:02d}.log").relative_to(run.directory)),
                    "log_hash": execution["log_hash"],
                },
                "verify_status": verify_status,
                "verify_errors": errors,
                "feedback": feedback_path,
                "at": _now(),
            }
        )
        result["verify_status"] = verify_status
        last_errors = errors
        _write_result(run, result)
        if passed:
            break

    if verify_status not in {"passed", "degraded"}:
        result["status"] = "failed"
        result["last_errors"] = last_errors
        _write_result(run, result)
        return result

    if until == "review":
        result["status"] = "review"
        _write_result(run, result)
        return result

    if verify_status == "degraded" and not accept_degraded:
        result["status"] = "review-invalid"
        result["error"] = "verification is degraded; pass --accept-degraded to review it"
        _write_result(run, result)
        return result

    _review_and_land(
        root=root,
        ticket=ticket,
        run=run,
        result=result,
        reviewer=reviewer.strip(),
        reviewer_command=reviewer_command,
        timeout=timeout,
        human=human,
        accept_degraded=accept_degraded,
    )
    return result
