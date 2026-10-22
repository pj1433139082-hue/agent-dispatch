from __future__ import annotations

from pathlib import Path

from agent_dispatch.verify import _evaluate_evidence


def test_command_evidence_accepts_an_expected_failure(tmp_path: Path) -> None:
    record, error, attested = _evaluate_evidence(
        {"kind": "command", "command": "node check.mjs", "exit_code": 1, "expect_exit": 1},
        run_dir=tmp_path,
        prefix="c1.e1",
    )

    assert error is None, error
    assert record is not None and record["exit_code"] == 1
    assert attested is False


def test_command_evidence_rejects_a_surprise_failure(tmp_path: Path) -> None:
    _record, error, _attested = _evaluate_evidence(
        {"kind": "command", "command": "node check.mjs", "exit_code": 1},
        run_dir=tmp_path,
        prefix="c1.e1",
    )

    assert error is not None and "expected 0" in error


def test_command_evidence_rejects_non_integer_expect_exit(tmp_path: Path) -> None:
    _record, error, _attested = _evaluate_evidence(
        {"kind": "command", "command": "x", "exit_code": 0, "expect_exit": "1"},
        run_dir=tmp_path,
        prefix="c1.e1",
    )

    assert error is not None and "expect_exit" in error
