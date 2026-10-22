"""Review packet: the immutable input an independent reviewer reads.

A reviewer that opens the live worktree can be fooled by whatever the executor
left behind, and cannot tell what changed. The packet freezes the ticket text,
the diff, the receipt and the verify record with hashes, so the verdict is
about a fixed artifact instead of a moving tree.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .state import Run
from .ticket import Ticket
from .verify import changed_files, worktree_diff_hash


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def build(root: Path, ticket: Ticket, run: Run) -> dict[str, object]:
    execution_root = Path(run.execution_root)
    base = str(run.data.get("base_commit", ""))
    files = changed_files(execution_root, base) if base else []
    diff = ""
    if base and files:
        import subprocess

        diff = subprocess.run(
            ["git", "diff", base, "--", *files],
            cwd=execution_root,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        # 新增文件在 git diff 里是空的；不补的话评审包会对着"没变化"签字。
        for relative in files:
            target = execution_root / relative
            if not target.is_file():
                continue
            tracked = subprocess.run(
                ["git", "ls-files", "--error-unmatch", relative],
                cwd=execution_root,
                capture_output=True,
                text=True,
                check=False,
            ).returncode == 0
            if tracked:
                continue
            body = target.read_text(encoding="utf-8", errors="replace").splitlines()
            hunk = ["diff --git a/" + relative + " b/" + relative, "new file mode 100644", "--- /dev/null", "+++ b/" + relative]
            hunk.extend("+" + line for line in body)
            diff += "\n".join(hunk) + "\n"
    ticket_text = _read(ticket.path)
    receipt_text = _read(run.directory / "receipt.json")
    verify_text = _read(run.directory / "verify.json")
    closeout_text = _read(run.directory / "closeout.json")
    return {
        "ticket_id": ticket.id,
        "run_id": run.id,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "base_commit": base,
        "diff_hash": worktree_diff_hash(execution_root, base) if base else "",
        "changed_files": files,
        "hashes": {
            "ticket": _sha256_text(ticket_text),
            "receipt": _sha256_text(receipt_text),
            "verify": _sha256_text(verify_text),
            "closeout": _sha256_text(closeout_text),
            "diff": _sha256_text(diff),
        },
        "ticket_text": ticket_text,
        "receipt": json.loads(receipt_text) if receipt_text.strip().startswith("{") else receipt_text,
        "verify": json.loads(verify_text) if verify_text.strip().startswith("{") else verify_text,
        "closeout": json.loads(closeout_text) if closeout_text.strip().startswith("{") else closeout_text,
        "diff": diff,
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Review packet: " + str(report["ticket_id"]) + " / " + str(report["run_id"]),
        "",
        "Base commit: " + str(report["base_commit"]),
        "Diff hash: " + str(report["diff_hash"]),
        "",
        "## Hashes",
        "",
        "| part | sha256 |",
        "|---|---|",
    ]
    hashes = report.get("hashes") or {}
    if isinstance(hashes, dict):
        for key, value in hashes.items():
            lines.append("| " + str(key) + " | " + str(value) + " |")
    lines.extend(["", "## Changed files", ""])
    files = report.get("changed_files") or []
    lines.extend("- " + str(item) for item in files) if files else lines.append("- (none)")
    lines.extend(["", "## Diff", "", chr(96) * 3 + "diff", str(report.get("diff", "")), chr(96) * 3, ""])
    lines.extend(["## Ticket", "", str(report.get("ticket_text", "")), ""])
    lines.extend(["## Receipt", "", chr(96) * 3 + "json", json.dumps(report.get("receipt"), ensure_ascii=False, indent=2), chr(96) * 3, ""])
    lines.extend(["## Verify", "", chr(96) * 3 + "json", json.dumps(report.get("verify"), ensure_ascii=False, indent=2), chr(96) * 3, ""])
    return "\n".join(lines)


def write(root: Path, ticket: Ticket, run: Run) -> tuple[Path, dict[str, object]]:
    report = build(root, ticket, run)
    json_path = run.directory / "review-packet.json"
    md_path = run.directory / "review-packet.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return md_path, report
