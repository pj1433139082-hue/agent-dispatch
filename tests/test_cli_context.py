from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 09: Wire the gate

**What to build:** A gate.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/gate.py
- Verify: python -c "print(1)"

## Acceptance

- [ ] The gate closes.
"""

SECTIONS = ("理解的目标", "计划", "准备改动的文件", "风险", "疑问")


def make_repo(tmp_path: Path) -> Path:
    directory = tmp_path / "tickets"
    directory.mkdir()
    (directory / "09-gate.md").write_text(TICKET, encoding="utf-8")
    return directory


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_context_command_writes_pack(tmp_path: Path) -> None:
    directory = make_repo(tmp_path)
    result = run_dispatch(tmp_path, "context", "09", "--tickets", str(directory))
    assert result.returncode == 0, result.stderr
    pack = tmp_path / ".dispatch" / "context" / "09.md"
    assert pack.is_file()
    assert "## Goal" in pack.read_text(encoding="utf-8")


def test_brief_gate_blocks_then_unblocks_render(tmp_path: Path) -> None:
    directory = make_repo(tmp_path)
    created = run_dispatch(tmp_path, "brief", "09", "--tickets", str(directory))
    assert created.returncode == 0, created.stderr
    assert (tmp_path / ".dispatch" / "briefs" / "09.md").is_file()

    unresolved = run_dispatch(tmp_path, "brief", "09", "--tickets", str(directory), "--check")
    assert unresolved.returncode == 1

    blocked = run_dispatch(
        tmp_path, "render", "09", "--tickets", str(directory), "--require-brief", "--no-worktree"
    )
    assert blocked.returncode == 1
    assert "brief" in blocked.stderr

    brief_file = tmp_path / ".dispatch" / "briefs" / "09.md"
    text = brief_file.read_text(encoding="utf-8")
    for section in SECTIONS:
        text = text.replace("## " + section + "\n\n<", "## " + section + "\n\nreal <")
    brief_file.write_text(text, encoding="utf-8")

    approved = run_dispatch(
        tmp_path, "brief", "09", "--tickets", str(directory), "--approve", "lead"
    )
    assert approved.returncode == 0, approved.stderr

    rendered = run_dispatch(
        tmp_path, "render", "09", "--tickets", str(directory), "--require-brief", "--with-context", "--no-worktree"
    )
    assert rendered.returncode == 0, rendered.stderr
    runs = list((tmp_path / ".dispatch" / "runs").iterdir())
    assert len(runs) == 1
    assert (runs[0] / "context.md").is_file()
    assert "## Context pack" in (runs[0] / "work-order.md").read_text(encoding="utf-8")
