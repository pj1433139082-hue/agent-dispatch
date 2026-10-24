"""S1..S5 流水线状态：把 ADR-0007 的五个阶段变成可查询、可拦截的门。

设计原则：只读、确定性、不调模型。每一阶段只回答"它齐了没"，以及"下一步该干什么"。
"""

from __future__ import annotations

from datetime import datetime, timezone
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
            continue
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
    confirmed = spec_confirmation(root, slug) if s3_ok else None

    drafts = drafts_dir(root, slug)
    draft_files = sorted(drafts.glob("*.md")) if drafts.is_dir() else []
    tickets_dir = root / "tickets"
    ticket_files = sorted(tickets_dir.glob("*.md")) if tickets_dir.is_dir() else []
    s4_ok = bool(draft_files) or bool(ticket_files)

    s5_ok = bool(ticket_files)
    stages = {
        "s1": {"ok": s1_ok, "detail": "questionnaire answered" if s1_ok else "; ".join(problems), "path": str(questionnaire)},
        "s2": {"ok": s2_ok and signed, "detail": (signed_note if s2_ok else "selection pack is missing"), "roles": roles},
        "s3": {"ok": s3_ok and confirmed is not None, "detail": (str(len(items)) + " delivery item(s)") if s3_ok else ("spec is missing" if not spec.is_file() else "spec has no delivery standard items"), "path": str(spec)},
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
    elif not confirmed:
        next_step = "s3-confirm"
    elif not s4_ok:
        next_step = "s4"
    elif not s5_ok:
        next_step = "s5"
    else:
        next_step = ""
    if draft_files and next_step == "":
        next_step = "s4-move-drafts"
    return {"slug": slug, "stages": stages, "next": next_step or "done", "ok": next_step == ""}


def _question(qid: str, header: str, question: str, options: list[tuple[str, str]]) -> dict[str, object]:
    return {
        "id": qid,
        "header": header,
        "question": question,
        "options": [{"label": label, "description": description} for label, description in options],
    }


def stage_prompt(root: Path, slug: str) -> dict[str, object]:
    """当前卡点要人回答什么——给会话层喂弹窗或决策卡用。"""
    report = stage_report(root, slug)
    step = str(report["next"])
    questions: list[dict[str, object]] = []
    hint = ""

    if step == "s1":
        questions.append(
            _question(
                "s1-tier",
                "S1 需求问卷",
                "问卷已经生成，先选提问颗粒度还是直接开始答？",
                [("现在答", "我逐题回答 docs/questions/" + slug + ".md"), ("先看问卷", "先把问题发给我看")],
            )
        )
        hint = "答案写进 docs/questions/" + slug + ".md 的 > 行"
    elif step == "s2":
        questions.append(
            _question(
                "s2-roles",
                "S2 选型角色",
                "选型要带哪些角色？三角色（开源借鉴 / 搜索取证 / 对抗审查）是必选的。",
                [
                    ("标准三角色", "只跑必选的三个"),
                    ("加领域约束", "另加 domain-owner"),
                    ("加成本守护", "另加 cost-keeper"),
                    ("两者都加", "domain-owner + cost-keeper"),
                ],
            )
        )
        hint = "按选择运行 dispatch select " + slug + " --with ..."
    elif step == "s2-signature":
        questions.append(
            _question(
                "s2-signature",
                "S2 选型签字",
                "选型证据包已生成，是否通过？",
                [
                    ("通过", "结论采纳，进入 S3"),
                    ("有保留通过", "采纳但有保留项，写进备注"),
                    ("打回", "结论不成立，退回重做"),
                ],
            )
        )
        hint = "把答案写回 docs/selection/" + slug + "/99-summary.md 的签字行（或运行 dispatch sign " + slug + " --by <人>）"
    elif step == "s3":
        questions.append(
            _question(
                "s3-spec",
                "S3 规格确认",
                "规格里的交付标准需要你确认：每条是否都该交付？",
                [("已核对，继续拆票", "按当前交付标准拆票"), ("要改", "我先改规格")],
            )
        )
        hint = "交付项写在 docs/specs/" + slug + ".md 的 ## Delivery standard，每条一个 '- [ ]'"
    return {"slug": slug, "stage": step or "done", "questions": questions, "answer_hint": hint}


VIA_MARKERS = ("dialog", "card")


def _today() -> str:
    from datetime import date

    return date.today().isoformat()


def sign_selection(root: Path, slug: str, by: str, choice: str = "pass", via: str = "", note: str = "") -> Path:
    """把签字写回 99-summary.md：签字人 + 勾选 + 确认方式（dialog / card）。"""
    if via not in VIA_MARKERS:
        raise ValueError("--via must be one of: " + ", ".join(VIA_MARKERS))
    summary = pack_dir(Path(root), slug) / SUMMARY
    if not summary.is_file():
        raise FileNotFoundError("selection pack is missing: docs/selection/" + slug)
    labels = {"pass": "通过", "hold": "有保留通过", "reject": "打回"}
    label = labels.get(choice, "通过")
    lines = summary.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- 签字人："):
            out.append("- 签字人：" + by)
            continue
        if stripped.startswith("- 确认方式："):
            out.append("- 确认方式：" + via)
            continue
        if stripped.startswith("- 日期："):
            out.append("- 日期：" + _today())
            continue
        if note and stripped.startswith("- 备注："):
            out.append("- 备注：" + note)
            continue
        if stripped.startswith("- 选择："):
            boxes = []
            for option in ("通过", "有保留通过", "打回"):
                mark = "☑" if option == label else "☐"
                boxes.append(mark + " " + option)
            out.append("- 选择：" + "　".join(boxes))
            continue
        out.append(line)
    if not any(line.startswith("- 选择：") for line in out):
        boxes = "　".join(("☑ " if option == label else "☐ ") + option for option in ("通过", "有保留通过", "打回"))
        out.append("- 选择：" + boxes)
    out.append("- 确认方式：" + via)
    summary.write_text("\n".join(out) + "\n", encoding="utf-8")
    return summary


CONFIRM_HEADING = "## Confirmation"


def spec_confirmation(root: Path, slug: str) -> dict[str, object] | None:
    """读规格里的确认块：有核对人且确认方式合法才算确认过。"""
    spec = spec_path(Path(root), slug)
    if not spec.is_file():
        return None
    text = spec.read_text(encoding="utf-8")
    index = text.find(CONFIRM_HEADING)
    if index < 0:
        return None
    block = text[index:]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        stripped = line.strip()
        for key in ("核对人", "日期", "确认方式", "备注"):
            prefix = "- " + key + "："
            if stripped.startswith(prefix):
                fields[key] = stripped[len(prefix):].strip()
    if not fields.get("核对人") or fields.get("确认方式") not in VIA_MARKERS:
        return None
    return fields


def confirm_spec(root: Path, slug: str, by: str, via: str, note: str = "") -> Path:
    """把 S3 的"规格已核对"写进规格文末（幂等：重跑覆盖同一块）。"""
    if via not in VIA_MARKERS:
        raise ValueError("--via must be one of: " + ", ".join(VIA_MARKERS))
    spec = spec_path(Path(root), slug)
    if not spec.is_file():
        raise FileNotFoundError("no spec for " + slug + " (run dispatch spec " + slug + " first)")
    text = spec.read_text(encoding="utf-8")
    index = text.find(CONFIRM_HEADING)
    if index >= 0:
        text = text[:index].rstrip() + "\n"
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    block = "\n".join(
        [
            CONFIRM_HEADING,
            "",
            "- 核对人：" + by,
            "- 日期：" + stamp,
            "- 确认方式：" + via,
            "- 备注：" + (note.strip() or "（无）"),
            "",
        ]
    )
    spec.write_text(text.rstrip() + "\n\n" + block, encoding="utf-8")
    return spec


def grill_questions(root: Path, slug: str) -> list[dict[str, object]]:
    """把 adversary 的假设 + oss 里没写"不采用理由"的参照，变成可以直接问的问题。"""
    folder = pack_dir(Path(root), slug)
    adversary = folder / "03-adversary.md"
    if not folder.is_dir():
        raise FileNotFoundError("selection pack is missing: docs/selection/" + slug)
    items: list[dict[str, object]] = []
    text = adversary.read_text(encoding="utf-8") if adversary.is_file() else ""
    if "## What to produce" in text or "Persona: builtin:adversary" in text:
        raise ValueError(
            "03-adversary.md 还是模板：先让 adversary 把假设与反例写进去，再跑 questions"
        )
    lines: list[str] = []
    skipped: list[str] = []
    if adversary.is_file():
        in_assumptions = False
        has_assumption_section = any(
            heading.strip().startswith("#") and "假设" in heading
            for heading in adversary.read_text(encoding="utf-8").splitlines()
        )
        for raw in adversary.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if stripped.startswith("#"):
                in_assumptions = "假设" in stripped
                continue
            if has_assumption_section and not in_assumptions:
                continue
            line = stripped
            if not line.startswith(("- ", "* ")):
                continue
            text = line[2:].strip()
            if not text or text.startswith("<") or "TODO" in text:
                skipped.append("占位：" + text[:30])
                continue
            if text.startswith("写 ") or text.startswith("证据门槛") or text.startswith("只读"):
                skipped.append("模板说明：" + text[:30])
                continue
            lines.append(text)
    if skipped:
        import sys as _sys

        _sys.stderr.write(
            "questions: 跳过 %d 条（模板说明/占位），要变成问题请改写后再跑\n" % len(skipped)
        )
    if len(lines) > 20:
        import sys as _sys2

        _sys2.stderr.write("questions: 只取前 20 条假设（共 %d 条）\n" % len(lines))
    for index, text in enumerate(lines[:20], start=1):
        items.append(
            {
                "id": f"adversary-{index}",
                "header": "对抗审查",
                "question": f"这条假设成立吗：{text}",
                "options": [
                    {"label": "成立", "description": "按这个假设继续"},
                    {"label": "不成立", "description": "写下反例，我据此改方案"},
                    {"label": "不确定", "description": "先做最小实验验证再定"},
                ],
            }
        )
    return items
