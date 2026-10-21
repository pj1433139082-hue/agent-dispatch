from __future__ import annotations

from pathlib import Path

from agent_dispatch.ticket import lint_tickets, load_tickets, parse_ticket


VALID = """# 01: Build the parser

**What to build:** A planner can parse one ticket and lint it.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/agent_dispatch/ticket.py
- Write scope: tests/test_ticket.py
- Read scope: docs/**
- Verify: python -m pytest tests/test_ticket.py -q

## Acceptance

- [ ] The parser returns the ticket id.
- [ ] The linter accepts a complete ticket.
"""


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_valid_ticket(tmp_path: Path) -> None:
    ticket = parse_ticket(write(tmp_path / "01-parser.md", VALID))

    assert ticket.id == "01"
    assert ticket.title == "Build the parser"
    assert ticket.what_to_build == "A planner can parse one ticket and lint it."
    assert ticket.owner == "implementer"
    assert ticket.risk == "L1"
    assert ticket.depends_on == ()
    assert ticket.write_scope == (
        "src/agent_dispatch/ticket.py",
        "tests/test_ticket.py",
    )
    assert ticket.read_scope == ("docs/**",)
    assert ticket.verify == ("python -m pytest tests/test_ticket.py -q",)
    assert len(ticket.acceptance) == 2
    assert ticket.content_hash


def test_repeated_keys_accumulate(tmp_path: Path) -> None:
    text = VALID.replace(
        "- Verify: python -m pytest tests/test_ticket.py -q",
        "- Verify: python -m pytest tests/test_ticket.py -q\n"
        "- Verify: python -m compileall src",
    )
    ticket = parse_ticket(write(tmp_path / "01-parser.md", text))

    assert ticket.verify == (
        "python -m pytest tests/test_ticket.py -q",
        "python -m compileall src",
    )


def test_parse_none_dependencies(tmp_path: Path) -> None:
    ticket = parse_ticket(write(tmp_path / "01-parser.md", VALID))
    assert ticket.depends_on == ()


def test_lint_reports_missing_fields(tmp_path: Path) -> None:
    text = VALID.replace("- Owner: implementer\n", "").replace(
        "- Risk: L1\n", ""
    ).replace("- Write scope: src/agent_dispatch/ticket.py\n", "").replace(
        "- Write scope: tests/test_ticket.py\n", ""
    ).replace("- Verify: python -m pytest tests/test_ticket.py -q\n", ""
    ).replace("- [ ] The parser returns the ticket id.\n", "").replace(
        "- [ ] The linter accepts a complete ticket.\n", ""
    )
    ticket = parse_ticket(write(tmp_path / "01-parser.md", text))
    issues = lint_tickets([ticket])

    codes = {issue.code for issue in issues}
    assert {"missing_owner", "missing_risk", "missing_write_scope", "missing_verify", "missing_acceptance"} <= codes


def test_lint_rejects_absolute_and_parent_scopes(tmp_path: Path) -> None:
    text = VALID.replace(
        "- Write scope: src/agent_dispatch/ticket.py",
        "- Write scope: /etc/passwd\n- Write scope: ../outside",
    )
    ticket = parse_ticket(write(tmp_path / "01-parser.md", text))
    codes = [issue.code for issue in lint_tickets([ticket])]
    assert codes.count("invalid_scope") == 2


def test_lint_rejects_duplicate_ids(tmp_path: Path) -> None:
    a = parse_ticket(write(tmp_path / "01-a.md", VALID))
    b = parse_ticket(write(tmp_path / "01-b.md", VALID.replace("Build the parser", "Other")))
    issues = lint_tickets([a, b])
    assert any(issue.code == "duplicate_id" for issue in issues)


def test_lint_rejects_self_and_unknown_dependencies(tmp_path: Path) -> None:
    self_dep = VALID.replace("**Blocked by:** None", "**Blocked by:** 01")
    ticket = parse_ticket(write(tmp_path / "01-parser.md", self_dep))
    codes = {issue.code for issue in lint_tickets([ticket])}
    assert "self_dependency" in codes

    unknown = VALID.replace("**Blocked by:** None", "**Blocked by:** 99")
    ticket = parse_ticket(write(tmp_path / "01-parser.md", unknown))
    codes = {issue.code for issue in lint_tickets([ticket])}
    assert "unknown_dependency" in codes


def test_lint_reports_cycle(tmp_path: Path) -> None:
    first = VALID.replace("**Blocked by:** None", "**Blocked by:** 02")
    second = VALID.replace("**Blocked by:** None", "**Blocked by:** 01").replace(
        "# 01: Build the parser", "# 02: Second"
    )
    tickets = [
        parse_ticket(write(tmp_path / "01-a.md", first)),
        parse_ticket(write(tmp_path / "02-b.md", second)),
    ]
    issues = lint_tickets(tickets)
    cycle_issues = [issue for issue in issues if issue.code == "cycle"]
    assert cycle_issues
    assert "01" in cycle_issues[0].message and "02" in cycle_issues[0].message


def test_load_tickets_ignores_non_markdown(tmp_path: Path) -> None:
    write(tmp_path / "01-parser.md", VALID)
    write(tmp_path / "notes.txt", "not a ticket")
    tickets = load_tickets(tmp_path)
    assert [ticket.id for ticket in tickets] == ["01"]
