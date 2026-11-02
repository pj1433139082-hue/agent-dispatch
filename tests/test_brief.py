from __future__ import annotations

from pathlib import Path

from agent_dispatch.brief import (
    SECTIONS,
    approval_status,
    approve_brief,
    check_brief,
    check_brief_text,
    ensure_brief,
    render_template,
)
from agent_dispatch.ticket import parse_ticket

TICKET = """# 08: Ship the panel

**What to build:** A panel.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/panel.py
- Verify: python -m pytest tests/test_panel.py -q

## Acceptance

- [ ] The panel ships.
"""


def make_ticket(tmp_path: Path):
    (tmp_path / "tickets").mkdir()
    path = tmp_path / "tickets" / "08-panel.md"
    path.write_text(TICKET, encoding="utf-8")
    return parse_ticket(path)


def filled(text: str) -> str:
    for section in SECTIONS:
        text = text.replace(f"## {section}\n\n<", f"## {section}\n\nreal content <")
    return text


def test_template_lists_every_section(tmp_path: Path) -> None:
    ticket = make_ticket(tmp_path)
    template = render_template(ticket)
    for section in SECTIONS:
        assert f"## {section}" in template


def test_placeholder_brief_fails(tmp_path: Path) -> None:
    ticket = make_ticket(tmp_path)
    ok, problems = check_brief_text(render_template(ticket))
    assert ok is False
    assert len(problems) == len(SECTIONS)


def test_filled_brief_passes_and_can_be_approved(tmp_path: Path) -> None:
    ticket = make_ticket(tmp_path)
    target = ensure_brief(tmp_path, ticket)
    target.write_text(filled(target.read_text(encoding="utf-8")), encoding="utf-8")

    ok, problems = check_brief(tmp_path, ticket.id)
    assert ok is True, problems

    record = approve_brief(tmp_path, ticket, "lead")
    assert record.is_file()
    accepted, why = approval_status(tmp_path, ticket)
    assert accepted is True, why


def test_editing_the_brief_after_approval_invalidates_it(tmp_path: Path) -> None:
    ticket = make_ticket(tmp_path)
    target = ensure_brief(tmp_path, ticket)
    target.write_text(filled(target.read_text(encoding="utf-8")), encoding="utf-8")
    approve_brief(tmp_path, ticket, "lead")

    target.write_text(target.read_text(encoding="utf-8") + "\nextra change\n", encoding="utf-8")

    accepted, why = approval_status(tmp_path, ticket)
    assert accepted is False
    assert "被改动" in why



def _brief_with_self_check(self_check: str) -> str:
    return (
        "## 理解的目标\n\n把这件做完，边界是不碰写域外的文件。\n\n"
        "## 计划\n\n1. 先读代码 2. 再改 3. 跑测试\n\n"
        "## 准备改动的文件\n\n- src/a.py 必须改\n\n"
        "## 写域自检\n\n" + self_check + "\n\n"
        "## 风险\n\n改错就 revert。\n\n"
        "## 疑问\n\n无。\n"
    )


def test_brief_requires_the_three_self_check_answers() -> None:
    """写域自检必须逐条回答 ①②③，不能只写一句「没问题」。

    这条校验来自两次真实返工：票 24 做到一半才发现要改的测试不在写域；
    票 25 的验收要求改 landing.py 而写域里没有。两者都是写票时的矛盾。
    """
    vague = "我仔细看过了，票面验收要求和写域一致，不会碰到写域外的东西。"
    ok, problems = check_brief_text(_brief_with_self_check(vague))

    assert not ok
    assert any("①②③" in item for item in problems), problems


def test_brief_accepts_a_self_check_that_answers_all_three() -> None:
    """逐条答了 ①②③ 的才放行。"""
    answered = (
        "① 验收要求的文件都在 Write scope：是。"
        "② 既有测试断言了要改掉的行为：无。"
        "③ 可能被漏掉的调用点：src/a.py 有三处调用，都要改。"
    )
    ok, problems = check_brief_text(_brief_with_self_check(answered))

    assert ok, problems


def test_brief_allows_self_check_to_be_marked_not_applicable() -> None:
    """纯文档票可以写「无」。"""
    ok, problems = check_brief_text(_brief_with_self_check("无"))

    assert ok, problems
