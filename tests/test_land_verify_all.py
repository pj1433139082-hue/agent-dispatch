from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# {tid}: verify all

**What to build:** 写 docs/{tid}.txt。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Write scope: docs/{tid}.txt
- Verify: {verify}

## Acceptance

- [ ] docs/{tid}.txt 存在。
"""

TRIVIAL = 'python -c "print(1)"'
GOOD = 'python -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'docs\').is_dir() else 1)"'
# 只在 worktree 里成立：executor 写了被 gitignore 的标记文件，合进分支后不存在
BAD = 'python -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'.full-suite-marker\').exists() else 1)"'

EXEC = """import json, os, pathlib
tid = os.environ["DISPATCH_TICKET_ID"]
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
p = pathlib.Path("docs") / (tid + ".txt")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(tid, encoding="utf-8")
pathlib.Path(".full-suite-marker").write_text("x", encoding="utf-8")
run.joinpath("receipt.json").write_text(json.dumps({
  "ticket_id": tid, "run_id": os.environ["DISPATCH_RUN_ID"], "status": "done", "summary": "ok",
  "criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "file", "path": str(p)}]}],
}), encoding="utf-8")
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def ready(tmp_path: Path, ids: tuple[str, ...] = ("01",), verify: str = TRIVIAL) -> None:
    (tmp_path / "tickets").mkdir()
    for tid in ids:
        (tmp_path / "tickets" / (tid + ".md")).write_text(TICKET.format(tid=tid, verify=verify), encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "off", "require_brief": False}), encoding="utf-8"
    )
    (tmp_path / "exec.py").write_text(EXEC, encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".dispatch/\n.full-suite-marker\n", encoding="utf-8")
    for args in (("init", "-q"), ("add", "-A"), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    for tid in ids:
        assert run_dispatch(tmp_path, "auto", tid, "--executor", "python exec.py").returncode == 0
        assert run_dispatch(tmp_path, "review", tid, "--reviewer", "reviewer-b", "--verdict", "pass").returncode == 0


def landing_record(tmp_path: Path) -> dict:
    path = next((tmp_path / ".dispatch" / "runs").glob("*/landing.json"))
    return json.loads(path.read_text(encoding="utf-8"))


def test_land_verify_all_runs_the_command_on_the_integration_branch(tmp_path: Path) -> None:
    ready(tmp_path)

    result = run_dispatch(tmp_path, "land", "01", "--verify-all", GOOD)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERIFY-ALL 01: pass" in result.stdout
    landing = landing_record(tmp_path)
    assert landing["status"] == "landed"
    assert landing["verify_all"]["status"] == "pass"
    assert landing["verify_all"]["commands"][0]["command"] == GOOD


def test_land_verify_all_marks_the_landing_unverified_when_it_fails(tmp_path: Path) -> None:
    ready(tmp_path)

    result = run_dispatch(tmp_path, "land", "01", "--verify-all", BAD)

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "VERIFY-ALL 01: fail" in combined
    landing = landing_record(tmp_path)
    assert landing["status"] == "landed-unverified"
    assert landing["verify_all_status"] == "fail"


def test_land_verify_all_is_repeatable_and_deduplicated(tmp_path: Path) -> None:
    ready(tmp_path)
    second = 'python -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'docs/01.txt\').is_file() else 1)"'

    result = run_dispatch(tmp_path, "land", "01", "--verify-all", GOOD, "--verify-all", GOOD, "--verify-all", second)

    assert result.returncode == 0, result.stdout + result.stderr
    landing = landing_record(tmp_path)
    assert [item["command"] for item in landing["verify_all"]["commands"]] == [GOOD, second]


def test_land_wave_verify_all_runs_once_on_the_wave_branch(tmp_path: Path) -> None:
    ready(tmp_path, ids=("01", "02"))
    both = 'python -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'docs/01.txt\').is_file() and pathlib.Path(\'docs/02.txt\').is_file() else 1)"'

    result = run_dispatch(tmp_path, "land", "--wave", "--branch", "wave/all", "--append", "--verify-all", both)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("VERIFY-ALL wave wave/all") == 1


def test_land_wave_verify_all_needs_a_wave_branch(tmp_path: Path) -> None:
    ready(tmp_path, ids=("01", "02"))

    result = run_dispatch(tmp_path, "land", "--wave", "--verify-all", GOOD)

    assert result.returncode != 0
    assert "--branch" in result.stdout + result.stderr
    branches = subprocess.run(["git", "branch", "--list"], cwd=tmp_path, text=True, capture_output=True, check=True).stdout
    assert "dispatch/land" not in branches


def test_land_help_lists_the_verify_all_flags(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "land", "--help")

    assert result.returncode == 0
    assert "--verify-all" in result.stdout
    assert "--verify-all-timeout" in result.stdout


def test_land_verify_all_runs_on_the_accumulated_branch(tmp_path: Path) -> None:
    ready(tmp_path, ids=("01", "02"))
    both = 'python -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'docs/01.txt\').is_file() and pathlib.Path(\'docs/02.txt\').is_file() else 1)"'

    assert run_dispatch(tmp_path, "land", "01", "--branch", "wave/all").returncode == 0
    result = run_dispatch(tmp_path, "land", "02", "--branch", "wave/all", "--append", "--verify-all", both)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERIFY-ALL 02: pass" in result.stdout


def test_land_wave_verify_all_fails_the_wave_when_the_command_fails(tmp_path: Path) -> None:
    ready(tmp_path, ids=("01", "02"))

    result = run_dispatch(tmp_path, "land", "--wave", "--branch", "wave/all", "--append", "--verify-all", BAD)

    assert result.returncode != 0
    assert "VERIFY-ALL wave wave/all: fail" in result.stdout + result.stderr


def test_land_reports_verify_all_even_when_the_ticket_verify_fails(tmp_path: Path) -> None:
    ready(tmp_path, verify=BAD)

    result = run_dispatch(tmp_path, "land", "01", "--verify", "--verify-all", GOOD)

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "VERIFY-AFTER 01: fail" in combined
    assert "VERIFY-ALL 01: pass" in combined
