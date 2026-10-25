"""Markdown ticket parsing and validation.

A ticket is the authored contract. Runtime state never lives in this file; it
lives in the dispatch state store so that an executor cannot rewrite the brief.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .persona import PERSONA_UNSET, Persona, PersonaError, load_persona

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
HEADING_RE = re.compile(r"^#\s+(?P<id>[^:]+):\s*(?P<title>.+?)\s*$")
SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$")
CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[[ xX]\]\s+(?P<text>.+?)\s*$")
BOLD_RE = re.compile(r"^\s*(?:[-*]\s+)?\*\*(?P<key>[^*]+?):\*\*\s*(?P<value>.*)$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<key>[A-Za-z][A-Za-z ]*?):\s*(?P<value>.*)$")
REQUIRES = {"local", "network", "ssh", "browser"}
RISKS = ("L0", "L1", "L2", "L3", "L4")

_META_KEYS = {
    "owner",
    "risk",
    "write scope",
    "read scope",
    "verify",
    "depends on",
    "blocked by",
    "persona",
}


@dataclass(frozen=True)
class Ticket:
    id: str
    title: str
    path: Path
    what_to_build: str = ""
    status: str = "ready-for-agent"
    owner: str = ""
    risk: str = ""
    depends_on: tuple[str, ...] = ()
    write_scope: tuple[str, ...] = ()
    read_scope: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    verify: tuple[str, ...] = ()
    acceptance: tuple[str, ...] = ()
    persona: str = ""
    persona_profile: Persona | None = field(default=None, compare=False, repr=False)
    persona_error: str = ""

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Issue:
    code: str
    ticket_id: str
    message: str
    level: str = "error"

    def format(self) -> str:
        return f"{self.level.upper()} {self.ticket_id or '-'} {self.code}: {self.message}"


def _clean_value(value: str) -> str:
    return value.strip().strip("`").strip()


def _split_list(value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []
    return [part.strip().strip("`") for part in value.split(",") if part.strip()]


def _dependencies(value: str) -> list[str]:
    value = value.strip()
    if not value or value.lower() in {"none", "none (can start immediately)", "-", "无"}:
        return []
    deps: list[str] = []
    for part in value.split(","):
        dep = part.strip().lstrip("#").strip()
        if dep and dep.lower() not in {"none", "-", "无"}:
            deps.append(dep)
    return deps


def parse_ticket(path: Path) -> Ticket:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    ticket_id = ""
    title = ""
    what_parts: list[str] = []
    status = "ready-for-agent"
    owner = ""
    risk = ""
    depends: list[str] = []
    write_scope: list[str] = []
    read_scope: list[str] = []
    requires: list[str] = []
    verify: list[str] = []
    acceptance: list[str] = []
    persona_spec = ""
    section = ""
    capture_what = False
    in_fence = False

    for raw in lines:
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue

        heading = HEADING_RE.match(line)
        if heading and not ticket_id:
            ticket_id = heading.group("id").strip()
            title = heading.group("title").strip()
            capture_what = False
            continue

        section_match = SECTION_RE.match(line)
        if section_match:
            section = section_match.group("title").strip().lower()
            capture_what = section == "what to build"
            continue

        checkbox = CHECKBOX_RE.match(line)
        if checkbox:
            acceptance.append(checkbox.group("text").strip())
            continue

        bold = BOLD_RE.match(line)
        if bold:
            key = bold.group("key").strip().lower()
            value = bold.group("value").strip()
            if key == "what to build":
                if value:
                    what_parts = [value]
                    capture_what = False
                else:
                    capture_what = True
            elif key == "blocked by":
                depends.extend(_dependencies(value))
                capture_what = False
            elif key == "status":
                status = value or status
                capture_what = False
            elif key == "owner":
                owner = value
                capture_what = False
            elif key == "risk":
                risk = value.upper()
                capture_what = False
            elif key == "write scope":
                write_scope.extend(_split_list(value))
                capture_what = False
            elif key == "read scope":
                read_scope.extend(_split_list(value))
                capture_what = False
            elif key == "verify":
                command = _clean_value(value)
                if command:
                    verify.append(command)
                capture_what = False
            elif key == "persona":
                persona_spec = _clean_value(value)
            elif key == "requires":
                requires.extend(_split_list(value))
                capture_what = False
            elif key in {"depends on", "blocked by"}:
                depends.extend(_dependencies(value))
                capture_what = False
            continue

        if section == "dispatch":
            bullet = BULLET_RE.match(line)
            if bullet:
                key = bullet.group("key").strip().lower()
                value = bullet.group("value").strip()
                if key in {"depends on", "blocked by"}:
                    depends.extend(_dependencies(value))
                elif key == "write scope":
                    write_scope.extend(_split_list(value))
                elif key == "read scope":
                    read_scope.extend(_split_list(value))
                elif key == "verify":
                    command = _clean_value(value)
                    if command:
                        verify.append(command)
                elif key == "owner":
                    owner = value
                elif key == "risk":
                    risk = value.upper()
                elif key == "persona":
                    persona_spec = _clean_value(value)
                elif key == "requires":
                    requires.extend(_split_list(value))
                capture_what = False
                continue

        if section == "verification":
            bullet = re.match(r"^\s*[-*]\s+(?P<value>.+?)\s*$", line)
            if bullet:
                command = _clean_value(bullet.group("value"))
                if command:
                    verify.append(command)
                continue

        if capture_what or section == "what to build":
            if line.strip():
                what_parts.append(line.strip())
            elif what_parts:
                capture_what = False

    if not ticket_id:
        ticket_id = path.stem
    what_to_build = " ".join(part for part in what_parts if part).strip()
    persona = "" if persona_spec.lower() in PERSONA_UNSET else persona_spec
    persona_profile = None
    persona_error = ""
    if persona:
        try:
            persona_profile = load_persona(persona, base_dir=path.parent)
        except PersonaError as exc:
            persona_error = str(exc)
    return Ticket(
        id=ticket_id,
        title=title,
        path=path,
        what_to_build=what_to_build,
        status=status,
        owner=owner,
        risk=risk,
        depends_on=tuple(dict.fromkeys(depends)),
        write_scope=tuple(dict.fromkeys(write_scope)),
        read_scope=tuple(dict.fromkeys(read_scope)),
        requires=tuple(dict.fromkeys(item.lower() for item in requires)),
        verify=tuple(verify),
        acceptance=tuple(acceptance),
        persona=persona,
        persona_profile=persona_profile,
        persona_error=persona_error,
    )


def load_tickets(directory: Path) -> list[Ticket]:
    directory = Path(directory)
    if not directory.exists():
        return []
    return [parse_ticket(path) for path in sorted(directory.glob("*.md"))]


def _scope_error(scope: str, root: Path | None = None) -> str | None:
    if not scope:
        return "empty scope"
    if scope.startswith("/") or re.match(r"^[A-Za-z]:", scope):
        if root is not None:
            try:
                relative = Path(scope).resolve().relative_to(Path(root).resolve())
            except (OSError, ValueError):
                return (
                    "absolute paths are not allowed, and this one is outside the project root; "
                    "write scopes must stay inside the repository"
                )
            return (
                "absolute paths are not allowed; use the relative path "
                + repr(relative.as_posix())
            )
        return "absolute paths are not allowed; use a path relative to the project root"
    normalized = scope.replace("\\", "/")
    if ".." in normalized.split("/"):
        return "parent-directory segments are not allowed"
    if "\\" in scope:
        return "use POSIX separators in scope globs"
    return None


def _find_cycle(edges: dict[str, list[str]]) -> list[str]:
    state: dict[str, int] = {}
    stack: list[str] = []
    position: dict[str, int] = {}

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        position[node] = len(stack)
        stack.append(node)
        for dep in edges.get(node, []):
            if state.get(dep, 0) == 1:
                return stack[position[dep] :] + [dep]
            if state.get(dep, 0) == 0:
                found = visit(dep)
                if found:
                    return found
        stack.pop()
        position.pop(node, None)
        state[node] = 2
        return None

    for node in sorted(edges):
        if state.get(node, 0) == 0:
            found = visit(node)
            if found:
                return found
    return []


PLACEHOLDER_MARKERS = ("待填", "TODO", "TBD", "FIXME")


def _placeholder(value: str) -> bool:
    text = value.strip()
    if not text:
        return True
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def lint_tickets(tickets: Iterable[Ticket], root: Path | None = None) -> list[Issue]:
    tickets = list(tickets)
    issues: list[Issue] = []
    by_id: dict[str, Ticket] = {}
    duplicates: set[str] = set()

    for ticket in tickets:
        if not ID_RE.match(ticket.id):
            issues.append(Issue("invalid_id", ticket.id, "id must match [A-Za-z0-9][A-Za-z0-9._-]*"))
        if not ticket.title:
            issues.append(Issue("missing_title", ticket.id, "a '# <id>: <title>' heading is required"))
        if not ticket.what_to_build:
            issues.append(Issue("missing_what", ticket.id, "What to build is required"))
        if not ticket.owner:
            issues.append(Issue("missing_owner", ticket.id, "Owner is required in the Dispatch section"))
        if not ticket.risk:
            issues.append(Issue("missing_risk", ticket.id, "Risk is required in the Dispatch section"))
        elif ticket.risk not in RISKS:
            issues.append(Issue("invalid_risk", ticket.id, f"risk must be one of {', '.join(RISKS)}"))
        if not ticket.write_scope:
            issues.append(Issue("missing_write_scope", ticket.id, "at least one Write scope is required"))
        if not ticket.verify:
            issues.append(Issue("missing_verify", ticket.id, "at least one Verify command is required"))
        if getattr(ticket, "requires", ()):
            unknown = [item for item in ticket.requires if item not in REQUIRES]
            if unknown:
                issues.append(Issue("invalid_requires", ticket.id, "requires must be one of " + ", ".join(sorted(REQUIRES)) + f" (got {', '.join(unknown)})", level="warning"))
            elif any(item in {"network", "ssh", "browser"} for item in ticket.requires):
                issues.append(Issue("environment_needed", ticket.id, "this ticket declares Requires: " + ", ".join(ticket.requires) + "; make sure the executor can satisfy it", level="warning"))
        for command in ticket.verify:
            lowered = command.lower()
            trivial = (
                lowered.strip() in {"true", "echo ok", "exit 0"}
                or "print(1)" in lowered
                or "print('ok')" in lowered
                or 'print("ok")' in lowered
                or lowered.strip().startswith("echo ")
            )
            if trivial:
                issues.append(Issue("weak_verify", ticket.id, "verify command looks trivially true (it cannot fail): " + command, level="warning"))
            if any(marker in lowered for marker in ("ssh ", "scp ", "curl ", "wget ", "http://", "https://")):
                issues.append(Issue("network_verify", ticket.id, "verify command looks network/remote dependent: " + command + " (prefer a local snapshot)", level="warning"))
        if not ticket.acceptance:
            issues.append(Issue("missing_acceptance", ticket.id, "at least one '- [ ]' acceptance item is required"))
        if ticket.persona and ticket.persona_error:
            issues.append(Issue("invalid_persona", ticket.id, ticket.persona_error))
        for scope in ticket.write_scope:
            if _placeholder(scope):
                issues.append(Issue("placeholder_value", ticket.id, f"write scope {scope!r} is still a placeholder"))
        for command in ticket.verify:
            if _placeholder(command):
                issues.append(Issue("placeholder_value", ticket.id, f"verify {command!r} is still a placeholder"))
        for scope in (*ticket.write_scope, *ticket.read_scope):
            error = _scope_error(scope, root)
            if error:
                issues.append(Issue("invalid_scope", ticket.id, f"{scope!r}: {error}"))
        if ticket.id in by_id:
            duplicates.add(ticket.id)
        else:
            by_id[ticket.id] = ticket

    for duplicate in sorted(duplicates):
        tickets_for_id = [ticket for ticket in tickets if ticket.id == duplicate]
        paths = ", ".join(str(ticket.path.name) for ticket in tickets_for_id)
        issues.append(Issue("duplicate_id", duplicate, f"id is used by more than one ticket: {paths}"))

    edges: dict[str, list[str]] = {}
    for ticket in tickets:
        valid_deps: list[str] = []
        for dep in ticket.depends_on:
            if dep == ticket.id:
                issues.append(Issue("self_dependency", ticket.id, "a ticket cannot depend on itself"))
            elif dep not in by_id:
                issues.append(Issue("unknown_dependency", ticket.id, f"blocking ticket {dep!r} does not exist"))
            else:
                valid_deps.append(dep)
        if ticket.id in by_id:
            edges[ticket.id] = valid_deps

    cycle = _find_cycle(edges)
    if cycle:
        issues.append(Issue("cycle", cycle[0], "dependency cycle: " + " -> ".join(cycle)))

    issues.sort(key=lambda issue: (issue.ticket_id, issue.code, issue.message))
    return issues
