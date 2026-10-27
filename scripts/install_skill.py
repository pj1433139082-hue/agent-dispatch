#!/usr/bin/env python3
"""Mirror the built skills into an install root (e.g. ~/.agents/skills).

The dist tree is the source of truth: each target directory is replaced, so
stale files from older versions (and any __pycache__) do not survive.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SKILLS = (
    "setup-agent-dispatch",
    "dispatch-flow",
    "grill-dispatch",
    "to-spec-dispatch",
    "to-tickets-dispatch",
    "implement-dispatch",
    "implement-spec-dispatch",
)


def mirror(source: Path, target: Path) -> int:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    return sum(1 for item in target.rglob("*") if item.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror dist/ skills into an install root.")
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or "."
    parser.add_argument("--target", type=Path, default=Path(home) / ".agents" / "skills")
    args = parser.parse_args()
    target: Path = args.target.expanduser()

    pairs = [(DIST / "agent-dispatch-skill", target / "agent-dispatch")]
    pairs += [(DIST / name, target / name) for name in SKILLS]
    for index, (source, dest) in enumerate(pairs):
        if not source.is_dir():
            if index == 0:
                print(f"missing build output: {source} (run scripts/build_skill.py first)")
                return 1
            print(f"skipped {source.name}: not built")
            continue
        count = mirror(source, dest)
        print(f"synced {dest.name}: {count} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
