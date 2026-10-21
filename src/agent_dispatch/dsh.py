"""DSH task board and Agent Teams adapters.

The DSH task board is a Host-authoritative ledger behind the Web GUI. Its
HTTP action endpoint accepts a JSON envelope:

    {"requestId": "...", "action": {"kind": "create", "id": "...", "input": {...}}}

This module builds those envelopes, pushes ready tickets to the board, and
records external outcomes for work completed by agents outside DSH. It never
runs a card: running is a deliberate human act in the board UI or through the
board's own run action.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

from .export import PERMISSIONS, ready_tickets, ticket_section
from .ticket import Ticket

DEFAULT_BASE_URL = "http://127.0.0.1:50567"
API_PREFIX = "/api/task-board"
DISPATCH_TAG = "dispatch"
MAP_VERSION = 1
MAX_TAG_LENGTH = 32
RISK_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}


class TaskBoardError(RuntimeError):
    """A task board request failed or returned an invalid payload."""

    def __init__(self, message: str, status: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def normalize_base_url(value: str | None = None) -> str:
    base = (value or os.environ.get("DSH_TASK_BOARD_URL") or DEFAULT_BASE_URL).strip()
    base = base.rstrip("/")
    if base.endswith(API_PREFIX):
        return base
    return base + API_PREFIX


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tag_for(ticket_id: str) -> str:
    raw = f"{DISPATCH_TAG}:{ticket_id}"
    if len(raw) <= MAX_TAG_LENGTH:
        return raw
    digest = hashlib.sha1(ticket_id.encode("utf-8")).hexdigest()[:8]
    return f"{DISPATCH_TAG}:{ticket_id[:14]}:{digest}"


def _uuid_for(project: str, ticket_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"agent-dispatch:{project}:{ticket_id}"))


def wave_id(project: str, ticket_ids: list[str]) -> str:
    joined = ",".join(sorted(ticket_ids))
    return _uuid_for(project, "wave:" + joined)


def _permission_for(risks: list[str]) -> str:
    highest = max(risks or ["L1"], key=lambda risk: RISK_ORDER.get(risk, 1))
    return PERMISSIONS.get(highest, "workspace-write")


def card_input(
    ticket: Ticket,
    *,
    workspace_id: str | None = None,
    team_run: bool | None = None,
    parent_id: str | None = None,
) -> dict[str, object]:
    """Build the NewTaskInput accepted by the board create action."""
    prompt = ticket_section(ticket).strip()
    tags = [
        {"name": DISPATCH_TAG},
        {"name": _tag_for(ticket.id)},
        {"name": ticket.risk or "L1"},
    ]
    payload: dict[str, object] = {
        "title": f"{ticket.id}: {ticket.title}",
        "description": ticket.what_to_build or ticket.title,
        "prompt": prompt,
        "tags": tags,
        "permission": _permission_for([ticket.risk or "L1"]),
    }
    if workspace_id:
        payload["workspaceId"] = workspace_id
    if parent_id:
        payload["parentId"] = parent_id
    if team_run is not None:
        payload["teamRun"] = team_run
    return payload


def create_action(
    ticket: Ticket,
    *,
    project: str,
    workspace_id: str | None = None,
    parent_id: str | None = None,
    team_run: bool | None = None,
) -> dict[str, object]:
    """Build one create action envelope for a ticket."""
    return {
        "requestId": str(uuid.uuid4()),
        "action": {
            "kind": "create",
            "id": _uuid_for(project, ticket.id),
            "input": card_input(
                ticket,
                workspace_id=workspace_id,
                parent_id=parent_id,
                team_run=team_run,
            ),
        },
        "initiator": "agent-dispatch",
    }


def build_card_actions(
    tickets: list[Ticket],
    *,
    project: str,
    workspace_id: str | None = None,
) -> list[dict[str, object]]:
    return [create_action(ticket, project=project, workspace_id=workspace_id) for ticket in tickets]


def build_team_actions(
    tickets: list[Ticket],
    *,
    project: str,
    workspace_id: str | None = None,
) -> list[dict[str, object]]:
    """Build one team-run parent card plus one direct subtask per ticket.

    DSH starts one Team Lead session for the parent and a teammate for each
    direct subtask. The board's default subtask depth is one, so this shape is
    the portable one.
    """
    ids = [ticket.id for ticket in tickets]
    parent_id = wave_id(project, ids)
    parent_input: dict[str, object] = {
        "title": f"Dispatch wave: {len(tickets)} ticket(s)",
        "description": (
            "Agent Team run for ready dispatch tickets. Each direct subtask is "
            "one ticket contract with its own write scope and verification command."
        ),
        "prompt": (
            "You are the Team Lead for this dispatch wave. Spawn one teammate per "
            "direct subtask. Each teammate must obey the ticket's write scope and run "
            "its verification command. Do not declare a ticket complete without evidence."
        ),
        "tags": [{"name": DISPATCH_TAG}, {"name": "dispatch:wave"}],
        "permission": _permission_for([ticket.risk or "L1" for ticket in tickets]),
        "teamRun": True,
    }
    if workspace_id:
        parent_input["workspaceId"] = workspace_id
    actions: list[dict[str, object]] = [
        {
            "requestId": str(uuid.uuid4()),
            "action": {"kind": "create", "id": parent_id, "input": parent_input},
            "initiator": "agent-dispatch",
        }
    ]
    actions.extend(
        create_action(
            ticket,
            project=project,
            workspace_id=workspace_id,
            parent_id=parent_id,
        )
        for ticket in tickets
    )
    return actions


class TaskBoardClient:
    """Minimal client for the DSH task board's loopback HTTP API."""

    def __init__(self, base_url: str | None = None, timeout: float = 15.0) -> None:
        self.base_url = normalize_base_url(base_url)
        self.timeout = timeout

    def _request(self, method: str, suffix: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        data = None
        headers = {
            "accept": "application/json",
            "sec-fetch-site": "same-origin",
        }
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["content-type"] = "application/json"
        req = request.Request(self.base_url + suffix, data=data, method=method, headers=headers)
        opener = request.build_opener(request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise TaskBoardError(f"DSH task board returned HTTP {exc.code}: {body}", exc.code, body) from exc
        except error.URLError as exc:
            raise TaskBoardError(
                f"cannot reach DSH task board at {self.base_url}: {exc.reason}. "
                "Start DSH Desktop and pass --url if the Web GUI uses another port."
            ) from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TaskBoardError(f"DSH task board returned non-JSON: {raw[:300]}") from exc
        if not isinstance(parsed, dict):
            raise TaskBoardError("DSH task board returned a non-object JSON payload")
        return parsed

    def state(self) -> dict[str, object]:
        return self._request("GET", "/state")

    def apply(self, action: dict[str, object], request_id: str | None = None, initiator: str = "agent-dispatch") -> dict[str, object]:
        envelope = {
            "requestId": request_id or str(uuid.uuid4()),
            "action": action,
            "initiator": initiator,
        }
        return self._request("POST", "/action", envelope)

    def update(self, task_id: str, patch: dict[str, object]) -> dict[str, object]:
        """Patch one card. DSH update actions accept only taskId and patch."""
        if not isinstance(patch, dict) or not patch:
            raise ValueError("patch must be a non-empty object")
        return self.apply({"kind": "update", "taskId": task_id, "patch": patch})

    def archive(self, task_id: str) -> dict[str, object]:
        """Archive one card. DSH archive actions accept only taskId."""
        return self.apply({"kind": "archive", "taskId": task_id})

    def delete(self, task_id: str) -> dict[str, object]:
        """Delete one card. DSH delete actions accept only taskId."""
        return self.apply({"kind": "delete", "taskId": task_id})


def load_map(root: Path) -> dict[str, object]:
    path = Path(root) / ".dispatch" / "dsh-map.json"
    if not path.exists():
        return {"version": MAP_VERSION, "tickets": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": MAP_VERSION, "tickets": {}}
    if not isinstance(data, dict):
        return {"version": MAP_VERSION, "tickets": {}}
    data.setdefault("version", MAP_VERSION)
    data.setdefault("tickets", {})
    return data


def save_map(root: Path, data: dict[str, object]) -> Path:
    directory = Path(root) / ".dispatch"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "dsh-map.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return path


def _task_index(state: dict[str, object]) -> dict[str, dict[str, object]]:
    tasks = state.get("tasks", [])
    if not isinstance(tasks, list):
        return {}
    return {
        str(task.get("id")): task
        for task in tasks
        if isinstance(task, dict) and task.get("id")
    }


def _resolve_mapping(
    root: Path, ticket_id: str, task_id: str | None
) -> tuple[dict[str, object], dict[str, object] | None, str]:
    map_data = load_map(root)
    entries = map_data.get("tickets", {})
    entry = entries.get(ticket_id) if isinstance(entries, dict) else None
    if task_id is None:
        if not isinstance(entry, dict) or not entry.get("task_id"):
            raise ValueError(
                f"ticket {ticket_id!r} has no DSH card mapping; run 'dispatch dsh push' first "
                "or pass --task-id"
            )
        task_id = str(entry["task_id"])
    return map_data, entry if isinstance(entry, dict) else None, task_id


def _mutation_result(
    snapshot: dict[str, object], *, ticket_id: str, task_id: str, action: str
) -> dict[str, object]:
    task = _task_index(snapshot).get(task_id, {})
    result: dict[str, object] = {
        "ok": True,
        "ticket_id": ticket_id,
        "task_id": task_id,
        "action": action,
    }
    if task:
        result["status"] = task.get("status", "")
        result["title"] = task.get("title", "")
        if task.get("archivedAt"):
            result["archived_at"] = task["archivedAt"]
    if action == "archive":
        result["archived"] = True
    if action == "delete":
        result["deleted"] = True
    return result


def push(
    tickets: list[Ticket],
    states: dict[str, str] | None = None,
    *,
    root: Path,
    base_url: str | None = None,
    project: str | None = None,
    mode: str = "cards",
    workspace_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Push ready tickets to the DSH task board. Never runs a card."""
    if mode not in {"cards", "team"}:
        raise ValueError(f"unknown DSH push mode: {mode}")
    ready = ready_tickets(tickets, states)
    project = project or Path(root).resolve().name
    client = TaskBoardClient(base_url)
    if dry_run:
        actions = (
            build_team_actions(ready, project=project, workspace_id=workspace_id)
            if mode == "team"
            else build_card_actions(ready, project=project, workspace_id=workspace_id)
        )
        pairs = list(zip(ready, actions[1:] if mode == "team" else actions))
        planned = [
            {
                "ticket_id": ticket.id,
                "task_id": action["action"]["id"],
                "title": action["action"]["input"].get("title", ""),
            }
            for ticket, action in pairs
        ]
        if mode == "team" and actions:
            planned.insert(
                0,
                {
                    "ticket_id": "(wave)",
                    "task_id": actions[0]["action"]["id"],
                    "title": actions[0]["action"]["input"].get("title", ""),
                },
            )
        return {
            "ok": True,
            "dry_run": True,
            "mode": mode,
            "project": project,
            "base_url": client.base_url,
            "actions": actions,
            "planned": planned,
        }
    if not ready:
        return {
            "ok": True,
            "mode": mode,
            "project": project,
            "base_url": client.base_url,
            "created": [],
            "existing": [],
            "message": "no ready tickets",
            "map_path": str(Path(root) / ".dispatch" / "dsh-map.json"),
        }

    board = client.state()
    by_id = _task_index(board)
    actions = (
        build_team_actions(ready, project=project, workspace_id=workspace_id)
        if mode == "team"
        else build_card_actions(ready, project=project, workspace_id=workspace_id)
    )
    created: list[dict[str, object]] = []
    existing: list[dict[str, object]] = []
    for envelope in actions:
        action = envelope["action"]
        task_id = str(action["id"])
        title = str(action["input"].get("title", ""))
        if task_id in by_id:
            existing.append({"task_id": task_id, "title": title, "status": by_id[task_id].get("status", "")})
            continue
        snapshot = client.apply(action, request_id=str(envelope["requestId"]), initiator="agent-dispatch")
        by_id = _task_index(snapshot)
        created.append({"task_id": task_id, "title": title})

    map_data = load_map(root)
    map_data["base_url"] = client.base_url
    map_data["project"] = project
    map_data["mode"] = mode
    entries = map_data.setdefault("tickets", {})
    for envelope in actions:
        action = envelope["action"]
        input_payload = action["input"]
        if action["kind"] != "create" or not isinstance(input_payload, dict):
            continue
        task_id = str(action["id"])
        title = str(input_payload.get("title", ""))
        if mode == "team" and title.startswith("Dispatch wave:"):
            map_data["wave_id"] = task_id
            continue
        # The child title is "<ticket id>: <title>"; recover the id from the
        # ticket list rather than parsing display text.
        for ticket in ready:
            if _uuid_for(project, ticket.id) == task_id:
                entries[ticket.id] = {
                    "task_id": task_id,
                    "title": title,
                    "mode": mode,
                    "pushed_at": _now(),
                }
                break
    map_path = save_map(root, map_data)
    return {
        "ok": True,
        "mode": mode,
        "project": project,
        "base_url": client.base_url,
        "created": created,
        "existing": existing,
        "map_path": str(map_path),
    }


def outcome(
    ticket_id: str,
    *,
    root: Path,
    result: str,
    initiated_by: str,
    summary: str = "",
    base_url: str | None = None,
    task_id: str | None = None,
) -> dict[str, object]:
    """Record an external outcome on the card mapped to a ticket."""
    if result not in {"succeeded", "failed"}:
        raise ValueError("result must be 'succeeded' or 'failed'")
    if not initiated_by.strip():
        raise ValueError("initiated_by must not be empty")
    map_data, entry, task_id = _resolve_mapping(root, ticket_id, task_id)
    client = TaskBoardClient(base_url or str(map_data.get("base_url") or ""))
    action: dict[str, object] = {
        "kind": "record-external-outcome",
        "taskId": task_id,
        "result": result,
        "initiatedBy": initiated_by.strip(),
    }
    if summary.strip():
        action["summary"] = summary.strip()
    snapshot = client.apply(action, initiator="agent-dispatch")
    task = _task_index(snapshot).get(task_id, {})
    if isinstance(entry, dict):
        entry["last_outcome"] = {
            "result": result,
            "initiated_by": initiated_by.strip(),
            "summary": summary.strip(),
            "recorded_at": _now(),
        }
        save_map(root, map_data)
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "task_id": task_id,
        "status": task.get("status", ""),
        "title": task.get("title", ""),
    }


def update_card(
    ticket_id: str,
    *,
    root: Path,
    patch: dict[str, object],
    base_url: str | None = None,
    task_id: str | None = None,
) -> dict[str, object]:
    """Patch a mapped DSH card without running it."""
    map_data, _entry, task_id = _resolve_mapping(root, ticket_id, task_id)
    client = TaskBoardClient(base_url or str(map_data.get("base_url") or ""))
    snapshot = client.update(task_id, patch)
    return _mutation_result(snapshot, ticket_id=ticket_id, task_id=task_id, action="update")


def archive_card(
    ticket_id: str,
    *,
    root: Path,
    base_url: str | None = None,
    task_id: str | None = None,
) -> dict[str, object]:
    """Archive a mapped DSH card without running it."""
    map_data, _entry, task_id = _resolve_mapping(root, ticket_id, task_id)
    client = TaskBoardClient(base_url or str(map_data.get("base_url") or ""))
    snapshot = client.archive(task_id)
    return _mutation_result(snapshot, ticket_id=ticket_id, task_id=task_id, action="archive")


def delete_card(
    ticket_id: str,
    *,
    root: Path,
    base_url: str | None = None,
    task_id: str | None = None,
) -> dict[str, object]:
    """Delete a mapped DSH card without running it."""
    map_data, _entry, task_id = _resolve_mapping(root, ticket_id, task_id)
    client = TaskBoardClient(base_url or str(map_data.get("base_url") or ""))
    snapshot = client.delete(task_id)
    return _mutation_result(snapshot, ticket_id=ticket_id, task_id=task_id, action="delete")


def board_status(*, root: Path, base_url: str | None = None) -> dict[str, object]:
    """Read the board and compare it with the local ticket mapping."""
    map_data = load_map(root)
    client = TaskBoardClient(base_url or str(map_data.get("base_url") or ""))
    board = client.state()
    by_id = _task_index(board)
    entries = map_data.get("tickets", {})
    rows: list[dict[str, object]] = []
    if isinstance(entries, dict):
        for ticket_id, entry in sorted(entries.items()):
            if not isinstance(entry, dict):
                continue
            task_id = str(entry.get("task_id", ""))
            task = by_id.get(task_id, {})
            executions = task.get("executions", [])
            latest = executions[-1] if isinstance(executions, list) and executions else {}
            rows.append(
                {
                    "ticket_id": ticket_id,
                    "task_id": task_id,
                    "title": task.get("title", entry.get("title", "")),
                    "state": task.get("status", "missing"),
                    "external": latest.get("external", False) if isinstance(latest, dict) else False,
                    "result": latest.get("result", "") if isinstance(latest, dict) else "",
                }
            )
    return {
        "ok": True,
        "base_url": client.base_url,
        "project": map_data.get("project", ""),
        "wave_id": map_data.get("wave_id", ""),
        "revision": board.get("revision", 0),
        "rows": rows,
    }


def format_status(document: dict[str, object]) -> str:
    rows = document.get("rows", [])
    if not isinstance(rows, list) or not rows:
        return "No DSH card mappings. Run 'dispatch dsh push' first."
    lines = [f"DSH board {document.get('base_url')} revision {document.get('revision')}"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        suffix = ""
        if row.get("external"):
            suffix = f" [external {row.get('result', '')}]"
        lines.append(
            f"{str(row.get('ticket_id', '')):<8} {str(row.get('state', '')):<8} {row.get('title', '')}{suffix}"
        )
    return "\n".join(lines)
