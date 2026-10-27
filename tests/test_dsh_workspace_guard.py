from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: ws

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: dsh-board
- Risk: L0
- Write scope: out.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
"""


class Board(http.server.BaseHTTPRequestHandler):
    posts: list[dict] = []

    def _reply(self, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self._reply({"tasks": []})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        Board.posts.append(payload)
        self._reply({"ok": True, "tasks": []})

    def log_message(self, *args: object) -> None:
        return


def run_dispatch(cwd: Path, url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["DSH_TASK_BOARD_URL"] = url
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def start_board() -> tuple[http.server.HTTPServer, str]:
    Board.posts = []
    server = http.server.HTTPServer(("127.0.0.1", 0), Board)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, "http://127.0.0.1:" + str(server.server_address[1])


def repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")


def test_push_requires_an_explicit_workspace(tmp_path: Path) -> None:
    repo(tmp_path)
    server, url = start_board()
    try:
        result = run_dispatch(tmp_path, url, "dsh", "push", "--project", "demo")
    finally:
        server.shutdown()

    assert result.returncode != 0
    assert "workspace" in (result.stdout + result.stderr).lower()


def test_push_sends_the_workspace_id(tmp_path: Path) -> None:
    repo(tmp_path)
    server, url = start_board()
    try:
        result = run_dispatch(tmp_path, url, "dsh", "push", "--project", "demo", "--workspace", "ws-42")
    finally:
        server.shutdown()

    assert result.returncode == 0, result.stdout + result.stderr
    creates = [p for p in Board.posts if p.get("action", {}).get("kind") == "create"]
    assert creates, Board.posts
    assert creates[0]["action"]["input"]["workspaceId"] == "ws-42"


def test_push_can_opt_into_the_default_workspace(tmp_path: Path) -> None:
    repo(tmp_path)
    server, url = start_board()
    try:
        result = run_dispatch(tmp_path, url, "dsh", "push", "--project", "demo", "--allow-default-workspace")
    finally:
        server.shutdown()

    assert result.returncode == 0, result.stdout + result.stderr
