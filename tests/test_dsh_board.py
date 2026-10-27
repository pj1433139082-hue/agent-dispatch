from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: board

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
"""


class FakeBoard(http.server.BaseHTTPRequestHandler):
    requests: list[tuple[str, str, object]] = []
    fail_status = 0

    def _reply(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        FakeBoard.requests.append(("GET", self.path, None))
        if FakeBoard.fail_status:
            self._reply(FakeBoard.fail_status, {"error": "boom"})
            return
        self._reply(200, {"tasks": []})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw.decode("utf-8") or "{}")
        FakeBoard.requests.append(("POST", self.path, payload))
        if FakeBoard.fail_status:
            self._reply(FakeBoard.fail_status, {"error": "boom"})
            return
        self._reply(200, {"ok": True, "taskId": "task-1"})

    def log_message(self, *args: object) -> None:  # 静音
        return


def start_board() -> tuple[http.server.HTTPServer, str]:
    FakeBoard.requests = []
    FakeBoard.fail_status = 0
    server = http.server.HTTPServer(("127.0.0.1", 0), FakeBoard)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, "http://127.0.0.1:" + str(server.server_address[1])


def run_dispatch(cwd: Path, url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["DSH_TASK_BOARD_URL"] = url
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_dsh_status_reads_the_board_state(tmp_path: Path) -> None:
    server, url = start_board()
    try:
        result = run_dispatch(tmp_path, url, "dsh", "status", "--json")
    finally:
        server.shutdown()

    assert result.returncode == 0, result.stdout + result.stderr
    assert ("GET", "/api/task-board/state", None) in FakeBoard.requests


def test_dsh_push_creates_cards_and_records_the_map(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    server, url = start_board()
    try:
        result = run_dispatch(tmp_path, url, "dsh", "push", "--project", "demo", "--workspace", "ws-1")
    finally:
        server.shutdown()

    assert result.returncode == 0, result.stdout + result.stderr
    posts = [item for item in FakeBoard.requests if item[0] == "POST"]
    assert posts, FakeBoard.requests
    kinds = [item[2]["action"]["kind"] for item in posts]
    assert "create" in kinds, kinds
    mapping = json.loads((tmp_path / ".dispatch" / "dsh-map.json").read_text(encoding="utf-8"))
    assert "01" in json.dumps(mapping)


def test_dsh_reports_an_http_error_clearly(tmp_path: Path) -> None:
    server, url = start_board()
    FakeBoard.fail_status = 500
    try:
        result = run_dispatch(tmp_path, url, "dsh", "status")
    finally:
        server.shutdown()

    assert result.returncode != 0
    assert "500" in (result.stdout + result.stderr)


def test_dsh_run_uses_the_recorded_mapping(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    server, url = start_board()
    try:
        assert run_dispatch(tmp_path, url, "dsh", "push", "--project", "demo", "--workspace", "ws-1").returncode == 0
        FakeBoard.requests = []
        result = run_dispatch(tmp_path, url, "dsh", "run", "01")
    finally:
        server.shutdown()

    assert result.returncode == 0, result.stdout + result.stderr
    posts = [item for item in FakeBoard.requests if item[0] == "POST"]
    assert posts and posts[0][2]["action"]["kind"] == "run", posts


def test_dsh_outcome_reports_an_external_result(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    server, url = start_board()
    try:
        assert run_dispatch(tmp_path, url, "dsh", "push", "--project", "demo", "--workspace", "ws-1").returncode == 0
        FakeBoard.requests = []
        result = run_dispatch(tmp_path, url, "dsh", "outcome", "01", "--result", "succeeded", "--by", "reviewer-b")
    finally:
        server.shutdown()

    assert result.returncode == 0, result.stdout + result.stderr
    posts = [item for item in FakeBoard.requests if item[0] == "POST"]
    assert posts, FakeBoard.requests
    assert "succeeded" in json.dumps(posts[0][2])
