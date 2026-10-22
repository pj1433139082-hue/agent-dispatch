from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )


def snapshot(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def test_read_only_commands_never_touch_project_data(tmp_path: Path) -> None:
    run_dir = tmp_path / ".dispatch" / "runs" / "01-probe-20261022T000000Z-bbbbbb"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": "01-probe-20261022T000000Z-bbbbbb", "ticket_id": "01-probe", "state": "running",
                    "created_at": datetime.now(timezone.utc).isoformat(), "skill_version": "0.0.1"}),
        encoding="utf-8",
    )
    state = tmp_path / ".dispatch" / "state.json"
    state.write_text(json.dumps({"version": 1, "tickets": {"01-probe": {"run_id": "01-probe-20261022T000000Z-bbbbbb", "state": "running"}}}), encoding="utf-8")

    before = snapshot(tmp_path / ".dispatch")
    for args in (("sweep",), ("sweep", "--json"), ("repair",), ("status",)):
        run_dispatch(tmp_path, *args)
    after = snapshot(tmp_path / ".dispatch")

    assert after == before, "只读命令改动了项目数据：" + ", ".join(sorted(set(after) ^ set(before)))
