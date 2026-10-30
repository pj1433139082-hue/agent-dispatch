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


def git(tmp_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=tmp_path, text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


def test_answer_fills_every_blank_from_a_json_list(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "align", "demo", "--level", "quick").returncode == 0
    questionnaire = tmp_path / "docs" / "questions" / "demo.md"
    blanks = [line for line in questionnaire.read_text(encoding="utf-8").splitlines() if line.strip() == ">"]
    answers = ["答案" + str(index) for index in range(1, len(blanks) + 1)]
    answers_file = tmp_path / "answers.json"
    answers_file.write_text(json.dumps(answers, ensure_ascii=False), encoding="utf-8")

    result = run_dispatch(tmp_path, "answer", "demo", "--answers", str(answers_file))

    assert result.returncode == 0, result.stdout + result.stderr
    text = questionnaire.read_text(encoding="utf-8")
    assert not [line for line in text.splitlines() if line.strip() == ">"]
    assert "答案1" in text


def test_answer_refuses_a_wrong_number_of_answers(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "align", "demo", "--level", "quick").returncode == 0
    answers_file = tmp_path / "answers.json"
    answers_file.write_text(json.dumps(["only one"]), encoding="utf-8")

    result = run_dispatch(tmp_path, "answer", "demo", "--answers", str(answers_file))

    assert result.returncode == 1
    assert "expected" in (result.stdout + result.stderr)


TICKET = """# 01: two files

**What to build:** write a.py and b.py
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: a.py
- Write scope: b.py
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('a.py').is_file() else 1)"

## Acceptance

- [ ] a.py exists
"""


def test_mutate_per_file_flags_a_changed_file_the_verify_does_not_cover(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(json.dumps({"persona_policy": "off"}), encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".dispatch/\n", encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets")).returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(str(run["execution_root"]))
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "a.py").write_text("a\n", encoding="utf-8")
    (worktree / "b.py").write_text("b\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "mutate", "01", "--per-file")

    assert result.returncode == 1, result.stdout + result.stderr
    record = json.loads((run_dir / "mutation.json").read_text(encoding="utf-8"))
    assert record["status"] == "weak"
    assert "b.py" in record["weak_files"]
