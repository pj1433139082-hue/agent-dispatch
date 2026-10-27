from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TICKET = """# {tid}: wave verify

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

EXEC = """import json, os, pathlib
tid = os.environ["DISPATCH_TICKET_ID"]
run = pathlib.Path(os.environ["DISPATCH_RUN_DIR"])
p = pathlib.Path("docs") / (tid + ".txt")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(tid, encoding="utf-8")
"""

SHARED = 'python -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'docs\').is_dir() else 1)"'
MARKER = 'python -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'.marker\').exists() else 1)"'

RECEIPT = (
    'run.joinpath("receipt.json").write_text(json.dumps({"ticket_id": tid, '
    '"run_id": os.environ["DISPATCH_RUN_ID"], "status": "done", "summary": "ok", '
    '"criteria": [{"id": 1, "verdict": "pass", "evidence": [{"kind": "file", "path": str(p)}]}]}), '
    'encoding="utf-8")'
)


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def ready(tmp_path: Path, ids: tuple[str, ...], verify: str, marker: bool = False) -> None:
    (tmp_path / "tickets").mkdir()
    for tid in ids:
        (tmp_path / "tickets" / (tid + ".md")).write_text(TICKET.format(tid=tid, verify=verify), encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "off", "require_brief": False}), encoding="utf-8"
    )
    body = EXEC
    if marker:
        body += 'pathlib.Path(".marker").write_text("x", encoding="utf-8")\n'
    body += RECEIPT + "\n"
    (tmp_path / "exec.py").write_text(body, encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".dispatch/\n" + (".marker\n" if marker else ""), encoding="utf-8")
    for args in (("init", "-q"), ("add", "-A"), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)
    for tid in ids:
        assert run_dispatch(tmp_path, "auto", tid, "--executor", "python exec.py").returncode == 0
        assert run_dispatch(tmp_path, "review", tid, "--reviewer", "reviewer-b", "--verdict", "pass").returncode == 0


def test_wave_verify_runs_the_shared_command_once(tmp_path: Path) -> None:
    ready(tmp_path, ("01", "02"), SHARED)

    result = run_dispatch(tmp_path, "land", "--wave", "--branch", "wave/v", "--append", "--verify")

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("VERIFY-AFTER wave") == 1


def test_wave_verify_fails_when_a_command_fails(tmp_path: Path) -> None:
    ready(tmp_path, ("01", "02"), MARKER, marker=True)

    result = run_dispatch(tmp_path, "land", "--wave", "--branch", "wave/v", "--append", "--verify")

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "VERIFY-AFTER wave" in combined
    assert "fail" in combined.lower()
