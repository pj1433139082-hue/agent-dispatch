from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: attest

## What to build

写 out.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: {risk}
- Write scope: out.txt
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('out.txt').exists() else 1)"

## Acceptance

- [ ] out.txt 存在。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def ready(tmp_path: Path, risk: str = "L1") -> Path:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET.format(risk=risk), encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
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


def test_l1_review_can_attest_the_packet(tmp_path: Path) -> None:
    run_dir = ready(tmp_path, "L1")
    assert run_dispatch(tmp_path, "review-packet", "01").returncode == 0
    digest = hashlib.sha256((run_dir / "review-packet.md").read_bytes()).hexdigest()

    result = run_dispatch(
        tmp_path, "review", "01", "--reviewer", "reviewer-b", "--verdict", "pass", "--packet-hash", digest,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    review = json.loads((run_dir / "review.json").read_text(encoding="utf-8"))
    assert review["packet_attested"] is True


def test_land_require_attestation_blocks_a_plain_review(tmp_path: Path) -> None:
    ready(tmp_path, "L1")
    assert run_dispatch(tmp_path, "review", "01", "--reviewer", "reviewer-b", "--verdict", "pass").returncode == 0

    result = run_dispatch(tmp_path, "land", "01", "--require-attestation")

    assert result.returncode != 0
    assert "attest" in (result.stdout + result.stderr).lower()
