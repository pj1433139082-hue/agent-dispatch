"""Issue tracker adapters: import an issue into a dispatch draft (read-only)."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


class TrackerError(Exception):
    """An issue could not be read."""


def _slug(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return value[:48] or "issue"


def fetch_issue(number: str, repo: str | None = None) -> dict[str, object]:
    command = ["gh", "issue", "view", str(number), "--json", "number,title,body,url,labels"]
    if repo:
        command += ["--repo", repo]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise TrackerError("gh issue view failed: " + (result.stderr or result.stdout).strip())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise TrackerError("gh returned invalid JSON: " + str(error)) from error
    return payload


def import_issue(
    root: Path,
    number: str,
    *,
    repo: str | None = None,
    from_file: Path | None = None,
) -> Path:
    """Write .dispatch/imports/<repo>-<number>-<slug>.md; never touches tickets/."""
    payload = json.loads(Path(from_file).read_text(encoding="utf-8")) if from_file else fetch_issue(number, repo)
    title = str(payload.get("title", "")).strip() or ("issue " + str(number))
    body = str(payload.get("body", "")).strip()
    url = str(payload.get("url", ""))
    labels = payload.get("labels") or []
    if isinstance(labels, list) and labels and isinstance(labels[0], dict):
        labels = [str(item.get("name", "")) for item in labels]
    number_value = str(payload.get("number", number))
    directory = Path(root) / ".dispatch" / "imports"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (number_value + "-" + _slug(title) + ".md")
    lines = [
        "# " + number_value + ": " + title,
        "",
        "## What to build",
        "",
        body or "(issue body is empty)",
        "",
        "**Blocked by:** None",
        "**Status:** ready-for-agent",
        "",
        "## Dispatch",
        "",
        "- Owner: (unassigned)",
        "- Risk: L2",
        "- Write scope: (fill in)",
        "- Verify: (fill in)",
    ]
    if url:
        lines.append("- Source: " + url)
    if labels:
        lines.append("- Labels: " + ", ".join(str(item) for item in labels))
    lines += ["", "## Acceptance", "", "- [ ] (fill in)", ""]
    target.write_text("\n".join(lines), encoding="utf-8")
    return target
