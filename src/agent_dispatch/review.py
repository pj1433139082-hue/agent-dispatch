"""Review gate: a different actor signs the verified run."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .state import DispatchState, Run
from .ticket import Ticket


def submit_review(
    root: Path,
    ticket: Ticket,
    run: Run,
    reviewer: str,
    verdict: str,
    notes: str = "",
    human: bool = False,
) -> tuple[dict[str, object] | None, list[str]]:
    reviewer = reviewer.strip()
    verdict = verdict.strip().lower()
    errors: list[str] = []

    if not reviewer:
        errors.append("reviewer identity is required")
    if verdict not in {"pass", "fail"}:
        errors.append("verdict must be 'pass' or 'fail'")

    store = DispatchState(root)
    current = store.ticket(ticket.id)
    if not current or current.get("state") != "review":
        errors.append(f"ticket {ticket.id} is not in review state; verify must pass first")

    verify_path = run.directory / "verify.json"
    if not verify_path.is_file():
        errors.append("verify.json is missing; verification must pass first")
    else:
        verify = json.loads(verify_path.read_text(encoding="utf-8"))
        if verify.get("status") != "passed":
            errors.append("verify.json did not pass; review is refused")

    if reviewer and (reviewer == ticket.owner or reviewer == str(run.data.get("claimed_by", ""))):
        errors.append("self-review is not allowed: reviewer equals the ticket owner or claiming agent")
    if ticket.risk == "L4" and not human:
        errors.append("L4 work requires an explicit human reviewer (--human)")

    if errors:
        return None, errors

    record: dict[str, object] = {
        "run_id": run.id,
        "ticket_id": ticket.id,
        "reviewer": reviewer,
        "verdict": verdict,
        "notes": notes,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if verdict == "pass" else "failed",
    }
    (run.directory / "review.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    next_state = "done" if verdict == "pass" else "failed"
    run.set_state(next_state)
    store.set_ticket(ticket.id, run.id, next_state)
    return record, []
