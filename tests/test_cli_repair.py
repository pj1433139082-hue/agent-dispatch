from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET_PREFLIGHT = """# 01: preflight

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

- [ ] out.txt 存在。"""

EXECUTOR_PREFLIGHT = """import json, os, pathlib
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
pathlib.Path("out.txt").write_text("ok", encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
    "ticket_id": "01", "run_id": os.environ["DISPATCH_RUN_ID"], "status": "done", "summary": "ok",
    "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
}), encoding="utf-8")"""


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )


def make_run(tmp_path: Path, run_id: str, ticket_id: str, *, state: str = "running") -> Path:
    run_dir = tmp_path / ".dispatch" / "runs" / run_id
    run_dir.mkdir(parents=True)
    created = datetime.now(timezone.utc).isoformat()
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": run_id, "ticket_id": ticket_id, "state": state, "created_at": created}),
        encoding="utf-8",
    )
    return run_dir


def write_state(tmp_path: Path, tickets: dict) -> Path:
    path = tmp_path / ".dispatch" / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "tickets": tickets}, indent=2), encoding="utf-8")
    return path


def test_repair_dry_run_reports_without_writing(tmp_path: Path) -> None:
    make_run(tmp_path, "01-probe-20261022T000000Z-eeeeee", "01-probe")
    state = write_state(tmp_path, {})
    before = state.read_bytes()

    result = run_dispatch(tmp_path, "repair")

    assert result.returncode == 0, result.stderr
    assert "01-probe" in result.stdout
    assert state.read_bytes() == before

def test_repair_write_adds_the_missing_ticket(tmp_path: Path) -> None:
    run_id = "01-probe-20261022T000000Z-ffffff"
    make_run(tmp_path, run_id, "01-probe")
    state = write_state(tmp_path, {})

    result = run_dispatch(tmp_path, "repair", "--write")

    assert result.returncode == 0, result.stderr
    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["tickets"]["01-probe"]["run_id"] == run_id
    assert data["tickets"]["01-probe"]["state"] == "running"

def test_repair_conflict_exits_1_and_leaves_the_ticket_alone(tmp_path: Path) -> None:
    make_run(tmp_path, "01-probe-20261022T010000Z-gggggg", "01-probe")
    state = write_state(
        tmp_path,
        {"01-probe": {"run_id": "01-probe-20261022T000000Z-oldold", "state": "running", "updated_at": "2026-10-21T00:00:00+00:00"}},
    )
    before = state.read_bytes()

    result = run_dispatch(tmp_path, "repair", "--write")

    assert result.returncode == 1
    assert "CONFLICT" in result.stderr
    assert state.read_bytes() == before

