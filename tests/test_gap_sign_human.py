from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# 01: l4

## What to build

写 out.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L4
- Write scope: out.txt
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('out.txt').exists() else 1)"

## Acceptance

- [ ] out.txt 存在。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def answer_questionnaire(root: Path, slug: str) -> None:
    path = root / "docs" / "questions" / (slug + ".md")
    text = path.read_text(encoding="utf-8")
    lines = ["> 答案" if line.strip() == ">" else line for line in text.split("\n")]
    path.write_text("\n".join(lines), encoding="utf-8")


def test_spec_is_refused_after_rejected_signature(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "align", "demo", "--level", "quick").returncode == 0
    answer_questionnaire(tmp_path, "demo")
    assert run_dispatch(tmp_path, "select", "demo").returncode == 0

    sign = run_dispatch(tmp_path, "sign", "demo", "--by", "甲方", "--via", "card", "--reject")
    assert sign.returncode == 0, sign.stdout + sign.stderr
    summary = (tmp_path / "docs" / "selection" / "demo" / "99-summary.md").read_text(encoding="utf-8")
    assert "☑ 打回" in summary

    result = run_dispatch(tmp_path, "spec", "demo", "--title", "x")

    assert result.returncode != 0, result.stdout + result.stderr
    output = (result.stdout + result.stderr).lower()
    assert "not signed" in output or "未签" in output, output


def test_l4_review_without_human_flag_is_refused(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(TICKET, encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(
            ["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
    (tmp_path / ".dispatch").mkdir(exist_ok=True)
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "off"}), encoding="utf-8"
    )
    assert run_dispatch(tmp_path, "render", "01", "--agent", "lead").returncode == 0
    assert run_dispatch(tmp_path, "start", "01").returncode == 0

    run_dir = sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "out.txt").write_text("ok", encoding="utf-8")
    (run_dir / "receipt.json").write_text(
        json.dumps(
            {
                "ticket_id": "01",
                "run_id": run["run_id"],
                "status": "done",
                "summary": "ok",
                "criteria": [
                    {
                        "id": 1,
                        "verdict": "pass",
                        "evidence": [{"kind": "inline", "content": "ok"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert run_dispatch(tmp_path, "verify", "01").returncode == 0
    assert run_dispatch(tmp_path, "review-packet", "01").returncode == 0
    digest = hashlib.sha256((run_dir / "review-packet.md").read_bytes()).hexdigest()

    result = run_dispatch(
        tmp_path,
        "review",
        "01",
        "--reviewer",
        "pj",
        "--verdict",
        "pass",
        "--packet-hash",
        digest,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "human" in (result.stdout + result.stderr).lower()
