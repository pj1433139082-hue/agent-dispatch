#!/usr/bin/env python3
"""Assemble a clean, copyable agent-dispatch skill directory."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist" / "agent-dispatch-skill"


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )


def build(output: Path) -> Path:
    output = output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    for name in ("SKILL.md", "README.md", "LICENSE", "pyproject.toml"):
        copy_file(ROOT / name, output / name)

    copy_file(ROOT / "scripts" / "dispatch.py", output / "scripts" / "dispatch.py")
    copy_file(ROOT / "scripts" / "acceptance.py", output / "scripts" / "acceptance.py")
    copy_file(ROOT / "scripts" / "test_parallel.py", output / "scripts" / "test_parallel.py")
    copy_file(ROOT / "scripts" / "gen_command_table.py", output / "scripts" / "gen_command_table.py")
    copy_file(ROOT / "docs" / "commands.md", output / "docs" / "commands.md")
    copy_tree(ROOT / "src" / "agent_dispatch", output / "src" / "agent_dispatch")
    copy_file(ROOT / "docs" / "flows.md", output / "docs" / "flows.md")
    adr = ROOT / "docs" / "adr"
    if adr.is_dir():
        copy_tree(adr, output / "docs" / "adr")
    glossary = ROOT / "GLOSSARY.md"
    if glossary.is_file():
        copy_file(glossary, output / "GLOSSARY.md")
    testing = ROOT / "docs" / "testing"
    if testing.is_dir():
        copy_tree(testing, output / "docs" / "testing")
    copy_tree(ROOT / "references", output / "references")
    copy_tree(ROOT / "templates", output / "templates")
    if (ROOT / "agents").is_dir():
        copy_tree(ROOT / "agents", output / "agents")

    companions = {
        "grill-skill": "grill-dispatch",
        "spec-skill": "to-spec-dispatch",
        "tickets-skill": "to-tickets-dispatch",
        "implement-skill": "implement-dispatch",
        "implement-spec-skill": "implement-spec-dispatch",
        "flow-skill": "dispatch-flow",
        "setup-skill": "setup-agent-dispatch",
    }
    for source, name in companions.items():
        target = output.parent / name
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        copy_file(ROOT / source / "SKILL.md", target / "SKILL.md")

    print(output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
