"""Failure feedback: carry verification findings into the next attempt.

A retry that reruns the same command without telling the executor what failed
wastes the attempt. This module writes the previous attempt's verification
errors into a file the next attempt is pointed at.
"""

from __future__ import annotations

from pathlib import Path

FEEDBACK_DIR = Path("auto")


def render_feedback(attempt: int, errors: list[str], log_name: str = "") -> str:
    lines = [
        "# Attempt " + str(attempt) + " failed verification",
        "",
        "Fix exactly these findings before re-running the verification command.",
        "Do not widen the write scope and do not edit the ticket.",
        "",
    ]
    if log_name:
        lines.extend(["Executor log: " + log_name, ""])
    if errors:
        lines.append("## Findings")
        lines.append("")
        lines.extend("- " + error for error in errors)
    else:
        lines.extend([
            "## Findings",
            "",
            "- (verification failed without a structured error list; read verify.json)",
        ])
    lines.append("")
    return "\n".join(lines)


def write_feedback(run_dir: Path, attempt: int, errors: list[str], log_name: str = "") -> Path:
    target = Path(run_dir) / FEEDBACK_DIR / ("feedback-" + str(attempt) + ".md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_feedback(attempt, errors, log_name), encoding="utf-8")
    return target
