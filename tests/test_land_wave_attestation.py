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


def test_land_wave_require_attestation_refuses_runs_whose_review_is_not_attested(
    tmp_path: Path,
) -> None:
    """波次 land 的 --require-attestation 必须和单票 land 一样拦下"评审没核评审包"的 run。

    期望值来源（独立于实现）：dispatch land --help 里 --require-attestation 的说明
    「Refuse to land unless the review attested the review packet (packet_attested)」；
    SKILL.md 命令表把 land <id> 与 --wave 写成同一行、同一组门禁
    （[--require-closeout] [--require-attestation] [--no-require-packet]）。
    """
    run_dir = prepare_done_run(tmp_path)
    review = json.loads((run_dir / "review.json").read_text(encoding="utf-8"))
    assert review["packet_attested"] is False  # L1 评审没给 --packet-hash，天然未核包

    result = run_dispatch(tmp_path, "land", "--wave", "--require-attestation", "--json")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "attest" in (result.stdout + result.stderr).lower()
    assert not (run_dir / "landing.json").exists()
