from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from agent_dispatch.ticket import parse_ticket

ROOT = Path(__file__).resolve().parents[1]

ROLE_CARD = """---
title: 代码审查员子agent
aliases: [代码审查员, Code Reviewer]
---

# 代码审查员

## 声明式角色卡

```yaml
domain: code
role: reviewer
capabilities:
  - 代码 diff 风险审查
must_call_when:
  - 用户要求 code review
```
"""


def ticket_text() -> str:
    return """# 01: Review the parser

**What to build:** Review the parser change.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Persona: (unassigned)
- Write scope: src/parser.py
- Verify: python -m pytest -q

## Acceptance

- [ ] The review is complete.
"""


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def make_project(tmp_path: Path) -> tuple[Path, Path]:
    tickets = tmp_path / "tickets"
    tickets.mkdir()
    (tickets / "01-review.md").write_text(ticket_text(), encoding="utf-8")
    source = tmp_path / "library" / "reviewer.md"
    source.parent.mkdir()
    source.write_text(ROLE_CARD, encoding="utf-8")
    return tickets, source


def test_assign_copies_persona_and_writes_ticket_field(tmp_path: Path) -> None:
    tickets, source = make_project(tmp_path)

    result = run_dispatch(
        tmp_path, "assign", "01", "--persona", str(source),
        "--tickets", str(tickets), "--root", str(tmp_path), "--by", "dispatcher",
    )

    assert result.returncode == 0, result.stderr
    stored = tickets / "personas" / "reviewer.md"
    assert stored.is_file()
    text = (tickets / "01-review.md").read_text(encoding="utf-8")
    assert "- Persona: personas/reviewer.md" in text
    ticket = parse_ticket(tickets / "01-review.md")
    assert ticket.persona_profile is not None
    assert ticket.persona_profile.name == "代码审查员"
    ledger = (tmp_path / ".dispatch" / "assignments.jsonl").read_text(encoding="utf-8")
    record = json.loads(ledger.splitlines()[0])
    assert record["ticket_id"] == "01"
    assert record["by"] == "dispatcher"
    assert record["persona"] == "personas/reviewer.md"


def test_assign_rejects_a_missing_persona(tmp_path: Path) -> None:
    tickets, _source = make_project(tmp_path)

    result = run_dispatch(
        tmp_path, "assign", "01", "--persona", str(tmp_path / "missing.md"),
        "--tickets", str(tickets), "--root", str(tmp_path),
    )

    assert result.returncode == 1
    assert "PERSONA" in result.stderr
    assert "- Persona: (unassigned)" in (tickets / "01-review.md").read_text(encoding="utf-8")


def test_assign_refuses_after_a_run_exists(tmp_path: Path) -> None:
    tickets, source = make_project(tmp_path)
    state_dir = tmp_path / ".dispatch"
    state_dir.mkdir()
    (state_dir / "state.json").write_text(
        json.dumps({"version": 1, "tickets": {"01": {"run_id": "r1", "state": "claimed"}}}),
        encoding="utf-8",
    )

    result = run_dispatch(
        tmp_path, "assign", "01", "--persona", str(source),
        "--tickets", str(tickets), "--root", str(tmp_path),
    )

    assert result.returncode == 1
    assert "run" in result.stderr.lower()


def test_personas_list_json_discovers_a_search_root(tmp_path: Path) -> None:
    source = tmp_path / "library" / "reviewer.md"
    source.parent.mkdir()
    source.write_text(ROLE_CARD, encoding="utf-8")

    result = run_dispatch(tmp_path, "personas", "list", "--search-root", str(source.parent), "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload[0]["name"] == "代码审查员"
    assert payload[0]["role"] == "reviewer"
    assert payload[0]["domain"] == "code"


def test_personas_show_outputs_the_prompt(tmp_path: Path) -> None:
    source = tmp_path / "library" / "reviewer.md"
    source.parent.mkdir()
    source.write_text(ROLE_CARD, encoding="utf-8")

    result = run_dispatch(tmp_path, "personas", "show", str(source))

    assert result.returncode == 0, result.stderr
    assert "代码审查员" in result.stdout
    assert "代码 diff 风险审查" in result.stdout


def test_codex_export_contains_the_assigned_persona(tmp_path: Path) -> None:
    tickets, source = make_project(tmp_path)
    assigned = run_dispatch(
        tmp_path, "assign", "01", "--persona", str(source),
        "--tickets", str(tickets), "--root", str(tmp_path),
    )
    assert assigned.returncode == 0, assigned.stderr

    result = run_dispatch(tmp_path, "export", "--format", "codex", "--tickets", str(tickets))

    assert result.returncode == 0, result.stderr
    assert "Agent persona: 代码审查员" in result.stdout
    assert "Ticket contract takes precedence" in result.stdout
