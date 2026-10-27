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


def answer_questionnaire(root: Path, slug: str) -> None:
    path = root / "docs" / "questions" / (slug + ".md")
    text = path.read_text(encoding="utf-8")
    lines = ["> 测试答案" if line.strip() == ">" else line for line in text.split("\n")]
    path.write_text("\n".join(lines), encoding="utf-8")

def sign_selection(root: Path, slug: str) -> None:
    path = root / "docs" / "selection" / slug / "99-summary.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("- 签字人：", "- 签字人：甲方").replace("☐ 通过", "☑ 通过")
    path.write_text(text, encoding="utf-8")


def test_spec_refuses_to_start_without_a_signed_selection(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "align", "demo", "--level", "quick").returncode == 0
    answer_questionnaire(tmp_path, "demo")

    result = run_dispatch(tmp_path, "spec", "demo")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "selection" in (result.stdout + result.stderr).lower()
    assert not (tmp_path / "docs" / "specs" / "demo.md").exists()


def test_spec_starts_once_the_selection_is_signed(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "align", "demo", "--level", "quick").returncode == 0
    answer_questionnaire(tmp_path, "demo")
    assert run_dispatch(tmp_path, "select", "demo").returncode == 0
    sign_selection(tmp_path, "demo")

    result = run_dispatch(tmp_path, "spec", "demo")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "docs" / "specs" / "demo.md").is_file()


def test_spec_force_skips_the_selection_gate(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "align", "demo", "--level", "quick").returncode == 0
    answer_questionnaire(tmp_path, "demo")

    assert run_dispatch(tmp_path, "spec", "demo", "--force").returncode == 0


def test_stage_reports_the_first_missing_step(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "stage", "demo", "--json")

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["stages"]["s1"]["ok"] is False
    assert report["next"] == "s1"


def test_stage_walks_forward_as_the_pipeline_advances(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "align", "demo", "--level", "quick").returncode == 0
    answer_questionnaire(tmp_path, "demo")
    assert json.loads(run_dispatch(tmp_path, "stage", "demo", "--json").stdout)["next"] == "s2"

    assert run_dispatch(tmp_path, "select", "demo").returncode == 0
    assert json.loads(run_dispatch(tmp_path, "stage", "demo", "--json").stdout)["next"] == "s2-signature"

    sign_selection(tmp_path, "demo")
    assert json.loads(run_dispatch(tmp_path, "stage", "demo", "--json").stdout)["next"] == "s3"
