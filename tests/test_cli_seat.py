from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )


def test_seat_reports_free_capacity(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "seat", "--cap", "8", "--occupied", "3")
    assert result.returncode == 0, result.stderr
    assert "剩 5" in result.stdout


def test_seat_recommends_reclaiming_inactive_members(tmp_path: Path) -> None:
    result = run_dispatch(
        tmp_path, "seat", "--cap", "8", "--occupied", "8", "--inactive", "oss-scout,adversary"
    )
    assert result.returncode == 1
    assert "回收" in result.stdout and "oss-scout" in result.stdout


def test_seat_blocks_when_full_and_nothing_to_reclaim(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "seat", "--cap", "2", "--occupied", "2", "--json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "blocked"
    assert payload["free"] == 0


def test_seat_rejects_a_nonsense_cap(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "seat", "--cap", "0")
    assert result.returncode == 2
