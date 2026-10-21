from __future__ import annotations

import json
import subprocess
from pathlib import Path

from agent_dispatch.brief import ensure_brief
from agent_dispatch.closeout import collect, declared_files, write
from agent_dispatch.state import Run
from agent_dispatch.ticket import parse_ticket

TICKET = """# 03: Close it out

## What to build

Ship it.

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: src/app.py
- Verify: python -c "print(1)"

## Acceptance

- [ ] it works
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args],
        cwd=repo, text=True, capture_output=True, check=True,
    ).stdout.strip()


def make(tmp_path: Path, *, extra_file: str = "") -> tuple[Path, object, Run]:
    repo = tmp_path / "repo"
    (repo / "tickets").mkdir(parents=True)
    ticket_path = repo / "tickets" / "03.md"
    ticket_path.write_text(TICKET, encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    (repo / "src" / "app.py").write_text("print(2)\n", encoding="utf-8")
    if extra_file:
        (repo / extra_file).write_text("stray\n", encoding="utf-8")
    run_dir = repo / ".dispatch" / "runs" / "R3"
    run_dir.mkdir(parents=True)
    data = {"run_id": "R3", "ticket_id": "03", "ticket_path": "tickets/03.md", "base_commit": base, "execution_root": str(repo)}
    (run_dir / "run.json").write_text(json.dumps(data), encoding="utf-8")
    (run_dir / "verify.json").write_text(json.dumps({"status": "passed", "errors": []}), encoding="utf-8")
    (run_dir / "receipt.json").write_text(
        json.dumps({"ticket_id": "03", "run_id": "R3", "status": "done", "summary": "ok",
                    "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "note", "note": "done"}]}]}),
        encoding="utf-8",
    )
    return repo, parse_ticket(ticket_path), Run(repo, run_dir, data)


def test_closeout_passes_on_a_clean_in_scope_run(tmp_path: Path) -> None:
    repo, ticket, run = make(tmp_path)
    report = collect(repo, ticket, run)
    assert report["status"] == "pass", report["findings"]
    assert report["changed_files"] == ["src/app.py"]


def test_closeout_flags_out_of_scope_changes(tmp_path: Path) -> None:
    repo, ticket, run = make(tmp_path, extra_file="stray.txt")
    report = collect(repo, ticket, run)
    assert report["status"] == "fail"
    assert any("写域" in finding for finding in report["findings"])


def test_closeout_flags_receipt_not_matching_acceptance(tmp_path: Path) -> None:
    repo, ticket, run = make(tmp_path)
    (run.directory / "receipt.json").write_text(
        json.dumps({"ticket_id": "03", "run_id": "R3", "status": "done", "summary": "ok", "criteria": []}),
        encoding="utf-8",
    )
    report = collect(repo, ticket, run)
    assert any("acceptance" in finding for finding in report["findings"])


def test_closeout_flags_changes_the_brief_did_not_declare(tmp_path: Path) -> None:
    repo, ticket, run = make(tmp_path, extra_file="src/other.py")
    brief = ensure_brief(repo, ticket)
    brief.write_text(
        "## 理解的目标\n\nx\n\n## 计划\n\ny\n\n## 准备改动的文件\n\n- src/app.py 主逻辑\n\n## 风险\n\nz\n\n## 疑问\n\n无\n",
        encoding="utf-8",
    )
    report = collect(repo, ticket, run)
    assert report["brief_declared"] == ["src/app.py"]
    assert "src/other.py" in report["changed_not_declared"]


def test_declared_files_reads_bullets_only(tmp_path: Path) -> None:
    text = "## x\n\n- src/a.py：入口\n- 不是路径的一句话\n- docs/b.md\n"
    assert declared_files(text) == ["docs/b.md", "src/a.py"]


def test_write_produces_both_artifacts(tmp_path: Path) -> None:
    repo, ticket, run = make(tmp_path)
    path, report = write(repo, ticket, run)
    assert path.is_file()
    assert (run.directory / "closeout.md").is_file()
    assert report["status"] == "pass"
