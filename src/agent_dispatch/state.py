"""Runtime state: tickets are authored input; runs own the mutable facts."""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .ticket import Ticket
from .workorder import render_work_order

ACTIVE_STATES = {"claimed", "running", "review"}
TERMINAL_STATES = {"done", "failed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "-" for char in value)


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

    @classmethod
    def create(cls, root: Path, ticket: Ticket, claimed_by: str = "") -> "Run":
        root = Path(root)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_id = f"{_safe_id(ticket.id)}-{stamp}-{uuid.uuid4().hex[:6]}"
        directory = root / ".dispatch" / "runs" / run_id
        directory.mkdir(parents=True, exist_ok=False)
        data: dict[str, object] = {
            "run_id": run_id,
            "ticket_id": ticket.id,
            "ticket_path": str(ticket.path),
            "ticket_hash": ticket.content_hash,
            "base_commit": current_commit(root),
            "state": "claimed",
            "owner": ticket.owner,
            "risk": ticket.risk,
            "claimed_by": claimed_by or ticket.owner,
            "created_at": _now(),
        }
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
