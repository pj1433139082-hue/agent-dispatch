from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: seam

## What to build

写 out.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] out.txt 存在。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Agents\n\n先读 CONTEXT.md，再动手。\n", encoding="utf-8")
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "commit", "-q", "-m", "base"], cwd=tmp_path, check=True)


def test_brief_gate_blocks_render_until_approved(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "brief", "01").returncode == 0
    brief = tmp_path / ".dispatch" / "briefs" / "01.md"
    text = brief.read_text(encoding="utf-8")
    for section in ("理解的目标", "计划", "准备改动的文件", "风险", "疑问"):
        text = text.replace("## " + section + "\n\n<", "## " + section + "\n\n填好了 <")
    brief.write_text(text, encoding="utf-8")

    blocked = run_dispatch(tmp_path, "render", "01", "--require-brief")
    assert blocked.returncode != 0
    assert "brief" in (blocked.stdout + blocked.stderr).lower()

    assert run_dispatch(tmp_path, "brief", "01", "--approve", "甲方").returncode == 0
    assert run_dispatch(tmp_path, "render", "01", "--require-brief").returncode == 0


def test_context_pack_collects_entry_docs(tmp_path: Path) -> None:
    repo(tmp_path)

    result = run_dispatch(tmp_path, "context", "01")

    assert result.returncode == 0, result.stderr
    pack = (tmp_path / ".dispatch" / "context" / "01.md").read_text(encoding="utf-8")
    assert "AGENTS.md" in pack
    assert "先读 CONTEXT.md" in pack


def test_select_accepts_a_custom_role(tmp_path: Path) -> None:
    persona = tmp_path / "my-role.md"
    persona.write_text("# 我的角色\n\n关注并发与回滚。\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "select", "demo", "--add", "concurrency:" + str(persona))

    assert result.returncode == 0, result.stderr
    files = sorted(p.name for p in (tmp_path / "docs" / "selection" / "demo").iterdir())
    assert any(name.startswith("9") for name in files), files


def test_export_agent_team_writes_a_brief_and_work_orders(tmp_path: Path) -> None:
    repo(tmp_path)

    result = run_dispatch(tmp_path, "export", "--format", "agent-team", "--output", str(tmp_path / "team.md"))

    assert result.returncode == 0, result.stderr
    text = (tmp_path / "team.md").read_text(encoding="utf-8")
    assert "01" in text
    assert len(text) > 200
