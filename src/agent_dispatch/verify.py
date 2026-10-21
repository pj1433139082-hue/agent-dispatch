"""Independent verification gate: commands, git diff, and evidence hashes."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .state import DispatchState, Run
from .ticket import Ticket

IGNORED_PREFIXES = (
    ".dispatch/",
    ".git/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
)
IGNORED_SUFFIXES = (".pyc", ".pyo")


def _normalize(path: str) -> str:
    value = path.replace("\\", "/").strip()
    while value.startswith("./"):
        value = value[2:]
    return value


def _glob_regex(pattern: str) -> re.Pattern[str]:
    out: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                out.append(".*")
                index += 2
                continue
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
        index += 1
    out.append("$")
    return re.compile("".join(out))


def path_matches_scope(scope: str, path: str) -> bool:
    scope = _normalize(scope)
    path = _normalize(path)
    if not scope or not path:
        return False
    if scope.endswith("/"):
        scope = scope + "**"
    if not any(marker in scope for marker in "*?["):
        return path == scope or path.startswith(scope.rstrip("/") + "/")
    return bool(_glob_regex(scope).match(path))


def _ignored(path: str) -> bool:
    return path.startswith(IGNORED_PREFIXES) or path.endswith(IGNORED_SUFFIXES)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)


def changed_files(root: Path, base_commit: str) -> list[str]:
    if not base_commit:
        raise ValueError("run has no base commit; render inside a git repository")
    diff = _git(root, "diff", "--name-only", "-z", base_commit)
    if diff.returncode != 0:
        raise ValueError(diff.stderr.decode("utf-8", errors="replace").strip())
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if untracked.returncode != 0:
        raise ValueError(untracked.stderr.decode("utf-8", errors="replace").strip())
    paths = {
        _normalize(path)
        for payload in (diff.stdout, untracked.stdout)
        for path in payload.decode("utf-8", errors="replace").split("\0")
        if path
    }
    return sorted(path for path in paths if not _ignored(path))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_command(command: str, root: Path, log_path: Path, timeout: int) -> dict[str, object]:
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        exit_code = result.returncode
        body = f"$ {command}\n\n[stdout]\n{result.stdout}\n[stderr]\n{result.stderr}"
    except (OSError, ValueError) as error:
        exit_code = -1
        body = f"$ {command}\n\n[failed to start]\n{error}\n"
    except subprocess.TimeoutExpired as error:
        exit_code = -1
        body = f"$ {command}\n\n[timeout after {timeout}s]\n{error}\n"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(body, encoding="utf-8")
    return {
        "command": command,
        "exit_code": exit_code,
        "log": log_path.name,
        "log_hash": _sha256(log_path),
    }


def verify_run(root: Path, ticket: Ticket, run: Run, timeout: int = 300) -> tuple[dict[str, object], bool]:
    root = Path(root)
    run_dir = run.directory
    checks: list[dict[str, object]] = []
    errors: list[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            errors.append(f"{name}: {detail}")

    ticket_path = run.ticket_path
    if not ticket_path.is_file():
        check("ticket", False, f"ticket file is missing: {ticket_path}")
    else:
        actual_hash = hashlib.sha256(ticket_path.read_bytes()).hexdigest()
        expected_hash = str(run.data.get("ticket_hash", ""))
        check(
            "ticket",
            actual_hash == expected_hash,
            "ticket changed after render" if actual_hash != expected_hash else "unchanged",
        )

    receipt_path = run_dir / "receipt.json"
    receipt: dict[str, object] | None = None
    if not receipt_path.is_file():
        check("receipt", False, "receipt.json is missing")
    else:
        try:
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            check("receipt", False, f"receipt.json is not valid JSON: {error}")
        else:
            if not isinstance(payload, dict):
                check("receipt", False, "receipt.json must be an object")
            else:
                receipt = payload
                problems: list[str] = []
                if payload.get("status") != "done":
                    problems.append(f"status is {payload.get('status')!r}, expected 'done'")
                if payload.get("ticket_id") != ticket.id:
                    problems.append("ticket_id does not match")
                if payload.get("run_id") != run.id:
                    problems.append("run_id does not match")
                if not isinstance(payload.get("summary"), str) or not payload.get("summary"):
                    problems.append("summary is required")
                evidence_value = payload.get("evidence")
                if not isinstance(evidence_value, list) or not evidence_value:
                    problems.append("evidence must be a non-empty array")
                check(
                    "receipt",
                    not problems,
                    "; ".join(problems) if problems else "valid receipt",
                )

    commands: list[dict[str, object]] = []
    if receipt is not None:
        for index, command in enumerate(ticket.verify, start=1):
            record = _run_command(
                command,
                root,
                run_dir / "logs" / f"{index:02d}.log",
                timeout,
            )
            commands.append(record)
            check(
                f"command {index}",
                record["exit_code"] == 0,
                f"exit code {record['exit_code']}" if record["exit_code"] else "passed",
            )

    files: list[str] = []
    try:
        files = changed_files(root, str(run.data.get("base_commit", "")))
    except ValueError as error:
        check("git diff", False, str(error))
    else:
        out_of_scope = [
            path
            for path in files
            if not any(path_matches_scope(scope, path) for scope in ticket.write_scope)
        ]
        check(
            "write scope",
            not out_of_scope,
            "out of scope: " + ", ".join(out_of_scope) if out_of_scope else "all changes in scope",
        )

    evidence: list[dict[str, object]] = []
    if receipt is not None and isinstance(receipt.get("evidence"), list):
        for item in receipt["evidence"]:
            if not isinstance(item, str) or not item:
                check("evidence", False, "evidence entries must be non-empty strings")
                continue
            candidate = Path(item)
            if candidate.is_absolute():
                check("evidence", False, f"absolute evidence path is not allowed: {item}")
                continue
            path = run_dir / candidate
            if not path.is_file():
                check("evidence", False, f"evidence file is missing: {item}")
                continue
            evidence.append({"path": item, "sha256": _sha256(path)})

    passed = not errors
    record: dict[str, object] = {
        "run_id": run.id,
        "ticket_id": ticket.id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed",
        "checks": checks,
        "changed_files": files,
        "commands": commands,
        "evidence": evidence,
        "errors": errors,
    }
    (run_dir / "verify.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    store = DispatchState(root)
    if passed:
        run.set_state("review")
        store.set_ticket(ticket.id, run.id, "review")
    else:
        run.set_state("failed")
        store.set_ticket(ticket.id, run.id, "failed")
    return record, passed
