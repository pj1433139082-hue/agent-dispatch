from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: auto attest

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

EXECUTOR = """import json, os, pathlib
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
pathlib.Path("out.txt").write_text("ok", encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
    "ticket_id": "01", "run_id": os.environ["DISPATCH_RUN_ID"], "status": "done", "summary": "ok",
    "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
}), encoding="utf-8")
"""

SILENT = """import json, os, pathlib
pathlib.Path(os.environ["DISPATCH_REVIEW_RESULT"]).write_text(
    json.dumps({"verdict": "pass", "notes": "no hash"}), encoding="utf-8"
)
"""

ATTEST = """import hashlib, json, os, pathlib
packet = pathlib.Path(os.environ["DISPATCH_REVIEW_PACKET"])
digest = hashlib.sha256(packet.read_bytes()).hexdigest()
pathlib.Path(os.environ["DISPATCH_REVIEW_RESULT"]).write_text(
    json.dumps({"verdict": "pass", "notes": "ok", "packet_hash": digest}), encoding="utf-8"
)
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo(tmp_path: Path, risk: str) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET.format(risk=risk), encoding="utf-8")
    (tmp_path / "exec.py").write_text(EXECUTOR, encoding="utf-8")
    (tmp_path / "silent.py").write_text(SILENT, encoding="utf-8")
    (tmp_path / "attest.py").write_text(ATTEST, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def test_l2_auto_requires_the_reviewer_to_attest_the_packet(tmp_path: Path) -> None:
    repo(tmp_path, "L2")

    result = run_dispatch(
        tmp_path, "auto", "01", "--executor", "python exec.py",
        "--until", "land", "--reviewer", "reviewer-b", "--reviewer-command", "python silent.py",
    )

    assert result.returncode != 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    auto = json.loads((run_dir / "auto.json").read_text(encoding="utf-8"))
    assert auto["status"] == "review-invalid", auto
    assert "packet" in str(auto.get("error", "")).lower()
    assert not (run_dir / "landing.json").exists()


def test_l2_auto_lands_when_the_reviewer_attests(tmp_path: Path) -> None:
    repo(tmp_path, "L2")

    result = run_dispatch(
        tmp_path, "auto", "01", "--executor", "python exec.py",
        "--until", "land", "--reviewer", "reviewer-b", "--reviewer-command", "python attest.py",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    review = json.loads((run_dir / "review.json").read_text(encoding="utf-8"))
    assert review["packet_attested"] is True
    assert (run_dir / "landing.json").is_file()


def test_l1_auto_still_lands_without_an_attestation(tmp_path: Path) -> None:
    repo(tmp_path, "L1")

    result = run_dispatch(
        tmp_path, "auto", "01", "--executor", "python exec.py",
        "--until", "land", "--reviewer", "reviewer-b", "--reviewer-command", "python silent.py",
    )

    assert result.returncode == 0, result.stdout + result.stderr
