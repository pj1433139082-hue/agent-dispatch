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


def test_command_only_criterion_is_degraded(tmp_path: Path) -> None:
    """D3: command is executor self-report, never re-run, so it cannot alone prove a criterion."""
    from agent_dispatch.verify import _evaluate_criteria
    from agent_dispatch.ticket import Ticket

    ticket = Ticket(
        id="01", title="t", path=Path("01.md"), what_to_build="x",
        owner="implementer", risk="L1", depends_on=(), write_scope=("src/01.py",),
        verify=("python -c \"print(1)\"",), acceptance=("it works.",),
    )
    receipt = {"criteria": [{"id": 1, "verdict": "pass", "evidence": [
        {"kind": "command", "command": "true", "exit_code": 0},
    ]}]}

    _records, _evidence, _errors, degraded = _evaluate_criteria(receipt, ticket, tmp_path)

    assert degraded is True, "a command-only criterion must be degraded"


def test_command_plus_file_criterion_is_not_degraded(tmp_path: Path) -> None:
    """One non-command item is enough; command is simply not counted."""
    from agent_dispatch.verify import _evaluate_criteria
    from agent_dispatch.ticket import Ticket

    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "proof.txt").write_text("ok", encoding="utf-8")
    ticket = Ticket(
        id="01", title="t", path=Path("01.md"), what_to_build="x",
        owner="implementer", risk="L1", depends_on=(), write_scope=("src/01.py",),
        verify=("python -c \"print(1)\"",), acceptance=("it works.",),
    )
    receipt = {"criteria": [{"id": 1, "verdict": "pass", "evidence": [
        {"kind": "command", "command": "true", "exit_code": 0},
        {"kind": "file", "path": "evidence/proof.txt"},
    ]}]}

    _records, _evidence, _errors, degraded = _evaluate_criteria(receipt, ticket, tmp_path)

    assert degraded is False, "one recomputable item is enough"
