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
    lines = ["> 答案" if line.strip() == ">" else line for line in text.split("\n")]
    path.write_text("\n".join(lines), encoding="utf-8")


def prepare_to_signature(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "align", "demo", "--level", "quick").returncode == 0
    answer_questionnaire(tmp_path, "demo")
    assert run_dispatch(tmp_path, "select", "demo").returncode == 0


def test_stage_prompt_asks_for_the_signature(tmp_path: Path) -> None:
    prepare_to_signature(tmp_path)

    result = run_dispatch(tmp_path, "stage", "demo", "--prompt")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["stage"] == "s2-signature"
    question = payload["questions"][0]
    assert [option["label"] for option in question["options"]] == ["通过", "有保留通过", "打回"]
    assert "99-summary" in payload["answer_hint"]


def test_stage_prompt_is_empty_when_nothing_to_ask(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "stage", "demo", "--prompt")

    payload = json.loads(result.stdout)
    assert payload["stage"] == "s1"
    assert payload["questions"]
    assert result.returncode == 0


def test_sign_records_an_approval_and_unblocks_spec(tmp_path: Path) -> None:
    prepare_to_signature(tmp_path)

    result = run_dispatch(tmp_path, "sign", "demo", "--by", "甲方")

    assert result.returncode == 0, result.stderr
    summary = (tmp_path / "docs" / "selection" / "demo" / "99-summary.md").read_text(encoding="utf-8")
    assert "- 签字人：甲方" in summary
    assert "☑ 通过" in summary
    assert run_dispatch(tmp_path, "spec", "demo").returncode == 0


def test_sign_supports_a_hold(tmp_path: Path) -> None:
    prepare_to_signature(tmp_path)

    assert run_dispatch(tmp_path, "sign", "demo", "--by", "甲方", "--hold").returncode == 0

    summary = (tmp_path / "docs" / "selection" / "demo" / "99-summary.md").read_text(encoding="utf-8")
    assert "☑ 有保留通过" in summary
    assert run_dispatch(tmp_path, "spec", "demo").returncode == 0


def test_sign_without_a_pack_fails(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "sign", "demo", "--by", "甲方")

    assert result.returncode == 1
    assert "selection" in (result.stdout + result.stderr).lower()
