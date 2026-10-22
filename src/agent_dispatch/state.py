"""Runtime state: tickets are authored input; runs own the mutable facts."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import __version__ as _skill_version
from .ticket import Ticket
from .workorder import render_work_order

ACTIVE_STATES = {"claimed", "running", "review"}
TERMINAL_STATES = {"done", "failed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "-" for char in value)


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def current_commit(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


class DispatchState:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.directory = self.root / ".dispatch"
        self.path = self.directory / "state.json"

    def load(self) -> dict[str, object]:
        if not self.path.exists():
            return {"version": 1, "tickets": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict[str, object]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)

    def ticket(self, ticket_id: str) -> dict[str, object] | None:
        return self.load().get("tickets", {}).get(ticket_id)  # type: ignore[union-attr]

    def set_ticket(self, ticket_id: str, run_id: str, state: str) -> None:
        data = self.load()
        data.setdefault("tickets", {})[ticket_id] = {
            "run_id": run_id,
            "state": state,
            "updated_at": _now(),
        }
        self.save(data)

    def done_ids(self) -> set[str]:
        return {
            ticket_id
            for ticket_id, value in self.load().get("tickets", {}).items()
            if value.get("state") == "done"
        }


class Run:
    def __init__(self, root: Path, directory: Path, data: dict[str, object]) -> None:
        self.root = Path(root)
        self.directory = Path(directory)
        self.data = data

    @property
    def id(self) -> str:
        return str(self.data["run_id"])

    @property
    def execution_root(self) -> Path:
        value = str(self.data.get("execution_root", ""))
        if not value:
            return self.root
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    @property
    def ticket_path(self) -> Path:
        path = Path(str(self.data["ticket_path"]))
        if path.is_absolute():
            return path
        candidate = self.root / path
        if candidate.exists():
            return candidate
        # Older runs stored a path relative to the process cwd, not the root.
        return path

    @classmethod
    def create(
        cls,
        root: Path,
        ticket: Ticket,
        claimed_by: str = "",
        use_worktree: bool = True,
    ) -> "Run":
        root = Path(root).resolve()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_id = f"{_safe_id(ticket.id)}-{stamp}-{uuid.uuid4().hex[:6]}"
        directory = root / ".dispatch" / "runs" / run_id
        directory.mkdir(parents=True, exist_ok=False)
        try:
            ticket_path = ticket.path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            ticket_path = str(ticket.path.resolve())
        base_commit = current_commit(root)
        data: dict[str, object] = {
            "run_id": run_id,
            "ticket_id": ticket.id,
            "ticket_path": ticket_path,
            "ticket_hash": ticket.content_hash,
            "base_commit": base_commit,
            "state": "claimed",
            "owner": ticket.owner,
            "risk": ticket.risk,
            "claimed_by": claimed_by or ticket.owner,
            "created_at": _now(),
            "skill_version": _skill_version,
            "use_worktree": False,
            "execution_root": "",
        }
        if use_worktree and base_commit:
            worktree_path = root / ".dispatch" / "worktrees" / run_id
            branch = f"dispatch/{run_id}"
            result = subprocess.run(
                ["git", "worktree", "add", "-b", branch, str(worktree_path), base_commit],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                shutil.rmtree(worktree_path, ignore_errors=True)
                detail = (result.stderr or result.stdout or "git worktree add failed").strip()
                raise ValueError("cannot create a worktree for this run: " + detail)
            data["use_worktree"] = True
            data["worktree_path"] = _relative_to_root(worktree_path, root)
            data["worktree_branch"] = branch
            data["execution_root"] = _relative_to_root(worktree_path, root)
        run = cls(root, directory, data)
        run.write()
        (directory / "work-order.md").write_text(
            render_work_order(ticket, data), encoding="utf-8"
        )
        return run

    @classmethod
    def load(cls, root: Path, run_id: str) -> "Run":
        directory = Path(root) / ".dispatch" / "runs" / run_id
        data = json.loads((directory / "run.json").read_text(encoding="utf-8"))
        return cls(root, directory, data)

    def write(self) -> None:
        (self.directory / "run.json").write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def set_state(self, state: str) -> None:
        self.data["state"] = state
        self.data["updated_at"] = _now()
        self.write()


def load_active_run(root: Path, ticket_id: str) -> Run | None:
    state = DispatchState(root).ticket(ticket_id)
    if not state or not state.get("run_id"):
        return None
    return Run.load(root, str(state["run_id"]))
