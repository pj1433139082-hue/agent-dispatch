"""Immutable run checkpoints: one generation per publish, never overwritten.

Borrowed shape from gstack's autoplan-checkpoint: a generation is a directory
holding a manifest (per-file sha256), the diff, the git status and a restore
note. Publishing writes a fresh generation and then flips current.json with an
atomic replace, so an interrupted publish leaves the previous one current.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .state import Run
from .verify import changed_files, worktree_diff_hash

CHECKPOINT_DIR = "checkpoints"
CURRENT_FILE = "current.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _slug(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", label.strip()).strip("-")
    return cleaned[:40] or "checkpoint"


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    return result.stdout


def checkpoints_dir(run: Run) -> Path:
    return run.directory / CHECKPOINT_DIR


def _next_number(directory: Path) -> int:
    numbers = []
    if directory.is_dir():
        for entry in directory.iterdir():
            match = re.match(r"^(\d{3})-", entry.name)
            if match and entry.is_dir():
                numbers.append(int(match.group(1)))
    return (max(numbers) + 1) if numbers else 1


def _current_name(run: Run) -> str:
    current = checkpoints_dir(run) / CURRENT_FILE
    if not current.is_file():
        return ""
    try:
        return str(json.loads(current.read_text(encoding="utf-8")).get("generation", ""))
    except (OSError, json.JSONDecodeError):
        return ""


def _restore_note(manifest: dict[str, object]) -> str:
    fence = chr(96) * 3
    lines = [
        "# Restore " + str(manifest["generation"]),
        "",
        "All paths are relative to the run execution root.",
        "",
        fence + "bash",
        "git checkout " + str(manifest.get("base_commit") or "HEAD") + " -- .",
        "git apply " + str(manifest["generation"]) + "/diff.patch",
        fence,
        "",
        "| file | sha256 |",
        "|---|---|",
    ]
    files = manifest.get("files") or []
    if isinstance(files, list):
        for entry in files:
            if isinstance(entry, dict):
                lines.append("| " + str(entry.get("path")) + " | " + str(entry.get("sha256", "(absent)")) + " |")
    lines.append("")
    return "\n".join(lines)


def publish(run: Run, label: str) -> Path:
    """Publish one immutable generation and switch current.json to it."""
    root = Path(run.execution_root)
    base = str(run.data.get("base_commit") or "")
    files = changed_files(root, base) if base else []
    entries = []
    for relative in files:
        target = root / relative
        entry: dict[str, object] = {"path": relative}
        if target.is_file():
            entry["sha256"] = _sha256(target)
            entry["size"] = target.stat().st_size
        else:
            entry["absent"] = True
        entries.append(entry)
    status_text = _git(root, "status", "--porcelain")
    diff_text = _git(root, "diff", base, "--", *files) if (base and files) else ""
    untracked = {
        line[3:].strip()
        for line in status_text.splitlines()
        if line.startswith("??")
    }
    for relative in files:
        if relative not in untracked:
            continue
        path = root / relative
        if not path.is_file():
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        added = body.splitlines()
        diff_text += (
            "\n--- /dev/null\n+++ b/" + relative + "\n"
            + "@@ -0,0 +1," + str(len(added)) + " @@\n"
            + "".join("+" + line + "\n" for line in added)
        )
    head = _git(root, "rev-parse", "HEAD").strip()

    directory = checkpoints_dir(run)
    number = _next_number(directory)
    name = str(number).zfill(3) + "-" + _slug(label)
    target = directory / name
    staging = directory / (".tmp-" + name)
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    manifest = {
        "generation": name,
        "run_id": run.id,
        "label": label,
        "created_at": _now(),
        "base_commit": base,
        "head": head,
        "diff_hash": worktree_diff_hash(root, base) if base else "",
        "files": entries,
        "parent": _current_name(run),
    }
    (staging / "checkpoint.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (staging / "status.txt").write_text(status_text, encoding="utf-8")
    (staging / "diff.patch").write_text(diff_text, encoding="utf-8")
    (staging / "restore.md").write_text(_restore_note(manifest), encoding="utf-8")

    if target.exists():
        raise FileExistsError("checkpoint " + name + " already exists")
    os.replace(staging, target)

    pointer = directory / (CURRENT_FILE + ".tmp")
    pointer.write_text(
        json.dumps({"generation": name, "at": manifest["created_at"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(pointer, directory / CURRENT_FILE)
    return target


def list_generations(run: Run) -> list[dict[str, object]]:
    directory = checkpoints_dir(run)
    if not directory.is_dir():
        return []
    current = _current_name(run)
    found: list[dict[str, object]] = []
    for entry in sorted(directory.iterdir()):
        manifest = entry / "checkpoint.json"
        if not entry.is_dir() or not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data["current"] = entry.name == current
        found.append(data)
    return found
