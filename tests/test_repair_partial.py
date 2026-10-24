from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def mkruns(tmp_path: Path) -> None:
    for ticket_id, run_id in (("01", "r-01"), ("02", "r-02")):
        directory = tmp_path / ".dispatch" / "runs" / run_id
        directory.mkdir(parents=True)
        (directory / "run.json").write_text(json.dumps({
            "ticket_id": ticket_id, "run_id": run_id, "state": "done",
            "created_at": "2026-10-24T00:00:00+00:00",
        }), encoding="utf-8")
    state = {
        "version": 1,
        "tickets": {
            "01": {"run_id": "wrong-run", "state": "done"},
            "02": {"run_id": "", "state": "done"},
        },
    }
    (tmp_path / ".dispatch" / "state.json").write_text(json.dumps(state), encoding="utf-8")


def test_repair_says_partial_when_conflicts_are_skipped(tmp_path: Path) -> None:
    mkruns(tmp_path)

    result = run_dispatch(tmp_path, "repair", "--write")

    assert result.returncode == 1
    assert "Written: partial" in result.stdout, result.stdout
