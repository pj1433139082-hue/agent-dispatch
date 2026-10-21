"""Command-line interface for agent-dispatch."""

from __future__ import annotations

import argparse
import json
import re
import sys
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
from .graph import build_plan
from .landing import LandingError, land_run
from .review import submit_review
from .state import ACTIVE_STATES, DispatchState, Run
from .ticket import Ticket, lint_tickets, load_tickets, parse_ticket
from .verify import verify_run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dispatch", description="Ticketed work dispatch.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lint_parser = subparsers.add_parser("lint", help="Validate ticket files.")
    lint_parser.add_argument("--tickets", type=Path, default=Path("tickets"))
    lint_parser.add_argument("--json", action="store_true", dest="as_json")

    plan_parser = subparsers.add_parser("plan", help="Compute dependency waves.")
    plan_parser.add_argument("--tickets", type=Path, default=Path("tickets"))
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

    start_parser = subparsers.add_parser("start", help="Mark a claimed run as running.")
    start_parser.add_argument("ticket_id")
    start_parser.add_argument("--root", type=Path, default=Path("."))

    verify_parser = subparsers.add_parser("verify", help="Run the independent verification gate.")
    verify_parser.add_argument("ticket_id")
    verify_parser.add_argument("--root", type=Path, default=Path("."))
    verify_parser.add_argument("--timeout", type=int, default=300)

    review_parser = subparsers.add_parser("review", help="Record a reviewer decision.")
    review_parser.add_argument("ticket_id")
    review_parser.add_argument("--reviewer", required=True)
    review_parser.add_argument("--verdict", required=True, choices=("pass", "fail"))
    review_parser.add_argument("--notes", default="")
    review_parser.add_argument("--human", action="store_true")
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
    land_parser.add_argument("ticket_id")
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
    auto_parser.add_argument("--root", type=Path, default=Path("."))
    auto_parser.add_argument("--json", action="store_true", dest="as_json")

    status_parser = subparsers.add_parser("status", help="Show effective ticket states.")
    status_parser.add_argument("--tickets", type=Path, default=None)
    status_parser.add_argument("--root", type=Path, default=Path("."))
    status_parser.add_argument("--json", action="store_true", dest="as_json")

    export_parser = subparsers.add_parser("export", help="Export ready work to another runner.")
    export_parser.add_argument(
        "--format",
        required=True,
        choices=("dsh-team", "dsh-board", "codex", "generic"),
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
    dsh_push.add_argument("--workspace", default=None, help="DSH workspace id; omit to let the board decide.")
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

    new_parser = subparsers.add_parser("new", help="Create a new ticket file.")
    new_parser.add_argument("ticket_id")
    new_parser.add_argument("--title", required=True)
    new_parser.add_argument("--what", default="Describe the work.")
    new_parser.add_argument("--owner", default="implementer")
    new_parser.add_argument("--risk", default="L1", choices=("L0", "L1", "L2", "L3", "L4"))
    new_parser.add_argument("--write-scope", action="append", default=[])
    new_parser.add_argument("--verify", action="append", default=[])
    new_parser.add_argument("--depends-on", action="append", default=[])
    new_parser.add_argument("--tickets", type=Path, default=Path("tickets"))
    return parser


def _tickets_dir(args: argparse.Namespace) -> Path:
    if args.tickets is not None:
        return args.tickets
    root = getattr(args, "root", Path("."))
    return root / "tickets"


def _load_and_lint(directory: Path):
    tickets = load_tickets(directory)
    issues = lint_tickets(tickets)
    if issues:
        for issue in issues:
            print(issue.format(), file=sys.stderr)
        return None, 1
    return tickets, 0


def _cmd_lint(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(args.tickets)
    if tickets is None:
        return code
    if args.as_json:
        print(json.dumps({"tickets": [ticket.id for ticket in tickets]}, indent=2))
    else:
        print(f"{len(tickets)} ticket(s) valid")
    return 0


def _state_map(root: Path) -> dict[str, str]:
    data = DispatchState(root).load()
    return {
        ticket_id: str(value.get("state", ""))
        for ticket_id, value in data.get("tickets", {}).items()
    }


def _cmd_status(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args))
    if tickets is None:
        return code
    document = status_document(tickets, _state_map(args.root))
    if args.as_json:
        print(json.dumps(document, indent=2, ensure_ascii=False))
        return 0
    for row in document["tickets"]:
        suffix = f" (blocked by {', '.join(row['blocked_by'])})" if row["blocked_by"] else ""
        print(f"{row['id']}  {row['state']:<10} {row['title']}{suffix}")
    print(f"Frontier: {', '.join(document['frontier']) or '-'}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args))
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
    directory = args.tickets
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
        *[f"- Write scope: {scope}" for scope in scopes],
        *[f"- Verify: {command}" for command in verify],
        "",
        "## Acceptance",
        "",
        f"- [ ] {args.title} is complete.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Created {path}")
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(args.tickets)
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
    tickets, code = _load_and_lint(_tickets_dir(args))
    if tickets is None:
        return code
    ticket = _find_ticket(tickets, args.ticket_id)
    if ticket is None:
        print(f"unknown ticket: {args.ticket_id}", file=sys.stderr)
        return 1

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

    run = Run.create(
        args.root, ticket, claimed_by=args.agent, use_worktree=not args.no_worktree
    )
    store.set_ticket(ticket.id, run.id, "claimed")
    print(f"Rendered {ticket.id} -> {run.directory}")
    print(f"Run ID: {run.id}")
    if run.data.get("use_worktree"):
        print(f"Execution root: {run.execution_root}")
        print(f"Worktree branch: {run.data.get('worktree_branch', '')}")
    return 0


def _cmd_start(args: argparse.Namespace) -> int:
    store = DispatchState(args.root)
    existing = store.ticket(args.ticket_id)
    if not existing:
        print(f"ticket {args.ticket_id} has no run", file=sys.stderr)
        return 1
    if existing.get("state") != "claimed":
        print(
            f"ticket {args.ticket_id} is {existing.get('state')}, expected claimed",
            file=sys.stderr,
        )
        return 1
    run = Run.load(args.root, str(existing["run_id"]))
    run.set_state("running")
    store.set_ticket(args.ticket_id, run.id, "running")
    print(f"Started {args.ticket_id} ({run.id})")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    store = DispatchState(args.root)
    existing = store.ticket(args.ticket_id)
    if not existing:
        print(f"ticket {args.ticket_id} has no run", file=sys.stderr)
        return 1
    if existing.get("state") != "running":
        print(
            f"ticket {args.ticket_id} is {existing.get('state')}, expected running",
            file=sys.stderr,
        )
        return 1
    run = Run.load(args.root, str(existing["run_id"]))
    ticket = parse_ticket(run.ticket_path)
    record, passed = verify_run(args.root, ticket, run, timeout=args.timeout)
    status = str(record.get("status", "failed"))
    if passed and status == "degraded":
        print(f"Verification degraded for {args.ticket_id} ({run.id})", file=sys.stderr)
        return 2
    if passed:
        print(f"Verification passed for {args.ticket_id} ({run.id})")
        return 0
    for error in record["errors"]:
        print(f"VERIFY {error}", file=sys.stderr)
    print(f"Verification failed for {args.ticket_id} ({run.id})", file=sys.stderr)
    return 1


def _cmd_review(args: argparse.Namespace) -> int:
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
    record, errors = submit_review(
        args.root,
        ticket,
        run,
        reviewer=args.reviewer,
        verdict=args.verdict,
        notes=args.notes,
        human=args.human,
        accept_degraded=args.accept_degraded,
    )
    if errors:
        for error in errors:
            print(f"REVIEW {error}", file=sys.stderr)
        return 1
    print(f"Review {record['verdict']} recorded for {args.ticket_id} ({run.id})")
    return 0


def _cmd_land(args: argparse.Namespace) -> int:
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
    if args.as_json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    print(f"Landed {args.ticket_id} -> {record['integration_branch']}")
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


def _cmd_auto(args: argparse.Namespace) -> int:
    tickets, code = _load_and_lint(_tickets_dir(args))
    if tickets is None:
        return code
    ticket = _find_ticket(tickets, args.ticket_id)
    if ticket is None:
        print(f"unknown ticket: {args.ticket_id}", file=sys.stderr)
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
    tickets, code = _load_and_lint(_tickets_dir(args))
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
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Recorded {result['status']} for {result['ticket_id']} ({result['task_id']})")
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
