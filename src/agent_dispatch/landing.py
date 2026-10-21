"""Landing: turn a reviewed run into an integration branch for a human PR."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .state import DispatchState, Run
from .ticket import parse_ticket
from .verify import worktree_diff_hash


class LandingError(Exception):
    """A landing precondition or git operation failed."""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


def _detail(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or "git command failed").strip()


def _run_git(root: Path, *args: str) -> str:
    result = _git(root, *args)
    if result.returncode != 0:
        raise LandingError(_detail(result))
    return result.stdout.strip()


def _branch_exists(root: Path, branch: str) -> bool:
    return _git(root, "rev-parse", "--verify", f"refs/heads/{branch}").returncode == 0


def _default_target(root: Path) -> str:
    for branch in ("main", "master"):
        if _branch_exists(root, branch):
            return branch
    current = _git(root, "branch", "--show-current").stdout.strip()
    return current or "main"


def _checkout_is_clean(root: Path) -> bool:
    status = _git(root, "status", "--porcelain", "--untracked-files=all").stdout
    for line in status.splitlines():
        path = line[3:] if len(line) > 3 else ""
        if path == ".dispatch" or path.startswith(".dispatch/"):
            continue
        if path:
            return False
    return True


def _assert_reviewed_worktree(run: Run) -> None:
    verify_path = run.directory / "verify.json"
    if not verify_path.is_file():
        raise LandingError("run has no verify record; verify before land")
    try:
        record = json.loads(verify_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LandingError("cannot read verify record: " + str(error)) from error
    if not isinstance(record, dict):
        raise LandingError("verify record must be a JSON object")
    expected = str(record.get("diff_hash", ""))
    if not expected:
        raise LandingError("verify record has no worktree diff hash; rerun verify")
    try:
        actual = worktree_diff_hash(run.execution_root, str(run.data.get("base_commit", "")))
    except ValueError as error:
        raise LandingError("cannot snapshot the run worktree: " + str(error)) from error
    if actual != expected:
        raise LandingError(
            "run worktree changed after verification; rerun verify and review before land"
        )


def _commit_worktree(run: Run) -> str:
    worktree = run.execution_root
    status = _git(worktree, "status", "--porcelain", "--untracked-files=all")
    if status.returncode != 0:
        raise LandingError(_detail(status))
    if status.stdout.strip():
        added = _git(worktree, "add", "-A")
        if added.returncode != 0:
            raise LandingError("cannot stage the run worktree: " + _detail(added))
        committed = _git(
            worktree,
            "-c",
            "user.name=agent-dispatch",
            "-c",
            "user.email=dispatch@localhost",
            "commit",
            "-m",
            f"dispatch: land {run.data['ticket_id']} ({run.id})",
        )
        if committed.returncode != 0:
            raise LandingError("cannot commit the run worktree: " + _detail(committed))
    commit = _run_git(worktree, "rev-parse", "HEAD")
    base = str(run.data.get("base_commit", ""))
    if commit == base:
        raise LandingError("run has no changes to land")
    if base:
        changed = _git(worktree, "diff", "--quiet", base, commit)
        if changed.returncode == 0:
            raise LandingError("run has no changes to land")
        if changed.returncode not in (0, 1):
            raise LandingError("cannot inspect the run diff: " + _detail(changed))
    return commit


def land_run(
    root: Path,
    ticket_id: str,
    *,
    target_branch: str | None = None,
    integration_branch: str | None = None,
) -> dict[str, object]:
    """Create an integration branch containing a reviewed run.

    The target branch is never checked out, merged into, or pushed. The result
    is a local branch plus a landing record for a human to open a PR from.
    """
    root = Path(root).resolve()
    store = DispatchState(root)
    current = store.ticket(ticket_id)
    if not current:
        raise LandingError(f"ticket {ticket_id!r} has no run; render it first")
    if current.get("state") != "done":
        raise LandingError(
            f"ticket {ticket_id!r} is {current.get('state')}, expected done; review must pass first"
        )

    run = Run.load(root, str(current["run_id"]))
    if run.data.get("state") != "done":
        raise LandingError(f"run {run.id} is not done; review must pass first")
    if not run.data.get("use_worktree") or not run.data.get("worktree_branch"):
        raise LandingError("land requires a worktree run; this run has no worktree branch")

    ticket = parse_ticket(run.ticket_path)
    if ticket.content_hash != str(run.data.get("ticket_hash", "")):
        raise LandingError("ticket content changed since render; rerender the run first")
    if not run.execution_root.is_dir():
        raise LandingError(f"run worktree is missing: {run.execution_root}")
    if (run.directory / "landing.json").exists():
        raise LandingError(f"run {run.id} already has a landing record")
    if not _checkout_is_clean(root):
        raise LandingError("main checkout is dirty; land will not modify a dirty checkout")

    run_branch = str(run.data["worktree_branch"])
    if not _branch_exists(root, run_branch):
        raise LandingError(f"run branch not found: {run_branch}")

    target = target_branch or _default_target(root)
    if not _branch_exists(root, target):
        raise LandingError(f"target branch not found: {target}")
    target_commit = _run_git(root, "rev-parse", f"refs/heads/{target}")

    integration = integration_branch or f"dispatch/land/{run.id}"
    if _branch_exists(root, integration):
        raise LandingError(f"integration branch already exists: {integration}")

    _assert_reviewed_worktree(run)
    run_commit = _commit_worktree(run)
    if _branch_exists(root, integration):
        raise LandingError(f"integration branch already exists: {integration}")

    landing_root = (
        root / ".dispatch" / "landings" / f"{run.id}-{uuid.uuid4().hex[:6]}"
    )
    landing_root.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        added = _git(
            root,
            "worktree",
            "add",
            "-b",
            integration,
            str(landing_root),
            target_commit,
        )
        if added.returncode != 0:
            raise LandingError("cannot create the integration worktree: " + _detail(added))
        created = True
        merged = _git(
            landing_root,
            "-c",
            "user.name=agent-dispatch",
            "-c",
            "user.email=dispatch@localhost",
            "merge",
            "--no-ff",
            "--no-edit",
            run_commit,
        )
        if merged.returncode != 0:
            raise LandingError("landing merge failed: " + _detail(merged))
        landing_commit = _run_git(landing_root, "rev-parse", "HEAD")
        ancestry = _git(root, "merge-base", "--is-ancestor", run_commit, landing_commit)
        if ancestry.returncode != 0:
            raise LandingError("integration branch does not contain the run commit")
    except LandingError:
        if created:
            _git(landing_root, "merge", "--abort")
            _git(root, "worktree", "remove", "--force", str(landing_root))
        if _branch_exists(root, integration):
            _git(root, "branch", "-D", integration)
        shutil.rmtree(landing_root, ignore_errors=True)
        _git(root, "worktree", "prune")
        raise

    removed = _git(root, "worktree", "remove", "--force", str(landing_root))
    if removed.returncode != 0:
        shutil.rmtree(landing_root, ignore_errors=True)
        _git(root, "worktree", "prune")

    record: dict[str, object] = {
        "ticket_id": ticket.id,
        "run_id": run.id,
        "target_branch": target,
        "target_commit": target_commit,
        "run_branch": run_branch,
        "run_commit": run_commit,
        "integration_branch": integration,
        "landing_commit": landing_commit,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "landed",
        "pushed": False,
        "pr_url": None,
    }
    landing_path = run.directory / "landing.json"
    landing_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    ledger = root / ".dispatch" / "ledger" / "landings.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    row = dict(record)
    row["landing_hash"] = hashlib.sha256(landing_path.read_bytes()).hexdigest()
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    run.data["landing"] = record
    run.write()
    return record
