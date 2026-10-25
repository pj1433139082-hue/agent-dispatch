from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: identity

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


def ready_for_review(tmp_path: Path, risk: str = "L1") -> Path:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET.format(risk=risk), encoding="utf-8")
    (tmp_path / ".dispatch").mkdir(exist_ok=True)
    (tmp_path / ".dispatch" / "config.json").write_text(json.dumps({"persona_policy": "off"}), encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    assert run_dispatch(tmp_path, "render", "01", "--no-worktree").returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    (tmp_path / "out.txt").write_text("ok", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": "01", "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", "01").returncode == 0
    return run_dir


def test_a_reviewer_with_the_executor_name_is_refused(tmp_path: Path) -> None:
    ready_for_review(tmp_path, "L1")

    result = run_dispatch(tmp_path, "review", "01", "--reviewer", "implementer", "--verdict", "pass")

    assert result.returncode != 0
    assert "self" in (result.stdout + result.stderr).lower() or "执行者" in (result.stdout + result.stderr)


def test_l1_self_review_needs_the_explicit_flag_and_then_passes(tmp_path: Path) -> None:
    ready_for_review(tmp_path, "L1")

    result = run_dispatch(
        tmp_path, "review", "01", "--reviewer", "implementer", "--verdict", "pass", "--self-reviewed",
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_l2_self_review_is_never_allowed(tmp_path: Path) -> None:
    ready_for_review(tmp_path, "L2")

    result = run_dispatch(
        tmp_path, "review", "01", "--reviewer", "implementer", "--verdict", "pass", "--self-reviewed",
    )

    assert result.returncode != 0


def test_l2_review_needs_the_packet_hash(tmp_path: Path) -> None:
    run_dir = ready_for_review(tmp_path, "L2")
    assert run_dispatch(tmp_path, "review-packet", "01").returncode == 0
    digest = hashlib.sha256((run_dir / "review-packet.md").read_bytes()).hexdigest()

    missing = run_dispatch(tmp_path, "review", "01", "--reviewer", "reviewer-b", "--verdict", "pass")
    assert missing.returncode != 0
    assert "packet" in (missing.stdout + missing.stderr).lower()

    wrong = run_dispatch(
        tmp_path, "review", "01", "--reviewer", "reviewer-b", "--verdict", "pass", "--packet-hash", "deadbeef",
    )
    assert wrong.returncode != 0

    ok = run_dispatch(
        tmp_path, "review", "01", "--reviewer", "reviewer-b", "--verdict", "pass", "--packet-hash", digest,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    review = json.loads((run_dir / "review.json").read_text(encoding="utf-8"))
    assert review["packet_attested"] is True
