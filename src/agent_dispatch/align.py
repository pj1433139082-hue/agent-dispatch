"""Requirement alignment artifacts: questionnaire, spec skeleton, ticket drafts.

Thin wrappers over the ask-matt flow. They only write skeletons and run the
gates between stages; the thinking (grilling, selection, spec prose) stays with
the agent. Every artifact is a file so a session restart loses nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

QUESTION_DIR = Path("docs") / "questions"
SPEC_DIR = Path("docs") / "specs"
DRAFT_DIR = Path(".dispatch") / "drafts"

LEVELS = {"quick": 3, "standard": 6, "thorough": 10}

# Question bank, most-blocking first. Each entry is (theme, question, hint).
BANK: list[tuple[str, str, str]] = [
    ("卡点", "五个阶段里哪几处必须停下来等你签字？", "决定自动化程度，也决定子 agent 什么时候能自己往前跑。"),
    ("交付标准", "「交付标准」用什么形式锁定？", "可命令化的验收命令是硬门禁，checkbox 用于人工核对。"),
    ("授权", "子 agent 可以自己做到哪一步？", "只读 / 独立 worktree 写 / 可推分支，逐级放大风险。"),
    ("证据", "技术选型的最低证据要求是什么？", "开源参照要指到具体文件或函数，并写明不采用的理由。"),
    ("落点", "问卷 / 规格 / 票据分别放在哪里？", "决定别人能不能找到，也决定能不能复用。"),
    ("失败处置", "交付不合格时怎么处理？", "回退上一阶段 / 就地补差 / 停下来问。"),
    ("范围", "这次明确不做什么？", "写进 Out of scope，避免规格无边。"),
    ("依赖", "有没有外部依赖需要别人配合？", "接口、账号、现场数据都算。"),
    ("验收人", "最终由谁验收？", "决定 closeout 之后谁签字。"),
    ("节奏", "要一次跑完五段，还是每段单独一轮？", "决定会话切分与上下文传递方式。"),
]


def questionnaire_path(root: Path, slug: str) -> Path:
    return Path(root) / QUESTION_DIR / (slug + ".md")


def spec_path(root: Path, slug: str) -> Path:
    return Path(root) / SPEC_DIR / (slug + ".md")


def drafts_dir(root: Path, slug: str) -> Path:
    return Path(root) / DRAFT_DIR / slug


def normalize_level(value: str) -> str:
    level = value.strip().lower()
    return level if level in LEVELS else "standard"


def render_questionnaire(slug: str, title: str, level: str) -> str:
    level = normalize_level(level)
    count = LEVELS[level]
    questions = BANK[:count]
    themes: list[str] = []
    lines = [
        "# " + title,
        "",
        "**Purpose:** 把这次要做的事对齐到可以写规格的程度。",
        "",
        "**From:** lead · **To:** 甲方 · **How your answers will be used:** 直接转成 spec 的输入。",
        "",
        "## 这次要多细（先答这一条）",
        "",
        "| 档位 | 问题数 | 适合 |",
        "|---|---|---|",
        "| quick | 3 | 已经想清楚，只确认卡点 |",
        "| standard | 6 | 默认，功能需求 + 交付标准 |",
        "| thorough | 10 | 跨团队 / 高风险 / 需要留证 |",
        "",
        "> 当前档位：" + level + "（" + str(count) + " 问）。要换档，改这一行再发我即可。",
        "",
        "## How to answer",
        "",
        "10–20 分钟。没想好写「待定」并说明卡在哪；不确定就直说。",
        "",
    ]
    current = ""
    for theme, question, hint in questions:
        if theme != current:
            lines.extend(["## " + theme, ""])
            current = theme
        lines.extend(["### " + question, "", "_Why this matters: " + hint + "_", "", "> ", ""])
    lines.extend(["## Anything else?", "", "还有什么没问到但会影响落地的？", "", "> ", ""])
    return "\n".join(lines)


def questionnaire_is_answered(path: Path) -> tuple[bool, list[str]]:
    if not path.is_file():
        return False, ["问卷不存在：" + str(path)]
    text = path.read_text(encoding="utf-8")
    pending = [line for line in text.splitlines() if line.strip() in {">", "> "}]
    if pending:
        return False, ["还有 " + str(len(pending)) + " 个问题没填（空引用行）"]
    return True, []


def render_spec(slug: str, title: str, answers: Path) -> str:
    return "\n".join([
        "# Spec: " + title,
        "",
        "> 来源问卷：" + str(answers).replace("\\", "/"),
        "",
        "## Problem Statement",
        "",
        "（从问卷来：甲方现在卡在哪）",
        "",
        "## Solution",
        "",
        "（一句话说清做完之后甲方能做什么）",
        "",
        "## User Stories",
        "",
        "1. As a ... I want ... so that ...",
        "",
        "## Delivery standard",
        "",
        "每一行一条可验收项；需要命令的写成 checkbox + verify 注释。",
        "",
        "- [ ] （可命令化的验收项） <!-- verify: <命令> -->",
        "- [ ] （人工核对项）",
        "",
        "## Implementation Decisions",
        "",
        "- ",
        "",
        "## Testing Decisions",
        "",
        "- ",
        "",
        "## Out of Scope",
        "",
        "- ",
        "",
        "## Further Notes",
        "",
        "- ",
        "",
    ])


DELIVERY_RE = re.compile(r"^\s*[-*]\s+\[ \]\s+(?P<text>.+?)\s*$")


def delivery_items(spec_text: str) -> list[str]:
    items: list[str] = []
    inside = False
    for line in spec_text.splitlines():
        if line.startswith("## "):
            inside = line.strip().lower().startswith("## delivery standard")
            continue
        if not inside:
            continue
        match = DELIVERY_RE.match(line)
        if match:
            text = re.sub(r"<!--.*?-->", "", match.group("text")).strip()
            if text and not text.startswith("（"):
                items.append(text)
    return items


def delivery_diagnosis(spec_text: str) -> tuple[list[str], str]:
    """返回 (items, reason)：reason 说明为什么没有可拆的交付项。"""
    section: list[str] = []
    inside = False
    for line in spec_text.splitlines():
        if line.startswith("## "):
            inside = line.strip().lower().startswith("## delivery standard")
            continue
        if inside:
            section.append(line)
    if not section:
        return [], "the '## Delivery standard' section is missing"
    items = delivery_items(spec_text)
    if items:
        return items, ""
    has_checkbox = any(DELIVERY_RE.match(line) for line in section)
    if has_checkbox:
        return [], "the section only has placeholder checkboxes; replace （…） with real items"
    if any(line.strip().startswith(("-", "*")) for line in section):
        return [], "the section has bullets but no checkbox items; write each item as '- [ ] <text>'"
    return [], "the section is empty; write each item as '- [ ] <text>'"


def render_draft_ticket(number: int, slug: str, item: str) -> str:
    return "\n".join([
        "# " + slug + "-" + str(number).zfill(2) + ": " + item,
        "",
        "## What to build",
        "",
        item,
        "",
        "**Blocked by:** None",
        "**Status:** draft（补齐 Write scope 与 Verify 后改成 ready-for-agent）",
        "",
        "## Dispatch",
        "",
        "- Owner: implementer",
        "- Risk: L1",
        "- Write scope: （待填）",
        "- Verify: （待填，必须可复跑）",
        "",
        "## Acceptance",
        "",
        "- [ ] " + item,
        "",
    ])


def write_drafts(root: Path, slug: str, items: list[str]) -> list[Path]:
    directory = drafts_dir(root, slug)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index, item in enumerate(items, start=1):
        target = directory / (str(index).zfill(2) + "-" + slug + ".md")
        target.write_text(render_draft_ticket(index, slug, item), encoding="utf-8")
        written.append(target)
    return written
