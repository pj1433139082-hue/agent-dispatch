"""Command-line interface for agent-dispatch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .auto import AutoError, auto_run
from .dsh import (
    TaskBoardError,
    archive_card,
    board_status,
    delete_card,
    format_status,
    outcome,
    push,
    run_card,
    update_card,
)
from .export import export_text, status_document
from .align import (
    delivery_diagnosis,
    delivery_items,
    normalize_level,
    questionnaire_is_answered,
    questionnaire_path,
    render_questionnaire,
    render_spec,
    spec_path,
    write_drafts,
)
from .brief import approve_brief, approval_status, check_brief, ensure_brief
from .checkpoints import list_generations, publish as publish_checkpoint
from .closeout import write as write_closeout
from .packet import write as write_review_packet
from .seats import DEFAULT_CAP, check as check_seats
from .select import DEFAULT_ROLES, all_roles, pack_dir, panel, write_pack as write_selection_pack
from .context import build_context_pack, write_context_pack
from .graph import build_plan
from .landing import LandingError, land_run
from .lifecycle import ScopeError, claim as claim_paths, expand_scope, gc as gc_worktrees, release as release_claims, evidence_state, repair as repair_state, sweep as sweep_runs
from .persona import BUILTIN_PERSONA_DIR, Persona, PersonaError, discover_personas, load_persona
from .pipeline import (
    grill_questions,
    confirm_spec,
    selection_signed,
    sign_selection,
    spec_confirmation,
    stage_prompt,
    stage_report,
)
from .review import submit_review
from .state import ACTIVE_STATES, DispatchState, Run
from .ticket import Ticket, lint_tickets, load_tickets, parse_ticket
from .verify import verify_run

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dispatch", description="Ticketed work dispatch.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lint_parser = subparsers.add_parser("lint", help="Validate ticket files.")
    lint_parser.add_argument("--tickets", type=Path, default=None)
    lint_parser.add_argument("--json", action="store_true", dest="as_json")

    plan_parser = subparsers.add_parser("plan", help="Compute dependency waves.")
    plan_parser.add_argument("--tickets", type=Path, default=None)
    plan_parser.add_argument(
        "--done", action="append", default=[], metavar="ID", help="Treat a ticket as done."
    )
    plan_parser.add_argument("--json", action="store_true", dest="as_json")

    render_parser = subparsers.add_parser("render", help="Create a run and a work order.")
    render_parser.add_argument("ticket_id")
    render_parser.add_argument("--tickets", type=Path, default=None)
    render_parser.add_argument("--root", type=Path, default=Path("."))
    render_parser.add_argument("--agent", default="", help="Agent claiming the run.")
    render_parser.add_argument(
        "--no-worktree",
        action="store_true",
        dest="no_worktree",
        help="Run in the main checkout instead of an isolated git worktree.",
    )
    render_parser.add_argument(
        "--deadline-minutes", type=int, default=15, dest="deadline_minutes",
        help="派单时限（分钟，默认 15）；sweep 用它判断 over_deadline。",
    )
    render_parser.add_argument(
        "--seat-cap", type=int, default=0, dest="seat_cap",
        help="With --claim: refuse when this agent already holds that many active tickets.",
    )
    render_parser.add_argument(
        "--claim", action="store_true",
        help="Also take file leases for the write scope (blocks a second run touching the same files).",
    )
    render_parser.add_argument(
        "--with-context",
        action="store_true",
        dest="with_context",
        help="Embed a repository-derived context pack into the run and its work order.",
    )
    render_parser.add_argument(
        "--require-brief",
        action="store_true",
        dest="require_brief",
        help="Refuse to render until a brief for this ticket has been accepted.",
    )

    context_parser = subparsers.add_parser(
        "context", help="Write the ticket's repository-derived context pack."
    )
    context_parser.add_argument("ticket_id")
    context_parser.add_argument("--tickets", type=Path, default=None)
    context_parser.add_argument("--root", type=Path, default=Path("."))
    context_parser.add_argument("--json", action="store_true", dest="as_json")

    brief_parser = subparsers.add_parser(
        "brief", help="Create, check, or accept a read-only brief before implementation."
    )
    brief_parser.add_argument("ticket_id")
    brief_parser.add_argument("--tickets", type=Path, default=None)
    brief_parser.add_argument("--root", type=Path, default=Path("."))
    brief_parser.add_argument("--check", action="store_true", dest="check")
    brief_parser.add_argument("--approve", default="", metavar="NAME")
    brief_parser.add_argument("--json", action="store_true", dest="as_json")

    checkpoint_parser = subparsers.add_parser(
        "checkpoint", help="Publish or list immutable run checkpoints."
    )
    checkpoint_parser.add_argument("ticket_id")
    checkpoint_parser.add_argument("--label", default="manual")
    checkpoint_parser.add_argument("--list", action="store_true", dest="list_only")
    checkpoint_parser.add_argument("--root", type=Path, default=Path("."))
    checkpoint_parser.add_argument("--json", action="store_true", dest="as_json")

    closeout_parser = subparsers.add_parser(
        "closeout", help="Compare ticket, brief and diff; write the closeout report."
    )
    closeout_parser.add_argument("ticket_id")
    closeout_parser.add_argument("--tickets", type=Path, default=None)
    closeout_parser.add_argument("--root", type=Path, default=Path("."))
    closeout_parser.add_argument("--json", action="store_true", dest="as_json")

    align_parser = subparsers.add_parser(
        "align", help="Write the requirement questionnaire for a slug (ask-matt stage S1)."
    )
    align_parser.add_argument("slug")
    align_parser.add_argument("--title", default="")
    align_parser.add_argument("--level", default="standard", help="quick | standard | thorough")
    align_parser.add_argument("--root", type=Path, default=Path("."))
    align_parser.add_argument("--json", action="store_true", dest="as_json")

    spec_parser = subparsers.add_parser(
        "spec", help="Write the spec skeleton once the questionnaire is answered (S3)."
    )
    spec_parser.add_argument("slug")
    spec_parser.add_argument("--title", default="")
    spec_parser.add_argument("--force", action="store_true", help="Write even if answers look unfilled.")
    spec_parser.add_argument("--root", type=Path, default=Path("."))
    spec_parser.add_argument("--json", action="store_true", dest="as_json")

    tickets_parser = subparsers.add_parser(
        "tickets", help="Draft one ticket per delivery-standard item (S4)."
    )
    tickets_parser.add_argument("slug")
    tickets_parser.add_argument("--force", action="store_true", help="Skip the S3 confirmation gate.")
    tickets_parser.add_argument("--root", type=Path, default=Path("."))
    tickets_parser.add_argument("--json", action="store_true", dest="as_json")

    select_parser = subparsers.add_parser(
        "select", help="Build the S2 selection panel (roles, personas, evidence briefs)."
    )
    select_parser.add_argument("slug", nargs="?", default="")
    select_parser.add_argument("--title", default="")
    select_parser.add_argument("--with", dest="with_roles", default="", help="逗号分隔的可选角色，如 domain-owner,cost-keeper")
    select_parser.add_argument(
        "--add", dest="extra_roles", action="append", default=[],
        metavar="ID[:PERSONA]", help="追加自定义角色，可重复",
    )
    select_parser.add_argument("--list", action="store_true", dest="list_only")
    select_parser.add_argument("--root", type=Path, default=Path("."))
    select_parser.add_argument("--json", action="store_true", dest="as_json")

    seat_parser = subparsers.add_parser(
        "seat", help="Check team seats before spawning an executor."
    )
    seat_parser.add_argument("--cap", type=int, default=DEFAULT_CAP)
    seat_parser.add_argument("--occupied", type=int, default=0)
    seat_parser.add_argument("--inactive", default="", help="逗号分隔的可回收成员")
    seat_parser.add_argument("--agent", default="", help="Count this agent's active tickets instead of --occupied.")
    seat_parser.add_argument("--root", type=Path, default=Path("."))
    seat_parser.add_argument("--json", action="store_true", dest="as_json")

    packet_parser = subparsers.add_parser(
        "review-packet", help="Freeze ticket, diff, receipt and verify into a review packet."
    )
    packet_parser.add_argument("ticket_id")
    packet_parser.add_argument("--tickets", type=Path, default=None)
    packet_parser.add_argument("--root", type=Path, default=Path("."))
    packet_parser.add_argument("--json", action="store_true", dest="as_json")

    claim_parser = subparsers.add_parser(
        "claim", help="Lease the ticket's write scope for its current run (conflict -> exit 3)."
    )
    claim_parser.add_argument("ticket_id")
    claim_parser.add_argument("--ttl-minutes", type=int, default=15, dest="ttl_minutes")
    claim_parser.add_argument("--tickets", type=Path, default=None)
    claim_parser.add_argument("--root", type=Path, default=Path("."))
    claim_parser.add_argument("--json", action="store_true", dest="as_json")

    gc_parser = subparsers.add_parser("gc", help="Reclaim worktrees of ended runs (clean = remove, dirty = HOLD).")
    gc_parser.add_argument("--apply", action="store_true")
    gc_parser.add_argument("--root", type=Path, default=Path("."))
    gc_parser.add_argument("--json", action="store_true", dest="as_json")

    questions_parser = subparsers.add_parser("questions", help="Turn the selection pack into grill questions.")
    questions_parser.add_argument("slug")
    questions_parser.add_argument("--root", type=Path, default=Path("."))
    questions_parser.add_argument("--json", action="store_true", dest="as_json")

    roots_parser = subparsers.add_parser("roots", help="Find dispatch roots living in subdirectories of this repo.")
    roots_parser.add_argument("--root", type=Path, default=Path("."))
    roots_parser.add_argument("--json", action="store_true", dest="as_json")

    wrap_parser = subparsers.add_parser("wrap", help="One-shot session wrap-up: status counts + doctor + next actions.")
    wrap_parser.add_argument("--root", type=Path, default=Path("."))
    wrap_parser.add_argument("--tickets", type=Path, default=None)
    wrap_parser.add_argument("--json", action="store_true", dest="as_json")
    hooks_parser = subparsers.add_parser("install-hooks", help="Install a pre-commit hook that runs dispatch wrap.")
    hooks_parser.add_argument("--root", type=Path, default=Path("."))
    hooks_parser.add_argument("--force", action="store_true")

    wrap_parser.add_argument("--fix", action="store_true", help="Also rebuild the index and drop expired leases before reporting.")

    setup_parser = subparsers.add_parser("setup", help="Write .dispatch/config.json (tickets dir, executor mode, default reviewer).")
    setup_parser.add_argument("--root", type=Path, default=Path("."))
    setup_parser.add_argument("--tickets", default=None, help="Ticket directory, relative to the project root (default: tickets).")
    setup_parser.add_argument("--executor-mode", choices=("teammate", "dsh", "command"), default=None)
    setup_parser.add_argument("--default-reviewer", default=None)
    setup_parser.add_argument("--json", action="store_true", dest="as_json")

    handoff_parser = subparsers.add_parser("handoff", help="Print the message to send a teammate so it can execute this run.")
    handoff_parser.add_argument("ticket_id")
    handoff_parser.add_argument("--to", default=None, help="Agent to hand off to (default: the ticket owner).")
    handoff_parser.add_argument("--root", type=Path, default=Path("."))
    handoff_parser.add_argument("--tickets", type=Path, default=None)
    handoff_parser.add_argument("--json", action="store_true", dest="as_json")

    doctor_parser = subparsers.add_parser("doctor", help="Read-only health check: tickets, index, leases, runs.")
    doctor_parser.add_argument("--root", type=Path, default=Path("."))
    doctor_parser.add_argument("--tickets", type=Path, default=None)
    doctor_parser.add_argument("--json", action="store_true", dest="as_json")
    doctor_parser.add_argument(
        "--fix", action="store_true",
        help="Apply safe fixes only: rebuild a stale index and drop expired leases.",
    )

    release_parser = subparsers.add_parser("release", help="Release this ticket's file leases (used when a run is stuck).")
    release_parser.add_argument("ticket_id")
    release_parser.add_argument("--root", type=Path, default=Path("."))
    release_parser.add_argument("--json", action="store_true", dest="as_json")

    retry_parser = subparsers.add_parser("retry", help="Put a failed ticket back to running so it can be verified again.")
    retry_parser.add_argument("ticket_id")
    retry_parser.add_argument("--reason", required=True, help="Why you are retrying; recorded on the run.")
    retry_parser.add_argument("--root", type=Path, default=Path("."))
    retry_parser.add_argument("--json", action="store_true", dest="as_json")

    confirm_parser = subparsers.add_parser("confirm", help="Record the S3 spec confirmation (client checked the delivery standard).")
    confirm_parser.add_argument("slug")
    confirm_parser.add_argument("--by", required=True)
    confirm_parser.add_argument("--via", required=True, choices=("dialog", "card"))
    confirm_parser.add_argument("--note", default="")
    confirm_parser.add_argument("--root", type=Path, default=Path("."))

    sign_parser = subparsers.add_parser("sign", help="Record the client signature on the S2 selection summary.")
    sign_parser.add_argument("slug")
    sign_parser.add_argument("--by", required=True, help="Who signs it.")
    sign_parser.add_argument("--note", default="", help="Optional note recorded on the signature line.")
    sign_parser.add_argument(
        "--via", required=True, choices=("dialog", "card"),
        help="How the client confirmed: dialog (interactive question) or card (text decision card).",
    )
    sign_parser.add_argument("--hold", action="store_true", help="Approve with reservations.")
    sign_parser.add_argument("--reject", action="store_true", help="Reject the selection.")
    sign_parser.add_argument("--root", type=Path, default=Path("."))

    stage_parser = subparsers.add_parser("stage", help="Show S1..S5 pipeline status for a slug.")
    stage_parser.add_argument("slug")
    stage_parser.add_argument("--root", type=Path, default=Path("."))
    stage_parser.add_argument("--json", action="store_true", dest="as_json")
    stage_parser.add_argument(
        "--prompt", action="store_true",
        help="Output the questions this stage needs a human to answer (for a dialog or decision card).",
    )

    sweep_parser = subparsers.add_parser("sweep", help="Read-only liveness report for active runs.")
    sweep_parser.add_argument("--root", type=Path, default=Path("."))
    sweep_parser.add_argument("--json", action="store_true", dest="as_json")

    repair_parser = subparsers.add_parser("repair", help="Rebuild the state index from run directories.")
    repair_parser.add_argument("--root", type=Path, default=Path("."))
    repair_parser.add_argument("--write", action="store_true", help="Write the rebuilt index back.")
    repair_parser.add_argument("--json", action="store_true", dest="as_json")

    start_parser = subparsers.add_parser("start", help="Mark a claimed run as running.")
    start_parser.add_argument("ticket_id")
    start_parser.add_argument("--root", type=Path, default=Path("."))

    verify_parser = subparsers.add_parser("verify", help="Run the independent verification gate.")
    verify_parser.add_argument("ticket_id")
    verify_parser.add_argument("--root", type=Path, default=Path("."))
    verify_parser.add_argument("--timeout", type=int, default=300)
    verify_parser.add_argument(
        "--allow-main-drift",
        action="store_true",
        dest="allow_main_drift",
        help="Allow uncommitted changes in the main checkout (reported, not fatal).",
    )

    review_parser = subparsers.add_parser("review", help="Record a reviewer decision.")
    review_parser.add_argument("ticket_id")
    review_parser.add_argument("--reviewer", default=None)
    review_parser.add_argument("--verdict", required=True, choices=("pass", "fail"))
    review_parser.add_argument("--notes", default="")
    review_parser.add_argument("--human", action="store_true")
    review_parser.add_argument(
        "--self-reviewed", action="store_true", dest="self_reviewed",
        help="L0/L1 only: record an explicit self-review trace (ADR-0008 D5).",
    )
    review_parser.add_argument(
        "--packet-hash", default=None, dest="packet_hash",
        help="sha256 of review-packet.md; required for L2+ so the reviewer proves they read the packet.",
    )
    review_parser.add_argument(
        "--accept-degraded",
        action="store_true",
        help="Accept a degraded verification result (attested evidence only).",
    )
    review_parser.add_argument("--root", type=Path, default=Path("."))

    land_parser = subparsers.add_parser(
        "land",
        help="Create an integration branch for a reviewed run; never pushes or merges the target.",
    )
    land_parser.add_argument("ticket_id", nargs="?", default=None)
    land_parser.add_argument(
        "--wave", action="store_true",
        help="Land every done, unlanded ticket in dependency order; stops at the first failure.",
    )
    land_parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="With --wave: preview which tickets would land / fail, without creating branches.",
    )
    land_parser.add_argument(
        "--continue-on-error", action="store_true", dest="continue_on_error",
        help="With --wave: keep landing independent tickets after a failure.",
    )
    land_parser.add_argument(
        "--into",
        default=None,
        help="Target branch (default: main when present, otherwise the current branch).",
    )
    land_parser.add_argument(
        "--branch",
        default=None,
        help="Integration branch name (default: dispatch/land/<run-id>).",
    )
    land_parser.add_argument("--root", type=Path, default=Path("."))
    land_parser.add_argument(
        "--require-closeout",
        action="store_true",
        dest="require_closeout",
        help="Refuse to land unless closeout.json reports pass.",
    )
    land_parser.add_argument(
        "--require-attestation",
        action="store_true",
        dest="require_attestation",
        help="Refuse to land unless the review attested the review packet (packet_attested).",
    )
    land_parser.add_argument(
        "--no-require-packet",
        action="store_false",
        dest="require_packet",
        default=True,
        help="Skip the L2+ requirement that review-packet.md exists with a matching hash.",
    )
    land_parser.add_argument("--json", action="store_true", dest="as_json")

    auto_parser = subparsers.add_parser(
        "auto",
        help="Run one ticket through an executor, verify, and optional review/land.",
    )
    auto_parser.add_argument("ticket_id")
    auto_parser.add_argument(
        "--executor", required=True, help="Shell command run inside the run worktree."
    )
    auto_parser.add_argument("--agent", default="", help="Agent claiming the run.")
    auto_parser.add_argument(
        "--resume", action="store_true",
        help="Continue the active run of this ticket instead of refusing (after dispatch retry).",
    )
    auto_parser.add_argument(
        "--max-attempts", type=int, default=1,
        help="Total executor attempts before failing (default: 1).",
    )
    auto_parser.add_argument(
        "--timeout", type=int, default=1800,
        help="Seconds allowed per executor or reviewer command.",
    )
    auto_parser.add_argument(
        "--verify-timeout", type=int, default=300,
        help="Seconds allowed per Verify command.",
    )
    auto_parser.add_argument(
        "--until", choices=("review", "land"), default="review",
        help="Stop at the review gate (default) or continue through review and landing.",
    )
    auto_parser.add_argument(
        "--reviewer", default="",
        help="Independent reviewer name; required with --until land.",
    )
    auto_parser.add_argument(
        "--reviewer-command", default="",
        help="Shell command that writes review-result.json; required with --until land.",
    )
    auto_parser.add_argument(
        "--accept-degraded", action="store_true",
        help="Allow a degraded verification to continue to review.",
    )
    auto_parser.add_argument(
        "--human", action="store_true", help="Mark the reviewer as human."
    )
    auto_parser.add_argument("--tickets", type=Path, default=None)
    auto_parser.add_argument(
        "--protocol", choices=("none", "full"), default="none",
        help="full = inject context + env hint, gate on brief, publish checkpoints, run closeout.",
    )
    auto_parser.add_argument("--env-hint", default="", help="Build prerequisites for the executor.")
    auto_parser.add_argument(
        "--require-brief", action="store_true", dest="require_brief",
        help="With --protocol full: refuse to start unless a brief was accepted.",
    )
    auto_parser.add_argument("--root", type=Path, default=Path("."))
    auto_parser.add_argument("--json", action="store_true", dest="as_json")
    auto_parser.add_argument(
        "--force", action="store_true",
        help="Skip the preflight health check (index vs disk).",
    )

    status_parser = subparsers.add_parser("status", help="Show effective ticket states.")
    status_parser.add_argument("--tickets", type=Path, default=None)
    status_parser.add_argument("--root", type=Path, default=Path("."))
    status_parser.add_argument("--all", action="store_true", dest="all_roots", help="Aggregate every dispatch root found under --root.")
    status_parser.add_argument("--json", action="store_true", dest="as_json")

    export_parser = subparsers.add_parser("export", help="Export ready work to another runner.")
    export_parser.add_argument(
        "--format",
        required=True,
        choices=("agent-team", "dsh-team", "dsh-board", "codex", "generic"),
        dest="export_format",
    )
    export_parser.add_argument("--tickets", type=Path, default=None)
    export_parser.add_argument("--root", type=Path, default=Path("."))
    export_parser.add_argument("--output", type=Path)

    dsh_parser = subparsers.add_parser(
        "dsh", help="Push ready work to the DSH task board and read outcomes back."
    )
    dsh_sub = dsh_parser.add_subparsers(dest="dsh_command", required=True)

    dsh_push = dsh_sub.add_parser("push", help="Create board cards for ready tickets; never runs them.")
    dsh_push.add_argument("--tickets", type=Path, default=None)
    dsh_push.add_argument("--root", type=Path, default=Path("."))
    dsh_push.add_argument("--url", default=None, help="DSH base URL (default: DSH_TASK_BOARD_URL or http://127.0.0.1:50567).")
    dsh_push.add_argument("--project", default=None, help="Project namespace for deterministic card ids.")
    dsh_push.add_argument("--workspace", default=None, help="DSH workspace id the card will run in (required).")
    dsh_push.add_argument(
        "--allow-default-workspace", action="store_true", dest="allow_default_workspace",
        help="Explicitly let the board pick its default workspace (work will run there, not in this repo).",
    )
    dsh_push.add_argument("--mode", choices=("cards", "team"), default="cards", dest="push_mode")
    dsh_push.add_argument("--dry-run", action="store_true", help="Print the action envelopes without calling DSH.")
    dsh_push.add_argument("--json", action="store_true", dest="as_json")

    dsh_status = dsh_sub.add_parser("status", help="Compare local ticket mappings with the DSH board.")
    dsh_status.add_argument("--root", type=Path, default=Path("."))
    dsh_status.add_argument("--url", default=None)
    dsh_status.add_argument("--json", action="store_true", dest="as_json")

    dsh_outcome = dsh_sub.add_parser(
        "outcome", help="Record an external agent outcome on a mapped DSH card."
    )
    dsh_outcome.add_argument("ticket_id")
    dsh_outcome.add_argument("--root", type=Path, default=Path("."))
    dsh_outcome.add_argument("--url", default=None)
    dsh_outcome.add_argument("--task-id", default=None, help="Override the mapped DSH task id.")
    dsh_outcome.add_argument("--result", required=True, choices=("succeeded", "failed"))
    dsh_outcome.add_argument("--by", required=True, dest="initiated_by", help="Who performed the work.")
    dsh_outcome.add_argument("--summary", default="")
    dsh_outcome.add_argument("--json", action="store_true", dest="as_json")
    dsh_outcome.add_argument(
        "--mark-done", action="store_true", dest="mark_done",
        help="Also mark the ticket done in dispatch and record .dispatch/external/<id>.json",
    )
    dsh_outcome.add_argument(
        "--evidence", default=None,
        help="Path (relative to the project root) that proves the board actually produced the artifact.",
    )

    dsh_update = dsh_sub.add_parser("update", help="Patch fields on a mapped DSH card.")
    dsh_update.add_argument("ticket_id")
    dsh_update.add_argument("--root", type=Path, default=Path("."))
    dsh_update.add_argument("--url", default=None)
    dsh_update.add_argument("--task-id", default=None, help="Override the mapped DSH task id.")
    dsh_update.add_argument("--title", default=None)
    dsh_update.add_argument("--description", default=None)
    dsh_update.add_argument("--prompt", default=None)
    dsh_update.add_argument("--patch", default=None, dest="patch_json", help="JSON object merged into the patch.")
    dsh_update.add_argument("--json", action="store_true", dest="as_json")

    dsh_archive = dsh_sub.add_parser("archive", help="Archive a mapped DSH card.")
    dsh_archive.add_argument("ticket_id")
    dsh_archive.add_argument("--root", type=Path, default=Path("."))
    dsh_archive.add_argument("--url", default=None)
    dsh_archive.add_argument("--task-id", default=None, help="Override the mapped DSH task id.")
    dsh_archive.add_argument("--json", action="store_true", dest="as_json")

    dsh_run = dsh_sub.add_parser("run", help="Ask DSH to run a mapped card; returns once accepted.")
    dsh_run.add_argument("ticket_id")
    dsh_run.add_argument("--root", type=Path, default=Path("."))
    dsh_run.add_argument("--url", default=None)
    dsh_run.add_argument("--task-id", default=None, help="Override the mapped DSH task id.")
    dsh_run.add_argument("--rerun", action="store_true", help="Send a rerun action instead of run.")
    dsh_run.add_argument("--json", action="store_true", dest="as_json")

    dsh_delete = dsh_sub.add_parser("delete", help="Delete a mapped DSH card.")
    dsh_delete.add_argument("ticket_id")
    dsh_delete.add_argument("--root", type=Path, default=Path("."))
    dsh_delete.add_argument("--url", default=None)
    dsh_delete.add_argument("--task-id", default=None, help="Override the mapped DSH task id.")
    dsh_delete.add_argument("--json", action="store_true", dest="as_json")

    assign_parser = subparsers.add_parser(
        "assign", help="Assign a persona to a ticket before dispatch."
    )
    assign_parser.add_argument("ticket_id")
    assign_parser.add_argument("--persona", required=True, help="Persona file or short name.")
    assign_parser.add_argument("--tickets", type=Path, default=None)
    assign_parser.add_argument("--root", type=Path, default=Path("."))
    assign_parser.add_argument("--by", default="dispatcher", help="Who assigned the persona.")
    assign_parser.add_argument("--json", action="store_true", dest="as_json")

    personas_parser = subparsers.add_parser(
        "personas", help="Discover and inspect agent persona sources."
    )
    personas_sub = personas_parser.add_subparsers(dest="personas_command", required=True)
    personas_list = personas_sub.add_parser("list", help="List discoverable personas.")
    personas_list.add_argument("--search-root", action="append", default=[])
    personas_list.add_argument("--tickets", type=Path, default=None)
    personas_list.add_argument("--root", type=Path, default=Path("."))
    personas_list.add_argument("--json", action="store_true", dest="as_json")
    personas_show = personas_sub.add_parser("show", help="Show one persona source.")
    personas_show.add_argument("spec")
    personas_show.add_argument("--search-root", action="append", default=[])
    personas_show.add_argument("--json", action="store_true", dest="as_json")

    new_parser = subparsers.add_parser("new", help="Create a new ticket file.")
    new_parser.add_argument("ticket_id")
    new_parser.add_argument("--title", required=True)
    new_parser.add_argument("--what", default="Describe the work.")
    new_parser.add_argument("--owner", default="implementer")
    new_parser.add_argument("--risk", default="L1", choices=("L0", "L1", "L2", "L3", "L4"))
    new_parser.add_argument("--write-scope", action="append", default=[])
    new_parser.add_argument("--verify", action="append", default=[])
    new_parser.add_argument("--depends-on", action="append", default=[])
    new_parser.add_argument("--persona", default="", help="Assign this persona right after creating the ticket.")
    new_parser.add_argument("--by", default="lead", help="Who assigns the persona.")
    new_parser.add_argument("--tickets", type=Path, default=None)
    return parser

CONFIG_NAME = "config.json"


def config_path(root: Path) -> Path:
    return Path(root) / ".dispatch" / CONFIG_NAME


def load_config(root: Path) -> dict[str, object]:
    path = config_path(root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _tickets_dir(args: argparse.Namespace) -> Path:
    if getattr(args, "tickets", None) is not None:
        return args.tickets
    root = Path(getattr(args, "root", Path(".")))
    configured = str(load_config(root).get("tickets_dir", "") or "")
    if configured:
        return root / configured
    return root / "tickets"

def _load_and_lint(directory: Path, root: Path | None = None):
    # 票目录的上一级就是项目根：用于把"绝对路径"翻译成相对写法
    project_root = Path(root) if root is not None else Path(directory).parent
    tickets = load_tickets(directory)
    issues = lint_tickets(tickets, project_root)
    warnings = [issue for issue in issues if issue.level == "warning"]
    errors = [issue for issue in issues if issue.level != "warning"]
    for issue in warnings:
        print(issue.format(), file=sys.stderr)
    if errors:
        for issue in errors:
            print(issue.format(), file=sys.stderr)
        return None, 1
    return tickets, 0

def _state_hint(ticket_id: str, current: object) -> str:
    if str(current) == "failed":
        return f" (the ticket is failed: run 'dispatch retry {ticket_id}' first)"
    return ""


def _cmd_lint(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    if args.as_json:
        print(json.dumps({"tickets": [ticket.id for ticket in tickets]}, indent=2))
    else:
        warnings = [issue for issue in lint_tickets(tickets, getattr(args, "root", None))]
        warnings = [issue for issue in warnings if issue.level == "warning"]
        suffix = f" ({len(warnings)} warning(s))" if warnings else ""
        print(f"{len(tickets)} ticket(s) valid{suffix}")
    return 0

def _state_map(root: Path) -> dict[str, str]:
    data = DispatchState(root).load()
    return {
        ticket_id: str(value.get("state", ""))
        for ticket_id, value in data.get("tickets", {}).items()
    }

def _cmd_status_all(args: argparse.Namespace) -> int:
    """把本仓所有 dispatch 根的状态汇总打出来（含当前根）。"""
    base = Path(args.root)
    roots: list[dict[str, object]] = []
    own_tickets = _tickets_dir(args)
    if own_tickets.is_dir() and any(own_tickets.glob("*.md")):
        roots.append({"root": str(base), "tickets": len(list(own_tickets.glob("*.md")))})
    roots.extend(_find_dispatch_roots(base))
    if not roots:
        print("no dispatch roots found")
        return 0
    for item in roots:
        root = Path(str(item["root"]))
        tickets_dir = root / "tickets"
        if not tickets_dir.is_dir():
            continue
        tickets = load_tickets(tickets_dir)
        document = status_document(tickets, _state_map(root))
        print(f"== {root} ({len(tickets)} ticket(s)) ==")
        for row in document["tickets"]:
            suffix = f" (blocked by {', '.join(row['blocked_by'])})" if row["blocked_by"] else ""
            print(f"  {row['id']}  {row['state']:<10} {row['title']}{suffix}")
        print(f"  Frontier: {', '.join(document['frontier']) or '-'}")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    if getattr(args, "all_roots", False):
        return _cmd_status_all(args)
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    document = status_document(tickets, _state_map(args.root))
    if args.as_json:
        print(json.dumps(document, indent=2, ensure_ascii=False))
        return 0
    store = DispatchState(args.root)
    runs_root = Path(args.root) / ".dispatch" / "runs"
    for row in document["tickets"]:
        suffix = f" (blocked by {', '.join(row['blocked_by'])})" if row["blocked_by"] else ""
        hint = f"   -> {row['hint']}" if str(row.get("hint", "")) else ""
        if str(row["state"]) in {"claimed", "running", "review"}:
            entry = store.ticket(str(row["id"])) or {}
            run_id = str(entry.get("run_id", ""))
            run_file = runs_root / run_id / "run.json"
            if run_file.is_file():
                try:
                    recorded = str(json.loads(run_file.read_text(encoding="utf-8")).get("ticket_hash", ""))
                except (OSError, json.JSONDecodeError):
                    recorded = ""
                current = next((t for t in (tickets or []) if t.id == row["id"]), None)
                if recorded and current is not None and current.content_hash != recorded:
                    hint = f"   -> 票在 render 后被改过（revert 或 retry {row['id']}）"
        if str(row["state"]) == "done":
            entry = store.ticket(str(row["id"])) or {}
            run_id = str(entry.get("run_id", ""))
            if run_id and not (runs_root / run_id / "landing.json").is_file():
                hint = f"   -> 未落地（dispatch land {row['id']}）"
        print(f"{row['id']}  {row['state']:<10} {row['title']}{suffix}{hint}")
    print(f"Frontier: {', '.join(document['frontier']) or '-'}")
    counts = {"failed": 0, "running": 0, "claimed": 0}
    for row in document["tickets"]:
        state = str(row["state"])
        if state in counts:
            counts[state] += 1
    if counts["failed"] or counts["running"] or counts["claimed"]:
        bits = []
        if counts["failed"]:
            bits.append(f"{counts['failed']} failed (dispatch retry <id>)")
        active = counts["running"] + counts["claimed"]
        if active:
            bits.append(f"{active} active run(s) (dispatch sweep / start)")
        print("Session wrap-up: " + "; ".join(bits) + "  |  then dispatch doctor")
    return 0

def _cmd_export(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    text = export_text(
        tickets, args.export_format, _state_map(args.root), project=args.root.resolve().name
    )
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(text, end="")
    return 0

def _cmd_new(args: argparse.Namespace) -> int:
    directory = _tickets_dir(args)
    directory.mkdir(parents=True, exist_ok=True)
    existing = load_tickets(directory)
    if any(ticket.id == args.ticket_id for ticket in existing):
        print(f"ticket {args.ticket_id} already exists", file=sys.stderr)
        return 1
    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-") or "ticket"
    path = directory / f"{args.ticket_id}-{slug}.md"
    if path.exists():
        print(f"file already exists: {path}", file=sys.stderr)
        return 1
    scopes = args.write_scope or ["src/"]
    verify = args.verify or ["python -m pytest -q"]
    depends = args.depends_on or []
    blocked = ", ".join(depends) if depends else "None"
    lines = [
        f"# {args.ticket_id}: {args.title}",
        "",
        f"**What to build:** {args.what}",
        f"**Blocked by:** {blocked}",
        "**Status:** ready-for-agent",
        "",
        "## Dispatch",
        "",
        f"- Owner: {args.owner}",
        f"- Risk: {args.risk}",
        "- Persona: (unassigned)",
        *[f"- Write scope: {scope}" for scope in scopes],
        *[f"- Verify: {command}" for command in verify],
        "",
        "## Acceptance",
        "",
        f"- [ ] {args.what}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Created {path}")
    if getattr(args, "persona", ""):
        assign_args = argparse.Namespace(
            root=getattr(args, "root", Path(".")),
            tickets=getattr(args, "tickets", None),
            ticket_id=args.ticket_id,
            persona=args.persona,
            by=getattr(args, "by", "lead"),
            as_json=False,
        )
        return _cmd_assign(assign_args)
    return 0

def _persona_roots(args: argparse.Namespace) -> list[Path]:
    roots = [Path(value) for value in getattr(args, "search_root", [])]
    directory = _tickets_dir(args)
    roots.append(directory / "personas")
    for raw_root in os.environ.get("AGENT_DISPATCH_PERSONA_ROOTS", "").split(os.pathsep):
        if raw_root.strip():
            roots.append(Path(raw_root.strip()))
    roots.append(BUILTIN_PERSONA_DIR)
    return roots

def _persona_dict(persona: Persona) -> dict[str, object]:
    return {
        "name": persona.name,
        "role": persona.role,
        "domain": persona.domain,
        "description": persona.description,
        "path": str(persona.path),
        "capabilities": list(persona.capabilities),
        "must_call_when": list(persona.must_call_when),
    }

def _set_persona_line(text: str, relative: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    dispatch = next(
        (index for index, line in enumerate(lines) if line.strip().lower() == "## dispatch"),
        None,
    )
    if dispatch is None:
        lines.extend(["", "## Dispatch", "", f"- Persona: {relative}"])
        return newline.join(lines) + newline
    end = next(
        (index for index in range(dispatch + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    for index in range(dispatch + 1, end):
        if re.match(r"^\s*[-*]\s+persona\s*:", lines[index], re.IGNORECASE):
            lines[index] = f"- Persona: {relative}"
            return newline.join(lines) + (newline if text.endswith("\n") else "")
    insert_at = dispatch + 1
    while insert_at < end and not lines[insert_at].strip():
        insert_at += 1
    owner_at = next(
        (
            index
            for index in range(dispatch + 1, end)
            if re.match(r"^\s*[-*]\s+owner\s*:", lines[index], re.IGNORECASE)
        ),
        None,
    )
    if owner_at is not None:
        insert_at = owner_at + 1
    lines.insert(insert_at, f"- Persona: {relative}")
    return newline.join(lines) + (newline if text.endswith("\n") else "")

def _cmd_assign(args: argparse.Namespace) -> int:
    directory = _tickets_dir(args)
    tickets = load_tickets(directory)
    ticket = _find_ticket(tickets, args.ticket_id)
    if ticket is None:
        print(f"unknown ticket: {args.ticket_id}", file=sys.stderr)
        return 1
    existing = DispatchState(args.root).ticket(ticket.id)
    if existing:
        state = str(existing.get("state", ""))
        if state == "done" or state in ACTIVE_STATES:
            print(
                f"ticket {ticket.id} already has a run ({state}); assign before dispatch",
                file=sys.stderr,
            )
            return 1
    try:
        persona = load_persona(args.persona)
    except PersonaError as exc:
        print(f"PERSONA: {exc}", file=sys.stderr)
        return 1

    personas_dir = directory / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    source = persona.path.resolve()
    destination = personas_dir / source.name
    if destination.exists() and destination.resolve() != source:
        if destination.read_bytes() != source.read_bytes():
            digest = hashlib.sha256(source.read_bytes()).hexdigest()[:8]
            destination = personas_dir / f"{source.stem}-{digest}{source.suffix or '.md'}"
    if destination.resolve() != source:
        shutil.copy2(source, destination)
    relative = destination.relative_to(directory).as_posix()

    before = hashlib.sha256(ticket.path.read_bytes()).hexdigest()
    updated = _set_persona_line(ticket.path.read_text(encoding="utf-8"), relative)
    ticket.path.write_text(updated, encoding="utf-8")
    after = hashlib.sha256(ticket.path.read_bytes()).hexdigest()
    record = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "ticket_id": ticket.id,
        "persona": relative,
        "persona_name": persona.name,
        "role": persona.role,
        "source": str(source),
        "by": args.by,
        "ticket_hash_before": before,
        "ticket_hash_after": after,
    }
    log = Path(args.root) / ".dispatch" / "assignments.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    if args.as_json:
        print(json.dumps({"ok": True, **record}, ensure_ascii=False, indent=2))
    else:
        print(f"Assigned {ticket.id} -> {relative} ({persona.name})")
        print(f"By: {args.by}")
    return 0

def _cmd_personas_list(args: argparse.Namespace) -> int:
    personas = discover_personas(_persona_roots(args))
    if args.as_json:
        print(json.dumps([_persona_dict(persona) for persona in personas], ensure_ascii=False, indent=2))
        return 0
    for persona in personas:
        detail = " / ".join(part for part in (persona.role, persona.domain) if part)
        print(f"{persona.name}\t{detail}\t{persona.path}")
    return 0

def _cmd_personas_show(args: argparse.Namespace) -> int:
    try:
        persona = load_persona(args.spec)
    except PersonaError:
        persona = None
        for root in _persona_roots(args):
            candidate = Path(root) / args.spec
            if candidate.is_file():
                try:
                    persona = load_persona(str(candidate))
                    break
                except PersonaError:
                    continue
        if persona is None:
            print(f"PERSONA: persona source not found: {args.spec}", file=sys.stderr)
            return 1
    if args.as_json:
        print(json.dumps(_persona_dict(persona), ensure_ascii=False, indent=2))
        return 0
    print(f"Name: {persona.name}")
    print(f"Source: {persona.path}")
    if persona.role:
        print(f"Role: {persona.role}")
    if persona.domain:
        print(f"Domain: {persona.domain}")
    if persona.description:
        print(f"Description: {persona.description}")
    if persona.capabilities:
        print("Capabilities:")
        for item in persona.capabilities:
            print(f"- {item}")
    if persona.must_call_when:
        print("Must call when:")
        for item in persona.must_call_when:
            print(f"- {item}")
    if persona.prompt:
        print()
        print(persona.prompt)
    return 0

def _cmd_plan(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    plan = build_plan(tickets, done=set(args.done))
    if args.as_json:
        print(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))
    else:
        for index, wave in enumerate(plan.waves, start=1):
            print(f"Wave {index}: {', '.join(wave)}")
        print(f"Frontier: {', '.join(plan.frontier) or '-'}")
        for ticket_id, deps in sorted(plan.blocked.items()):
            print(f"Blocked {ticket_id}: {', '.join(deps)}")
        for conflict in plan.conflicts:
            print(
                f"Conflict {conflict.first} / {conflict.second}: "
                + ", ".join(conflict.scopes)
            )
        for error in plan.errors:
            print(f"Error: {error}", file=sys.stderr)
    return 1 if plan.errors else 0

def _find_ticket(tickets: list[Ticket], ticket_id: str) -> Ticket | None:
    return next((ticket for ticket in tickets if ticket.id == ticket_id), None)

def _cmd_render(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    ticket = _find_ticket(tickets, args.ticket_id)
    if ticket is None:
        print(f"unknown ticket: {args.ticket_id}", file=sys.stderr)
        return 1

    policy = str(load_config(Path(args.root)).get("persona_policy", "l2")).lower()
    if policy in {"off", "none", "optional"}:
        pass
    else:
        threshold = {"l2": {"L2", "L3", "L4"}, "l3": {"L3", "L4"}, "l4": {"L4"}}.get(policy, {"L2", "L3", "L4"})
        if ticket.risk in threshold and not ticket.persona:
            print(
                f"ticket {ticket.id}: risk {ticket.risk} needs a persona; run dispatch assign {ticket.id} --persona <name> (or set persona_policy=off in .dispatch/config.json)",
                file=sys.stderr,
            )
            return 6

    require_brief = getattr(args, "require_brief", False) or bool(load_config(Path(args.root)).get("require_brief", False))
    if require_brief:
        ok, why = approval_status(args.root, ticket)
        if not ok:
            print(f"ticket {ticket.id}: brief gate ON, {why}", file=sys.stderr)
            return 1
        print(f"Brief gate: {why}")


    store = DispatchState(args.root)
    existing = store.ticket(ticket.id)
    if existing:
        state = str(existing.get("state", ""))
        if state == "done":
            print(f"ticket {ticket.id} is already done", file=sys.stderr)
            return 1
        if state in ACTIVE_STATES:
            run = Run.load(args.root, str(existing["run_id"]))
            if run.data.get("state") != "failed":
                print(
                    f"ticket {ticket.id} already has an active run: {run.id}",
                    file=sys.stderr,
                )
                return 1

    missing = sorted(dep for dep in ticket.depends_on if dep not in store.done_ids())
    if missing:
        print(
            f"ticket {ticket.id} is blocked by unfinished tickets: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    if getattr(args, "seat_cap", 0):
        agent_name = args.agent or "lead"
        load = _agent_load(args.root, agent_name)
        if load >= args.seat_cap:
            print(
                f"SEAT full: {agent_name} already holds {load}/{args.seat_cap} active ticket(s); "
                "finish or release one first",
                file=sys.stderr,
            )
            return 5
    try:
        run = Run.create(
            args.root,
            ticket,
            claimed_by=args.agent,
            use_worktree=not args.no_worktree,
            deadline_seconds=max(1, args.deadline_minutes) * 60,
        )
    except ValueError as error:
        print(f"RENDER {error}", file=sys.stderr)
        return 7
    store.set_ticket(ticket.id, run.id, "claimed")
    if getattr(args, "with_context", False):
        pack_text = build_context_pack(args.root, ticket, exclude_run_id=run.id)
        context_file = run.directory / "context.md"
        context_file.write_text(pack_text, encoding="utf-8")
        work_order = run.directory / "work-order.md"
        if work_order.is_file():
            work_order.write_text(
                work_order.read_text(encoding="utf-8") + "\n## Context pack\n\n" + pack_text,
                encoding="utf-8",
            )
        print(f"Context pack: {context_file}")
    if getattr(args, "claim", False):
        try:
            paths = expand_scope(args.root, list(ticket.write_scope))
        except ScopeError as error:
            print("SCOPE-UNRESOLVED " + str(error), file=sys.stderr)
            return 4
        lease_report = claim_paths(args.root, ticket.id, run.id, paths)
        for item in lease_report["conflicts"]:
            print(
                "LEASE conflict " + item["path"] + " held by " + item["ticket_id"],
                file=sys.stderr,
            )
        if lease_report["conflicts"]:
            print(f"Rendered {ticket.id} -> {run.directory} (leases blocked; run dispatch release)", file=sys.stderr)
            return 3
        print("Claimed " + str(len(lease_report["granted"])) + " file lease(s)")
    print(f"Rendered {ticket.id} -> {run.directory}")
    print(f"Run ID: {run.id}")
    if run.data.get("use_worktree"):
        print(f"Execution root: {run.execution_root}")
        print(f"Worktree branch: {run.data.get('worktree_branch', '')}")
    return 0

def _cmd_context(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    ticket = _find_ticket(tickets, args.ticket_id)
    if ticket is None:
        print(f"unknown ticket: {args.ticket_id}", file=sys.stderr)
        return 1
    target = write_context_pack(args.root, ticket)
    text = target.read_text(encoding="utf-8")
    if args.as_json:
        print(json.dumps({"ticket": ticket.id, "path": str(target), "chars": len(text)}, ensure_ascii=False))
    else:
        print(f"Context pack: {target}")
        print(f"Chars: {len(text)}")
    return 0

def _cmd_brief(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    ticket = _find_ticket(tickets, args.ticket_id)
    if ticket is None:
        print(f"unknown ticket: {args.ticket_id}", file=sys.stderr)
        return 1
    if args.approve:
        try:
            target = approve_brief(args.root, ticket, args.approve)
        except ValueError as error:
            print(f"brief 未通过：{error}", file=sys.stderr)
            return 1
        print(f"Approved: {target}")
        return 0
    if args.check:
        ok, problems = check_brief(args.root, ticket.id)
        if args.as_json:
            print(json.dumps({"ticket": ticket.id, "ok": ok, "problems": problems}, ensure_ascii=False))
        elif ok:
            print(f"Brief OK: {ticket.id}")
        else:
            for problem in problems:
                print(f"FAIL: {problem}", file=sys.stderr)
        return 0 if ok else 1
    target = ensure_brief(args.root, ticket)
    print(f"Brief: {target}")
    return 0

def _cmd_select(args: argparse.Namespace) -> int:
    if args.list_only:
        rows = [
            {"id": role.id, "name": role.name, "required": role.required, "persona": role.persona, "deliverable": role.deliverable}
            for role in all_roles().values()
        ]
        if args.as_json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return 0
        for row in rows:
            mark = "必须" if row["required"] else "可选"
            print(f"{row['id']:<14} {mark}  {row['name']}  -> {row['deliverable']}")
        return 0
    slug = (args.slug or "").strip()
    if not slug:
        print("slug is required (or use --list)", file=sys.stderr)
        return 1
    optional = [part.strip() for part in args.with_roles.split(",") if part.strip()]
    extra: list[tuple[str, str]] = []
    for raw in args.extra_roles:
        role_id, _, persona = raw.partition(":")
        extra.append((role_id, persona))
    try:
        roles = panel(optional, extra)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    title = args.title.strip() or slug
    written = write_selection_pack(args.root, slug, title, roles)
    if args.as_json:
        print(json.dumps({"slug": slug, "roles": [role.id for role in roles], "files": [str(path) for path in written]}, ensure_ascii=False))
        return 0
    print(f"Selection pack: {pack_dir(args.root, slug)}")
    for path in written:
        print(f"  - {path.name}")
    print("Next: hand each brief to its agent; collect evidence; fill 99-summary.md; wait for the client signature.")
    return 0


def _cmd_align(args: argparse.Namespace) -> int:
    slug = args.slug.strip()
    if not slug:
        print("slug is required", file=sys.stderr)
        return 1
    level = normalize_level(args.level)
    title = args.title.strip() or slug
    target = questionnaire_path(args.root, slug)
    if target.exists():
        print(f"questionnaire already exists: {target}", file=sys.stderr)
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_questionnaire(slug, title, level), encoding="utf-8")
    if args.as_json:
        print(json.dumps({"slug": slug, "level": level, "path": str(target)}, ensure_ascii=False))
    else:
        print(f"Questionnaire: {target} (level={level})")
    return 0


def _cmd_spec(args: argparse.Namespace) -> int:
    slug = args.slug.strip()
    answers = questionnaire_path(args.root, slug)
    ok, problems = questionnaire_is_answered(answers)
    if not ok and not args.force:
        print(f"align first: {slug}", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    signed, signed_note = selection_signed(args.root, slug)
    if not signed and not args.force:
        print("selection is not signed: " + signed_note, file=sys.stderr)
        print("run dispatch select " + slug + " first, get the client signature, or pass --force", file=sys.stderr)
        return 1
    target = spec_path(args.root, slug)
    if target.exists():
        print(f"spec already exists: {target}", file=sys.stderr)
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    title = args.title.strip() or slug
    target.write_text(render_spec(slug, title, answers), encoding="utf-8")
    if args.as_json:
        print(json.dumps({"slug": slug, "path": str(target), "answered": ok}, ensure_ascii=False))
    else:
        print(f"Spec: {target}")
    return 0


def _cmd_tickets(args: argparse.Namespace) -> int:
    slug = args.slug.strip()
    spec = spec_path(args.root, slug)
    if not spec.is_file():
        print(f"no spec for {slug} (run dispatch spec {slug} first)", file=sys.stderr)
        return 1
    if spec_confirmation(args.root, slug) is None and not getattr(args, "force", False):
        print(
            "confirm the spec first: dispatch confirm " + slug + " --by <人> --via dialog|card "
            "(or pass --force)",
            file=sys.stderr,
        )
        return 1
    items, reason = delivery_diagnosis(spec.read_text(encoding="utf-8"))
    if not items:
        print(f"spec {slug}: no delivery items to split ({reason})", file=sys.stderr)
        return 1
    written = write_drafts(args.root, slug, items)
    if args.as_json:
        print(json.dumps({"slug": slug, "tickets": [str(path) for path in written]}, ensure_ascii=False))
        return 0
    print(f"Drafted {len(written)} ticket(s) under {written[0].parent}")
    for path in written:
        print(f"  - {path.name}")
    print("Next: fill Write scope and Verify in each draft, move it to tickets/, then run lint.")
    return 0


def _agent_load(root: Path, agent: str) -> int:
    """这个 agent 目前占着几张活跃票（claimed / running / review）。"""
    store = DispatchState(root)
    runs_root = Path(root) / ".dispatch" / "runs"
    load = 0
    for ticket_id, entry in (store.load().get("tickets") or {}).items():
        if str(entry.get("state", "")) not in {"claimed", "running", "review"}:
            continue
        run_file = runs_root / str(entry.get("run_id", "")) / "run.json"
        if not run_file.is_file():
            continue
        try:
            data = json.loads(run_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(data.get("claimed_by", "")) == agent:
            load += 1
    return load


def _cmd_seat(args: argparse.Namespace) -> int:
    inactive = [part.strip() for part in args.inactive.split(",") if part.strip()]
    occupied = args.occupied
    if getattr(args, "agent", ""):
        occupied = _agent_load(Path(getattr(args, "root", Path("."))), args.agent)
    try:
        report = check_seats(
            cap=args.cap,
            occupied=occupied,
            inactive=inactive,
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"seats: {report['occupied']}/{report['cap']} 占用，剩 {report['free']}")
        print(f"verdict: {report['verdict']} — {report['advice']}")
    return 0 if report["free"] > 0 else 1


def _cmd_review_packet(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    ticket = _find_ticket(tickets, args.ticket_id)
    if ticket is None:
        print(f"unknown ticket: {args.ticket_id}", file=sys.stderr)
        return 1
    _, run = _current_run(args.root, args.ticket_id)
    if run is None:
        print(f"ticket {args.ticket_id} has no run", file=sys.stderr)
        return 1
    path, report = write_review_packet(args.root, ticket, run)
    if args.as_json:
        print(json.dumps({"path": str(path), "hashes": report.get("hashes")}, ensure_ascii=False))
    else:
        print(f"Review packet: {path}")
        print(f"Diff hash: {report.get('diff_hash')}")
    return 0


def _cmd_checkpoint(args: argparse.Namespace) -> int:
    _, run = _current_run(args.root, args.ticket_id)
    if run is None:
        print(f"ticket {args.ticket_id} has no run", file=sys.stderr)
        return 1
    if args.list_only:
        generations = list_generations(run)
        if args.as_json:
            print(json.dumps(generations, ensure_ascii=False, indent=2))
            return 0
        if not generations:
            print("(no checkpoints)")
            return 0
        for item in generations:
            mark = "*" if item.get("current") else " "
            print(f"{mark} {item.get('generation')}  {item.get('label')}  files={len(item.get('files') or [])}")
        return 0
    try:
        target = publish_checkpoint(run, args.label)
    except (OSError, FileExistsError) as error:
        print(f"checkpoint failed: {error}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps({"generation": target.name, "path": str(target)}, ensure_ascii=False))
    else:
        print(f"Checkpoint: {target}")
    return 0


def _cmd_closeout(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    ticket = _find_ticket(tickets, args.ticket_id)
    if ticket is None:
        print(f"unknown ticket: {args.ticket_id}", file=sys.stderr)
        return 1
    _, run = _current_run(args.root, args.ticket_id)
    if run is None:
        print(f"ticket {args.ticket_id} has no run", file=sys.stderr)
        return 1
    report_file, report = write_closeout(args.root, ticket, run)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Closeout {report['status'].upper()}: {report_file}")
        for finding in report.get("findings", []):
            print(f"  - {finding}")
    return 0 if report["status"] == "pass" else 1


def _cmd_questions(args: argparse.Namespace) -> int:
    try:
        items = grill_questions(args.root, args.slug)
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.as_json or True:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    return 0 if items else 2


def _wrap_fix(root: Path) -> dict[str, object]:
    """安全的自愈：重建索引 + 清掉过期租约。不动 worktree、不删分支。"""
    summary: dict[str, object] = {}
    try:
        repair = repair_state(root, write=True)
        summary["repaired"] = True
        summary["added"] = repair.get("added", [])
    except Exception as error:  # noqa: BLE001
        summary["repaired"] = False
        summary["error"] = str(error)
    released: list[str] = []
    locks = root / ".dispatch" / "locks"
    if locks.is_dir():
        now = datetime.now(timezone.utc)
        for entry in sorted(locks.glob("*.json")):
            try:
                payload = json.loads(entry.read_text(encoding="utf-8"))
                expires = datetime.fromisoformat(str(payload.get("expires_at", "")))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < now:
                try:
                    entry.unlink()
                    released.append(str(payload.get("path", entry.name)))
                except OSError:
                    pass
    summary["released"] = released
    return summary


SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}


def _find_dispatch_roots(root: Path, max_depth: int = 4) -> list[dict[str, object]]:
    """扫仓库里其它 dispatch 根（有 dispatch/config.json 或 .dispatch/state.json 或 tickets/）。"""
    found: list[dict[str, object]] = []
    root = Path(root).resolve()

    def walk(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            return
        has_config = (directory / "config.json").is_file() and directory.name == "dispatch"
        has_state = (directory / ".dispatch" / "state.json").is_file()
        has_tickets = (directory / "tickets").is_dir() and directory.name == "dispatch"
        if ".dispatch" in directory.parts:
            return
        if has_config or has_state or has_tickets:
            tickets_dir = directory / "tickets"
            count = 0
            if tickets_dir.is_dir():
                count = len([item for item in tickets_dir.glob("*.md")])
            found.append({"root": str(directory), "tickets": count})
            return
        for entry in entries:
            if entry.is_dir() and entry.name not in SKIP_DIRS:
                walk(entry, depth + 1)

    for entry in sorted(root.iterdir()) if root.is_dir() else []:
        if entry.is_dir() and entry.name not in SKIP_DIRS:
            walk(entry, 1)
    return found


def _cmd_roots(args: argparse.Namespace) -> int:
    roots = _find_dispatch_roots(Path(args.root))
    if args.as_json:
        print(json.dumps({"roots": roots}, ensure_ascii=False, indent=2))
        return 0
    if not roots:
        print("no dispatch roots found")
        return 0
    print(f"{len(roots)} dispatch root(s):")
    for item in roots:
        print(f"  {item['root']}  ({item['tickets']} ticket(s))")
    return 0


def _cmd_wrap(args: argparse.Namespace) -> int:
    root = Path(args.root)
    directory = _tickets_dir(args)
    fix_summary = _wrap_fix(root) if getattr(args, "fix", False) else None
    report = _health_report(root, directory)
    tickets, _ = _load_and_lint(directory, root)
    document = status_document(tickets or [], _state_map(root))
    counts: dict[str, int] = {}
    for row in document["tickets"]:
        counts[str(row["state"])] = counts.get(str(row["state"]), 0) + 1
    issues = list(report.get("issues", [])) + list(report.get("warnings", []))
    if not directory.exists():
        others = _find_dispatch_roots(root)
        if others:
            issues.append("other dispatch root(s) found: " + ", ".join(str(item["root"]) for item in others[:3]) + " (pass --root <path> to inspect them)")
    runs_dir = root / ".dispatch" / "runs"
    runs_total = runs_landed = 0
    runs_without_landing: list[str] = []
    if runs_dir.is_dir():
        for entry in sorted(runs_dir.iterdir()):
            if not entry.is_dir() or not (entry / "run.json").is_file():
                continue
            runs_total += 1
            if (entry / "landing.json").is_file():
                runs_landed += 1
            else:
                runs_without_landing.append(entry.name)
    unlanded: set[str] = set()
    for name in runs_without_landing:
        try:
            info = json.loads((runs_dir / name / "run.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ticket_id = str(info.get("ticket_id", ""))
        if ticket_id:
            unlanded.add(ticket_id)
    unlanded_tickets = sorted(unlanded)
    if runs_without_landing:
        detail = f" — tickets: {', '.join(unlanded_tickets)}" if unlanded_tickets else ""
        issues.append(
            f"{len(runs_without_landing)} ended run(s) without landing.json (dispatch gc to review, or land them){detail}"
        )
    actions: list[str] = []
    for issue in issues:
        if "need dispatch retry:" in issue:
            ids = issue.split("need dispatch retry:")[1].strip()
            for ticket_id in [item.strip() for item in ids.split(",") if item.strip()]:
                actions.append(f"dispatch retry {ticket_id}")
        elif "past their deadline" in issue:
            actions.append("dispatch sweep            # 看哪条 run 超期")
        elif "will block land" in issue:
            actions.append("git add/commit 或 .gitignore 掉上面列的文件")
        elif "no run on disk" in issue:
            actions.append("dispatch doctor --fix")
        elif "without landing.json" in issue:
            actions.append("dispatch land --wave --dry-run   # 先看会落哪几张")
            actions.append("dispatch gc               # 看哪些 run 可 REMOVE / 需 HOLD")
        elif "repair check failed" in issue:
            actions.append("dispatch repair           # 先 dry-run 看看")
    payload = {
        "fix": fix_summary,
        "tickets": len(document["tickets"]),
        "states": counts,
        "frontier": document["frontier"],
        "issues": issues,
        "actions": actions,
        "runs_total": runs_total,
        "runs_landed": runs_landed,
        "runs_without_landing": runs_without_landing,
        "unlanded_tickets": unlanded_tickets,
        "clean": not issues,
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not issues else 1
    if fix_summary:
        bits = []
        if fix_summary.get("repaired"):
            bits.append("index rebuilt")
        released = fix_summary.get("released") or []
        if released:
            bits.append(f"released {len(released)} expired lease(s)")
        print("Fixed: " + ("; ".join(bits) or "nothing to fix"))
    summary = ", ".join(f"{state} {count}" for state, count in sorted(counts.items())) or "no tickets"
    print(f"Wrap-up: {len(document['tickets'])} ticket(s) — {summary}")
    print("Frontier: " + (", ".join(document["frontier"]) or "-"))
    if issues:
        print("Issues:")
        for issue in issues:
            print("  - " + issue)
        if actions:
            print("Next:")
            for action in actions:
                print("  " + action)
        print(f"Verdict: NOT CLEAN ({len(issues)} issue(s))")
        return 1
    print("Verdict: CLEAN")
    return 0


def _cmd_install_hooks(args: argparse.Namespace) -> int:
    """装一个 pre-commit 钩子：有 .dispatch/ 就跑 wrap，不干净就挡提交。"""
    root = Path(args.root).resolve()
    hooks = root / ".git" / "hooks"
    if not hooks.parent.is_dir():
        print(f"not a git repository: {root}", file=sys.stderr)
        return 1
    hooks.mkdir(parents=True, exist_ok=True)
    target = hooks / "pre-commit"
    if target.exists() and not args.force:
        print(f"{target} already exists; pass --force to overwrite", file=sys.stderr)
        return 1
    dispatch_py = Path(__file__).resolve().parents[2] / "scripts" / "dispatch.py"
    if not dispatch_py.is_file():
        dispatch_py = Path(sys.argv[0]).resolve()
    hook_path = str(dispatch_py).replace("\\", "/")
    lines = [
        "#!/bin/sh",
        "# installed by agent-dispatch: block commits while the dispatch wrap-up is not clean",
        "[ -d .dispatch ] || exit 0",
        "[ -f \"" + hook_path + "\" ] || exit 0",
        "python \"" + hook_path + "\" wrap --root . || {",
        "  echo 'dispatch wrap is not clean; fix the issues above (or commit with --no-verify)'",
        "  exit 1",
        "}",
        "",
    ]
    target.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    try:
        target.chmod(0o755)
    except OSError:
        pass
    print(f"Installed {target}")
    return 0


def _cmd_setup(args: argparse.Namespace) -> int:
    root = Path(args.root)
    current = load_config(root)
    tickets = args.tickets or str(current.get("tickets_dir", "tickets"))
    target = root / tickets
    if not target.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        print(f"Created {target}")
    updated = {
        "version": 1,
        "tickets_dir": tickets.replace("\\", "/"),
        "executor_mode": args.executor_mode or str(current.get("executor_mode", "command")),
        "default_reviewer": args.default_reviewer or str(current.get("default_reviewer", "")),
        "require_brief": True,
        "persona_policy": "l2",
        "skill_version": __version__,
    }
    ignore = root / ".gitignore"
    if not ignore.exists():
        ignore.write_text(".dispatch/\n", encoding="utf-8")
    elif ".dispatch/" not in ignore.read_text(encoding="utf-8", errors="replace"):
        with ignore.open("a", encoding="utf-8") as stream:
            stream.write("\n.dispatch/\n")
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.as_json:
        print(json.dumps({"config": str(path), **updated}, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote {path}")
        for key in ("tickets_dir", "executor_mode", "default_reviewer"):
            print(f"  {key}: {updated[key]}")
    return 0


def _cmd_handoff(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    ticket = _find_ticket(tickets, args.ticket_id)
    if ticket is None:
        print(f"unknown ticket: {args.ticket_id}", file=sys.stderr)
        return 1
    _, run = _current_run(args.root, args.ticket_id)
    if run is None:
        print(f"ticket {args.ticket_id} has no run; render it first", file=sys.stderr)
        return 1
    work_order = (run.directory / "work-order.md").resolve()
    if not work_order.is_file():
        print(f"ticket {args.ticket_id}: work-order.md is missing", file=sys.stderr)
        return 1
    target = args.to or ticket.owner or "implementer"
    execution_root = run.execution_root
    message = "\n".join(
        [
            f"请执行票据 {ticket.id}（run {run.id}）。",
            "",
            f"工作单：{work_order}",
            f"执行根：{execution_root}",
            f"分支：dispatch/{run.id}",
            "",
            "要求：",
            f"1. 只在执行根内改动，写域见工作单；",
            f"2. 完成后把回执写到 {run.directory / 'receipt.json'}（status=done + 每条判据的证据）；",
            "3. 环境变量 DISPATCH_RUN_DIR / DISPATCH_RUN_ID 已由派单方提供；",
            "4. 不要改票据、不要合并分支。",
        ]
    )
    payload = {
        "ticket_id": ticket.id,
        "run_id": run.id,
        "to": target,
        "work_order": str(work_order),
        "execution_root": str(execution_root),
        "branch": "dispatch/" + run.id,
        "run_dir": str(run.directory.resolve()),
        "receipt": str((run.directory / "receipt.json").resolve()),
        "message": message,
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Hand off {ticket.id} to {target}:")
        print(message)
    return 0


def _dirty_paths(root: Path) -> list[str]:
    import subprocess as _subprocess

    try:
        out = _subprocess.run(
            ["git", "status", "--porcelain", "-uall"], cwd=root, capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return []
    paths = [line[3:].strip() for line in out.splitlines() if line.strip()]
    return [path for path in paths if path]


def _blocks_land(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith(".dispatch/") or normalized.startswith(".scratch/"):
        return False
    return True


def _health_report(root: Path, directory: Path) -> dict[str, object]:
    """只读体检：票、索引、失败票、超期 run、宿主装进来的技能包。"""
    root = Path(root)
    issues: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, object]] = []

    tickets: list = []
    if not directory.exists():
        issues.append(f"tickets directory is missing: {directory}")
    else:
        tickets, _ = _load_and_lint(directory, root)
        if tickets is None:
            tickets = []
        if not tickets:
            issues.append("no tickets found; dispatch cannot advance anything")
    checks.append({"name": "tickets", "ok": bool(tickets), "detail": f"{len(tickets)} ticket(s)"})

    states = _state_map(root)
    failed = sorted(tid for tid, value in states.items() if value == "failed")
    if failed:
        issues.append("failed tickets need dispatch retry: " + ", ".join(failed))
    checks.append({"name": "failed", "ok": not failed, "detail": ", ".join(failed) or "none"})

    runs_dir = root / ".dispatch" / "runs"
    external_dir = root / ".dispatch" / "external"
    ghosts = sorted(
        tid
        for tid, entry in (DispatchState(root).load().get("tickets") or {}).items()
        if not (runs_dir / str(entry.get("run_id", ""))).is_dir()
        and not (external_dir / (tid + ".json")).is_file()
    )
    if ghosts:
        issues.append("index entries with no run on disk: " + ", ".join(ghosts) + " (run dispatch doctor --fix)")

    edited: list[str] = []
    store = DispatchState(root)
    for ticket in tickets or []:
        entry = store.ticket(ticket.id) or {}
        state = str(entry.get("state", ""))
        if state not in {"claimed", "running", "review"}:
            continue
        run_id = str(entry.get("run_id", ""))
        run_file = runs_dir / run_id / "run.json"
        if not run_file.is_file():
            continue
        try:
            recorded = str(json.loads(run_file.read_text(encoding="utf-8")).get("ticket_hash", ""))
        except (OSError, json.JSONDecodeError):
            recorded = ""
        if recorded and ticket.content_hash != recorded:
            edited.append(ticket.id)
    if edited:
        issues.append("tickets edited after render: " + ", ".join(sorted(edited)) + " (revert or dispatch retry)")
    checks.append({"name": "ticket-edits", "ok": not edited, "detail": ", ".join(sorted(edited)) or "none"})

    dirty = _dirty_paths(root)
    blockers = [path for path in dirty if _blocks_land(path)]
    if blockers:
        warnings.append(
            "uncommitted files will block land (commit or ignore): " + ", ".join(blockers[:8])
        )
    checks.append({"name": "checkout", "ok": not blockers, "detail": ", ".join(blockers[:8]) or "clean"})

    try:
        report = repair_state(root, write=False)
    except Exception as error:  # noqa: BLE001 - 一项检查挂了不该拖垮整个体检
        issues.append(f"repair check failed: {error}")
    else:
        if isinstance(report, dict):
            conflicts = report.get("conflicts", [])
            mismatches = [
                row for row in report.get("rows", []) if str(row.get("action", "")) == "mismatch"
            ]
            if conflicts:
                issues.append(f"index/disk conflicts: {len(conflicts)}")
            if mismatches:
                issues.append(f"state/evidence mismatches: {len(mismatches)} (run dispatch repair --write)")

    overdue = [row for row in sweep_runs(root) if row.get("over_deadline")]
    if overdue:
        issues.append("runs past their deadline: " + ", ".join(str(row.get("ticket_id")) for row in overdue))
    checks.append({"name": "deadline", "ok": not overdue, "detail": f"{len(overdue)} overdue"})

    locks = sorted((root / ".dispatch" / "locks").glob("*.json")) if (root / ".dispatch" / "locks").exists() else []
    if locks:
        checks.append({"name": "leases", "ok": True, "detail": f"{len(locks)} active lease(s)"})

    host_packages: list[str] = []
    for base in (".agents/skills", ".claude/skills", ".codex/skills"):
        folder = root / base
        if folder.is_dir():
            host_packages.extend(base + "/" + child.name for child in sorted(folder.iterdir()) if child.is_dir())
    if host_packages:
        warnings.append(
            "host-installed skill packages inside the repo: "
            + ", ".join(host_packages[:5])
            + (" …" if len(host_packages) > 5 else "")
            + " (keep them out of the repo unless they are part of what this project ships)"
        )

    return {"ok": not issues, "issues": issues, "warnings": warnings, "checks": checks}


def _fix_safe(root: Path) -> list[str]:
    """只做两种安全修复：重建索引、清掉过期租约。别的只报告。"""
    fixed: list[str] = []
    try:
        report = repair_state(Path(root), write=True)
    except Exception as error:  # noqa: BLE001
        fixed.append(f"index repair failed: {error}")
    else:
        if isinstance(report, dict):
            written = report.get("written", report.get("repaired", 0))
            if written:
                count = written if isinstance(written, int) and not isinstance(written, bool) else None
                fixed.append("index rebuilt" + (f" ({count} ticket(s))" if count else ""))
    # 索引里指向不存在 run 的条目：索引是投影，磁盘没有就该删
    try:
        state = DispatchState(Path(root))
        data = state.load()
        runs_dir = Path(root) / ".dispatch" / "runs"
        external_dir = Path(root) / ".dispatch" / "external"
        stale = [
            tid
            for tid, entry in (data.get("tickets") or {}).items()
            if not (runs_dir / str(entry.get("run_id", ""))).is_dir()
            and not (external_dir / (tid + ".json")).is_file()
        ]
        for tid in stale:
            data["tickets"].pop(tid, None)
        if stale:
            state.save(data)
            fixed.append("dropped stale index entries: " + ", ".join(sorted(stale)))
    except Exception as error:  # noqa: BLE001
        fixed.append(f"index cleanup failed: {error}")
    now = datetime.now(timezone.utc)
    lock_dir = Path(root) / ".dispatch" / "locks"
    if lock_dir.is_dir():
        for lock in sorted(lock_dir.glob("*.json")):
            try:
                data = json.loads(lock.read_text(encoding="utf-8"))
                expires = datetime.fromisoformat(str(data.get("expires_at", "")))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < now:
                try:
                    lock.unlink()
                    fixed.append(f"removed expired lease {lock.stem}")
                except OSError:
                    continue
    return fixed


def _cmd_doctor(args: argparse.Namespace) -> int:
    root = Path(args.root)
    directory = Path(getattr(args, "tickets", None) or (root / "tickets"))
    fixed: list[str] = []
    if getattr(args, "fix", False):
        fixed = _fix_safe(root)
        payload = _health_report(root, directory)
    else:
        payload = _health_report(root, directory)
    payload = {**payload, "fixed": fixed}
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("OK" if payload["ok"] else "PROBLEMS")
        for check in payload["checks"]:
            print(f"  {check['name']:<10} {check['detail']}")
        for issue in payload["issues"]:
            print("  - " + issue)
        for warning in payload["warnings"]:
            print("  ! " + warning)
        for item in payload["fixed"]:
            print("  + fixed: " + item)
    return 0 if payload["ok"] else 1


def _cmd_release(args: argparse.Namespace) -> int:
    _, run = _current_run(args.root, args.ticket_id)
    if run is None:
        if args.as_json:
            print(json.dumps({"ticket_id": args.ticket_id, "run_id": "", "released": []}, ensure_ascii=False))
        else:
            print(f"Released 0 lease(s) for {args.ticket_id} (no run)")
        return 0
    released = release_claims(args.root, run.id)
    if args.as_json:
        print(json.dumps({"ticket_id": args.ticket_id, "run_id": run.id, "released": released}, ensure_ascii=False, indent=2))
    else:
        print(f"Released {len(released)} lease(s) for {run.id}")
        for path in released:
            print("  - " + path)
    return 0


def _cmd_retry(args: argparse.Namespace) -> int:
    state = DispatchState(args.root)
    entry = state.ticket(args.ticket_id)
    if entry is None:
        print(f"ticket {args.ticket_id}: not in the index (render it first)", file=sys.stderr)
        return 1
    current = str(entry.get("state", ""))
    if current == "done":
        print(f"ticket {args.ticket_id} is done; nothing to retry", file=sys.stderr)
        return 1
    if current not in {"failed", "claimed"}:
        print(
            f"ticket {args.ticket_id} is {current or 'unknown'}; only a failed or stuck-claimed ticket can be retried",
            file=sys.stderr,
        )
        return 1
    try:
        run = Run.load(args.root, str(entry.get("run_id", "")))
    except Exception:
        print(f"ticket {args.ticket_id}: run {entry.get('run_id')!r} is missing", file=sys.stderr)
        return 1
    attempts = run.directory / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    number = len(list(attempts.glob("verify-*.json"))) + 1
    kept: list[str] = []
    for name in ("verify.json", "review.json", "closeout.json"):
        source = run.directory / name
        if source.is_file():
            target = attempts / (name.replace(".json", "") + "-" + f"{number:02d}" + ".json")
            source.replace(target)
            kept.append(str(target.relative_to(run.directory)).replace("\\", "/"))
    run.data["attempt"] = int(run.data.get("attempt", 1)) + 1
    run.set_state("running")
    run.write()
    data = state.load()
    ticket_entry = data.setdefault("tickets", {}).setdefault(args.ticket_id, {})
    history = ticket_entry.setdefault("history", [])
    if isinstance(history, list):
        history.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "from": current,
                "to": "running",
                "reason": args.reason,
            }
        )
    ticket_entry["run_id"] = run.id
    ticket_entry["state"] = "running"
    ticket_entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    state.save(data)
    payload = {
        "ticket_id": args.ticket_id,
        "run_id": run.id,
        "state": "running",
        "attempt": run.data["attempt"],
        "archived": kept,
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Retried {args.ticket_id} -> running (attempt {run.data['attempt']})")
        for item in kept:
            print(f"  archived {item}")
    return 0


def _cmd_confirm(args: argparse.Namespace) -> int:
    try:
        path = confirm_spec(args.root, args.slug, args.by, args.via, args.note)
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    print("Confirmed " + args.slug + " (" + args.via + ") -> " + str(path))
    return 0


def _cmd_sign(args: argparse.Namespace) -> int:
    choice = "reject" if args.reject else ("hold" if args.hold else "pass")
    try:
        path = sign_selection(args.root, args.slug, args.by, choice, args.via, getattr(args, "note", ""))
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    print("Signed " + args.slug + " (" + choice + ") -> " + str(path))
    return 0


def _cmd_stage(args: argparse.Namespace) -> int:
    if getattr(args, "prompt", False):
        payload = stage_prompt(args.root, args.slug)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["questions"] else 2
    report = stage_report(args.root, args.slug)
    health = _health_report(Path(args.root), Path(args.root) / "tickets")
    report = {**report, "health": {"ok": health["ok"], "issues": health["issues"]}}
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for name in ("s1", "s2", "s3", "s4", "s5"):
            item = report["stages"][name]
            mark = "OK  " if item["ok"] else "MISS"
            print(mark + " " + name + "  " + str(item["detail"]))
        print("health: " + ("OK" if health["ok"] else "; ".join(str(x) for x in health["issues"][:2])))
        print("next: " + str(report["next"]))
    return 0 if report["ok"] else 1


def _cmd_claim(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    ticket = _find_ticket(tickets, args.ticket_id)
    if ticket is None:
        print(f"unknown ticket: {args.ticket_id}", file=sys.stderr)
        return 1
    _, run = _current_run(args.root, args.ticket_id)
    if run is None:
        print(f"ticket {args.ticket_id} has no run", file=sys.stderr)
        return 1
    try:
        paths = expand_scope(args.root, list(ticket.write_scope))
    except ScopeError as error:
        print("SCOPE-UNRESOLVED " + str(error), file=sys.stderr)
        return 4
    report = claim_paths(
        args.root, ticket.id, run.id, paths, ttl_seconds=max(1, args.ttl_minutes) * 60
    )
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Claimed " + str(len(report["granted"])) + " file(s) for " + run.id)
        for item in report["conflicts"]:
            print(
                "CONFLICT " + item["path"] + " held by " + item["ticket_id"] + " (" + item["run_id"] + ")",
                file=sys.stderr,
            )
    return 3 if report["conflicts"] else 0


def _cmd_gc(args: argparse.Namespace) -> int:
    rows = gc_worktrees(args.root, apply=args.apply)
    if args.as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("(no ended runs with worktrees)")
        return 0
    for row in rows:
        print(row["verdict"].ljust(7) + row["ticket_id"].ljust(28) + row["state"].ljust(8) + ("dirty " if row["dirty"] else "clean ") + ("landed" if row["landed"] else "unlanded"))
    if not args.apply:
        print("Dry run; add --apply to remove the REMOVE rows.")
    return 0


def _cmd_sweep(args: argparse.Namespace) -> int:
    rows = sweep_runs(args.root)
    if args.as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("(no active runs)")
        return 0
    for row in rows:
        idle = row["idle_seconds"]
        idle_text = str(idle) + "s" if isinstance(idle, int) else "no artifacts yet"
        age = row["age_seconds"]
        age_text = str(age) + "s" if isinstance(age, int) else "?"
        flag = "RECEIPT" if row["has_receipt"] else "working"
        over = " OVER-DEADLINE" if row.get("over_deadline") else ""
        print(row["ticket_id"].ljust(28) + row["state"].ljust(9) + "age=" + age_text.ljust(8) + "idle=" + idle_text.ljust(16) + flag + over)
    return 0


def _cmd_repair(args: argparse.Namespace) -> int:
    report = repair_state(args.root, write=args.write)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Runs on disk: " + str(report["runs"]))
        print("Missing from index: " + (", ".join(report["added"]) or "-"))
        print("State differs: " + (", ".join(report["state_changed"]) or "-"))
        for conflict in report["conflicts"]:
            print("CONFLICT " + conflict["ticket_id"] + ": index=" + str(conflict["state_run"]) + " disk=" + str(conflict["disk_run"]), file=sys.stderr)
        for item in report.get("evidence_mismatch", []):
            print("EVIDENCE-MISMATCH " + item["ticket_id"] + ": state=" + str(item["state_run"]) + " evidence=" + str(item["evidence"]))
        if report["written"] and report["conflicts"]:
            print("Written: partial (conflicts skipped; see CONFLICT above)")
        elif report["written"]:
            print("Written: yes")
        else:
            print("Written: no (dry run; add --write)")
    return 1 if report["conflicts"] else 0


def _cmd_start(args: argparse.Namespace) -> int:
    store = DispatchState(args.root)
    existing = store.ticket(args.ticket_id)
    if not existing:
        print(f"ticket {args.ticket_id} has no run", file=sys.stderr)
        return 1
    if existing.get("state") != "claimed":
        print(
            f"ticket {args.ticket_id} is {existing.get('state')}, expected claimed"
            + _state_hint(args.ticket_id, existing.get("state")),
            file=sys.stderr,
        )
        return 1
    run = Run.load(args.root, str(existing["run_id"]))
    run.set_state("running")
    store.set_ticket(args.ticket_id, run.id, "running")
    print(f"Started {args.ticket_id} ({run.id})")
    return 0

def _record_verify_failure(run: Run, errors: list[str]) -> int:
    """把这次失败写进 verify-history.jsonl，返回"同样的失败之前出现过几次"。"""
    history = run.directory / "verify-history.jsonl"
    repeats = 0
    if history.is_file():
        try:
            for line in history.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if [str(item) for item in entry.get("errors", [])] == errors:
                    repeats += 1
        except OSError:
            repeats = 0
    try:
        with history.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "errors": errors}, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return repeats


def _cmd_verify(args: argparse.Namespace) -> int:
    store = DispatchState(args.root)
    existing = store.ticket(args.ticket_id)
    if not existing:
        print(f"ticket {args.ticket_id} has no run", file=sys.stderr)
        return 1
    if existing.get("state") != "running":
        print(
            f"ticket {args.ticket_id} is {existing.get('state')}, expected running"
            + _state_hint(args.ticket_id, existing.get("state")),
            file=sys.stderr,
        )
        return 1
    run = Run.load(args.root, str(existing["run_id"]))
    ticket = parse_ticket(run.ticket_path)
    record, passed = verify_run(
        args.root,
        ticket,
        run,
        timeout=args.timeout,
        allow_main_drift=args.allow_main_drift,
    )
    status = str(record.get("status", "failed"))
    if passed and status == "degraded":
        print(f"Verification degraded for {args.ticket_id} ({run.id})", file=sys.stderr)
        return 2
    if passed:
        print(f"Verification passed for {args.ticket_id} ({run.id})")
        print(f"Record: {run.directory / 'verify.json'}")
        return 0
    errors = [str(item) for item in record["errors"]]
    for error in errors:
        print(f"VERIFY {error}", file=sys.stderr)
    repeats = _record_verify_failure(run, errors)
    if repeats >= 2:
        print(
            f"VERIFY repeated failure: the same {len(errors)} error(s) have now failed {repeats + 1} times. "
            "Re-running will not change it. Fix the implementation or the environment the command needs — "
            "do not weaken the criterion just to make it green (that hides the bug; if you must change it, "
            "record why in the receipt notes).",
            file=sys.stderr,
        )
    print(f"Verification failed for {args.ticket_id} ({run.id})", file=sys.stderr)
    return 1

def _cmd_review(args: argparse.Namespace) -> int:
    if not getattr(args, "reviewer", None):
        configured = str(load_config(Path(args.root)).get("default_reviewer", "") or "")
        if not configured:
            print("review needs --reviewer <名字> (or set one with dispatch setup --default-reviewer)", file=sys.stderr)
            return 1
        args.reviewer = configured
    store = DispatchState(args.root)
    existing = store.ticket(args.ticket_id)
    if not existing:
        print(f"ticket {args.ticket_id} has no run", file=sys.stderr)
        return 1
    if existing.get("state") != "review":
        print(
            f"ticket {args.ticket_id} is {existing.get('state')}, expected review; verify must pass first",
            file=sys.stderr,
        )
        return 1
    run = Run.load(args.root, str(existing["run_id"]))
    ticket = parse_ticket(run.ticket_path)
    attested = False
    if getattr(args, "packet_hash", None) and ticket.risk in {"L0", "L1"}:
        packet = run.directory / "review-packet.md"
        if not packet.is_file():
            print(f"REVIEW L0/L1: review packet missing: run dispatch review-packet {args.ticket_id}", file=sys.stderr)
            return 1
        actual = hashlib.sha256(packet.read_bytes()).hexdigest()
        if str(args.packet_hash).lower() != actual:
            print(f"REVIEW packet hash mismatch: packet is {actual}", file=sys.stderr)
            return 1
        attested = True
    if ticket.risk in {"L2", "L3", "L4"}:
        packet = run.directory / "review-packet.md"
        if not packet.is_file():
            print(f"REVIEW L2+ needs a review packet: run dispatch review-packet {args.ticket_id} first", file=sys.stderr)
            return 1
        supplied = str(getattr(args, "packet_hash", "") or "")
        if not supplied:
            print("REVIEW L2+ needs --packet-hash <sha256 of review-packet.md>", file=sys.stderr)
            return 1
        actual = hashlib.sha256(packet.read_bytes()).hexdigest()
        if supplied.lower() != actual:
            print(f"REVIEW packet hash mismatch: packet is {actual}", file=sys.stderr)
            return 1
        attested = True
    record, errors = submit_review(
        args.root,
        ticket,
        run,
        reviewer=args.reviewer,
        verdict=args.verdict,
        notes=args.notes,
        human=args.human,
        accept_degraded=args.accept_degraded,
        self_reviewed=args.self_reviewed,
        packet_attested=attested,
    )
    if errors:
        for error in errors:
            print(f"REVIEW {error}", file=sys.stderr)
        return 1
    print(f"Review {record['verdict']} recorded for {args.ticket_id} ({run.id})")
    return 0

def _current_run(root: Path, ticket_id: str):
    store = DispatchState(root)
    existing = store.ticket(ticket_id)
    if not existing:
        return None, None
    return store, Run.load(root, str(existing["run_id"]))


def _land_wave(args: argparse.Namespace) -> int:
    directory = Path(getattr(args, "tickets", None) or (Path(args.root) / "tickets"))
    tickets, issues = _load_and_lint(directory)
    if issues:
        for issue in issues:
            print(f"ERROR {issue.ticket_id} {issue.code}: {issue.message}", file=sys.stderr)
        return 1
    states = _state_map(args.root)
    done = {
        ticket.id
        for ticket in tickets
        if states.get(ticket.id) == "done" or str(ticket.status).strip().lower() == "done"
    }
    order: list[str] = []
    pending = {ticket.id: ticket for ticket in tickets}
    while pending:
        # 纯拓扑：只有依赖都已排进去的才就绪（完成与否不影响顺序）
        ready = [
            tid
            for tid, ticket in pending.items()
            if all(dep in order or dep not in pending for dep in ticket.depends_on)
        ]
        ready = ready or sorted(pending)  # 环或坏依赖：给个确定顺序，别死循环
        for tid in sorted(ready):
            order.append(tid)
            pending.pop(tid)
    landed: list[dict[str, object]] = []
    planned: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    failed: list[dict[str, object]] = []
    landed_ids: set[str] = set()
    for tid in order:
        ticket = next(item for item in tickets if item.id == tid)
        blocked = [dep for dep in ticket.depends_on if dep not in landed_ids]
        if tid not in done:
            skipped.append({"ticket_id": tid, "reason": "not done"})
            continue
        if blocked:
            skipped.append({"ticket_id": tid, "reason": "dependency not landed: " + ", ".join(blocked)})
            continue
        _, run = _current_run(args.root, tid)
        if run is None:
            skipped.append({"ticket_id": tid, "reason": "no run"})
            continue
        if (run.directory / "landing.json").is_file():
            landed_ids.add(tid)
            skipped.append({"ticket_id": tid, "reason": "already landed"})
            continue
        if getattr(args, "require_closeout", False):
            closeout_file = run.directory / "closeout.json"
            verdict = ""
            if closeout_file.is_file():
                try:
                    verdict = str(json.loads(closeout_file.read_text(encoding="utf-8")).get("status", ""))
                except (OSError, json.JSONDecodeError):
                    verdict = ""
            if verdict != "pass":
                failed.append({"ticket_id": tid, "reason": "closeout.json 不是 pass"})
                if not args.continue_on_error:
                    break
                continue

        if getattr(args, "dry_run", False):
            planned.append({"ticket_id": tid, "reason": "would land"})
            landed_ids.add(tid)
            continue
        try:
            record = land_run(args.root, tid, target_branch=args.into, integration_branch=args.branch)
        except LandingError as error:
            failed.append({"ticket_id": tid, "reason": str(error)})
            if not args.continue_on_error:
                break
            continue
        landed_ids.add(tid)
        landed.append({"ticket_id": tid, "branch": record.get("integration_branch")})
    payload = {"landed": landed, "planned": planned, "skipped": skipped, "failed": failed, "dry_run": bool(getattr(args, "dry_run", False))}
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in planned:
            print(f"WOULD  {item['ticket_id']}  {item['reason']}")
        for item in landed:
            print(f"LANDED {item['ticket_id']} -> {item['branch']}")
        for item in skipped:
            print(f"SKIP   {item['ticket_id']}  {item['reason']}")
        for item in failed:
            print(f"FAILED {item['ticket_id']}  {item['reason']}", file=sys.stderr)
    return 1 if failed else 0


def _cmd_land(args: argparse.Namespace) -> int:
    if getattr(args, "wave", False):
        return _land_wave(args)
    if getattr(args, "require_attestation", False):
        _, run = _current_run(args.root, args.ticket_id)
        if run is None:
            print(f"ticket {args.ticket_id}: no run to check attestation", file=sys.stderr)
            return 1
        review_file = run.directory / "review.json"
        attested = False
        if review_file.is_file():
            try:
                attested = bool(json.loads(review_file.read_text(encoding="utf-8")).get("packet_attested"))
            except (OSError, json.JSONDecodeError):
                attested = False
        if not attested:
            print(
                f"ticket {args.ticket_id}: review is not packet-attested (run review --packet-hash for L2+, or reviewer must echo packet_hash in auto)",
                file=sys.stderr,
            )
            return 1
    if getattr(args, "require_closeout", False):
        _, run = _current_run(args.root, args.ticket_id)
        if run is None:
            print(f"ticket {args.ticket_id}: no run to close out", file=sys.stderr)
            return 1
        report_file = run.directory / "closeout.json"
        if not report_file.is_file():
            print(f"ticket {args.ticket_id}: no closeout.json (run dispatch closeout first)", file=sys.stderr)
            return 1
        try:
            report = json.loads(report_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"ticket {args.ticket_id}: closeout.json unreadable: {error}", file=sys.stderr)
            return 1
        if str(report.get("status", "")) != "pass":
            print(f"ticket {args.ticket_id}: closeout is {report.get('status')}; refusing to land", file=sys.stderr)
            for finding in report.get("findings", []):
                print(f"  - {finding}", file=sys.stderr)
            return 1
    if getattr(args, "require_packet", True):
        _, run = _current_run(args.root, args.ticket_id)
        if run is None:
            print(f"ticket {args.ticket_id}: no run to land", file=sys.stderr)
            return 1
        if not (run.directory / "review-packet.md").is_file():
            print(
                f"ticket {args.ticket_id}: no review-packet.md; run dispatch review-packet {args.ticket_id} first "
                "(or pass --no-require-packet)",
                file=sys.stderr,
            )
            return 1
    if getattr(args, "require_attestation", False):
        _, run = _current_run(args.root, args.ticket_id)
        if run is None:
            print(f"ticket {args.ticket_id}: no run to land", file=sys.stderr)
            return 1
        review_file = run.directory / "review.json"
        attested = False
        if review_file.is_file():
            try:
                attested = bool(json.loads(review_file.read_text(encoding="utf-8")).get("packet_attested"))
            except (OSError, json.JSONDecodeError):
                attested = False
        if not attested:
            print(
                f"ticket {args.ticket_id}: reviewer did not attest the review packet; "
                "rerun auto with a reviewer that returns packet_hash, or drop --require-attestation",
                file=sys.stderr,
            )
            return 1

    try:
        record = land_run(
            args.root,
            args.ticket_id,
            target_branch=args.into,
            integration_branch=args.branch,
        )
    except LandingError as exc:
        print(f"LAND {exc}", file=sys.stderr)
        return 1
    # land 之后释放这个 run 的文件租约：票已经合入，写域不再被占用
    released = release_claims(args.root, str(record.get("run_id", "")))
    if args.as_json:
        print(json.dumps({**record, "released_claims": released}, ensure_ascii=False, indent=2))
        return 0
    print(f"Landed {args.ticket_id} -> {record['integration_branch']}")
    if released:
        print(f"Released {len(released)} file lease(s)")
    print(f"Target: {record['target_branch']} ({record['target_commit']})")
    print(f"Run commit: {record['run_commit']}")
    print(f"Landing commit: {record['landing_commit']}")
    print("Pushed: no")
    print("Next: push the integration branch and open a PR yourself.")
    return 0

def _auto_exit_code(result: dict[str, object]) -> int:
    status = str(result.get("status", ""))
    if status == "landed":
        return 0
    if status == "review":
        return 2 if result.get("verify_status") == "degraded" else 0
    return 1

def _preflight(root: Path, tickets_dir: Path) -> list[str]:
    """开跑前的最小体检：只挡会让 auto 在烂索引上瞎跑的问题。"""
    health = _health_report(Path(root), Path(tickets_dir))
    return [issue for issue in health["issues"] if "retry" not in issue]


def _cmd_auto(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    ticket = _find_ticket(tickets, args.ticket_id)
    if ticket is None:
        print(f"unknown ticket: {args.ticket_id}", file=sys.stderr)
        return 1
    auto_policy = str(load_config(Path(args.root)).get("persona_policy", "l2")).lower()
    auto_threshold = {"l2": {"L2", "L3", "L4"}, "l3": {"L3", "L4"}, "l4": {"L4"}}.get(auto_policy, {"L2", "L3", "L4"})
    if auto_policy not in {"off", "none", "optional"} and ticket.risk in auto_threshold and not ticket.persona:
        print(
            f"ticket {ticket.id}: risk {ticket.risk} needs a persona; run dispatch assign {ticket.id} --persona <name>",
            file=sys.stderr,
        )
        return 6
    if not getattr(args, "force", False):
        problems = _preflight(args.root, _tickets_dir(args))
        if problems:
            print("AUTO preflight failed; fix the index first:", file=sys.stderr)
            for problem in problems:
                print("  - " + problem, file=sys.stderr)
            print("  try: dispatch doctor --fix  (or pass --force)", file=sys.stderr)
            return 1
    try:
        result = auto_run(
            args.root,
            ticket,
            executor=args.executor,
            agent=args.agent,
            max_attempts=args.max_attempts,
            timeout=args.timeout,
            verify_timeout=args.verify_timeout,
            until=args.until,
            reviewer=args.reviewer,
            reviewer_command=args.reviewer_command,
            accept_degraded=args.accept_degraded,
            human=args.human,
            protocol=args.protocol,
            env_hint=args.env_hint,
            require_brief=args.require_brief,
            resume=getattr(args, "resume", False),
        )
    except AutoError as exc:
        print(f"AUTO {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return _auto_exit_code(result)

    print(f"Auto {ticket.id} -> {result.get('run_directory', '')}")
    attempts = result.get("attempts", [])
    if isinstance(attempts, list):
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            executor = attempt.get("executor", {})
            exit_code = executor.get("exit_code", "?") if isinstance(executor, dict) else "?"
            print(
                f"Attempt {attempt.get('attempt', '?')}: executor exit {exit_code}; "
                f"verification {attempt.get('verify_status', '?')}"
            )
    status = str(result.get("status", ""))
    if status == "review":
        print("Auto stopped at review.")
        print(
            "Next: dispatch review "
            + ticket.id
            + " --reviewer <name> --verdict pass|fail"
        )
    elif status == "landed":
        landing = result.get("landing", {})
        if isinstance(landing, dict):
            print(f"Landed {ticket.id} -> {landing.get('integration_branch', '')}")
            print(f"Target: {landing.get('target_branch', '')} ({landing.get('target_commit', '')})")
        print("Pushed: no")
        print("Next: push the integration branch and open a PR yourself.")
    elif status == "review-failed":
        print(f"AUTO review failed for {ticket.id}", file=sys.stderr)
    elif status == "review-invalid":
        print(f"AUTO review invalid: {result.get('error', '')}", file=sys.stderr)
    elif status == "land-failed":
        print(f"AUTO land failed: {result.get('error', '')}", file=sys.stderr)
    else:
        print(f"AUTO failed after {len(attempts) if isinstance(attempts, list) else 0} attempt(s)", file=sys.stderr)
        for error in result.get("last_errors", []):
            print(f"VERIFY {error}", file=sys.stderr)
    return _auto_exit_code(result)

def _cmd_dsh_push(args: argparse.Namespace) -> int:
    tickets_for_warning, _ = _load_and_lint(_tickets_dir(args), getattr(args, "root", None)) or ([], 1)
    weak = sorted(
        ticket.id
        for ticket in (tickets_for_warning or [])
        if ticket.risk in {"L0", "L1", "L2"}
    )
    if weak:
        print(
            "DSH: note: cards below L3 run with workspace-write, which cannot execute commands "
            "in the board session; dispatch flows need L3+. Affected: " + ", ".join(weak),
            file=sys.stderr,
        )
    if not getattr(args, "dry_run", False) and not args.workspace and not getattr(args, "allow_default_workspace", False):
        print(
            "DSH: push needs --workspace <id>: the card runs inside that workspace, "
            "not in this repo. Pass --allow-default-workspace to accept the board default.",
            file=sys.stderr,
        )
        return 1
    tickets, code = _load_and_lint(_tickets_dir(args), getattr(args, "root", None))
    if tickets is None:
        return code
    try:
        report = push(
            tickets,
            _state_map(args.root),
            root=args.root,
            base_url=args.url,
            project=args.project,
            mode=args.push_mode,
            workspace_id=args.workspace,
            dry_run=args.dry_run,
        )
    except (TaskBoardError, ValueError) as exc:
        print(f"DSH: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    if report.get("dry_run"):
        print(f"DSH dry run: {len(report['actions'])} action(s) for {report['project']}")
        for item in report["planned"]:
            print(f"  create {item['task_id']}  {item['title']}")
        return 0
    created = report.get("created", [])
    existing = report.get("existing", [])
    print(f"DSH board {report['base_url']} ({report['mode']}, project {report['project']})")
    print(f"Created {len(created)} card(s), kept {len(existing)} existing card(s).")
    for item in created:
        print(f"  + {item['task_id']}  {item['title']}")
    for item in existing:
        print(f"  = {item['task_id']}  {item['title']} [{item.get('status', '')}]")
    print(f"Map: {report['map_path']}")
    return 0

def _cmd_dsh_status(args: argparse.Namespace) -> int:
    try:
        document = board_status(root=args.root, base_url=args.url)
    except (TaskBoardError, ValueError) as exc:
        print(f"DSH: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(document, indent=2, ensure_ascii=False))
    else:
        print(format_status(document))
    return 0

def _cmd_dsh_outcome(args: argparse.Namespace) -> int:
    if getattr(args, "mark_done", False) and args.result == "succeeded":
        evidence = str(getattr(args, "evidence", "") or "")
    try:
        result = outcome(
            args.ticket_id,
            root=args.root,
            result=args.result,
            initiated_by=args.initiated_by,
            summary=args.summary,
            base_url=args.url,
            task_id=args.task_id,
        )
    except (TaskBoardError, ValueError) as exc:
        print(f"DSH: {exc}", file=sys.stderr)
        return 1
    if getattr(args, "mark_done", False) and args.result == "succeeded":
        evidence = str(getattr(args, "evidence", "") or "")
        if not evidence:
            print("DSH: --mark-done needs --evidence <path>; board status alone is not evidence", file=sys.stderr)
            return 1
        if not (Path(args.root) / evidence).exists():
            print(f"DSH: evidence not found: {evidence}", file=sys.stderr)
            return 1
        external = Path(args.root) / ".dispatch" / "external"
        external.mkdir(parents=True, exist_ok=True)
        record = {
            "ticket_id": args.ticket_id,
            "result": args.result,
            "by": args.initiated_by,
            "summary": args.summary,
            "task_id": result["task_id"],
            "board_status": result["status"],
            "evidence": evidence,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        (external / (args.ticket_id + ".json")).write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        store = DispatchState(Path(args.root))
        entry = store.ticket(args.ticket_id) or {}
        store.set_ticket(args.ticket_id, str(entry.get("run_id", "")), "done")
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Recorded {result['status']} for {result['ticket_id']} ({result['task_id']})")
        if getattr(args, "mark_done", False):
            print("Marked done in dispatch" if args.result == "succeeded" else "Left state alone (result was not succeeded)")
    return 0

def _cmd_dsh_update(args: argparse.Namespace) -> int:
    patch: dict[str, object] = {}
    if args.title is not None:
        patch["title"] = args.title
    if args.description is not None:
        patch["description"] = args.description
    if args.prompt is not None:
        patch["prompt"] = args.prompt
    if args.patch_json:
        try:
            extra = json.loads(args.patch_json)
        except json.JSONDecodeError as exc:
            print(f"DSH: --patch is not valid JSON: {exc}", file=sys.stderr)
            return 1
        if not isinstance(extra, dict):
            print("DSH: --patch must be a JSON object", file=sys.stderr)
            return 1
        patch.update(extra)
    if not patch:
        print("DSH: provide --title, --description, --prompt or --patch", file=sys.stderr)
        return 1
    try:
        result = update_card(
            args.ticket_id,
            root=args.root,
            patch=patch,
            base_url=args.url,
            task_id=args.task_id,
        )
    except (TaskBoardError, ValueError) as exc:
        print(f"DSH: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Updated {result['ticket_id']} ({result['task_id']}): {result.get('title', '')}")
    return 0

def _cmd_dsh_run(args: argparse.Namespace) -> int:
    try:
        result = run_card(
            args.ticket_id,
            root=args.root,
            base_url=args.url,
            task_id=args.task_id,
            rerun=args.rerun,
        )
    except (TaskBoardError, ValueError) as exc:
        print(f"DSH: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Triggered {result['action']} for {result['ticket_id']} ({result['task_id']})")
        print(f"Status: {result.get('status', '')}")
    return 0

def _cmd_dsh_archive(args: argparse.Namespace) -> int:
    try:
        result = archive_card(
            args.ticket_id,
            root=args.root,
            base_url=args.url,
            task_id=args.task_id,
        )
    except (TaskBoardError, ValueError) as exc:
        print(f"DSH: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Archived {result['ticket_id']} ({result['task_id']})")
    return 0

def _cmd_dsh_delete(args: argparse.Namespace) -> int:
    try:
        result = delete_card(
            args.ticket_id,
            root=args.root,
            base_url=args.url,
            task_id=args.task_id,
        )
    except (TaskBoardError, ValueError) as exc:
        print(f"DSH: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Deleted {result['ticket_id']} ({result['task_id']})")
    return 0

def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "lint":
        return _cmd_lint(args)
    if args.command == "plan":
        return _cmd_plan(args)
    if args.command == "render":
        return _cmd_render(args)
    if args.command == "context":
        return _cmd_context(args)
    if args.command == "brief":
        return _cmd_brief(args)
    if args.command == "select":
        return _cmd_select(args)
    if args.command == "seat":
        return _cmd_seat(args)
    if args.command == "review-packet":
        return _cmd_review_packet(args)
    if args.command == "align":
        return _cmd_align(args)
    if args.command == "spec":
        return _cmd_spec(args)
    if args.command == "tickets":
        return _cmd_tickets(args)
    if args.command == "checkpoint":
        return _cmd_checkpoint(args)
    if args.command == "closeout":
        return _cmd_closeout(args)
    if args.command == "repair":
        return _cmd_repair(args)
    if args.command == "questions":
        return _cmd_questions(args)

    if args.command == "install-hooks":
        return _cmd_install_hooks(args)
    if args.command == "roots":
        return _cmd_roots(args)
    if args.command == "wrap":
        return _cmd_wrap(args)
    if args.command == "setup":
        return _cmd_setup(args)
    if args.command == "handoff":
        return _cmd_handoff(args)
    if args.command == "doctor":
        return _cmd_doctor(args)
    if args.command == "release":
        return _cmd_release(args)
    if args.command == "retry":
        return _cmd_retry(args)
    if args.command == "confirm":
        return _cmd_confirm(args)
    if args.command == "sign":
        return _cmd_sign(args)
    if args.command == "stage":
        return _cmd_stage(args)
    if args.command == "claim":
        return _cmd_claim(args)
    if args.command == "gc":
        return _cmd_gc(args)
    if args.command == "sweep":
        return _cmd_sweep(args)
    if args.command == "start":
        return _cmd_start(args)
    if args.command == "verify":
        return _cmd_verify(args)
    if args.command == "review":
        return _cmd_review(args)
    if args.command == "land":
        return _cmd_land(args)
    if args.command == "auto":
        return _cmd_auto(args)
    if args.command == "status":
        return _cmd_status(args)
    if args.command == "export":
        return _cmd_export(args)
    if args.command == "assign":
        return _cmd_assign(args)
    if args.command == "personas":
        if args.personas_command == "list":
            return _cmd_personas_list(args)
        if args.personas_command == "show":
            return _cmd_personas_show(args)
        return 2
    if args.command == "dsh":
        if args.dsh_command == "push":
            return _cmd_dsh_push(args)
        if args.dsh_command == "status":
            return _cmd_dsh_status(args)
        if args.dsh_command == "outcome":
            return _cmd_dsh_outcome(args)
        if args.dsh_command == "update":
            return _cmd_dsh_update(args)
        if args.dsh_command == "archive":
            return _cmd_dsh_archive(args)
        if args.dsh_command == "run":
            return _cmd_dsh_run(args)
        if args.dsh_command == "delete":
            return _cmd_dsh_delete(args)
        return 2
    if args.command == "new":
        return _cmd_new(args)
    return 2
