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


def test_questions_turn_adversary_assumptions_into_grill_questions(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "select", "demo").returncode == 0
    adversary = tmp_path / "docs" / "selection" / "demo" / "03-adversary.md"
    adversary.write_text(
        "# adversary\n\n## 假设\n\n- 假设用户只跑单机\n- 假设数据量小于 10GB\n", encoding="utf-8"
    )

    result = run_dispatch(tmp_path, "questions", "demo", "--json")

    assert result.returncode == 0, result.stderr
    items = json.loads(result.stdout)
    assert len(items) == 2
    assert "单机" in items[0]["question"]
    assert items[0]["options"]


def test_questions_fail_without_a_selection_pack(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "questions", "nope")

    assert result.returncode != 0
    assert "selection" in (result.stdout + result.stderr).lower()
