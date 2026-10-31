"""Git guardrails: block accidental pushes to the main branches."""
from __future__ import annotations

import os
import stat
from pathlib import Path

HOOK = """#!/bin/sh
# installed by dispatch guard: block direct pushes to main/master
blocked=0
while read local_ref local_sha remote_ref remote_sha; do
  case "$remote_ref" in
    refs/heads/main|refs/heads/master)
      echo "BLOCKED by dispatch guard: push to $remote_ref is not allowed; open a PR from a feature branch." >&2
      blocked=1
      ;;
  esac
done
exit $blocked
"""


def hook_path(root: Path) -> Path:
    return Path(root) / ".git" / "hooks" / "pre-push"


def install(root: Path, force: bool = False) -> Path:
    target = hook_path(root)
    if target.exists() and not force:
        raise ValueError("pre-push hook already exists (use --force to overwrite): " + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(HOOK, encoding="utf-8")
    try:
        target.chmod(target.stat().st_mode | stat.S_IEXEC)
    except OSError:
        pass
    return target


def status(root: Path) -> dict[str, object]:
    target = hook_path(root)
    return {
        "path": str(target),
        "installed": target.is_file(),
        "blocks_main": "refs/heads/main" in target.read_text(encoding="utf-8") if target.is_file() else False,
    }
