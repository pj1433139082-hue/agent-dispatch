from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# {tid}: wave continue

## What to build

写 out{tid}.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out{tid}.txt
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('out{tid}.txt').exists() else 1)"

## Acceptance

- [ ] out{tid}.txt 存在。
"""

BRIEF = """# Brief: {tid}

## 理解的目标

写 out{tid}.txt。

## 计划

1. 建 out{tid}.txt

## 准备改动的文件

- out{tid}.txt —— 产物
- phantom.txt —— 打算改但最后没改

## 风险

无

## 疑问

无。
"""


SINGLE_TICKET = """# 01: auto closeout

## What to build

写 out.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: out.txt
- Verify: python -c "import pathlib,sys; sys.exit(0 if pathlib.Path('out.txt').exists() else 1)"

## Acceptance

- [ ] out.txt 存在。
"""

SINGLE_BRIEF = """# Brief: 01

## 理解的目标

写 out.txt。

## 计划

1. 建 out.txt

## 准备改动的文件

- out.txt —— 产物
- phantom.txt —— 打算改但最后没改

## 风险

无

## 疑问

无。
"""

EXECUTOR = """import json, os, pathlib
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
pathlib.Path("out.txt").write_text("hello", encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
  "ticket_id": "01",
  "run_id": os.environ["DISPATCH_RUN_ID"],
  "status": "done",
  "summary": "ok",
  "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
}), encoding="utf-8")
"""

REVIEWER = """import json, os, pathlib
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
run.joinpath("review-result.json").write_text(json.dumps({
  "verdict": "pass", "reviewer": "reviewer-b", "notes": "ok",
}), encoding="utf-8")
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=cwd, env=env, text=True, capture_output=True, check=False,
    )


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args],
        cwd=cwd, text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


def make_repo(tmp_path: Path, ticket_ids: list[str]) -> None:
    (tmp_path / "tickets").mkdir()
    for tid in ticket_ids:
        (tmp_path / "tickets" / (tid + ".md")).write_text(TICKET.format(tid=tid), encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "off"}), encoding="utf-8",
    )
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")


def write_brief(tmp_path: Path, tid: str) -> None:
    brief = tmp_path / ".dispatch" / "briefs" / (tid + ".md")
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(BRIEF.format(tid=tid), encoding="utf-8")


def run_dir_of(tmp_path: Path, tid: str) -> Path:
    return [p for p in (tmp_path / ".dispatch" / "runs").iterdir() if p.name.startswith(tid + "-")][0]


def drive_to_done(tmp_path: Path, tid: str) -> Path:
    assert run_dispatch(tmp_path, "render", tid, "--agent", "lead").returncode == 0
    assert run_dispatch(tmp_path, "start", tid).returncode == 0
    run_dir = run_dir_of(tmp_path, tid)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    worktree = Path(run["execution_root"])
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / ("out" + tid + ".txt")).write_text("ok", encoding="utf-8")
    (run_dir / "receipt.json").write_text(json.dumps({
        "ticket_id": tid, "run_id": run["run_id"], "status": "done", "summary": "ok",
        "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
    }), encoding="utf-8")
    assert run_dispatch(tmp_path, "verify", tid).returncode == 0
    assert run_dispatch(tmp_path, "review", tid, "--reviewer", "reviewer-b", "--verdict", "pass").returncode == 0
    return run_dir


def test_wave_continue_on_error_lands_later_tickets_after_a_closeout_failure(tmp_path: Path) -> None:
    """--continue-on-error 的语义：失败票排在前，后面的好票仍要落地（否则这个 flag 等于没有）。"""
    make_repo(tmp_path, ["01", "02"])
    # 01 的 brief 声明了 phantom.txt 却不会改它 → closeout 必报「声明了却没改」；02 是好票
    write_brief(tmp_path, "01")
    assert run_dispatch(tmp_path, "brief", "01", "--check").returncode == 0
    assert run_dispatch(tmp_path, "brief", "01", "--approve", "tester").returncode == 0

    bad_run = drive_to_done(tmp_path, "01")
    good_run = drive_to_done(tmp_path, "02")

    bad = run_dispatch(tmp_path, "closeout", "01", "--json")
    assert json.loads(bad.stdout)["status"] == "fail"
    good = run_dispatch(tmp_path, "closeout", "02", "--json")
    assert json.loads(good.stdout)["status"] == "pass", good.stdout

    # 第一枪：不带 continue-on-error → 停在 01，02 不许落
    stop = run_dispatch(tmp_path, "land", "--wave", "--require-closeout", "--json")
    assert stop.returncode != 0, stop.stdout + stop.stderr
    assert not (good_run / "landing.json").exists(), "不带 continue-on-error 时不应该继续落后面的票"
    assert not (bad_run / "landing.json").exists()

    # 第二枪：带 continue-on-error → 01 仍失败，但 02 必须落地
    result = run_dispatch(
        tmp_path, "land", "--wave", "--require-closeout", "--continue-on-error", "--json",
    )
    payload = json.loads(result.stdout)
    assert result.returncode != 0, "有票失败时 land --wave 必须返回非零"
    assert [item["ticket_id"] for item in payload["landed"]] == ["02"], payload
    assert any(item["ticket_id"] == "01" and "closeout" in str(item["reason"]) for item in payload["failed"]), payload
    assert (good_run / "landing.json").is_file()

def test_auto_until_land_does_not_land_when_closeout_fails(tmp_path: Path) -> None:
    """--until land + --protocol full：closeout 不过必须停在 review 之前，不许落地。"""
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01.md").write_text(SINGLE_TICKET, encoding="utf-8")
    (tmp_path / "exec.py").write_text(EXECUTOR, encoding="utf-8")
    (tmp_path / "review.py").write_text(REVIEWER, encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "off"}), encoding="utf-8",
    )
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    brief = tmp_path / ".dispatch" / "briefs" / "01.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(SINGLE_BRIEF, encoding="utf-8")
    assert run_dispatch(tmp_path, "brief", "01", "--check").returncode == 0
    assert run_dispatch(tmp_path, "brief", "01", "--approve", "tester").returncode == 0

    result = run_dispatch(
        tmp_path, "auto", "01",
        "--executor", "python exec.py",
        "--protocol", "full", "--require-brief",
        "--until", "land",
        "--reviewer", "reviewer-b",
        "--reviewer-command", "python review.py",
    )

    assert result.returncode != 0, result.stdout + result.stderr
    run_dir = run_dir_of(tmp_path, "01")
    auto = json.loads((run_dir / "auto.json").read_text(encoding="utf-8"))
    assert auto["status"] == "closeout-failed", auto
    assert any("声明了却没改" in str(item) for item in auto.get("closeout_findings", [])), auto
    assert not (run_dir / "landing.json").exists()
    assert git(tmp_path, "branch", "--list", "dispatch/land/*") == ""
