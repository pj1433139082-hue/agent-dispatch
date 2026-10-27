"""Closeout: the ticket, the brief and the diff must agree before landing.

A reviewer that only looks at verify.json cannot see that the executor changed a
file nobody asked for, or skipped the file the brief promised. Closeout writes
that comparison down as one machine-readable report plus a readable page.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .brief import brief_path
from .state import Run
from .ticket import Ticket
from .verify import changed_files, path_matches_scope

PATHLIKE = ("/", "\\", ".txt", ".py", ".js", ".ts", ".md", ".json", ".css", ".html", ".yml", ".yaml", ".toml", ".mjs")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def declared_files(text: str) -> list[str]:
    """Files a brief promised to touch: bullets that look like paths."""
    found: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(("-", "*")):
            continue
        body = stripped.lstrip("-* ").strip()
        candidate = re.split(r"[\s：:（(，,、]", body, maxsplit=1)[0].strip().strip(chr(96)).strip()
        if not candidate:
            continue
        if any(marker in candidate for marker in PATHLIKE):
            found.append(candidate.rstrip("/"))
    return sorted(set(found))


def collect(root: Path, ticket: Ticket, run: Run) -> dict[str, object]:
    verify = _read_json(run.directory / "verify.json")
    receipt = _read_json(run.directory / "receipt.json")
    base = str(run.data.get("base_commit") or "")
    changed = changed_files(Path(run.execution_root), base) if base else []
    out_of_scope = [
        path for path in changed
        if not any(path_matches_scope(scope, path) for scope in ticket.write_scope)
    ]
    criteria = receipt.get("criteria") or []
    criteria_count = len(criteria) if isinstance(criteria, list) else 0

    brief_file = brief_path(root, ticket.id)
    brief_declared: list[str] = []
    if brief_file.is_file():
        brief_declared = declared_files(brief_file.read_text(encoding="utf-8"))
    changed_not_declared = [
        path for path in changed
        if brief_declared and not any(path == item or path.startswith(item.rstrip("/") + "/") for item in brief_declared)
    ]

    declared_not_changed = [
        item for item in brief_declared
        if not any(path == item or path.startswith(item.rstrip("/") + "/") for path in changed)
    ]

    findings: list[str] = []
    verify_status = str(verify.get("status", ""))
    if not verify:
        findings.append("没有 verify.json：验收没跑过就谈不上收口")
    elif verify_status not in {"passed", "degraded"}:
        findings.append("verify 状态是 " + (verify_status or "?") + "，不是 passed/degraded")
    if criteria_count != len(ticket.acceptance):
        findings.append(
            "回执 criteria " + str(criteria_count) + " 条，票面 acceptance " + str(len(ticket.acceptance)) + " 条，未逐条对应"
        )
    if out_of_scope:
        findings.append("改动越出写域：" + ", ".join(out_of_scope))
    if changed_not_declared:
        findings.append("brief 没声明却改了：" + ", ".join(changed_not_declared))
    if brief_declared and declared_not_changed:
        findings.append("brief 声明了却没改：" + ", ".join(declared_not_changed))

    return {
        "ticket_id": ticket.id,
        "run_id": run.id,
        "checked_at": _now(),
        "verify_status": verify_status or "(missing)",
        "acceptance_count": len(ticket.acceptance),
        "criteria_count": criteria_count,
        "changed_files": changed,
        "out_of_scope": out_of_scope,
        "brief_declared": brief_declared,
        "changed_not_declared": changed_not_declared,
        "findings": findings,
        "status": "pass" if not findings else "fail",
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Closeout: " + str(report["ticket_id"]) + " / " + str(report["run_id"]),
        "",
        "Checked at " + str(report["checked_at"]) + " - **" + str(report["status"]).upper() + "**",
        "",
        "| check | value |",
        "|---|---|",
        "| verify status | " + str(report["verify_status"]) + " |",
        "| acceptance items | " + str(report["acceptance_count"]) + " |",
        "| receipt criteria | " + str(report["criteria_count"]) + " |",
        "| changed files | " + str(len(report["changed_files"])) + " |",
        "| out of write scope | " + str(len(report["out_of_scope"])) + " |",
        "| brief declared | " + str(len(report["brief_declared"])) + " |",
        "",
        "## Findings",
        "",
    ]
    findings = report["findings"]
    if isinstance(findings, list) and findings:
        lines.extend("- " + str(item) for item in findings)
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def write(root: Path, ticket: Ticket, run: Run) -> tuple[Path, dict[str, object]]:
    report = collect(root, ticket, run)
    json_path = run.directory / "closeout.json"
    md_path = run.directory / "closeout.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, report
