"""Review gate: a different actor signs the verified run."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .packet import write as write_packet
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
        "self_reviewed": record["self_reviewed"],
        "packet_attested": record["packet_attested"],
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
    self_reviewed: bool = False,
    packet_attested: bool | None = None,
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
        # ADR-0008 D5：L0/L1 允许自评，但必须显式 --self-reviewed 留痕；L2+ 一律不许。
        if self_reviewed and ticket.risk in {"L0", "L1"}:
            pass
        elif self_reviewed:
            errors.append("self-review is only allowed for L0/L1 tickets")
        else:
            errors.append("self-review is not allowed: reviewer equals the ticket owner or claiming agent (L0/L1 may pass --self-reviewed)")
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
        "self_reviewed": bool(self_reviewed),
        "packet_attested": bool(packet_attested),
    }
    review_path = run.directory / "review.json"
    review_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    try:
        write_packet(root, ticket, run)
    except Exception:  # noqa: BLE001 - packet 生成失败不阻断评审，但要留痕
        record["packet_error"] = True
    review_hash = hashlib.sha256(review_path.read_bytes()).hexdigest()
    _append_ledger(root, record, review_hash)
    next_state = "done" if verdict == "pass" else "failed"
    run.set_state(next_state)
    store.set_ticket(ticket.id, run.id, next_state)
    return record, []
