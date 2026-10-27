from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_test_plan_has_the_fresh_review_rule() -> None:
    text = read("docs/testing/test-plan.md")
    assert "文档改动必须由 fresh 会话复现" in text
    assert "外行会卡在哪" in text


def test_test_plan_warns_about_editing_during_a_run() -> None:
    text = read("docs/testing/test-plan.md")
    assert "跑全量期间不要改仓库" in text


def test_roster_setup_documents_the_three_sizes_and_the_rollback_trap() -> None:
    text = read("docs/team/roster-setup.md")
    assert "174.0 MB" in text and "401.5 MB" in text and "1,583" in text
    assert "patchReload" in text  # 只在"这个键不存在"的说明里出现
    assert "10 行" in text
    assert "removed" in text and "回滚" in text


def test_skill_mentions_roster_limits_and_cleanup_hazard() -> None:
    text = read("SKILL.md")
    assert "团队名册：名额与删除" in text
    assert "cleanup_team" in text
    assert "team member limit" in text.lower()
