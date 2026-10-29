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


def prepare_done_run(tmp_path: Path) -> Path:
    """走完整条手工链路到 done：render → start → verify → review（L1，不核评审包）。"""
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
    verified = run_dispatch(tmp_path, "verify", "01")
    assert verified.returncode == 0, verified.stderr
    reviewed = run_dispatch(tmp_path, "review", "01", "--reviewer", "reviewer", "--verdict", "pass")
    assert reviewed.returncode == 0, reviewed.stderr
    return run_dir


def test_land_wave_requires_the_review_packet_like_single_ticket_land(tmp_path: Path) -> None:
    """波次 land 默认也要 review-packet.md：单票 land 默认要求，波次不能绕过。

    期望值来源：SKILL.md「land 默认要求 review-packet.md 存在」；--no-require-packet 的说明
    「Skip the L2+ requirement that review-packet.md exists with a matching hash」只给老 run 迁移用。
    """
    run_dir = prepare_done_run(tmp_path)
    (run_dir / "review-packet.md").unlink()

    result = run_dispatch(tmp_path, "land", "--wave", "--json")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "review-packet" in (result.stdout + result.stderr)
    assert not (run_dir / "landing.json").exists()


def test_land_wave_no_require_packet_still_lands(tmp_path: Path) -> None:
    run_dir = prepare_done_run(tmp_path)
    (run_dir / "review-packet.md").unlink()

    result = run_dispatch(tmp_path, "land", "--wave", "--no-require-packet")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (run_dir / "landing.json").is_file()
