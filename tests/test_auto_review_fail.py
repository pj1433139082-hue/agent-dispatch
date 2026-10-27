from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: review-fail

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

EXECUTOR = """import json, os, pathlib
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
pathlib.Path("out.txt").write_text("done", encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
    "ticket_id": "01", "run_id": os.environ["DISPATCH_RUN_ID"], "status": "done", "summary": "ok",
    "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
}), encoding="utf-8")
"""

REVIEWER_FAIL = """import json, os, pathlib
pathlib.Path(os.environ["DISPATCH_REVIEW_RESULT"]).write_text(
    json.dumps({"verdict": "fail", "notes": "评审不通过：证据不足"}), encoding="utf-8"
)
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_a_failing_reviewer_stops_auto_before_landing(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "exec.py").write_text(EXECUTOR, encoding="utf-8")
    (tmp_path / "reviewer.py").write_text(REVIEWER_FAIL, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)

    result = run_dispatch(
        tmp_path, "auto", "01",
        "--executor", "python exec.py",
        "--until", "land",
        "--reviewer", "reviewer-b",
        "--reviewer-command", "python reviewer.py",
    )

    assert result.returncode != 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    auto = json.loads((run_dir / "auto.json").read_text(encoding="utf-8"))
    assert auto["status"] == "review-failed", auto
    assert not (run_dir / "landing.json").exists(), "评审 fail 绝不能 land"
    review = json.loads((run_dir / "review.json").read_text(encoding="utf-8"))
    assert review["verdict"] == "fail"
