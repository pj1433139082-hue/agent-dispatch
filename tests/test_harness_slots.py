from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = [
    "SKILL.md",
    "grill-skill/SKILL.md",
    "spec-skill/SKILL.md",
    "tickets-skill/SKILL.md",
    "implement-skill/SKILL.md",
    "implement-spec-skill/SKILL.md",
    "flow-skill/SKILL.md",
    "setup-skill/SKILL.md",
]
SLOTS = ["ask", "shell", "spawn_worker", "spawn_once", "list_workers", "message", "wait"]
# NOTE: `subagent` is deliberately absent -- it is also a *phase-boundary option name*
# (continue/clear/handoff/subagent/compact), so "no bare tool names" cannot be asserted for it.
HARNESS_TOOLS = ["spawn_teammate", "list_agents", "send_message", "wait_agent", "ask_user_question"]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_harness_adapters_doc_covers_every_slot() -> None:
    text = read("references/harness-adapters.md")
    for slot in SLOTS:
        assert "`" + slot + "`" in text, slot
    for harness in ("DSH", "千问办公", "Claude Code", "Codex"):
        assert harness in text, harness


def test_skills_speak_in_capability_slots() -> None:
    for rel in SKILLS:
        text = read(rel)
        for name in HARNESS_TOOLS:
            for line in text.splitlines():
                if name not in line:
                    continue
                # 允许"槽名 + 具体实现"的说明性写法，但正文必须以槽为主语
                assert ("槽" in line) or ("DSH=" in line) or ("千问办公=" in line), (rel, name, line.strip()[:120])


def test_team_mode_documents_both_spawn_workers() -> None:
    text = read("grill-skill/SKILL.md")
    assert "spawn_worker" in text
    assert "spawn_once" in text
    assert "spawn_teammate" in text and "task" in text


def test_worker_slots_are_not_interchangeable() -> None:
    """A one-shot executor is not on the roster: team tools must not be used to find it."""
    adapters = read("references/harness-adapters.md")
    assert "spawn_once" in adapters
    assert "not found" in adapters
    assert "不能互换" in adapters
    flow = read("flow-skill/SKILL.md")
    assert "| subagent |" in flow
    assert "| teammate |" in flow


def test_absent_slots_have_a_documented_fallback() -> None:
    text = read("references/harness-adapters.md")
    assert "solo" in text
    assert "文件交接" in text
