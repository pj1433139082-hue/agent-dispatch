from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_sign_records_the_date(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "select", "demo").returncode == 0

    assert run_dispatch(tmp_path, "sign", "demo", "--by", "pj", "--via", "card").returncode == 0

    text = (tmp_path / "docs" / "selection" / "demo" / "99-summary.md").read_text(encoding="utf-8")
    assert "- 日期：" + date.today().isoformat() in text


def test_stage_points_at_moving_drafts_when_they_are_still_pending(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text("# 01: x\n\n## What to build\n\nx\n\n**Blocked by:** None\n**Status:** ready-for-agent\n\n## Dispatch\n\n- Owner: a\n- Risk: L1\n- Write scope: x.txt\n- Verify: python -c \"print(1)\"\n\n## Acceptance\n\n- [ ] x\n", encoding="utf-8")
    assert run_dispatch(tmp_path, "align", "demo", "--level", "quick").returncode == 0
    questions = tmp_path / "docs" / "questions" / "demo.md"
    filled = [line if line.strip() != ">" else "> 答：x" for line in questions.read_text(encoding="utf-8").splitlines()]
    questions.write_text("\n".join(filled) + "\n", encoding="utf-8")
    assert run_dispatch(tmp_path, "select", "demo").returncode == 0
    assert run_dispatch(tmp_path, "sign", "demo", "--by", "pj", "--via", "card").returncode == 0
    assert run_dispatch(tmp_path, "spec", "demo").returncode == 0
    spec = tmp_path / "docs" / "specs" / "demo.md"
    text = spec.read_text(encoding="utf-8").replace("（可命令化的验收项）", "真实验收项")
    spec.write_text(text, encoding="utf-8")
    assert run_dispatch(tmp_path, "confirm", "demo", "--by", "pj", "--via", "card", "--force").returncode == 0
    drafts = tmp_path / ".dispatch" / "drafts" / "demo"
    drafts.mkdir(parents=True)
    (drafts / "01-demo.md").write_text("# 01: draft\n", encoding="utf-8")

    payload = json.loads(run_dispatch(tmp_path, "stage", "demo", "--json").stdout)

    assert payload["next"] == "s4-move-drafts", payload
