from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
