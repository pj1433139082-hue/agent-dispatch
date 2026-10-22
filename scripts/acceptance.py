#!/usr/bin/env python3
"""发布前验收冒烟：两条真机路径，一条命令跑完。

A. 安装副本全链路：auto `--protocol full --until land`（brief 门 → context → checkpoint → closeout → review → land）
B. 老项目升级回归：没有 skill_version / deadline_seconds 的旧 run，只读命令不许崩、不许迁移数据

用法：
    python scripts/acceptance.py           # 人读
    python scripts/acceptance.py --json    # 机读（CI）

退出码：两条都过 0，否则 1。临时目录用完即删。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / "scripts" / "dispatch.py"

TICKET = """# 01-accept: acceptance

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

EXECUTOR = """import json, os, pathlib
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
pathlib.Path("out.txt").write_text("hi", encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
    "ticket_id": "01-accept",
    "run_id": os.environ["DISPATCH_RUN_ID"],
    "status": "done",
    "summary": "ok",
    "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "inline", "content": "ok"}]}],
}), encoding="utf-8")
"""

REVIEWER = """import json, os, pathlib
pathlib.Path(os.environ["DISPATCH_REVIEW_RESULT"]).write_text(
    json.dumps({"verdict": "pass", "notes": "acceptance"}), encoding="utf-8"
)
"""


def run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DISPATCH), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=accept", "-c", "user.email=accept@example.com", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def scenario_full_path(base: Path) -> dict[str, object]:
    workspace = base / "full"
    (workspace / "tickets").mkdir(parents=True)
    (workspace / "tickets" / "01-accept.md").write_text(TICKET, encoding="utf-8")
    (workspace / "exec.py").write_text(EXECUTOR, encoding="utf-8")
    (workspace / "reviewer.py").write_text(REVIEWER, encoding="utf-8")
    (workspace / "AGENTS.md").write_text("# Agents\n\nread CONTEXT.md\n", encoding="utf-8")
    git(workspace, "init", "-q")
    git(workspace, "add", ".")
    git(workspace, "commit", "-q", "-m", "base")

    result = run(
        workspace,
        "auto", "01-accept",
        "--executor", "python exec.py",
        "--protocol", "full",
        "--until", "land",
        "--reviewer", "acceptance-bot",
        "--reviewer-command", "python reviewer.py",
    )
    runs = sorted((workspace / ".dispatch" / "runs").iterdir())
    run_dir = runs[-1] if runs else None
    auto: dict[str, object] = {}
    if run_dir and (run_dir / "auto.json").is_file():
        auto = json.loads((run_dir / "auto.json").read_text(encoding="utf-8"))
    artifacts = sorted(p.name for p in run_dir.iterdir()) if run_dir else []
    sweep = run(workspace, "sweep", "--json")
    return {
        "exit_code": result.returncode,
        "status": auto.get("status"),
        "artifacts": artifacts,
        "active_runs_after": len(json.loads(sweep.stdout or "[]")),
        "ok": result.returncode == 0
        and auto.get("status") == "landed"
        and {"context.md", "closeout.json", "review.json", "landing.json"} <= set(artifacts)
        and len(json.loads(sweep.stdout or "[]")) == 0,
    }


def scenario_legacy(base: Path) -> dict[str, object]:
    workspace = base / "legacy"
    run_dir = workspace / ".dispatch" / "runs" / "01-old-20260101T000000Z-legacy"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": "01-old-20260101T000000Z-legacy",
                "ticket_id": "01-old",
                "state": "running",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".dispatch" / "state.json").write_text(
        json.dumps({"version": 1, "tickets": {"01-old": {"run_id": "01-old-20260101T000000Z-legacy", "state": "running"}}}),
        encoding="utf-8",
    )
    (workspace / "tickets").mkdir()
    (workspace / "tickets" / "01-old.md").write_text(TICKET.replace("01-accept", "01-old"), encoding="utf-8")

    before = sorted(str(p.relative_to(workspace / ".dispatch")) for p in (workspace / ".dispatch").rglob("*") if p.is_file())
    codes = {}
    for name in ("status", "repair"):
        codes[name] = run(workspace, name).returncode
    sweep = run(workspace, "sweep", "--json")
    row = (json.loads(sweep.stdout) or [{}])[0]
    after = sorted(str(p.relative_to(workspace / ".dispatch")) for p in (workspace / ".dispatch").rglob("*") if p.is_file())
    return {
        "exit_codes": codes,
        "sweep_exit": sweep.returncode,
        "deadline_default": row.get("deadline_seconds"),
        "over_deadline": row.get("over_deadline"),
        "files_unchanged": before == after,
        "ok": codes == {"status": 0, "repair": 0}
        and sweep.returncode == 0
        and row.get("deadline_seconds") == 900
        and before == after,
    }


def main(argv: list[str]) -> int:
    base = Path(tempfile.mkdtemp(prefix="agent-dispatch-accept-"))
    try:
        report = {
            "at": datetime.now(timezone.utc).isoformat(),
            "full_path": scenario_full_path(base),
            "legacy_project": scenario_legacy(base),
        }
    finally:
        shutil.rmtree(base, ignore_errors=True)
    report["ok"] = bool(report["full_path"]["ok"] and report["legacy_project"]["ok"])

    if "--json" in argv:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for name, key in (("A 全链路（auto --protocol full --until land）", "full_path"), ("B 老项目升级回归", "legacy_project")):
            item = report[key]
            print(("PASS " if item["ok"] else "FAIL ") + name)
            for field, value in item.items():
                if field != "ok":
                    print("      " + field + ": " + json.dumps(value, ensure_ascii=False))
        print("\nACCEPTANCE " + ("PASS" if report["ok"] else "FAIL"))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
