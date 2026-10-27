from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: x

**What to build:** x
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: a
- Risk: L1
- Write scope: out.txt
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('out.txt').exists() else 1)"

## Acceptance

- [ ] out.txt
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_retry_refreshes_the_context_pack_with_the_attempt_number(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "off", "require_brief": False}), encoding="utf-8"
    )
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)

    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead", "--with-context").returncode == 0
    run_dir = next((tmp_path / ".dispatch" / "runs").glob("*/"))
    context_file = run_dir / "context.md"
    assert "first run" in context_file.read_text(encoding="utf-8")

    run_dispatch(tmp_path, "start", "01")
    (tmp_path / ".gitignore").write_text(".dispatch/\n", encoding="utf-8")  # 让 verify 因主仓脏失败
    (tmp_path / "out.txt").write_text("x", encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", "01").returncode != 0

    assert run_dispatch(tmp_path, "retry", "01", "--reason", "retest").returncode == 0

    text = context_file.read_text(encoding="utf-8")
    assert "attempt 2" in text, text
    assert "first run" not in text
