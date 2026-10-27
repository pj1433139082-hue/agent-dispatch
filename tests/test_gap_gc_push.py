from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET_TEMPLATE = """# {ticket_id}: {title}

## What to build

写 out.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: {risk}
- Write scope: out.txt
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('out.txt').exists() else 1)"

## Acceptance

- [ ] out.txt 存在。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write_ticket(root: Path, ticket_id: str, risk: str, title: str) -> None:
    tickets = root / "tickets"
    tickets.mkdir(exist_ok=True)
    (tickets / f"{ticket_id}.md").write_text(
        TICKET_TEMPLATE.format(ticket_id=ticket_id, risk=risk, title=title),
        encoding="utf-8",
    )


def init_repo(root: Path) -> None:
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "base")


def test_gc_holds_done_unlanded_worktree(tmp_path: Path) -> None:
    """done + not landed + worktree still present must be HOLD, not REMOVE."""
    write_ticket(tmp_path, "01", "L1", "gc unlanded")
    init_repo(tmp_path)

    rendered = run_dispatch(tmp_path, "render", "01", "--agent", "lead")
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr

    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree

    # Commit the implementation so the worktree is clean; the HOLD must be
    # caused by "not landed", not by uncommitted changes.
    (worktree / "out.txt").write_text("ok", encoding="utf-8")
    git(worktree, "add", "out.txt")
    git(worktree, "commit", "-q", "-m", "out")

    started = run_dispatch(tmp_path, "start", "01")
    assert started.returncode == 0, started.stdout + started.stderr

    receipt = {
        "ticket_id": "01",
        "run_id": run["run_id"],
        "status": "done",
        "summary": "ok",
        "criteria": [
            {
                "id": 1,
                "verdict": "pass",
                "evidence": [{"kind": "inline", "content": "ok"}],
            }
        ],
    }
    (run_dir / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

    verified = run_dispatch(tmp_path, "verify", "01")
    assert verified.returncode == 0, verified.stdout + verified.stderr
    reviewed = run_dispatch(tmp_path, "review", "01", "--reviewer", "reviewer-b", "--verdict", "pass")
    assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr

    result = run_dispatch(tmp_path, "gc", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    rows = [row for row in json.loads(result.stdout) if row["ticket_id"] == "01"]
    assert len(rows) == 1, result.stdout
    row = rows[0]
    assert row["state"] == "done", row
    assert row["verdict"] == "HOLD", row
    assert row["dirty"] is False, row
    assert row["landed"] is False, row

    # v0.97.1's gc --json rows have no reason field; the plain-text row carries
    # the "unlanded" marker. If a reason field is added later, prefer it.
    text = run_dispatch(tmp_path, "gc")
    assert text.returncode == 0, text.stdout + text.stderr
    reason = str(row.get("reason") or "")
    if reason:
        assert "unlanded" in reason, row
    else:
        assert "unlanded" in text.stdout, text.stdout


def test_dsh_push_warns_for_tickets_below_l3(tmp_path: Path) -> None:
    """dsh push must warn when L1/L2 tickets cannot execute on the board."""
    write_ticket(tmp_path, "01", "L1", "low risk one")
    write_ticket(tmp_path, "02", "L2", "low risk two")
    write_ticket(tmp_path, "03", "L3", "board-safe three")
    init_repo(tmp_path)

    result = run_dispatch(
        tmp_path,
        "dsh",
        "push",
        "--dry-run",
        "--json",
        "--workspace",
        "ws-1",
        "--project",
        "p",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True, payload

    warnings = [
        line
        for line in result.stderr.splitlines()
        if "DSH: note:" in line and "below L3" in line
    ]
    assert warnings, result.stderr
    warning = warnings[0]
    assert "L3" in warning, warning
    assert "01" in warning, warning
    assert "02" in warning, warning
    assert "03" not in warning, warning
