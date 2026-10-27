"""Two-phase execution: a read-only brief must be accepted before code is written.

Phase one answers "what do I think this ticket means". Phase two may touch files
only after that answer was accepted, which is the alignment step a single-shot
card run does not have.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .ticket import Ticket

BRIEF_DIR = Path(".dispatch") / "briefs"
SECTIONS = ("理解的目标", "计划", "准备改动的文件", "风险", "疑问")
HINTS = {
    "理解的目标": "一句话说清这张票要达成什么，以及你判断的边界。",
    "计划": "打算分几步做，每步怎么验证。",
    "准备改动的文件": "逐个列出路径，说明为什么必须改它。",
    "风险": "最可能出错的地方、回滚方式、会不会碰到写域外的文件。",
    "疑问": "不确定的点；没有就写「无」。",
}
PLACEHOLDER_PREFIXES = ("<", "（请", "(请", "todo", "TODO")


def brief_path(root: Path, ticket_id: str) -> Path:
    return Path(root) / BRIEF_DIR / (ticket_id + ".md")


def approval_path(root: Path, ticket_id: str) -> Path:
    return Path(root) / BRIEF_DIR / (ticket_id + "-approval.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render_template(ticket: Ticket) -> str:
    lines: list[str] = [
        "# Brief: " + ticket.id + ": " + ticket.title,
        "",
        "> 只读阶段产物。不要改任何代码；先写清你理解的任务，等待审核。",
        "",
    ]
    for section in SECTIONS:
        lines.extend(["## " + section, "", "<填写：" + HINTS[section] + ">", ""])
    return "\n".join(lines)


def ensure_brief(root: Path, ticket: Ticket) -> Path:
    target = brief_path(root, ticket.id)
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_template(ticket), encoding="utf-8")
    return target


def parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = ""
    buffer: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                sections[current] = "\n".join(buffer).strip()
            current = line[3:].strip()
            buffer = []
            continue
        if current:
            buffer.append(line)
    if current:
        sections[current] = "\n".join(buffer).strip()
    return sections


MIN_SECTION_CHARS = 8


def check_brief_text(text: str) -> tuple[bool, list[str]]:
    sections = parse_sections(text)
    problems: list[str] = []
    bodies: dict[str, str] = {}
    for section in SECTIONS:
        body = sections.get(section, "").strip()
        if not body:
            problems.append("缺少或为空：" + section)
            continue
        if body.startswith(PLACEHOLDER_PREFIXES):
            problems.append("仍是占位内容：" + section)
            continue
        if body.lower().rstrip("。.") in {"无", "none", "n/a", "na"}:
            bodies[section] = body
            continue
        if len(body) < MIN_SECTION_CHARS:
            problems.append(f"太短（至少 {MIN_SECTION_CHARS} 字）：" + section)
            continue
        bodies[section] = body
    if len(bodies) == len(SECTIONS) and len(set(bodies.values())) == 1:
        problems.append("五段内容完全相同，像是占位填充")
    return (not problems, problems)


def check_brief(root: Path, ticket_id: str) -> tuple[bool, list[str]]:
    target = brief_path(root, ticket_id)
    if not target.is_file():
        return False, ["没有 brief：" + str(target) + "（先跑 dispatch brief）"]
    return check_brief_text(target.read_text(encoding="utf-8"))


def approve_brief(root: Path, ticket: Ticket, approver: str) -> Path:
    ok, problems = check_brief(root, ticket.id)
    if not ok:
        raise ValueError("; ".join(problems))
    text = brief_path(root, ticket.id).read_text(encoding="utf-8")
    payload = {
        "ticket_id": ticket.id,
        "approver": approver,
        "approved_at": _now(),
        "brief_sha256": _sha256(text),
        "ticket_hash": ticket.content_hash,
    }
    target = approval_path(root, ticket.id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def approval_status(root: Path, ticket: Ticket) -> tuple[bool, str]:
    target = approval_path(root, ticket.id)
    if not target.is_file():
        return False, "没有 brief 审核记录（先 dispatch brief，再 dispatch brief --approve <人>）"
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return False, "审核记录无法读取：" + str(error)
    brief = brief_path(root, ticket.id)
    if not brief.is_file():
        return False, "审核记录存在但 brief 文件已丢失"
    if payload.get("brief_sha256") != _sha256(brief.read_text(encoding="utf-8")):
        return False, "brief 在审核之后被改动过，需重新审核"
    if payload.get("ticket_hash") != ticket.content_hash:
        return False, "票据在审核之后被改动过，需重新审核"
    return True, "brief 已由 " + str(payload.get("approver", "?")) + " 于 " + str(payload.get("approved_at", "?")) + " 审核"
