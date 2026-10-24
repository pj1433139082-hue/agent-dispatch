from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: closeout

## What to build

写 out.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('out.txt').exists() else 1)"

## Acceptance

- [ ] out.txt 存在。
"""

BRIEF = """# Brief: 01

## 理解的目标

写 out.txt。

## 计划

1. 建文件

## 准备改动的文件

- out.txt —— 产物
- phantom.txt —— 我打算改但最后没改

## 风险

无

## 疑问

无
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def prepared(tmp_path: Path) -> Path:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    brief = tmp_path / ".dispatch" / "briefs" / "01.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(BRIEF, encoding="utf-8")
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "out.txt").write_text("ok", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", "01").returncode == 0
    return run_dir


def test_closeout_reports_files_the_brief_promised_but_nobody_changed(tmp_path: Path) -> None:
    prepared(tmp_path)

    result = run_dispatch(tmp_path, "closeout", "01", "--json")

    payload = json.loads(result.stdout)
    findings = payload.get("findings") or []
    assert any("声明了却没改" in item and "phantom.txt" in item for item in findings), findings


def test_land_wave_honours_require_closeout(tmp_path: Path) -> None:
    prepared(tmp_path)
    assert run_dispatch(tmp_path, "review", "01", "--reviewer", "reviewer-b", "--verdict", "pass").returncode == 0

    result = run_dispatch(tmp_path, "land", "--wave", "--require-closeout", "--json")

    payload = json.loads(result.stdout)
    assert result.returncode != 0
    assert any("closeout" in str(item.get("reason", "")) for item in payload["failed"]), payload