def test_repair_reports_evidence_mismatch(tmp_path: Path) -> None:
    run_id = "01-probe-20261022T020000Z-hhhhhh"
    run_dir = make_run(tmp_path, run_id, "01-probe", state="failed")
    (run_dir / "verify.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    write_state(tmp_path, {"01-probe": {"run_id": run_id, "state": "failed", "updated_at": "2026-10-22T00:00:00+00:00"}})

    result = run_dispatch(tmp_path, "repair")

    assert "EVIDENCE-MISMATCH" in result.stdout
    assert "01-probe" in result.stdout


def test_repair_write_skips_evidence_mismatch(tmp_path: Path) -> None:
    run_id = "01-probe-20261022T020500Z-iiiiii"
    run_dir = make_run(tmp_path, run_id, "01-probe", state="failed")
    (run_dir / "verify.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    state = write_state(tmp_path, {"01-probe": {"run_id": run_id, "state": "review", "updated_at": "2026-10-22T00:00:00+00:00"}})
    before = json.loads(state.read_text(encoding="utf-8"))

    run_dispatch(tmp_path, "repair", "--write")

    after = json.loads(state.read_text(encoding="utf-8"))
    assert after["tickets"]["01-probe"]["state"] == before["tickets"]["01-probe"]["state"]


def test_repair_refuses_to_add_a_done_ticket_without_evidence(tmp_path: Path) -> None:
    """A run.json claiming done with no review/closeout/verify must not become done."""
    run_id = "01-ghost-20261102T000000Z-aaaaaa"
    make_run(tmp_path, run_id, "01-ghost", state="done")
    state = write_state(tmp_path, {})

    report = run_dispatch(tmp_path, "repair", "--json")
    assert report.returncode == 0, report.stderr
    payload = json.loads(report.stdout)
    assert [item["ticket_id"] for item in payload["evidence_blocked"]] == ["01-ghost"]

    result = run_dispatch(tmp_path, "repair", "--write")

    assert result.returncode == 0, result.stderr
    data = json.loads(state.read_text(encoding="utf-8"))
    assert "01-ghost" not in data["tickets"], "must not add a done ticket that has no passing review"
    # 该票被拒写：报告里计入 evidence_blocked（json 模式可查），state 不发生新增


def test_repair_keeps_a_failed_ticket_failed_when_run_claims_done(tmp_path: Path) -> None:
    """Existing index value wins: a done claim without evidence cannot upgrade failed."""
    run_id = "02-ghost-20261102T000000Z-bbbbbb"
    make_run(tmp_path, run_id, "02-ghost", state="done")
    state = write_state(
        tmp_path,
        {"02-ghost": {"run_id": run_id, "state": "failed", "updated_at": "2026-11-01T00:00:00+00:00"}},
    )

    result = run_dispatch(tmp_path, "repair", "--write")

    assert result.returncode == 0, result.stderr
    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["tickets"]["02-ghost"]["state"] == "failed", "failed must not be upgraded to done without evidence"


def test_repair_writes_done_when_a_passing_review_exists(tmp_path: Path) -> None:
    """The legitimate path still works: review.json verdict=pass is the proof."""
    run_id = "03-real-20261102T000000Z-cccccc"
    run_dir = make_run(tmp_path, run_id, "03-real", state="done")
    (run_dir / "review.json").write_text(json.dumps({"verdict": "pass"}), encoding="utf-8")
    state = write_state(tmp_path, {})

    result = run_dispatch(tmp_path, "repair", "--write")

    assert result.returncode == 0, result.stderr
    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["tickets"]["03-real"]["state"] == "done"
    assert data["tickets"]["03-real"]["status_source"] == "evidence"


def test_repair_records_status_source_for_non_done_states(tmp_path: Path) -> None:
    """Non-done states record run.json as their source."""
    run_id = "04-probe-20261102T000000Z-dddddd"
    make_run(tmp_path, run_id, "04-probe", state="running")
    state = write_state(tmp_path, {})

    result = run_dispatch(tmp_path, "repair", "--write")

    assert result.returncode == 0, result.stderr
    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["tickets"]["04-probe"]["status_source"] == "run.json"


def test_status_reports_evidence_mismatch_but_stays_exit_0(tmp_path: Path) -> None:
    """status 是只读查询：列出不一致，但退出码必须仍是 0。"""
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01-probe.md").write_text(
        "# 01-probe: probe\n\n**What to build:** x\n**Blocked by:** None\n**Status:** ready-for-agent\n\n"
        "## Dispatch\n\n- Owner: implementer\n- Risk: L1\n- Write scope: out.txt\n"
        "- Verify: python -c \"print(1)\"\n\n## Acceptance\n\n- [ ] x\n",
        encoding="utf-8",
    )
    run_id = "01-probe-20261022T030000Z-jjjjjj"
    run_dir = make_run(tmp_path, run_id, "01-probe", state="failed")
    (run_dir / "verify.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    write_state(tmp_path, {"01-probe": {"run_id": run_id, "state": "failed", "updated_at": "2026-10-22T00:00:00+00:00"}})

    result = run_dispatch(tmp_path, "status")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "EVIDENCE-MISMATCH" in result.stdout, result.stdout
    assert "state=failed" in result.stdout
    assert "evidence=review" in result.stdout


def test_status_json_carries_evidence_mismatch(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01-probe.md").write_text(
        "# 01-probe: probe\n\n**What to build:** x\n**Blocked by:** None\n**Status:** ready-for-agent\n\n"
        "## Dispatch\n\n- Owner: implementer\n- Risk: L1\n- Write scope: out.txt\n"
        "- Verify: python -c \"print(1)\"\n\n## Acceptance\n\n- [ ] x\n",
        encoding="utf-8",
    )
    run_id = "01-probe-20261022T030500Z-kkkkkk"
    run_dir = make_run(tmp_path, run_id, "01-probe", state="failed")
    (run_dir / "verify.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    write_state(tmp_path, {"01-probe": {"run_id": run_id, "state": "failed", "updated_at": "2026-10-22T00:00:00+00:00"}})

    result = run_dispatch(tmp_path, "status", "--json")

    assert result.returncode == 0, result.stderr
    document = json.loads(result.stdout)
    rows = document["evidence_mismatch"]
    assert len(rows) == 1, rows
    assert rows[0]["ticket_id"] == "01-probe"
    assert rows[0]["state_run"] == "failed"
    assert rows[0]["evidence"] == "review"


def test_repair_reports_evidence_blocked(tmp_path: Path) -> None:
    """done 但缺 passing review 的票：repair 文本模式要打 EVIDENCE-BLOCKED。"""
    run_id = "01-probe-20261022T031000Z-llllll"
    make_run(tmp_path, run_id, "01-probe", state="done")
    write_state(tmp_path, {"01-probe": {"run_id": run_id, "state": "done", "updated_at": "2026-10-22T00:00:00+00:00"}})

    result = run_dispatch(tmp_path, "repair")

    assert "EVIDENCE-BLOCKED" in result.stdout, result.stdout + result.stderr
    assert "01-probe" in result.stdout


def test_status_mismatch_appends_to_existing_hint(tmp_path: Path) -> None:
    """mismatch 提示必须追加，不能把「未落地」等既有 hint 覆盖掉。"""
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01-probe.md").write_text(
        "# 01-probe: probe\n\n**What to build:** x\n**Blocked by:** None\n**Status:** ready-for-agent\n\n"
        "## Dispatch\n\n- Owner: implementer\n- Risk: L1\n- Write scope: out.txt\n"
        "- Verify: python -c \"print(1)\"\n\n## Acceptance\n\n- [ ] x\n",
        encoding="utf-8",
    )
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    # 造一个 done 但未落地的 run，同时让它与证据不一致（state=done 而证据=review）。
    run_id = "01-probe-20261022T040000Z-mmmmmm"
    run_dir = make_run(tmp_path, run_id, "01-probe", state="done")
    (run_dir / "verify.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    write_state(tmp_path, {"01-probe": {"run_id": run_id, "state": "done", "updated_at": "2026-10-22T00:00:00+00:00"}})

    result = run_dispatch(tmp_path, "status")

    assert result.returncode == 0, result.stderr
    assert "EVIDENCE-MISMATCH" in result.stdout, result.stdout
    assert "未落地" in result.stdout, "既有 hint 被覆盖了: " + result.stdout


def test_auto_preflight_does_not_block_on_evidence_mismatch(tmp_path: Path) -> None:
    """auto 的 preflight 不该因证据不一致拒跑（_health_report 是 doctor/auto 共用的）。"""
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET_PREFLIGHT, encoding="utf-8")
    (tmp_path / "exec.py").write_text(EXECUTOR_PREFLIGHT, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    run_id = "01-20261022T050000Z-nnnnnn"
    run_dir = make_run(tmp_path, run_id, "01", state="failed")
    (run_dir / "verify.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    write_state(tmp_path, {"01": {"run_id": run_id, "state": "failed", "updated_at": "2026-10-22T00:00:00+00:00"}})

    result = run_dispatch(tmp_path, "auto", "01", "--executor", "python exec.py")

    combined = (result.stdout + result.stderr).lower()
    assert "preflight failed" not in combined, "auto 被 mismatch 拦住了: " + result.stdout + result.stderr


