from __future__ import annotations

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


def answer(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text("\n".join(line.replace("> ", "> 已答：按推荐") if line.strip() == "> " else line.replace("> ", "> 已答") if line.strip() == ">" else line for line in text.splitlines()), encoding="utf-8")


def test_align_writes_a_questionnaire_with_a_level(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "align", "pipeline", "--title", "编排主流程", "--level", "quick")
    assert result.returncode == 0, result.stderr
    path = tmp_path / "docs" / "questions" / "pipeline.md"
    text = path.read_text(encoding="utf-8")
    assert "# 编排主流程" in text
    assert "quick（3 问）" in text
    assert text.count("### ") == 3


def test_align_refuses_to_overwrite(tmp_path: Path) -> None:
    run_dispatch(tmp_path, "align", "x")
    second = run_dispatch(tmp_path, "align", "x")
    assert second.returncode == 1


def test_spec_requires_an_answered_questionnaire(tmp_path: Path) -> None:
    blocked = run_dispatch(tmp_path, "spec", "pipeline")
    assert blocked.returncode == 1
    assert "align first" in blocked.stderr

    run_dispatch(tmp_path, "align", "pipeline", "--title", "P")
    still_blocked = run_dispatch(tmp_path, "spec", "pipeline")
    assert still_blocked.returncode == 1
    assert "没填" in still_blocked.stderr

    answered = run_dispatch(tmp_path, "spec", "pipeline", "--title", "P", "--force")
    assert answered.returncode == 0, answered.stderr
    assert (tmp_path / "docs" / "specs" / "pipeline.md").is_file()


def test_tickets_need_a_spec_with_delivery_items(tmp_path: Path) -> None:
    missing = run_dispatch(tmp_path, "tickets", "pipeline")
    assert missing.returncode == 1

    spec = tmp_path / "docs" / "specs" / "pipeline.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Spec\n\n## Delivery standard\n\n- [ ] 交付项一 <!-- verify: python -c pass -->\n- [ ] 交付项二\n", encoding="utf-8")

    assert run_dispatch(tmp_path, "confirm", "pipeline", "--by", "甲方", "--via", "card").returncode == 0
    drafted = run_dispatch(tmp_path, "tickets", "pipeline")
    assert drafted.returncode == 0, drafted.stderr
    files = sorted((tmp_path / ".dispatch" / "drafts" / "pipeline").iterdir())
    assert [path.name for path in files] == ["01-pipeline.md", "02-pipeline.md"]
    assert "**Status:** draft" in files[0].read_text(encoding="utf-8")
