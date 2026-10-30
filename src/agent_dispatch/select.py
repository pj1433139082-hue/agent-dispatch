"""Selection panel: the agents a technical choice must survive before it is signed.

Stage S2 of ADR-0007. Three roles are mandatory (open-source scout, search
scout, adversary); two more are opt-in; callers can add roles with their own
persona. Each role gets a read-only brief and one evidence file; the summary
holds a signature line for the client, because the selection is theirs to accept.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PANEL_DIR = Path("docs") / "selection"


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    mission: str
    deliverable: str
    persona: str
    required: bool
    evidence: str


DEFAULT_ROLES: tuple[Role, ...] = (
    Role(
        id="oss-scout",
        name="开源借鉴侦察",
        mission="在真实开源项目里找对照实现，为选型提供可核对的参照。",
        deliverable="01-oss.md",
        persona="builtin:oss-scout",
        required=True,
        evidence=">=2 个开源参照，指到具体文件:函数（或提交哈希），并写明不采用的理由",
    ),
    Role(
        id="search-scout",
        name="搜索取证",
        mission="用官方文档与搜索为选型补事实：版本、限制、兼容性、弃用状态。",
        deliverable="02-sources.md",
        persona="builtin:search-scout",
        required=True,
        evidence="每条事实附 URL + 原文摘录 + 抓取日期 + 版本号；查不到写未证实",
    ),
    Role(
        id="adversary",
        name="对抗性审查",
        mission="专门找方案会怎么失败：反例、边界、迁移成本、不可逆点。",
        deliverable="03-adversary.md",
        persona="builtin:adversary",
        required=True,
        evidence="列出方案没写出来的假设，每条给一个能证伪它的最小实验或反例，最多 7 条",
    ),
    Role(
        id="domain-owner",
        name="领域约束",
        mission="守住现场与既有系统的硬约束：环境、网络、停机窗口、运维习惯。",
        deliverable="04-domain.md",
        persona="builtin:domain-owner",
        required=False,
        evidence="硬约束逐条列出，标明绝对不行 / 代价高但可行，并给最小可行落点",
    ),
    Role(
        id="cost-keeper",
        name="成本守护",
        mission="盯体积、性能、依赖与长期维护成本。",
        deliverable="05-cost.md",
        persona="builtin:cost-keeper",
        required=False,
        evidence="新增依赖与体积（gzip）、运行开销、维护活跃度，全部给数字",
    ),
)


def all_roles() -> dict[str, Role]:
    return {role.id: role for role in DEFAULT_ROLES}


def panel(with_optional: list[str] | None = None, extra: list[tuple[str, str]] | None = None) -> list[Role]:
    roles = [role for role in DEFAULT_ROLES if role.required]
    known = all_roles()
    for name in with_optional or []:
        cleaned = name.strip()
        if not cleaned or cleaned in {role.id for role in roles}:
            continue
        role = known.get(cleaned)
        if role is None:
            raise ValueError("unknown optional role: " + cleaned)
        roles.append(role)
    for index, (role_id, persona) in enumerate(extra or [], start=1):
        if not role_id.strip():
            raise ValueError("custom role needs an id")
        roles.append(
            Role(
                id=role_id.strip(),
                name=role_id.strip(),
                mission="由甲方指定的自定义角色，按 persona 执行。",
                deliverable=str(90 + index).zfill(2) + "-" + role_id.strip() + ".md",
                persona=persona.strip() or "(no persona given)",
                required=False,
                evidence="按 persona 自述的判据；结论要能被 lead 复核",
            )
        )
    return roles


def pack_dir(root: Path, slug: str) -> Path:
    return Path(root) / PANEL_DIR / slug


def render_role_brief(slug: str, role: Role, title: str) -> str:
    return "\n".join([
        "# " + role.name + " brief: " + title,
        "",
        "Slug: " + slug,
        "Persona: " + role.persona,
        "",
        "## Mission",
        "",
        role.mission,
        "",
        "## What to produce",
        "",
        "- 写 **" + role.deliverable + "** 到本目录（同 pack 目录下），不要写别的文件。",
        "- 证据门槛：" + role.evidence + "。",
        "- 只读：不改仓库代码、不改票据、不运行有副作用的命令。",
        "",
        "## How to answer",
        "",
        "1. 先写清你回答的问题与判据。",
        "2. 给证据（文件:函数 / URL + 摘录 / 反例实验）。",
        "3. 给结论三态之一：建议采用 / 建议不采用 / 证据不足。",
        "4. 末尾列未证实项。",
        "",
    ])


def render_panel_json(slug: str, title: str, roles: list[Role], mode: str = "solo") -> str:
    import json

    payload = {
        "slug": slug,
        "title": title,
        "stage": "S2 selection",
        "mode": mode,
        "roles": [
            {
                "id": role.id,
                "name": role.name,
                "persona": role.persona,
                "deliverable": role.deliverable,
                "required": role.required,
                "evidence": role.evidence,
            }
            for role in roles
        ],
        "gate": "结论需甲方签字；未签字不得进入 S3",
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_summary(slug: str, title: str, roles: list[Role], mode: str = "solo") -> str:
    lines = [
        "# 选型结论: " + title,
        "",
        "> 汇总各角色证据后填这张表；**结论由甲方签字才算过**（ADR-0007 Q1）。",
        ">",
        "> 产物模式：" + ("team（每份证据由独立子会话产出，文件头必须带 Persona 行）" if mode == "team" else "solo（主代理代做，文件头标注）"),
        "",
        "| 角色 | 结论 | 证据位置 | 未证实项 |",
        "|---|---|---|---|",
    ]
    for role in roles:
        lines.append("| " + role.name + "（" + role.id + "） | 待填 | " + role.deliverable + " | 待填 |")
    lines.extend([
        "",
        "## 决策",
        "",
        "- 采用：",
        "- 不采用：",
        "- 理由：",
        "",
        "## 甲方签字",
        "",
        "- 签字人：",
        "- 日期：",
        "- 备注：",
        "- 选择：☐ 通过　☐ 有保留通过　☐ 打回",
        "",
    ])
    return "\n".join(lines)


def write_pack(root: Path, slug: str, title: str, roles: list[Role], mode: str = "solo") -> list[Path]:
    directory = pack_dir(root, slug)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    panel_file = directory / "00-panel.json"
    panel_file.write_text(render_panel_json(slug, title, roles, mode), encoding="utf-8")
    written.append(panel_file)
    for role in roles:
        target = directory / role.deliverable
        if not target.exists():
            target.write_text(render_role_brief(slug, role, title), encoding="utf-8")
        written.append(target)
    summary = directory / "99-summary.md"
    summary.write_text(render_summary(slug, title, roles, mode), encoding="utf-8")
    written.append(summary)
    return written
