from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SPEC = """# demo

## Problem

x

## Delivery standard

- [ ] 写 greeting.txt <!-- verify: python -c "print(1)" -->

## Out of Scope

- 
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def write_spec(root: Path, slug: str = "demo") -> Path:
    path = root / "docs" / "specs" / (slug + ".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SPEC, encoding="utf-8")
    return path


def test_confirm_records_the_spec_review(tmp_path: Path) -> None:
    write_spec(tmp_path)

    result = run_dispatch(tmp_path, "confirm", "demo", "--by", "甲方", "--via", "dialog")

    assert result.returncode == 0, result.stderr
    text = (tmp_path / "docs" / "specs" / "demo.md").read_text(encoding="utf-8")
    assert "## Confirmation" in text
    assert "甲方" in text
    assert "dialog" in text


def test_confirm_requires_a_via_marker(tmp_path: Path) -> None:
    write_spec(tmp_path)

    result = run_dispatch(tmp_path, "confirm", "demo", "--by", "甲方")

    assert result.returncode != 0
    assert "via" in (result.stdout + result.stderr).lower()


def test_tickets_refuse_an_unconfirmed_spec(tmp_path: Path) -> None:
    write_spec(tmp_path)

    result = run_dispatch(tmp_path, "tickets", "demo")

    assert result.returncode != 0
    assert "confirm" in (result.stdout + result.stderr).lower()


def test_tickets_start_after_confirmation(tmp_path: Path) -> None:
    write_spec(tmp_path)
    assert run_dispatch(tmp_path, "confirm", "demo", "--by", "甲方", "--via", "card").returncode == 0

    result = run_dispatch(tmp_path, "tickets", "demo")

    assert result.returncode == 0, result.stderr
    assert list((tmp_path / ".dispatch" / "drafts" / "demo").glob("*.md"))


def test_stage_points_at_the_confirmation_step(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "align", "demo", "--level", "quick").returncode == 0
    questions = tmp_path / "docs" / "questions" / "demo.md"
    text = questions.read_text(encoding="utf-8")
    questions.write_text("\n".join("> 答案" if line.strip() == ">" else line for line in text.split("\n")), encoding="utf-8")
    assert run_dispatch(tmp_path, "select", "demo").returncode == 0
    assert run_dispatch(tmp_path, "sign", "demo", "--by", "甲方", "--via", "card").returncode == 0
    write_spec(tmp_path)

    payload = json.loads(run_dispatch(tmp_path, "stage", "demo", "--json").stdout)

    assert payload["next"] == "s3-confirm"
