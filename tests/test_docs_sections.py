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


def test_roster_setup_documents_the_obsolete_model() -> None:
    """0.2.2-rc.3 已移除独立 roster；文档应说明作废原因与正确配置，而不是继续教旧做法。"""
    text = read("docs/team/roster-setup.md")
    assert "已随 DSH 0.2.2-rc.3 作废" in text or "作废" in text
    assert "REMOVED_CONFIG_KEYS" in text
    assert "maxMembers" in text          # 只在「被拒绝」的说明里出现
    assert "dsh-agent-team" in text      # 新包名
    assert "dsh-experimental-agent-team" not in text   # 旧包名不该再出现
    assert "不要照着做" in text


def test_skill_documents_the_roster_removal() -> None:
    """SKILL.md 不能再教 maxMembers 扩容或 cleanup_team，要说明新模型。"""
    text = read("SKILL.md")
    assert "没有 `maxMembers`" in text or "没有 maxMembers" in text
    assert "subagent 树" in text
    assert "每树并发 8" in text or "每树并发" in text
    # 旧工具名只允许出现在「已移除」的说明里
    for legacy in ("cleanup_team", "delete_teammate", "rename_teammate"):
        if legacy in text:
            idx = text.index(legacy)
            window = text[max(0, idx - 120): idx + 120]
            assert ("移除" in window) or ("已随" in window), (legacy, window[:160])
