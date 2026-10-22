"""S1..S5 流水线状态：把 ADR-0007 的五个阶段变成可查询、可拦截的门。

设计原则：只读、确定性、不调模型。每一阶段只回答"它齐了没"，以及"下一步该干什么"。
"""

from __future__ import annotations

from pathlib import Path

from .align import delivery_items, drafts_dir, questionnaire_is_answered, questionnaire_path, spec_path
from .select import pack_dir

SUMMARY = "99-summary.md"


def selection_signed(root: Path, slug: str) -> tuple[bool, str]:
    """99-summary.md 里"签字人"非空且"选择"勾了通过，才算签字。"""
    summary = pack_dir(Path(root), slug) / SUMMARY
    if not summary.is_file():
        return False, "selection pack is missing: docs/selection/" + slug
    text = summary.read_text(encoding="utf-8")
    signer = ""
    approved = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- 签字人："):
            signer = stripped.split("：", 1)[1].strip()
        if stripped.startswith("- 选择："):
            approved = "☑" in stripped
    has_choice_line = "- 选择：" in text
    if not signer:
        return False, "selection is unsigned: fill '- 签字人：' in " + str(summary)
    if has_choice_line and not approved:
        return False, "selection has no approved box ticked in " + str(summary)
    return True, "signed by " + signer


def _roles_in_pack(root: Path, slug: str) -> list[str]:
    directory = pack_dir(Path(root), slug)
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.md"))


def stage_report(root: Path, slug: str) -> dict[str, object]:
    root = Path(root)
    questionnaire = questionnaire_path(root, slug)
    answered, problems = questionnaire_is_answered(questionnaire) if questionnaire.is_file() else (False, ["questionnaire is missing"])
    s1_ok = questionnaire.is_file() and answered

    roles = _roles_in_pack(root, slug)
    s2_ok = bool(roles)
    signed, signed_note = selection_signed(root, slug)

    spec = spec_path(root, slug)
    items = delivery_items(spec.read_text(encoding="utf-8")) if spec.is_file() else []
    s3_ok = spec.is_file() and bool(items)

    drafts = drafts_dir(root, slug)
    draft_files = sorted(drafts.glob("*.md")) if drafts.is_dir() else []
    tickets_dir = root / "tickets"
    ticket_files = sorted(tickets_dir.glob("*.md")) if tickets_dir.is_dir() else []
    s4_ok = bool(draft_files) or bool(ticket_files)

    stages = {
        "s1": {"ok": s1_ok, "detail": "questionnaire answered" if s1_ok else "; ".join(problems), "path": str(questionnaire)},
        "s2": {"ok": s2_ok and signed, "detail": (signed_note if s2_ok else "selection pack is missing"), "roles": roles},
        "s3": {"ok": s3_ok, "detail": (str(len(items)) + " delivery item(s)") if s3_ok else ("spec is missing" if not spec.is_file() else "spec has no delivery standard items"), "path": str(spec)},
        "s4": {"ok": s4_ok, "detail": str(len(draft_files)) + " draft(s), " + str(len(ticket_files)) + " ticket(s)"},
        "s5": {"ok": bool(ticket_files), "detail": "dispatch the tickets (render + subagent); not auto-run"},
    }

    if not s1_ok:
        next_step = "s1"
    elif not s2_ok:
        next_step = "s2"
    elif not signed:
        next_step = "s2-signature"
    elif not s3_ok:
        next_step = "s3"
    elif not s4_ok:
        next_step = "s4"
    else:
        next_step = ""
    return {"slug": slug, "stages": stages, "next": next_step or "done", "ok": next_step == ""}
