from __future__ import annotations

from pathlib import Path

from agent_dispatch.feedback import render_feedback, write_feedback


def test_feedback_lists_every_error() -> None:
    text = render_feedback(2, ["criterion 1: evidence missing", "write scope: src/other.py"])
    assert "# Attempt 2 failed verification" in text
    assert "- criterion 1: evidence missing" in text
    assert "- write scope: src/other.py" in text
    assert "Do not widen the write scope" in text


def test_feedback_without_errors_points_at_verify_json() -> None:
    text = render_feedback(1, [])
    assert "verify.json" in text


def test_write_feedback_lands_in_the_run_directory(tmp_path: Path) -> None:
    target = write_feedback(tmp_path, 3, ["boom"], log_name="attempt-03.log")
    assert target == tmp_path / "auto" / "feedback-3.md"
    assert "Executor log: attempt-03.log" in target.read_text(encoding="utf-8")
