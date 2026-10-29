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


def prepare(tmp_path: Path) -> Path:
    directory = tmp_path / "tickets"
    directory.mkdir()
    (directory / "01-a.md").write_text(ticket_text(), encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    assert run_dispatch(tmp_path, "render", "01", "--tickets", str(directory)).returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    return directory


def test_criterion_with_note_and_reproducible_evidence_is_passed_not_degraded(
    tmp_path: Path,
) -> None:
    """note 可以和可复算证据混用：只有「仅 note」的 criterion 才降级。

    期望值来源（独立于实现）：README「一个 criterion 如果只有 note 证据，会把整体结论降为
    degraded」；references/ticket-contract.md「degraded：没有 fail，但至少一个 criterion 只有
    note 证据」；SKILL.md「某条判据的**全部**证据都是 attested → degraded」。证据书写顺序不该
    改变结论。
    """
    prepare(tmp_path)
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
                        "evidence": [
                            {"kind": "note", "note": "先手工看了一眼，判断方向对"},
                            {"kind": "file", "path": "evidence/proof.txt"},
                        ],
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

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 0, result.stderr
    record = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))
    assert record["status"] == "passed"
    assert record["degraded"] is False
    state = json.loads((tmp_path / ".dispatch" / "state.json").read_text(encoding="utf-8"))
    assert state["tickets"]["01"]["state"] == "review"
