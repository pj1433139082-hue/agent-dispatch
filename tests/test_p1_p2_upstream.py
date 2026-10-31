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


def test_align_for_writes_a_stakeholder_questionnaire(tmp_path: Path) -> None:
    result = run_dispatch(
        tmp_path, "align", "demo", "--level", "standard", "--for", "领域专家", "--deadline", "2026-11-05"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    text = (tmp_path / "docs" / "questions" / "demo.md").read_text(encoding="utf-8")
    assert "To:** 领域专家" in text
    assert "截止：2026-11-05" in text
    assert text.count("### ") == 6


def test_setup_records_the_tracker_type(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    result = run_dispatch(tmp_path, "setup", "--tracker", "github", "--tracker-repo", "acme/project")

    assert result.returncode == 0, result.stdout + result.stderr
    config = json.loads((tmp_path / ".dispatch" / "config.json").read_text(encoding="utf-8"))
    assert config["tracker"] == {"type": "github", "repo": "acme/project"}


def test_issue_import_writes_a_draft_without_touching_tickets(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    fixture = tmp_path / "issue.json"
    fixture.write_text(json.dumps({
        "number": 42, "title": "Add export button", "body": "Users need CSV export.",
        "url": "https://github.com/acme/project/issues/42",
        "labels": [{"name": "enhancement"}],
    }), encoding="utf-8")

    result = run_dispatch(tmp_path, "issue", "42", "--from-file", str(fixture))

    assert result.returncode == 0, result.stdout + result.stderr
    drafts = list((tmp_path / ".dispatch" / "imports").glob("*.md"))
    assert len(drafts) == 1
    text = drafts[0].read_text(encoding="utf-8")
    assert "Add export button" in text and "CSV export" in text
    assert "https://github.com/acme/project/issues/42" in text
    assert list((tmp_path / "tickets").iterdir()) == []


def test_wiki_init_add_list_and_check(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "wiki", "init").returncode == 0
    assert run_dispatch(tmp_path, "wiki", "add", "--slug", "decisions", "--title", "Decisions", "--body", "# 决策\n\n用 YAML。", "--summary", "为什么选 YAML").returncode == 0
    assert run_dispatch(tmp_path, "wiki", "add", "--slug", "glossary", "--title", "Glossary", "--body", "术语。").returncode == 0

    listed = run_dispatch(tmp_path, "wiki", "list")
    assert "decisions.md" in listed.stdout and "glossary.md" in listed.stdout
    assert run_dispatch(tmp_path, "wiki", "check").returncode == 0

    (tmp_path / "wiki" / "orphan.md").write_text("# Orphan\n", encoding="utf-8")
    broken = run_dispatch(tmp_path, "wiki", "check")
    assert broken.returncode == 1
    assert "orphan" in broken.stderr


def test_guard_installs_a_pre_push_hook_that_blocks_main(tmp_path: Path) -> None:
    (tmp_path / ".git" / "hooks").mkdir(parents=True)

    assert run_dispatch(tmp_path, "guard", "status").returncode == 1
    installed = run_dispatch(tmp_path, "guard", "install")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    hook = tmp_path / ".git" / "hooks" / "pre-push"
    assert "refs/heads/main" in hook.read_text(encoding="utf-8")
    assert run_dispatch(tmp_path, "guard", "status").returncode == 0
    assert run_dispatch(tmp_path, "guard", "install").returncode == 1
    assert run_dispatch(tmp_path, "guard", "install", "--force").returncode == 0
