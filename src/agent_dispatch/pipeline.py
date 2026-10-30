"""S1..S5 流水线状态：把 ADR-0007 的五个阶段变成可查询、可拦截的门。

设计原则：只读、确定性、不调模型。每一阶段只回答"它齐了没"，以及"下一步该干什么"。
"""

from __future__ import annotations

import hashlib
import json

import hashlib

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
            approved = ("☑ 通过" in stripped) or ("☑ 有保留通过" in stripped)
            rejected = "☑ 打回" in stripped
    has_choice_line = "- 选择：" in text
    if not signer:
        return False, "selection is unsigned: fill '- 签字人：' in " + str(summary)
    if "☑ 打回" in text:
        return False, "selection was rejected (打回) in " + str(summary)
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


def _team_pack_problems(pack: Path) -> list[str]:
    """team 模式：每份证据必须由对应子会话产出（文件头带 Persona 行）。"""
    panel_path = pack / "00-panel.json"
    if not panel_path.is_file():
        return []
    try:
        payload = json.loads(panel_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["00-panel.json 读不出来"]
    if str(payload.get("mode", "solo")) != "team":
        return []
    problems: list[str] = []
    for role in payload.get("roles", []):
        deliverable = str(role.get("deliverable", ""))
        persona = str(role.get("persona", ""))
        path = pack / deliverable
        if not path.is_file():
            problems.append(deliverable + " 不存在")
            continue
        text = path.read_text(encoding="utf-8")
        if ("Persona: " + persona) not in text:
            problems.append(deliverable + " 缺 Persona 行（team 模式必须由对应子会话产出）")
        elif "## What to produce" in text:
            problems.append(deliverable + " 还是 brief 模板（team 模式必须由子会话改写成证据）")
    return problems

def _adversary_says_insufficient(pack: Path) -> bool:
    """03-adversary.md 的结论行是否写着"证据不足"（模板不算）。"""
    path = pack / "03-adversary.md"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if "## What to produce" in text:
        return False
    for raw in text.splitlines():
        line = raw.strip().lstrip("-* ").strip()
        if not line.startswith("结论"):
            continue
        if "证据不足" in line:
            return True
    return False

REVIEW_WINDOW = "07-review-window.json"


def open_review_window(root: Path, slug: str) -> Path:
    """评审窗口开启：给每份证据拍一份 sha256 快照。"""
    pack = pack_dir(Path(root), slug)
    panel_path = pack / "00-panel.json"
    if not panel_path.is_file():
        raise FileNotFoundError("selection pack is missing: docs/selection/" + slug)
    panel = json.loads(panel_path.read_text(encoding="utf-8"))
    files: dict[str, str] = {}
    for role in panel.get("roles", []):
        name = str(role.get("deliverable", ""))
        path = pack / name
        if path.is_file():
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {
        "slug": slug,
        "mode": panel.get("mode", "solo"),
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "closed_at": None,
        "files": files,
        "changed": [],
    }
    target = pack / REVIEW_WINDOW
    target.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def close_review_window(root: Path, slug: str) -> tuple[Path, list[str]]:
    """评审窗口关闭：对比快照，返回被改过的文件。"""
    pack = pack_dir(Path(root), slug)
    target = pack / REVIEW_WINDOW
    if not target.is_file():
        raise FileNotFoundError("review window is not open (run: dispatch review-window " + slug + " --open)")
    record = json.loads(target.read_text(encoding="utf-8"))
    changed: list[str] = []
    for name, expected in dict(record.get("files", {})).items():
        path = pack / str(name)
        if not path.is_file():
            changed.append(str(name) + " (missing)")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != str(expected):
            changed.append(str(name))
    record["closed_at"] = datetime.now(timezone.utc).isoformat()
    record["changed"] = changed
    target.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return target, changed


def review_window_problem(pack: Path) -> str:
    target = pack / REVIEW_WINDOW
    if not target.is_file():
        return "评审窗口未开启（dispatch review-window <slug> --open）"
    try:
        record = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "07-review-window.json 读不出来"
    if not record.get("closed_at"):
        return "评审窗口未关闭（dispatch review-window <slug> --close）"
    changed = record.get("changed") or []
    if changed:
        return "评审窗口内文件被改过：" + ", ".join(str(item) for item in changed)
    return ""

def answer_questionnaire(root: Path, slug: str, answers: list[str]) -> Path:
    """无人值守：按顺序把答案填进问卷的空 `> ` 行（条数必须与空行数一致）。"""
    from .align import questionnaire_path

    path = questionnaire_path(Path(root), slug)
    if not path.is_file():
        raise FileNotFoundError("questionnaire is missing: " + str(path))
    lines = path.read_text(encoding="utf-8").splitlines()
    blanks = [index for index, line in enumerate(lines) if line.strip() == ">"]
    if len(answers) != len(blanks):
        raise ValueError(
            "expected " + str(len(blanks)) + " answer(s), got " + str(len(answers))
        )
    for index, answer in zip(blanks, answers):
        lines[index] = "> " + str(answer).strip()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path

def sign_selection(root: Path, slug: str, by: str, choice: str = "pass", via: str = "", note: str = "") -> Path:
    """把签字写回 99-summary.md：签字人 + 勾选 + 确认方式（dialog / card）。"""
    if via not in VIA_MARKERS:
        raise ValueError("--via must be one of: " + ", ".join(VIA_MARKERS))
    summary = pack_dir(Path(root), slug) / SUMMARY
    if not summary.is_file():
        raise FileNotFoundError("selection pack is missing: docs/selection/" + slug)
    pack = pack_dir(Path(root), slug)
    problems = _team_pack_problems(pack)
    if problems:
        raise ValueError("team 模式下证据不可签字：" + "；".join(problems))
    try:
        panel = json.loads((pack / "00-panel.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        panel = {}
    if str(panel.get("mode", "solo")) == "team":
        window_problem = review_window_problem(pack)
        if window_problem:
            raise ValueError(window_problem)
    if choice == "pass" and _adversary_says_insufficient(pack) and not note:
        raise ValueError(
            "adversary 的结论是「证据不足」：签 pass 必须用 --note 写明要补的证据，或改用 --hold"
        )

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
    recorded = ""
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("- spec_sha256："):
            recorded = stripped.split("：", 1)[1].strip()
    if recorded:
        current = hashlib.sha256(_spec_body(text).encode("utf-8")).hexdigest()
        if recorded != current:
            return None
    return fields


SPEC_SECTIONS = (
    "Problem Statement",
    "Solution",
    "User Stories",
    "Delivery standard",
    "Implementation Decisions",
    "Testing Decisions",
    "Out of Scope",
)

PLACEHOLDER_MARKS = (
    "（从问卷来",
    "（一句话说清",
    "（可命令化的验收项）",
    "（人工核对项）",
    "（…）",
    "As a ... I want ... so that ...",
    "每一行一条可验收项",
)


def spec_placeholder_problems(text: str) -> list[str]:
    """S3 门：确认之前，规格不能是空壳。返回问题清单（空 = 可以确认）。"""
    problems: list[str] = []
    bodies: dict[str, str] = {}
    for name in SPEC_SECTIONS:
        marker = "## " + name
        start = text.find(marker)
        if start < 0:
            problems.append("缺少小节：" + name)
            continue
        body = text[start + len(marker):]
        nxt = body.find("\n## ")
        if nxt >= 0:
            body = body[:nxt]
        body = body.strip()
        bodies[name] = body
        if not body:
            problems.append("小节为空：" + name)
        elif any(mark in body for mark in PLACEHOLDER_MARKS):
            problems.append("仍是占位内容：" + name)
    delivery = bodies.get("Delivery standard", "")
    real_items = [
        line for line in delivery.splitlines()
        if line.strip().startswith("- [") and not any(mark in line for mark in PLACEHOLDER_MARKS)
    ]
    if delivery and not real_items:
        problems.append("Delivery standard 没有真实条目（只有占位 checkbox）")
    return problems


def _spec_body(text: str) -> str:
    """确认块之前的部分（用于指纹）。"""
    index = text.find(CONFIRM_HEADING)
    return text[:index].rstrip() if index >= 0 else text.rstrip()


def confirm_spec(root: Path, slug: str, by: str, via: str, note: str = "", force: bool = False) -> Path:
    """把 S3 的"规格已核对"写进规格文末（幂等：重跑覆盖同一块）。"""
    if via not in VIA_MARKERS:
        raise ValueError("--via must be one of: " + ", ".join(VIA_MARKERS))
    spec = spec_path(Path(root), slug)
    if not spec.is_file():
        raise FileNotFoundError("no spec for " + slug + " (run dispatch spec " + slug + " first)")
    text = spec.read_text(encoding="utf-8")
    problems = [] if force else spec_placeholder_problems(text)
    if problems:
        raise ValueError("spec 还没写完，不能确认：" + "; ".join(problems))
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
            "- spec_sha256：" + hashlib.sha256(_spec_body(text).encode("utf-8")).hexdigest(),
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
