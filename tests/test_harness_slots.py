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
# 0.2.2-rc.3 起 spawn_teammate 已移除（Team 并入 subagent 树），改用仍存在的工具名做"正文不得直接写工具名"的检查
HARNESS_TOOLS = ["list_agents", "send_message", "wait_agent", "ask_user_question"]


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
    assert "spawn_worker" in text and "task" in text


def test_worker_slots_may_merge_on_new_harness_versions() -> None:
    """0.2.2-rc.3 起 DSH 的两个 worker 槽落到同一个 subagent 工具；映射必须说明这件事。"""
    adapters = read("references/harness-adapters.md")
    assert "spawn_once" in adapters
    assert "spawn_worker" in adapters
    assert ("并入" in adapters) or ("同一实现" in adapters)
    assert "subagent" in adapters
def test_absent_slots_have_a_documented_fallback() -> None:
    text = read("references/harness-adapters.md")
    assert "solo" in text
    assert "文件交接" in text
