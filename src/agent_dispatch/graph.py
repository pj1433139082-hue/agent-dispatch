"""Dependency waves and same-wave write-scope conflicts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from .ticket import Ticket


@dataclass(frozen=True)
class ScopeConflict:
    first: str
    second: str
    scopes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {"first": self.first, "second": self.second, "scopes": list(self.scopes)}


@dataclass(frozen=True)
class WavePlan:
    waves: list[list[str]]
    frontier: list[str]
    blocked: dict[str, list[str]]
    conflicts: list[ScopeConflict]
    cycle: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "waves": [list(wave) for wave in self.waves],
            "frontier": list(self.frontier),
            "blocked": {key: list(value) for key, value in sorted(self.blocked.items())},
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "cycle": list(self.cycle),
            "errors": list(self.errors),
        }


def _normalize(scope: str) -> str:
    normalized = scope.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def _glob_regex(pattern: str) -> re.Pattern[str]:
    out: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                out.append(".*")
                index += 2
                continue
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
        index += 1
    out.append("$")
    return re.compile("".join(out))


def _literal_prefix(pattern: str) -> str:
    cut = len(pattern)
    for marker in ("*", "?", "["):
        found = pattern.find(marker)
        if found != -1:
            cut = min(cut, found)
    return pattern[:cut]


def scopes_overlap(first: str, second: str) -> bool:
    """Return True when two write-scope globs can name the same path.

    This is deliberately conservative: it may report a conflict for two broad
    globs that happen not to intersect, but it never lets a literal file pass a
    broad directory glob.
    """
    left = _normalize(first)
    right = _normalize(second)
    if not left or not right:
        return False
    if left == right:
        return True
    if left.startswith(right + "/") or right.startswith(left + "/"):
        return True
    if _glob_regex(left).match(right) or _glob_regex(right).match(left):
        return True
    left_prefix = _literal_prefix(left)
    right_prefix = _literal_prefix(right)
    if left_prefix and right_prefix:
        if left_prefix.startswith(right_prefix) or right_prefix.startswith(left_prefix):
            return True
    return False


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


def build_plan(tickets: list[Ticket], done: set[str] | None = None) -> WavePlan:
    done = set(done or ())
    by_id = {ticket.id: ticket for ticket in tickets}
    pending = {ticket.id: ticket for ticket in tickets if ticket.id not in done}
    errors: list[str] = []

    for ticket in pending.values():
        for dep in ticket.depends_on:
            if dep not in by_id:
                errors.append(f"{ticket.id} depends on missing ticket {dep}")

    known_deps = {
        ticket.id: [dep for dep in ticket.depends_on if dep in by_id and dep not in done]
        for ticket in pending.values()
    }
    cycle_path = _find_cycle(known_deps)
    cycle = sorted(set(cycle_path))
    if cycle_path:
        errors.append("dependency cycle: " + " -> ".join(cycle_path))

    schedulable = {ticket_id: deps for ticket_id, deps in known_deps.items() if ticket_id not in cycle_path}
    remaining = {ticket_id: len(deps) for ticket_id, deps in schedulable.items()}
    waves: list[list[str]] = []
    scheduled: set[str] = set()

    while remaining:
        wave = sorted(ticket_id for ticket_id, count in remaining.items() if count == 0)
        if not wave:
            break
        waves.append(wave)
        scheduled.update(wave)
        for ticket_id in wave:
            remaining.pop(ticket_id, None)
        for ticket_id, deps in schedulable.items():
            if ticket_id in remaining:
                remaining[ticket_id] = len([dep for dep in deps if dep not in scheduled])

    frontier = list(waves[0]) if waves else []
    blocked: dict[str, list[str]] = {}
    for ticket_id, ticket in pending.items():
        if ticket_id in frontier:
            continue
        unresolved = [dep for dep in ticket.depends_on if dep not in done]
        if unresolved:
            blocked[ticket_id] = sorted(unresolved)

    conflicts: list[ScopeConflict] = []
    for wave in waves:
        for index, first_id in enumerate(wave):
            for second_id in wave[index + 1 :]:
                first = by_id[first_id]
                second = by_id[second_id]
                shared = sorted(
                    {
                        left
                        for left in first.write_scope
                        for right in second.write_scope
                        if scopes_overlap(left, right)
                    }
                    | {
                        right
                        for left in first.write_scope
                        for right in second.write_scope
                        if scopes_overlap(left, right)
                    }
                )
                if shared:
                    conflicts.append(
                        ScopeConflict(first=first_id, second=second_id, scopes=tuple(shared))
                    )

    return WavePlan(
        waves=waves,
        frontier=frontier,
        blocked=blocked,
        conflicts=conflicts,
        cycle=cycle,
        errors=sorted(errors),
    )
