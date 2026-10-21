from __future__ import annotations

from pathlib import Path

import pytest

from agent_dispatch.persona import PersonaError, discover_personas, load_persona, persona_section
from agent_dispatch.ticket import lint_tickets, parse_ticket


ROLE_CARD = """---
title: 代码审查员子agent
aliases: [代码审查员, Code Reviewer]
---

# 代码审查员

负责审查代码 diff 的运行时风险。

## 声明式角色卡

```yaml
domain: code
role: reviewer
capabilities:
  - 代码 diff 风险审查
  - 输出生产级 findings
must_call_when:
  - 用户要求 code review
forbidden_actions:
  - 直接修复或合并
```
"""


AGENCY_CARD = """---
name: Code Reviewer
description: Expert code reviewer.
color: purple
---

# Code Reviewer Agent

You are **Code Reviewer**, an expert reviewer.
"""


VALID = """# 01: Build the parser

**What to build:** A planner can parse one ticket and lint it.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Persona: personas/reviewer.md
- Write scope: src/agent_dispatch/ticket.py
- Verify: python -m pytest -q

## Acceptance

- [ ] The parser returns the ticket id.
"""


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_local_declarative_role_card(tmp_path: Path) -> None:
    path = write(tmp_path / "代码审查员子agent.md", ROLE_CARD)

    persona = load_persona(str(path))

    assert persona.name == "代码审查员"
    assert persona.domain == "code"
    assert persona.role == "reviewer"
    assert persona.capabilities == ("代码 diff 风险审查", "输出生产级 findings")
    assert persona.must_call_when == ("用户要求 code review",)
    assert persona.prompt.startswith("# 代码审查员")
    assert "title:" not in persona.prompt


def test_loads_agency_style_frontmatter(tmp_path: Path) -> None:
    path = write(tmp_path / "engineering-code-reviewer.md", AGENCY_CARD)

    persona = load_persona(str(path))

    assert persona.name == "Code Reviewer"
    assert persona.description == "Expert code reviewer."
    assert persona.role == ""
    assert persona.prompt.startswith("# Code Reviewer Agent")


def test_discover_personas_skips_plain_markdown(tmp_path: Path) -> None:
    write(tmp_path / "代码审查员子agent.md", ROLE_CARD)
    write(tmp_path / "engineering-code-reviewer.md", AGENCY_CARD)
    write(
        tmp_path / "notes" / "20-返修回信模板.md",
        "---\ntitle: 20-返修回信模板\ntags: [kind/template]\n---\n\n# 20-返修回信模板\n\n正文。\n",
    )
    write(tmp_path / "notes" / "adr.md", "# ADR 0001\n\n只记录决策。\n")

    names = {persona.name for persona in discover_personas([tmp_path])}

    assert names == {"代码审查员", "Code Reviewer"}

def test_missing_persona_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(PersonaError):
        load_persona(str(tmp_path / "missing.md"))


def test_ticket_parses_persona_and_lints(tmp_path: Path) -> None:
    write(tmp_path / "personas" / "reviewer.md", ROLE_CARD)
    ticket = parse_ticket(write(tmp_path / "01-parser.md", VALID))

    assert ticket.persona == "personas/reviewer.md"
    assert ticket.persona_profile is not None
    assert ticket.persona_profile.name == "代码审查员"
    assert ticket.persona_error == ""
    assert lint_tickets([ticket]) == []


def test_ticket_reports_unreadable_persona(tmp_path: Path) -> None:
    ticket = parse_ticket(write(tmp_path / "01-parser.md", VALID))

    assert ticket.persona == "personas/reviewer.md"
    assert ticket.persona_profile is None
    assert ticket.persona_error
    issues = lint_tickets([ticket])
    assert [issue.code for issue in issues] == ["invalid_persona"]


def test_persona_section_is_compact_and_contract_first(tmp_path: Path) -> None:
    write(tmp_path / "personas" / "reviewer.md", ROLE_CARD)
    ticket = parse_ticket(write(tmp_path / "01-parser.md", VALID))

    text = persona_section(ticket)

    assert "Agent persona: 代码审查员" in text
    assert "Role: reviewer" in text
    assert "代码 diff 风险审查" in text
    assert "用户要求 code review" in text
    assert "Ticket contract takes precedence" in text


def test_persona_section_is_empty_when_unassigned(tmp_path: Path) -> None:
    text = VALID.replace("- Persona: personas/reviewer.md\n", "")
    ticket = parse_ticket(write(tmp_path / "01-parser.md", text))

    assert persona_section(ticket) == ""
