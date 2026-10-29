"""Agent persona loading and rendering.

A ticket's Persona field points at a Markdown persona source.  The source can
be a local declarative role card (YAML frontmatter plus a "声明式角色卡"
fenced block), an agency-style agent prompt (frontmatter plus body), a GSD
agent prompt (frontmatter plus XML body), or a ruflo SKILL.md (one or two
leading YAML blocks).  Only the standard library is used.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .ticket import Ticket

MAX_PROMPT_CHARS = 12000
PERSONA_UNSET = {"", "-", "none", "(none)", "unassigned", "(unassigned)", "tbd", "未分配", "无"}
BUILTIN_PERSONA_DIR = Path(__file__).resolve().parents[2] / "agents" / "personas"


class PersonaError(ValueError):
    """A persona source could not be found or read."""


@dataclass(frozen=True)
class Persona:
    name: str
    path: Path
    source: str
    role: str = ""
    domain: str = ""
    description: str = ""
    capabilities: tuple[str, ...] = ()
    must_call_when: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = ()
    prompt: str = ""
    declared: bool = True


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _scalar(value: str) -> str | list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_strip_quotes(part) for part in inner.split(",") if part.strip()]
    return _strip_quotes(value)


def _parse_yaml_block(block: list[str]) -> dict[str, str | list[str]]:
    data: dict[str, str | list[str]] = {}
    index = 0
    while index < len(block):
        line = block[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not match:
            index += 1
            continue
        key = match.group(1)
        raw = match.group(2).strip()
        if raw in {"|", ">"}:
            index += 1
            captured: list[str] = []
            while index < len(block) and (block[index].startswith("  ") or not block[index].strip()):
                captured.append(block[index][2:] if block[index].startswith("  ") else "")
                index += 1
            data[key] = "\n".join(captured).strip()
            continue
        if not raw:
            index += 1
            items: list[str] = []
            while index < len(block):
                item = re.match(r"^\s*-\s+(.+)$", block[index])
                if not item:
                    break
                items.append(_strip_quotes(item.group(1).strip()))
                index += 1
            data[key] = items
            continue
        data[key] = _scalar(raw)
        index += 1
    return data


def _looks_like_metadata(block: list[str]) -> bool:
    keys = {
        "name",
        "title",
        "description",
        "domain",
        "role",
        "type",
        "capabilities",
        "must_call_when",
        "aliases",
        "vibe",
    }
    for line in block:
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):", line)
        if match and match.group(1) in keys:
            return True
    return False


def _split_frontmatter(text: str) -> tuple[list[list[str]], str]:
    lines = text.splitlines()
    blocks: list[list[str]] = []
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    while index < len(lines) and lines[index].strip() == "---":
        end = index + 1
        while end < len(lines) and lines[end].strip() != "---":
            end += 1
        if end >= len(lines):
            break
        block = lines[index + 1 : end]
        if not blocks or _looks_like_metadata(block):
            blocks.append(block)
        index = end + 1
        while index < len(lines) and not lines[index].strip():
            index += 1
    return blocks, "\n".join(lines[index:]).strip()


def _role_card_block(text: str) -> list[str]:
    heading = re.search(r"^##\s+(?:声明式角色卡|Role card|Role Card)\s*$", text, re.MULTILINE)
    if not heading:
        return []
    remainder = text[heading.end() :]
    fence = re.search(r"\x60{3}(?:yaml|yml)\s*\n(.*?)\x60{3}", remainder, re.DOTALL | re.IGNORECASE)
    if not fence:
        return []
    return fence.group(1).splitlines()


def _merge(metadata: dict[str, str | list[str]], extra: dict[str, str | list[str]]) -> None:
    for key, value in extra.items():
        if isinstance(value, list):
            existing = metadata.get(key)
            if isinstance(existing, list):
                metadata[key] = [*existing, *value]
            elif isinstance(existing, str) and existing:
                metadata[key] = [existing, *value]
            else:
                metadata[key] = value
        elif key not in metadata or not metadata[key]:
            metadata[key] = value


def _as_list(value: str | list[str] | None) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(item for item in value if item)
    if isinstance(value, str) and value:
        return (value,)
    return ()


def _as_text(value: str | list[str] | None) -> str:
    if isinstance(value, list):
        return ", ".join(value)
    return value or ""


def _meaningful(value: str | list[str] | None) -> bool:
    if isinstance(value, list):
        return any(item.strip() and not item.strip().startswith("<") for item in value)
    return bool(value and value.strip() and not value.strip().startswith("<"))


def _display_name(metadata: dict[str, str | list[str]], path: Path) -> str:
    name = _as_text(metadata.get("name")) or _as_text(metadata.get("title"))
    aliases = _as_list(metadata.get("aliases"))
    if not name and aliases:
        name = aliases[0]
    if not name:
        name = path.stem
    return re.sub(r"子agent$", "", name).strip() or path.stem


def _first_paragraph(body: str) -> str:
    for block in re.split(r"\n\s*\n", body):
        text = " ".join(line.strip() for line in block.splitlines() if line.strip())
        if not text or text.startswith("#") or text.startswith("\x60\x60\x60"):
            continue
        return text
    return ""


def _candidate_paths(spec: str, base_dir: Path | None) -> list[Path]:
    expanded = Path(os.path.expanduser(os.path.expandvars(spec)))
    if expanded.is_absolute():
        return [expanded]
    candidates: list[Path] = []
    for root in [base_dir, Path.cwd(), BUILTIN_PERSONA_DIR]:
        if root is not None:
            candidates.append(Path(root) / expanded)
    for raw_root in os.environ.get("AGENT_DISPATCH_PERSONA_ROOTS", "").split(os.pathsep):
        if raw_root.strip():
            candidates.append(Path(raw_root.strip()) / expanded)
    if not expanded.suffix:
        candidates.extend(
            path.with_suffix(".md") for path in list(candidates) if path.suffix == ""
        )
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(candidate)
    return unique


def load_persona(spec: str, *, base_dir: Path | None = None) -> Persona:
    """Load a persona file from an explicit path or a searchable short name."""
    raw = spec.strip().strip("\x60").strip()
    if raw.lower() in PERSONA_UNSET:
        raise PersonaError("persona is unassigned")
    candidates = _candidate_paths(raw, base_dir)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        searched = ", ".join(str(candidate) for candidate in candidates[:7])
        raise PersonaError(f"persona source not found: {raw!r} (searched: {searched})")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PersonaError(f"cannot read persona {path}: {exc}") from exc

    blocks, body = _split_frontmatter(text)
    role_card = _role_card_block(text)
    metadata: dict[str, str | list[str]] = {}
    for block in blocks:
        _merge(metadata, _parse_yaml_block(block))
    _merge(metadata, _parse_yaml_block(role_card))

    declared = any(
        _meaningful(metadata.get(key))
        for key in ("role", "capabilities", "must_call_when", "vibe", "tools", "color", "emoji")
    )
    if not declared:
        path_parts = {part.lower() for part in path.parts}
        declared = bool(
            _meaningful(metadata.get("name"))
            and _meaningful(metadata.get("description"))
            and ({"agents", "agency-agents-main"} & path_parts)
        )

    name = _display_name(metadata, path)
    description = _as_text(metadata.get("description")) or _as_text(metadata.get("vibe"))
    if not description:
        description = _first_paragraph(body)
    prompt = body
    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[:MAX_PROMPT_CHARS].rstrip() + "\n\n[persona prompt truncated]"
    return Persona(
        name=name,
        path=path,
        source=raw,
        role=_as_text(metadata.get("role")) or _as_text(metadata.get("type")),
        domain=_as_text(metadata.get("domain")),
        description=description,
        capabilities=_as_list(metadata.get("capabilities")),
        must_call_when=_as_list(metadata.get("must_call_when")),
        forbidden_actions=_as_list(metadata.get("forbidden_actions")),
        prompt=prompt,
        declared=declared,
    )


def discover_personas(roots: Iterable[Path]) -> list[Persona]:
    """Load every Markdown persona under the given roots, ignoring bad files."""
    found: dict[Path, Persona] = {}
    for root in roots:
        root = Path(root)
        paths: list[Path] = []
        if root.is_file() and root.suffix.lower() == ".md":
            paths = [root]
        elif root.is_dir():
            paths = sorted(root.rglob("*.md"))
        for path in paths:
            try:
                persona = load_persona(str(path), base_dir=path.parent)
            except PersonaError:
                continue
            if not persona.declared:
                continue
            found.setdefault(path.resolve(), persona)
    return sorted(found.values(), key=lambda persona: (persona.name.lower(), str(persona.path)))


PERSONA_POLICY_OFF = {"off", "none", "optional"}
PERSONA_POLICY_THRESHOLDS = {
    "l2": {"L2", "L3", "L4"},
    "l3": {"L3", "L4"},
    "l4": {"L4"},
}


def persona_policy(root) -> str:
    """读 .dispatch/config.json 的 persona_policy（缺省 l2）。"""
    path = Path(str(root)) / ".dispatch" / "config.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "l2"
    return str(payload.get("persona_policy", "l2")).lower()


def persona_required(risk: str, policy: str) -> bool:
    """L2+ (默认) 是否强制要求人格：policy=off 一律不强制。"""
    if policy in PERSONA_POLICY_OFF:
        return False
    return risk in PERSONA_POLICY_THRESHOLDS.get(policy, {"L2", "L3", "L4"})


def persona_source_path(root, source: str):
    """把票面的 Persona 字符串解析成角色卡文件（builtin: 走技能内置目录）。"""
    if not source:
        return None
    if source.startswith("builtin:"):
        return BUILTIN_PERSONA_DIR / (source.split(":", 1)[1] + ".md")
    candidate = Path(source)
    if candidate.is_absolute():
        return candidate
    direct = Path(str(root)) / candidate
    if direct.is_file():
        return direct
    return Path(str(root)) / "tickets" / candidate


def persona_fingerprint(ticket, root=None) -> dict[str, str] | None:
    """Bind the persona bytes at render time: source, name, sha256."""
    source = str(getattr(ticket, "persona", "") or "")
    profile = getattr(ticket, "persona_profile", None)
    if not source or profile is None:
        return None
    try:
        digest = hashlib.sha256(profile.path.read_bytes()).hexdigest()
    except OSError:
        return None
    recorded = source
    if root is not None:
        try:
            recorded = profile.path.resolve().relative_to(Path(str(root)).resolve()).as_posix()
        except (OSError, ValueError):
            recorded = str(profile.path.resolve())
    return {"source": recorded, "name": profile.name, "sha256": digest}


def persona_section(ticket: "Ticket", heading: str = "###") -> str:
    """Render the persona preamble injected into work orders and DSH prompts."""
    if not ticket.persona:
        return ""
    if ticket.persona_error or ticket.persona_profile is None:
        return "\n".join(
            [
                f"{heading} Agent persona",
                "",
                f"Source: {ticket.persona}",
                f"Unavailable: {ticket.persona_error or 'persona could not be loaded'}",
                "",
                "Ticket contract takes precedence over this persona. If they conflict, "
                "follow the ticket's write scope, acceptance, and Verify sections.",
            ]
        )
    persona = ticket.persona_profile
    lines = [f"{heading} Agent persona: {persona.name}", "", f"Source: {ticket.persona}"]
    details: list[str] = []
    if persona.role:
        details.append(f"Role: {persona.role}")
    if persona.domain:
        details.append(f"Domain: {persona.domain}")
    if persona.description:
        details.append(f"Description: {persona.description}")
    if details:
        lines.extend(["", *[f"- {item}" for item in details]])
    if persona.capabilities:
        lines.extend(["", "Capabilities:", *[f"- {item}" for item in persona.capabilities]])
    if persona.must_call_when:
        lines.extend(["", "Must call when:", *[f"- {item}" for item in persona.must_call_when]])
    if persona.prompt:
        lines.extend(["", persona.prompt])
    lines.extend(
        [
            "",
            "Ticket contract takes precedence over this persona. If they conflict, "
            "follow the ticket's write scope, acceptance, and Verify sections.",
        ]
    )
    return "\n".join(lines)
