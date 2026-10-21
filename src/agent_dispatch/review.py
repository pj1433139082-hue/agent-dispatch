"""Review gate: a different actor signs the verified run."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .state import DispatchState, Run
from .ticket import Ticket


def _append_ledger(root: Path, record: dict[str, object], review_hash: str) -> None:
    ledger = Path(root) / ".dispatch" / "ledger" / "reviews.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "at": record["reviewed_at"],
        "ticket_id": record["ticket_id"],
        "run_id": record["run_id"],
        "reviewer": record["reviewer"],
        "verdict": record["verdict"],
        "notes": record["notes"],
        "verify_status": record["verify_status"],
        "accepted_degraded": record["accepted_degraded"],
        "review_hash": review_hash,
    }
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def submit_review(
    root: Path,
    ticket: Ticket,
    run: Run,
    reviewer: str,
    verdict: str,
    notes: str = "",
    human: bool = False,
    accept_degraded: bool = False,
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

    verify_status = ""
    verify_path = run.directory / "verify.json"
    if not verify_path.is_file():
        errors.append("verify.json is missing; verification must pass first")
    else:
        verify = json.loads(verify_path.read_text(encoding="utf-8"))
        verify_status = str(verify.get("status", ""))
        if verify_status not in {"passed", "degraded"}:
            errors.append("verify.json did not pass; review is refused")
        elif verify_status == "degraded" and not accept_degraded:
            errors.append(
                "verification is degraded; review needs explicit --accept-degraded"
            )

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
        "verify_status": verify_status,
        "accepted_degraded": bool(accept_degraded and verify_status == "degraded"),
    }
    review_path = run.directory / "review.json"
    review_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    review_hash = hashlib.sha256(review_path.read_bytes()).hexdigest()
    _append_ledger(root, record, review_hash)
    next_state = "done" if verdict == "pass" else "failed"
    run.set_state(next_state)
    store.set_ticket(ticket.id, run.id, next_state)
    return record, []
