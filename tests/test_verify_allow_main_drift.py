from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBE = (
    'python -c "import pathlib, sys; '
    "sys.exit(0 if pathlib.Path('src/01.py').is_file() else 1)"
    '"'
)


def ticket_text() -> str:
    return f"""# 01: A

**What to build:** Ship A.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/01.py
- Verify: {PROBE}

## Acceptance

- [ ] A works.
"""


def git(tmp_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


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


def only_run(tmp_path: Path) -> Path:
    return sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]


def prepare_running_run(tmp_path: Path) -> Path:
    """render → start → 写回执与产物，停在 running（不 verify）。"""
    directory = tmp_path / "tickets"
    directory.mkdir()
    (directory / "01-a.md").write_text(ticket_text(), encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(directory)).returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = only_run(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    (run_dir / "evidence").mkdir()
    (run_dir / "evidence" / "proof.txt").write_text("proof\n", encoding="utf-8")
    (run_dir / "receipt.json").write_text(
        json.dumps(
            {
                "ticket_id": "01",
                "run_id": run["run_id"],
                "status": "done",
                "summary": "implemented",
                "criteria": [
                    {
                        "id": 1,
                        "verdict": "pass",
                        "evidence": [{"kind": "file", "path": "evidence/proof.txt"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    worktree = Path(str(run["execution_root"]))
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "src").mkdir()
    (worktree / "src" / "01.py").write_text("print('done')\n", encoding="utf-8")
    return run_dir


def test_verify_refuses_a_dirty_main_checkout(tmp_path: Path) -> None:
    """主检出有未提交文件时 verify 默认拒绝（exit 1）。"""
    prepare_running_run(tmp_path)
    (tmp_path / "scratch-dirty.txt").write_text("dirty\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 1, result.stdout + result.stderr
    combined = (result.stdout + result.stderr).lower()
    assert "clean checkout required" in combined
    assert "scratch-dirty.txt" in combined


def test_verify_allow_main_drift_reports_but_passes(tmp_path: Path) -> None:
    """--allow-main-drift：同一个脏主检出只报告、判 passed。"""
    prepare_running_run(tmp_path)
    (tmp_path / "scratch-dirty.txt").write_text("dirty\n", encoding="utf-8")

    result = run_dispatch(tmp_path, "verify", "01", "--allow-main-drift")

    assert result.returncode == 0, result.stdout + result.stderr
    run_dir = only_run(tmp_path)
    record = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))
    assert record["status"] == "passed"
