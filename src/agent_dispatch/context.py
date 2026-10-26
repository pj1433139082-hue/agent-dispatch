"""Context pack: the project context a ticket does not carry.

A ticket contract says what to build and how to verify it. It does not say what
the project entry docs require, what earlier runs of the same ticket learned, or
which neighbours are in flight. A fresh session - and especially a board card,
which receives only the ticket text - therefore starts blind. The context pack
collects those facts from the repository into one file.

Read-only and deterministic: no network, no model calls.
"""

from __future__ import annotations

import json
from pathlib import Path

from .state import DispatchState
from .ticket import Ticket, load_tickets

CONTEXT_DIR = Path(".dispatch") / "context"
ENTRY_DOCS = ("AGENTS.md", "CLAUDE.md", "CONTEXT.md")
MAX_DOC_LINES = 60
MAX_DOC_CHARS = 6000
MAX_PRIOR_RUNS = 5
FENCE = chr(96) * 3


def context_path(root: Path, ticket_id: str) -> Path:
    return Path(root) / CONTEXT_DIR / (ticket_id + ".md")


def _read_head(path: Path, max_lines: int = MAX_DOC_LINES) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    head = "\n".join(text.splitlines()[:max_lines]).strip()
    return head[:MAX_DOC_CHARS]


def _prior_runs(root: Path, ticket_id: str, exclude_run_id: str | None = None) -> list[dict[str, object]]:
    runs_root = Path(root) / ".dispatch" / "runs"
    if not runs_root.is_dir():
        return []
    found: list[dict[str, object]] = []
    for directory in runs_root.iterdir():
        run_file = directory / "run.json"
        if not directory.is_dir() or not run_file.is_file():
            continue
        try:
            data = json.loads(run_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(data.get("ticket_id", "")) != ticket_id:
            continue
        if exclude_run_id and str(data.get("run_id", "")) == exclude_run_id:
            continue
        verify_status = ""
        verify_file = directory / "verify.json"
        if verify_file.is_file():
            try:
                verify_status = str(json.loads(verify_file.read_text(encoding="utf-8")).get("status", ""))
            except (OSError, json.JSONDecodeError):
                verify_status = "unreadable"
        auto_error = ""
        auto_file = directory / "auto.json"
        if auto_file.is_file():
            try:
                auto_error = str(json.loads(auto_file.read_text(encoding="utf-8")).get("error", ""))
            except (OSError, json.JSONDecodeError):
                auto_error = "unreadable"
        found.append(
            {
                "run_id": str(data.get("run_id", directory.name)),
                "state": str(data.get("state", "")),
                "created_at": str(data.get("created_at", "")),
                "verify": verify_status,
                "error": auto_error,
            }
        )
    found.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return found[:MAX_PRIOR_RUNS]


def _neighbours(root: Path, ticket: Ticket) -> list[str]:
    if not ticket.depends_on:
        return []
    try:
        known = {item.id: item for item in load_tickets(Path(root) / "tickets")}
    except Exception:  # a missing ticket folder only costs the neighbour titles
        known = {}
    store = DispatchState(root)
    lines: list[str] = []
    for dep in ticket.depends_on:
        title = known[dep].title if dep in known else "(ticket file not found)"
        state = str((store.ticket(dep) or {}).get("state", "unknown"))
        lines.append("- " + dep + ": " + title + " - state=" + state)
    return lines


def _pitfalls(root: Path) -> list[str]:
    docs = Path(root) / "docs"
    if not docs.is_dir():
        return []
    keywords = ("坑", "pitfall", "lessons", "retro")
    found: list[str] = []
    for candidate in sorted(docs.rglob("*.md")):
        lowered = candidate.name.lower()
        if any(word in lowered for word in keywords):
            found.append(candidate.relative_to(root).as_posix())
    return found[:5]


def build_context_pack(root: Path, ticket: Ticket, exclude_run_id: str | None = None, run_attempt: int | None = None) -> str:
    root = Path(root)
    parts: list[str] = [
        "# Context pack: " + ticket.id + ": " + ticket.title,
        "",
        "Generated from the repository, not from a model. Everything below is a",
        "fact this ticket does not restate.",
        "",
        "## Ticket frame",
        "",
        "- id: " + ticket.id,
        "- status: " + ticket.status,
        "- owner: " + (ticket.owner or "(unset)"),
        "- risk: " + (ticket.risk or "(unset)"),
        "- persona: " + (ticket.persona or "(unset)"),
        "- blocked by: " + (", ".join(ticket.depends_on) or "none"),
        "",
        "## Goal",
        "",
        ticket.what_to_build or "(empty)",
        "",
        "## Write scope",
        "",
    ]
    parts.extend("- " + item for item in ticket.write_scope)
    if not ticket.write_scope:
        parts.append("- (none declared)")
    parts.extend(["", "## Read scope", ""])
    parts.extend("- " + item for item in ticket.read_scope)
    if not ticket.read_scope:
        parts.append("- (none declared)")
    parts.extend(["", "## Definition of done", ""])
    parts.extend("- [ ] " + item for item in ticket.acceptance)
    if not ticket.acceptance:
        parts.append("- (none declared)")
    if ticket.verify:
        parts.extend(["", "Verification commands:", "", FENCE + "bash"])
        parts.extend(ticket.verify)
        parts.append(FENCE)

    parts.extend(["", "## Project entry documents", ""])
    included = False
    for name in ENTRY_DOCS:
        doc = root / name
        if not doc.is_file():
            continue
        head = _read_head(doc)
        if not head:
            continue
        included = True
        parts.extend(["### " + name, "", FENCE + "text", head, FENCE, ""])
    if not included:
        parts.append("- (no AGENTS.md / CLAUDE.md / CONTEXT.md at the repository root)")

    prior = _prior_runs(root, ticket.id, exclude_run_id)
    parts.extend(["", "## Earlier runs of this ticket", ""])
    if prior:
        for item in prior:
            line = "- " + str(item["run_id"]) + ": state=" + str(item["state"])
            if item["verify"]:
                line += "; verify=" + str(item["verify"])
            if item["error"]:
                line += "; error=" + str(item["error"])
            parts.append(line)
    else:
        attempt = 0
        try:
            attempt = int(run_attempt)
        except (TypeError, ValueError):
            attempt = 0
        if attempt and attempt > 1:
            parts.append(f"- none (attempt {attempt} of the same run; see verify-history.jsonl)")
        else:
            parts.append("- none (this is the first run)")

    neighbours = _neighbours(root, ticket)
    parts.extend(["", "## Blocking neighbours", ""])
    parts.extend(neighbours or ["- none"])

    pitfalls = _pitfalls(root)
    parts.extend(["", "## Known-pitfall notes", ""])
    parts.extend(("- " + item for item in pitfalls) if pitfalls else ["- (none found under docs/)"])
    parts.append("")
    return "\n".join(parts)


def write_context_pack(root: Path, ticket: Ticket, exclude_run_id: str | None = None) -> Path:
    target = context_path(root, ticket.id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_context_pack(root, ticket, exclude_run_id), encoding="utf-8")
    return target
