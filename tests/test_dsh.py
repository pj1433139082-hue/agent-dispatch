from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from agent_dispatch.dsh import (
    TaskBoardError,
    _uuid_for,
    archive_card,
    board_status,
    build_card_actions,
    build_team_actions,
    delete_card,
    format_status,
    load_map,
    outcome,
    push,
    update_card,
)
from agent_dispatch.ticket import Ticket


def ticket(ticket_id: str, risk: str = "L1") -> Ticket:
    return Ticket(
        id=ticket_id,
        title=f"Ticket {ticket_id}",
        path=Path(f"{ticket_id}.md"),
        what_to_build=f"Ship {ticket_id}.",
        owner="implementer",
        risk=risk,
        write_scope=(f"src/{ticket_id}.py",),
        verify=("python -m pytest -q",),
        acceptance=(f"{ticket_id} works.",),
    )


class BoardStub:
    """A tiny in-process copy of the task board contract."""

    def __init__(self) -> None:
        self.revision = 0
        self.tasks: list[dict[str, object]] = []
        self.requests: list[dict[str, object]] = []
        self.lock = threading.Lock()
        board = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path != "/api/task-board/state":
                    board.respond(self, 404, {"error": "not found"})
                    return
                board.respond(self, 200, board.snapshot())

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/api/task-board/action":
                    board.respond(self, 404, {"error": "not found"})
                    return
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    envelope = json.loads(raw or b"{}")
                    action = envelope["action"]
                    board.apply(action)
                except Exception as exc:  # noqa: BLE001 - test stub reports the error
                    board.respond(self, 400, {"error": str(exc)})
                    return
                board.respond(self, 200, board.snapshot())

            def log_message(self, *args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def respond(self, handler: BaseHTTPRequestHandler, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return {"schemaVersion": 6, "revision": self.revision, "tasks": json.loads(json.dumps(self.tasks))}

    def apply(self, action: dict[str, object]) -> None:
        with self.lock:
            kind = action.get("kind")
            if kind == "create":
                task_id = str(action["id"])
                if any(task["id"] == task_id for task in self.tasks):
                    raise ValueError("duplicate task id")
                card = dict(action["input"])  # type: ignore[arg-type]
                task = {
                    "id": task_id,
                    "title": card.get("title", ""),
                    "status": "todo",
                    "description": card.get("description", ""),
                    "permission": card.get("permission", "workspace-write"),
                    "tags": card.get("tags", []),
                    "executions": [],
                }
                for key in ("parentId", "teamRun", "workspaceId"):
                    if key in card:
                        task[key] = card[key]
                self.tasks.append(task)
            elif kind == "delete":
                task_id = str(action["taskId"])
                self.tasks = [task for task in self.tasks if task["id"] != task_id]
            elif kind == "update":
                task_id = str(action["taskId"])
                task = next((item for item in self.tasks if item["id"] == task_id), None)
                if task is None:
                    raise ValueError("unknown task")
                patch = action.get("patch")
                if not isinstance(patch, dict):
                    raise ValueError("patch must be an object")
                task.update(patch)
            elif kind == "archive":
                task_id = str(action["taskId"])
                task = next((item for item in self.tasks if item["id"] == task_id), None)
                if task is None:
                    raise ValueError("unknown task")
                task["archivedAt"] = "2026-10-21T00:00:00+00:00"
            elif kind == "record-external-outcome":
                task_id = str(action["taskId"])
                task = next((item for item in self.tasks if item["id"] == task_id), None)
                if task is None:
                    raise ValueError("unknown task")
                result = str(action["result"])
                task["status"] = "done" if result == "succeeded" else "failed"
                executions = task.setdefault("executions", [])
                assert isinstance(executions, list)
                executions.append(
                    {
                        "id": "exec-1",
                        "result": result,
                        "error": action.get("summary", ""),
                        "initiatedBy": action.get("initiatedBy", ""),
                        "external": True,
                    }
                )
            else:
                raise ValueError(f"unsupported action: {kind}")
            self.revision += 1
            self.requests.append(action)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


@pytest.fixture
def board() -> BoardStub:
    stub = BoardStub()
    try:
        yield stub
    finally:
        stub.close()


def test_card_action_is_a_create_envelope_with_a_deterministic_id() -> None:
    first = build_card_actions([ticket("A")], project="probe")[0]
    second = build_card_actions([ticket("A")], project="probe")[0]

    action = first["action"]
    assert action["kind"] == "create"
    assert action["id"] == second["action"]["id"]
    assert action["id"] == _uuid_for("probe", "A")
    card = action["input"]
    assert card["title"] == "A: Ticket A"
    assert card["tags"] == [{"name": "dispatch"}, {"name": "dispatch:A"}, {"name": "L1"}]
    assert "status" not in card


def test_team_actions_make_one_parent_and_one_child_per_ticket() -> None:
    actions = build_team_actions([ticket("A"), ticket("B", risk="L3")], project="probe")

    assert len(actions) == 3
    parent = actions[0]["action"]
    assert parent["input"]["teamRun"] is True
    assert parent["input"]["permission"] == "danger-full-access"
    parent_id = parent["id"]
    for child in actions[1:]:
        assert child["action"]["input"]["parentId"] == parent_id
        assert "teamRun" not in child["action"]["input"]


def test_push_creates_cards_once_and_writes_a_map(tmp_path: Path, board: BoardStub) -> None:
    first = push([ticket("A")], root=tmp_path, base_url=board.url, project="probe")
    second = push([ticket("A")], root=tmp_path, base_url=board.url, project="probe")

    assert len(first["created"]) == 1
    assert first["existing"] == []
    assert len(second["created"]) == 0
    assert len(second["existing"]) == 1
    assert len(board.requests) == 1
    mapped = load_map(tmp_path)["tickets"]["A"]
    assert mapped["task_id"] == _uuid_for("probe", "A")
    assert mapped["mode"] == "cards"


def test_team_push_creates_parent_and_children(tmp_path: Path, board: BoardStub) -> None:
    report = push([ticket("A"), ticket("B")], root=tmp_path, base_url=board.url, project="probe", mode="team")

    assert len(report["created"]) == 3
    tasks = board.snapshot()["tasks"]
    parent = next(task for task in tasks if task["title"].startswith("Dispatch wave:"))
    children = [task for task in tasks if task.get("parentId") == parent["id"]]
    assert len(children) == 2
    assert parent["teamRun"] is True
    mapped = load_map(tmp_path)
    assert mapped["wave_id"] == parent["id"]
    assert set(mapped["tickets"]) == {"A", "B"}


def test_outcome_records_external_result_and_status(tmp_path: Path, board: BoardStub) -> None:
    push([ticket("A")], root=tmp_path, base_url=board.url, project="probe")

    result = outcome(
        "A",
        root=tmp_path,
        result="succeeded",
        initiated_by="worker",
        summary="all good",
        base_url=board.url,
    )

    assert result["status"] == "done"
    task = board.snapshot()["tasks"][0]
    assert task["status"] == "done"
    assert task["executions"][0]["external"] is True
    assert task["executions"][0]["result"] == "succeeded"
    assert task["executions"][0]["error"] == "all good"
    assert load_map(tmp_path)["tickets"]["A"]["last_outcome"]["result"] == "succeeded"

    status = board_status(root=tmp_path, base_url=board.url)
    assert status["rows"][0]["state"] == "done"
    assert status["rows"][0]["external"] is True
    assert "external succeeded" in format_status(status)


def test_update_card_sends_exact_action_and_reads_back(tmp_path: Path, board: BoardStub) -> None:
    push([ticket("A")], root=tmp_path, base_url=board.url, project="probe")
    task_id = _uuid_for("probe", "A")

    result = update_card(
        "A",
        root=tmp_path,
        patch={"title": "Renamed", "description": "New description"},
        base_url=board.url,
    )

    assert board.requests[-1] == {
        "kind": "update",
        "taskId": task_id,
        "patch": {"title": "Renamed", "description": "New description"},
    }
    assert result["action"] == "update"
    assert result["title"] == "Renamed"
    assert board.snapshot()["tasks"][0]["description"] == "New description"


def test_archive_card_sends_exact_action(tmp_path: Path, board: BoardStub) -> None:
    push([ticket("A")], root=tmp_path, base_url=board.url, project="probe")
    task_id = _uuid_for("probe", "A")

    result = archive_card("A", root=tmp_path, base_url=board.url)

    assert board.requests[-1] == {"kind": "archive", "taskId": task_id}
    assert result["action"] == "archive"
    assert result["archived"] is True
    assert board.snapshot()["tasks"][0]["archivedAt"]


def test_delete_card_sends_exact_action_and_removes_card(tmp_path: Path, board: BoardStub) -> None:
    push([ticket("A")], root=tmp_path, base_url=board.url, project="probe")
    task_id = _uuid_for("probe", "A")

    result = delete_card("A", root=tmp_path, base_url=board.url)

    assert board.requests[-1] == {"kind": "delete", "taskId": task_id}
    assert result["action"] == "delete"
    assert result["deleted"] is True
    assert board.snapshot()["tasks"] == []


def test_mutation_can_override_a_missing_mapping(tmp_path: Path, board: BoardStub) -> None:
    push([ticket("A")], root=tmp_path, base_url=board.url, project="probe")
    task_id = _uuid_for("probe", "A")

    result = update_card(
        "external",
        root=tmp_path,
        patch={"title": "External card"},
        base_url=board.url,
        task_id=task_id,
    )

    assert result["task_id"] == task_id
    assert result["title"] == "External card"


def test_outcome_without_mapping_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no DSH card mapping"):
        outcome("missing", root=tmp_path, result="failed", initiated_by="worker")


def test_dry_run_never_contacts_the_board(tmp_path: Path) -> None:
    report = push(
        [ticket("A")],
        root=tmp_path,
        base_url="http://127.0.0.1:9",
        project="probe",
        mode="team",
        dry_run=True,
    )

    assert report["dry_run"] is True
    assert len(report["actions"]) == 2
    assert [row["ticket_id"] for row in report["planned"]] == ["(wave)", "A"]
    assert not (tmp_path / ".dispatch" / "dsh-map.json").exists()


def test_http_error_is_wrapped(tmp_path: Path, board: BoardStub) -> None:
    push([ticket("A")], root=tmp_path, base_url=board.url, project="probe")
    with pytest.raises(TaskBoardError):
        outcome(
            "A",
            root=tmp_path,
            result="succeeded",
            initiated_by="worker",
            base_url=board.url + "/missing",
        )
