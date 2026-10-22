from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )


def make_run(tmp_path: Path, run_id: str, *, ticket_id: str = "01-probe", state: str = "running", age_minutes: int = 5, receipt: bool = False) -> Path:
    run_dir = tmp_path / ".dispatch" / "runs" / run_id
    run_dir.mkdir(parents=True)
    created = (datetime.now(timezone.utc) - timedelta(minutes=age_minutes)).isoformat()
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": run_id, "ticket_id": ticket_id, "state": state, "created_at": created}),
        encoding="utf-8",
    )
    (run_dir / "work-order.md").write_text("# work order\n", encoding="utf-8")
    if receipt:
        (run_dir / "receipt.json").write_text("{}", encoding="utf-8")
    return run_dir


def test_sweep_lists_an_active_run(tmp_path: Path) -> None:
    make_run(tmp_path, "01-probe-20261022T000000000000Z-aaaaaa")

    result = run_dispatch(tmp_path, "sweep", "--json")

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert len(rows) == 1
    row = rows[0]
    assert row["ticket_id"] == "01-probe"
    assert row["state"] == "running"
    assert row["has_receipt"] is False
    assert row["age_seconds"] >= 0

def test_sweep_skips_finished_runs(tmp_path: Path) -> None:
    make_run(tmp_path, "01-done-20261022T000000000000Z-bbbbbb", ticket_id="01-done", state="done")
    make_run(tmp_path, "02-failed-20261022T000000Z-cccccc", ticket_id="02-failed", state="failed")
    make_run(tmp_path, "03-live-20261022T000000Z-dddddd", ticket_id="03-live", state="running")

    result = run_dispatch(tmp_path, "sweep", "--json")

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert [row["ticket_id"] for row in rows] == ["03-live"]
