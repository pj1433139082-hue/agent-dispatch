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


def state_of(tmp_path: Path) -> str:
    data = json.loads((tmp_path / ".dispatch" / "state.json").read_text(encoding="utf-8"))
    return str(data["tickets"]["01"]["state"])


def prepare_degraded(tmp_path: Path) -> Path:
    """只有 note 证据的 criterion → verify 判 degraded（退出码 2），票停在 review。"""
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
                        "evidence": [{"kind": "note", "note": "我手工看过，应该没问题"}],
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
    assert verified.returncode == 2, verified.stderr
    assert state_of(tmp_path) == "review"
    return run_dir


def test_reviewer_can_reject_a_degraded_verification_without_accepting_it(
    tmp_path: Path,
) -> None:
    """degraded 只约束"放行"：评审判 fail 是不放行，不该被 --accept-degraded 卡住。

    期望值来源（独立于实现）：README「degraded 必须由评审显式 --accept-degraded 才能放行」——
    「放行」= verdict pass；references/ticket-contract.md 的状态机 review --verdict fail →
    failed，且 failed 票可 retry；如果连 reject 都要先"接受降解"，票会永久卡在 review
    （retry 只接受 failed / claimed），没有任何出口。
    """
    run_dir = prepare_degraded(tmp_path)

    result = run_dispatch(
        tmp_path,
        "review",
        "01",
        "--reviewer",
        "reviewer",
        "--verdict",
        "fail",
        "--notes",
        "证据不可复算，退回补物证",
    )

    assert result.returncode == 0, result.stderr
    record = json.loads((run_dir / "review.json").read_text(encoding="utf-8"))
    assert record["verdict"] == "fail"
    assert record["status"] == "failed"
    assert state_of(tmp_path) == "failed"
    retried = run_dispatch(tmp_path, "retry", "01", "--reason", "补可复算证据后重验")
    assert retried.returncode == 0, retried.stderr
