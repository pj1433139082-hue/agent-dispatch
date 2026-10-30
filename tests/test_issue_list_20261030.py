from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: A

**What to build:** Ship A.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: {scope}
- Verify: {verify}

## Acceptance

- [ ] A works.
"""


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


def repo(tmp_path: Path, *, scope: str = "out.txt", verify: str = 'python -c "print(1)"') -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET.format(scope=scope, verify=verify), encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(json.dumps({"persona_policy": "off"}), encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".dispatch/\n", encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")


def test_verify_lists_dirty_paths_and_drops_the_generic_gitignore_advice(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets")).returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    (tmp_path / "tmp-junk").mkdir()
    (tmp_path / "tmp-junk" / "x.txt").write_text("x", encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01")

    output = result.stdout + result.stderr
    assert "tmp-junk" in output
    assert "clean checkout required" in output
    assert "git add .gitignore" not in output


def test_allow_dirty_lets_a_known_path_through(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets")).returncode == 0
    (tmp_path / "tmp-junk").mkdir()
    (tmp_path / "tmp-junk" / "x.txt").write_text("x", encoding="utf-8")
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "x",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "note", "text": "done"}]}],
    }), encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01", "--allow-dirty", "tmp-junk")

    assert "tmp-junk" not in (result.stdout + result.stderr)


def test_package_init_is_allowed_inside_a_declared_scope() -> None:
    from agent_dispatch.verify import package_init_allowed

    assert package_init_allowed("scripts/fan_analysis/registry.py", "scripts/fan_analysis/__init__.py")
    assert package_init_allowed("scripts/fan_analysis/registry.py", "scripts/__init__.py")
    assert package_init_allowed("scripts/fan_analysis/", "scripts/fan_analysis/sub/__init__.py")
    assert not package_init_allowed("scripts/fan_analysis/registry.py", "other/__init__.py")
    assert not package_init_allowed("scripts/fan_analysis/registry.py", "scripts/fan_analysis/mod.py")


def test_retry_marks_the_old_receipt_stale(tmp_path: Path) -> None:
    repo(tmp_path, verify='python -c "raise SystemExit(1)"')
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets")).returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "x",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "note", "text": "done"}]}],
    }), encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", "01").returncode == 1

    assert run_dispatch(tmp_path, "retry", "01", "--reason", "flake").returncode == 0
    again = run_dispatch(tmp_path, "verify", "01")

    assert "receipt stale" in (again.stdout + again.stderr)
    assert list((run_dir / "attempts").glob("receipt-*.bak"))


def test_unknown_ticket_reports_the_tickets_directory(tmp_path: Path) -> None:
    repo(tmp_path)

    result = run_dispatch(tmp_path, "render", "99", "--tickets", str(tmp_path / "tickets"))

    assert str(tmp_path / "tickets") in (result.stdout + result.stderr)


def test_drop_archives_a_run_whose_worktree_is_gone(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets")).returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    shutil.rmtree(tmp_path / ".dispatch" / "worktrees", ignore_errors=True)

    dropped = run_dispatch(tmp_path, "drop", "01", "--reason", "worktree lost")

    assert dropped.returncode == 0, dropped.stdout + dropped.stderr
    assert not run_dir.exists()
    assert list((tmp_path / ".dispatch" / "archive" / "runs").iterdir())
    wrap = run_dispatch(tmp_path, "wrap")
    assert "without a persona" not in wrap.stdout
    assert "without landing.json" not in wrap.stdout


def test_gc_reports_and_clears_orphan_runs(tmp_path: Path) -> None:
    repo(tmp_path, verify='python -c "raise SystemExit(1)"')
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets")).returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "x",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "note", "text": "done"}]}],
    }), encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", "01").returncode == 1
    shutil.rmtree(tmp_path / ".dispatch" / "worktrees", ignore_errors=True)

    listed = run_dispatch(tmp_path, "gc", "--json")
    assert "ORPHAN" in listed.stdout
    applied = run_dispatch(tmp_path, "gc", "--apply")

    assert applied.returncode == 0
    assert not run_dir.exists()


def test_questions_accepts_an_evidence_file_with_a_persona_line(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "select", "demo").returncode == 0
    adversary = tmp_path / "docs" / "selection" / "demo" / "03-adversary.md"
    adversary.write_text(
        "# adversary\n\nPersona: builtin:adversary\n\n## 假设\n\n- 假设用户只跑单机\n",
        encoding="utf-8",
    )

    result = run_dispatch(tmp_path, "questions", "demo", "--json", "--with-skipped")

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert len(payload["questions"]) == 1
    assert "skipped" in payload


def test_review_window_state_lives_under_dispatch_not_docs(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "select", "demo", "--mode", "team").returncode == 0
    directory = tmp_path / "docs" / "selection" / "demo"
    for name, persona in (("01-oss.md", "builtin:oss-scout"), ("02-sources.md", "builtin:search-scout"), ("03-adversary.md", "builtin:adversary")):
        (directory / name).write_text("# 证据\n\nPersona: " + persona + "\n\n结论：方案可评\n", encoding="utf-8")

    assert run_dispatch(tmp_path, "review-window", "demo", "--open").returncode == 0

    assert (tmp_path / ".dispatch" / "reviews" / "demo.json").is_file()
    assert not (directory / "07-review-window.json").exists()


def test_panel_missing_role_requires_a_note_to_sign_pass(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "select", "demo", "--mode", "team").returncode == 0
    directory = tmp_path / "docs" / "selection" / "demo"
    for name, persona in (("01-oss.md", "builtin:oss-scout"), ("02-sources.md", "builtin:search-scout"), ("03-adversary.md", "builtin:adversary")):
        (directory / name).write_text("# 证据\n\nPersona: " + persona + "\n\n结论：方案可评\n", encoding="utf-8")
    (directory / "06-cross-review.md").write_text("# 交叉评审\n\n- 反驳\n", encoding="utf-8")
    assert run_dispatch(tmp_path, "panel", "demo", "--set", "oss-scout=missing").returncode == 0
    assert run_dispatch(tmp_path, "review-window", "demo", "--open").returncode == 0
    assert run_dispatch(tmp_path, "review-window", "demo", "--close").returncode == 0

    refused = run_dispatch(tmp_path, "sign", "demo", "--by", "lead", "--via", "card")
    assert refused.returncode == 1
    assert "未产出" in (refused.stdout + refused.stderr)
    allowed = run_dispatch(tmp_path, "sign", "demo", "--by", "lead", "--via", "card", "--note", "oss 本轮缺产出，已用 search 证据替代")
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr


def test_align_preset_changes_the_question_bank(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "align", "demo", "--level", "quick", "--preset", "research").returncode == 0

    text = (tmp_path / "docs" / "questions" / "demo.md").read_text(encoding="utf-8")

    assert "主张" in text
    assert "五个阶段" not in text


def test_gc_treats_a_claimed_run_with_a_missing_worktree_as_orphan(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets")).returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    shutil.rmtree(tmp_path / ".dispatch" / "worktrees", ignore_errors=True)

    listed = run_dispatch(tmp_path, "gc", "--json")
    assert "ORPHAN" in listed.stdout
    applied = run_dispatch(tmp_path, "gc", "--apply")

    assert applied.returncode == 0
    assert not run_dir.exists()
