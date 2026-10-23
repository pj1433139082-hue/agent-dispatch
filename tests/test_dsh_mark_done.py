from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 09: board done

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
        self.rfile.read(length)
        self._reply({"ok": True, "tasks": []})

    def log_message(self, *args: object) -> None:
        return


def run_dispatch(cwd: Path, url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["DSH_TASK_BOARD_URL"] = url
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_mark_done_records_an_external_result(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "09.md").write_text(TICKET, encoding="utf-8")
    server = http.server.HTTPServer(("127.0.0.1", 0), Board)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:" + str(server.server_address[1])
    try:
        assert run_dispatch(tmp_path, url, "dsh", "push", "--project", "demo").returncode == 0
        (tmp_path / "out.txt").write_text("done", encoding="utf-8")
        result = run_dispatch(
            tmp_path, url, "dsh", "outcome", "09",
            "--result", "succeeded", "--by", "dsh-board", "--mark-done", "--evidence", "out.txt", "--json",
        )
    finally:
        server.shutdown()

    assert result.returncode == 0, result.stdout + result.stderr
    state = json.loads((tmp_path / ".dispatch" / "state.json").read_text(encoding="utf-8"))
    assert state["tickets"]["09"]["state"] == "done"
    record = json.loads((tmp_path / ".dispatch" / "external" / "09.json").read_text(encoding="utf-8"))
    assert record["by"] == "dsh-board"
    assert record["result"] == "succeeded"


def test_externally_completed_tickets_are_not_ghost_entries(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "09.md").write_text(TICKET, encoding="utf-8")
    server = http.server.HTTPServer(("127.0.0.1", 0), Board)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:" + str(server.server_address[1])
    try:
        assert run_dispatch(tmp_path, url, "dsh", "push", "--project", "demo").returncode == 0
        (tmp_path / "out.txt").write_text("done", encoding="utf-8")
        assert run_dispatch(
            tmp_path, url, "dsh", "outcome", "09",
            "--result", "succeeded", "--by", "dsh-board", "--mark-done", "--evidence", "out.txt",
        ).returncode == 0
        doctor = run_dispatch(tmp_path, url, "doctor", "--json")
    finally:
        server.shutdown()

    payload = json.loads(doctor.stdout)
    assert payload["ok"] is True, payload
    assert not any("no run on disk" in issue for issue in payload["issues"])


def test_mark_done_requires_evidence(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "09.md").write_text(TICKET, encoding="utf-8")
    server = http.server.HTTPServer(("127.0.0.1", 0), Board)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:" + str(server.server_address[1])
    try:
        assert run_dispatch(tmp_path, url, "dsh", "push", "--project", "demo").returncode == 0
        refused = run_dispatch(
            tmp_path, url, "dsh", "outcome", "09",
            "--result", "succeeded", "--by", "dsh-board", "--mark-done",
        )
        assert refused.returncode != 0
        assert "evidence" in (refused.stdout + refused.stderr).lower()
        assert not (tmp_path / ".dispatch" / "state.json").exists() or "09" not in (tmp_path / ".dispatch" / "state.json").read_text(encoding="utf-8")

        (tmp_path / "out.txt").write_text("done", encoding="utf-8")
        ok = run_dispatch(
            tmp_path, url, "dsh", "outcome", "09",
            "--result", "succeeded", "--by", "dsh-board", "--mark-done", "--evidence", "out.txt",
        )
        assert ok.returncode == 0, ok.stdout + ok.stderr
        state = json.loads((tmp_path / ".dispatch" / "state.json").read_text(encoding="utf-8"))
        assert state["tickets"]["09"]["state"] == "done"
        record = json.loads((tmp_path / ".dispatch" / "external" / "09.json").read_text(encoding="utf-8"))
        assert record["evidence"] == "out.txt"
    finally:
        server.shutdown()
