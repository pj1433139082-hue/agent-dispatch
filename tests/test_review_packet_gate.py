from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: packet

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

GOOD_REVIEWER = """import json, os, pathlib
packet = pathlib.Path(os.environ["DISPATCH_REVIEW_PACKET"])
import hashlib
digest = hashlib.sha256(packet.read_bytes()).hexdigest()
pathlib.Path(os.environ["DISPATCH_REVIEW_RESULT"]).write_text(
    json.dumps({"verdict": "pass", "notes": "ok", "packet_hash": digest}), encoding="utf-8"
)
"""

BAD_REVIEWER = """import json, os, pathlib
pathlib.Path(os.environ["DISPATCH_REVIEW_RESULT"]).write_text(
    json.dumps({"verdict": "pass", "notes": "wrong object", "packet_hash": "deadbeef"}), encoding="utf-8"
)
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "exec.py").write_text(EXECUTOR, encoding="utf-8")
    (tmp_path / "good.py").write_text(GOOD_REVIEWER, encoding="utf-8")
    (tmp_path / "bad.py").write_text(BAD_REVIEWER, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def test_packet_hash_matches_verify_diff_hash(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]

    packet = run_dispatch(tmp_path, "review-packet", "01", "--json")
    assert packet.returncode == 0, packet.stderr
    hashes = json.loads(packet.stdout)["hashes"]
    verify = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))

    assert verify["diff_hash"] == hashes["diff"], (verify["diff_hash"], hashes["diff"])
    assert verify.get("diff_scope") == "tracked+untracked"


def test_auto_hands_the_packet_to_the_reviewer_and_checks_its_hash(tmp_path: Path) -> None:
    repo(tmp_path)

    good = run_dispatch(
        tmp_path, "auto", "01", "--executor", "python exec.py",
        "--until", "land", "--reviewer", "reviewer-b", "--reviewer-command", "python good.py",
    )
    assert good.returncode == 0, good.stdout + good.stderr
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    assert (run_dir / "review-packet.md").is_file()
    assert (run_dir / "landing.json").is_file()


def test_a_wrong_packet_hash_blocks_the_landing(tmp_path: Path) -> None:
    repo(tmp_path)

    result = run_dispatch(
        tmp_path, "auto", "01", "--executor", "python exec.py",
        "--until", "land", "--reviewer", "reviewer-b", "--reviewer-command", "python bad.py",
    )

    assert result.returncode != 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    auto = json.loads((run_dir / "auto.json").read_text(encoding="utf-8"))
    assert auto["status"] == "review-invalid", auto
    assert not (run_dir / "landing.json").exists()


def test_land_requires_a_packet(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py").returncode == 0
    assert run_dispatch(tmp_path, "review", "01", "--reviewer", "reviewer-b", "--verdict", "pass").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    (run_dir / "review-packet.md").unlink()

    result = run_dispatch(tmp_path, "land", "01")

    assert result.returncode != 0
    assert "packet" in (result.stdout + result.stderr).lower()


def test_legacy_verify_record_is_flagged_in_the_packet(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py").returncode == 0
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    verify_path = run_dir / "verify.json"
    data = json.loads(verify_path.read_text(encoding="utf-8"))
    data.pop("diff_scope", None)
    verify_path.write_text(json.dumps(data), encoding="utf-8")

    result = run_dispatch(tmp_path, "review-packet", "01", "--json")

    assert result.returncode == 0, result.stderr
    text = (run_dir / "review-packet.md").read_text(encoding="utf-8")
    assert "legacy" in text.lower(), text[:400]


def test_land_can_require_a_reviewer_attestation(tmp_path: Path) -> None:
    repo(tmp_path)
    assert run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py").returncode == 0
    assert run_dispatch(tmp_path, "review", "01", "--reviewer", "reviewer-b", "--verdict", "pass").returncode == 0
    assert run_dispatch(tmp_path, "review-packet", "01").returncode == 0

    result = run_dispatch(tmp_path, "land", "01", "--require-attestation")

    assert result.returncode != 0
    assert "attest" in (result.stdout + result.stderr).lower()


def test_land_accepts_an_attested_review(tmp_path: Path) -> None:
    repo(tmp_path)
    result = run_dispatch(
        tmp_path, "auto", "01", "--executor", "python exec.py",
        "--until", "land", "--reviewer", "reviewer-b", "--reviewer-command", "python good.py",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    review = json.loads((run_dir / "review.json").read_text(encoding="utf-8"))
    assert review.get("packet_attested") is True
