from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: Protocol probe

## What to build

Write out.txt.

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('out.txt').exists() else 1)"

## Acceptance

- [ ] out.txt exists.
"""

EXECUTOR = """import json, os, pathlib
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
pathlib.Path("out.txt").write_text("hello", encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
  "ticket_id": "01",
  "run_id": os.environ["DISPATCH_RUN_ID"],
  "status": "done",
  "summary": "ok",
  "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
}), encoding="utf-8")
"""


def git(tmp_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=tmp_path, text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


def make_repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01-probe.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "exec.py").write_text(EXECUTOR, encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Agents\n\nread CONTEXT.md\n", encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )


def only_run(tmp_path: Path) -> Path:
    return sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]


def test_protocol_full_requires_an_accepted_brief(tmp_path: Path) -> None:
    make_repo(tmp_path)

    result = run_dispatch(
        tmp_path, "auto", "01",
        "--executor", "python exec.py",
        "--protocol", "full", "--require-brief",
    )

    assert result.returncode == 1
    assert "brief 未通过" in result.stderr
    auto = json.loads((only_run(tmp_path) / "auto.json").read_text(encoding="utf-8"))
    assert auto["status"] == "protocol-failed"
    assert "brief" in auto["error"]


def test_protocol_full_injects_context_checkpoint_and_closeout(tmp_path: Path) -> None:
    make_repo(tmp_path)

    result = run_dispatch(
        tmp_path, "auto", "01",
        "--executor", "python exec.py",
        "--protocol", "full", "--env-hint", "npm --prefix ui ci",
    )

    assert result.returncode == 0, result.stderr
    run_dir = only_run(tmp_path)
    auto = json.loads((run_dir / "auto.json").read_text(encoding="utf-8"))
    assert auto["status"] == "review"
    assert auto["protocol"]["context"] is True
    assert auto["protocol"]["env_hint"] is True
    assert (run_dir / "context.md").is_file()
    assert (run_dir / "checkpoints" / "001-attempt-1" / "checkpoint.json").is_file()
    assert json.loads((run_dir / "closeout.json").read_text(encoding="utf-8"))["status"] == "pass"
    work_order = (run_dir / "work-order.md").read_text(encoding="utf-8")
    assert "## Context pack" in work_order and "Environment prerequisites" in work_order


def test_closeout_failure_stops_before_review(tmp_path: Path) -> None:
    make_repo(tmp_path)
    # 先造一份"只声明改 other.txt"的已批 brief：verify 会过（写域内），
    # 但 closeout 会发现 out.txt 没在 brief 里声明 → 判 fail。
    assert run_dispatch(tmp_path, "brief", "01").returncode == 0
    brief = tmp_path / ".dispatch" / "briefs" / "01.md"
    text = brief.read_text(encoding="utf-8")
    for section, body in (
        ("理解的目标", "写 out.txt"),
        ("计划", "一步写完"),
        ("准备改动的文件", "- other.txt 只是声明，不实际改"),
        ("风险", "无"),
        ("疑问", "无"),
    ):
        text = text.replace("## " + section + "\n\n<", "## " + section + "\n\n" + body + " <")
    brief.write_text(text, encoding="utf-8")
    assert run_dispatch(tmp_path, "brief", "01", "--approve", "lead").returncode == 0

    result = run_dispatch(
        tmp_path, "auto", "01",
        "--executor", "python exec.py",
        "--protocol", "full", "--require-brief",
    )

    run_dir = only_run(tmp_path)
    auto = json.loads((run_dir / "auto.json").read_text(encoding="utf-8"))
    assert auto["status"] == "closeout-failed", auto
    assert any("brief 没声明" in str(item) for item in auto["closeout_findings"]), auto["closeout_findings"]
    assert result.returncode == 1
