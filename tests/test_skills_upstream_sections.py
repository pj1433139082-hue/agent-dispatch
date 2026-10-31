from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_dispatch_flow_routes_foggy_work_to_wayfinder() -> None:
    text = read("flow-skill/SKILL.md")
    assert "A0｜雾大" in text
    assert "wayfinder" in text
    assert "决策票" in text


def test_dispatch_flow_has_phase_boundaries_and_external_input() -> None:
    text = read("flow-skill/SKILL.md")
    assert "阶段边界" in text
    for option in ("continue", "clear", "handoff", "subagent", "compact"):
        assert option in text
    assert "外部输入" in text and "triage" in text


def test_tickets_skill_separates_decision_and_execution_tickets() -> None:
    text = read("tickets-skill/SKILL.md")
    assert "决策票 vs 执行票" in text
    assert ".out-of-scope/" in text


def test_implement_skill_requires_alternatives_for_risky_tickets() -> None:
    text = read("implement-skill/SKILL.md")
    assert "方案备选" in text
    assert "Design It Twice" in text
