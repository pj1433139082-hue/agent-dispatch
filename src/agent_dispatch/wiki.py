"""Repo wiki: a small, greppable memory that survives sessions."""
from __future__ import annotations

import re
from pathlib import Path

INDEX = "index.md"


def wiki_dir(root: Path) -> Path:
    return Path(root) / "wiki"


def init(root: Path) -> Path:
    directory = wiki_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / INDEX
    if not target.is_file():
        target.write_text("# Wiki\n\n## Pages\n\n", encoding="utf-8")
    return target


def add(root: Path, slug: str, title: str, body: str, summary: str = "") -> Path:
    directory = wiki_dir(root)
    init(root)
    target = directory / (slug.strip().strip("/") + ".md")
    target.write_text("# " + title + "\n\n" + body.strip() + "\n", encoding="utf-8")
    index = directory / INDEX
    text = index.read_text(encoding="utf-8")
    line = "- [" + title + "](" + target.name + ")" + (": " + summary.strip() if summary else "")
    if "(" + target.name + ")" not in text:
        if not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
        index.write_text(text, encoding="utf-8")
    return target


def pages(root: Path) -> list[str]:
    directory = wiki_dir(root)
    if not directory.is_dir():
        return []
    return sorted(path.name for path in directory.glob("*.md") if path.name != INDEX)


def check(root: Path) -> list[str]:
    directory = wiki_dir(root)
    index = directory / INDEX
    if not index.is_file():
        return ["wiki/index.md is missing (dispatch wiki init)"]
    text = index.read_text(encoding="utf-8")
    linked = set(re.findall(r"\]\(([^)]+\.md)\)", text))
    problems: list[str] = []
    for name in sorted(linked):
        if not (directory / name).is_file():
            problems.append("index links a missing page: " + name)
    for name in pages(root):
        if name not in linked:
            problems.append("orphan page (not linked from index): " + name)
    return problems
