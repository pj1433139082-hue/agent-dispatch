from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_dispatch.brief import check_brief_text  # noqa: E402
from agent_dispatch.context import build_context_pack  # noqa: E402
from agent_dispatch.ticket import load_tickets  # noqa: E402

GOOD = """# Brief: 01

## 理解的目标
创建 hello.txt，内容包含 hello，供下游脚本读取。

## 计划
1. 在执行根新建 hello.txt 并写入 hello。

## 准备改动的文件
- hello.txt —— 新增产物

## 风险
若执行根已有同名文件，会被覆盖；先检查再写。

## 疑问
无。
"""


def test_brief_rejects_filler_text() -> None:
    filler = GOOD.replace("创建 hello.txt，内容包含 hello，供下游脚本读取。", "填好了")
    ok, problems = check_brief_text(filler)
    assert not ok
    assert any("太短" in p for p in problems)


def test_brief_rejects_identical_sections() -> None:
    same = """# Brief: 01

## 理解的目标
这里是一段足够长的内容，但它被复制到了每一段里面。

## 计划
这里是一段足够长的内容，但它被复制到了每一段里面。

## 准备改动的文件
这里是一段足够长的内容，但它被复制到了每一段里面。

## 风险
这里是一段足够长的内容，但它被复制到了每一段里面。

## 疑问
这里是一段足够长的内容，但它被复制到了每一段里面。
"""
    ok, problems = check_brief_text(same)
    assert not ok
    assert any("完全相同" in p for p in problems)


def test_brief_accepts_a_real_brief() -> None:
    ok, problems = check_brief_text(GOOD)
    assert ok, problems


def test_context_mentions_the_attempt_when_retrying(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(
        "# 01: x\n\n**What to build:** x\n**Blocked by:** None\n**Status:** ready-for-agent\n\n"
        "## Dispatch\n\n- Owner: a\n- Risk: L1\n- Write scope: out.txt\n- Verify: true\n\n"
        "## Acceptance\n\n- [ ] x\n",
        encoding="utf-8",
    )
    ticket = load_tickets(tmp_path / "tickets")[0]

    text = build_context_pack(tmp_path, ticket, None, run_attempt=2)

    assert "attempt 2" in text
    assert "first run" not in text
