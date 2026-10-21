#!/usr/bin/env python3
"""Run the bundled agent-dispatch framework without installing it."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    source_root = skill_root / "src"
    package = source_root / "agent_dispatch"
    if not package.is_dir():
        print(
            f"agent-dispatch: bundled framework not found at {package}",
            file=sys.stderr,
        )
        return 2
    sys.path.insert(0, str(source_root))
    from agent_dispatch.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
