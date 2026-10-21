from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ticket_text(ticket_id: str, title: str, blocked_by: str = "None") -> str:
    return f"""# {ticket_id}: {title}

**What to build:** Ship {title}.
**Blocked by:** {blocked_by}
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/{ticket_id}.py
- Verify: python -m pytest -q

## Acceptance

- [ ] {title} works.
"""


def git(tmp_path: Path, *args: str) -> str:
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            *args,
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def make_repo(tmp_path: Path, tickets: dict[str, str]) -> Path:
    directory = tmp_path / "tickets"
    directory.mkdir()
    for name, text in tickets.items():
        (directory / name).write_text(text, encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    return directory


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def only_run(tmp_path: Path) -> Path:
    runs = sorted((tmp_path / ".dispatch" / "runs").iterdir())
    assert len(runs) == 1
    return runs[0]


def read_state(tmp_path: Path) -> dict:
    return json.loads((tmp_path / ".dispatch" / "state.json").read_text(encoding="utf-8"))


def test_render_writes_run_directory_and_work_order(tmp_path: Path) -> None:
    directory = make_repo(tmp_path, {"01-a.md": ticket_text("01", "A")})

    result = run_dispatch(tmp_path, "render", "01", "--tickets", str(directory))

    assert result.returncode == 0, result.stderr
    run_dir = only_run(tmp_path)
    assert (run_dir / "work-order.md").is_file()
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    ticket_path = directory / "01-a.md"
    assert run["ticket_hash"] == hashlib.sha256(ticket_path.read_bytes()).hexdigest()
    assert run["base_commit"] == git(tmp_path, "rev-parse", "HEAD")
    assert run["state"] == "claimed"
    assert read_state(tmp_path)["tickets"]["01"]["state"] == "claimed"


def test_work_order_contains_the_contract(tmp_path: Path) -> None:
    directory = make_repo(tmp_path, {"01-a.md": ticket_text("01", "A")})

    result = run_dispatch(tmp_path, "render", "01", "--tickets", str(directory))

    assert result.returncode == 0, result.stderr
    text = (only_run(tmp_path) / "work-order.md").read_text(encoding="utf-8")
    assert "## Goal" in text
    assert "## Write scope" in text
    assert "## Acceptance" in text
    assert "## Verification" in text
    assert "Receipt contract" in text


def test_render_refuses_unfinished_dependencies(tmp_path: Path) -> None:
    directory = make_repo(
        tmp_path,
        {
            "01-a.md": ticket_text("01", "A"),
            "02-b.md": ticket_text("02", "B", "01"),
        },
    )

    result = run_dispatch(tmp_path, "render", "02", "--tickets", str(directory))

    assert result.returncode == 1
    assert "blocked" in result.stderr.lower()
    assert not (tmp_path / ".dispatch" / "runs").exists()


def test_second_render_is_refused_while_active(tmp_path: Path) -> None:
    directory = make_repo(tmp_path, {"01-a.md": ticket_text("01", "A")})
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(directory)).returncode == 0

    result = run_dispatch(tmp_path, "render", "01", "--tickets", str(directory))

    assert result.returncode == 1
    assert "active" in result.stderr.lower()


def test_render_is_allowed_after_a_failed_run(tmp_path: Path) -> None:
    directory = make_repo(tmp_path, {"01-a.md": ticket_text("01", "A")})
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(directory)).returncode == 0
    state_path = tmp_path / ".dispatch" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["tickets"]["01"]["state"] = "failed"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    result = run_dispatch(tmp_path, "render", "01", "--tickets", str(directory))

    assert result.returncode == 0, result.stderr
    assert len(list((tmp_path / ".dispatch" / "runs").iterdir())) == 2


def test_start_moves_claimed_to_running(tmp_path: Path) -> None:
    directory = make_repo(tmp_path, {"01-a.md": ticket_text("01", "A")})
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(directory)).returncode == 0

    result = run_dispatch(tmp_path, "start", "01")

    assert result.returncode == 0, result.stderr
    assert read_state(tmp_path)["tickets"]["01"]["state"] == "running"
    assert json.loads((only_run(tmp_path) / "run.json").read_text(encoding="utf-8"))["state"] == "running"
