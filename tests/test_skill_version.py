from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: versioned

## What to build

x

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "print(1)"

## Acceptance

- [ ] x
"""


def test_render_records_the_skill_version(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", "commit", "-q", "-m", "base"], cwd=tmp_path, check=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "agent_dispatch", "render", "01", "--no-worktree"],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "src"))
    from agent_dispatch import __version__

    assert run.get("skill_version") == __version__
