from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def repo_with_persona(tmp_path: Path) -> None:
    (tmp_path / "tickets" / "personas").mkdir(parents=True)
    shutil.copy2(ROOT / "agents" / "personas" / "dispatcher.md", tmp_path / "tickets" / "personas" / "dispatcher.md")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)


def test_new_can_assign_a_persona_in_the_same_call(tmp_path: Path) -> None:
    repo_with_persona(tmp_path)

    result = run_dispatch(
        tmp_path, "new", "01", "--title", "recon runtime", "--what", "写报告",
        "--write-scope", "reports/01.md", "--persona", "dispatcher.md",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    ticket = next((tmp_path / "tickets").glob("01-*.md"))
    text = ticket.read_text(encoding="utf-8")
    assert "- Persona: personas/dispatcher.md" in text
    ledger = (tmp_path / ".dispatch" / "assignments.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(ledger[-1])["ticket_id"] == "01"
    assert (tmp_path / "tickets" / "personas" / "dispatcher.md").is_file()


def test_new_without_persona_still_works(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "README.md").write_text("seed", encoding="utf-8")
    for args in (("init", "-q"), ("add", "."), ("commit", "-q", "-m", "base")):
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args], cwd=tmp_path, check=True, capture_output=True)

    result = run_dispatch(tmp_path, "new", "02", "--title", "plain", "--what", "x", "--write-scope", "src/")

    assert result.returncode == 0
    ticket = next((tmp_path / "tickets").glob("02-*.md"))
    assert "- Persona: (unassigned)" in ticket.read_text(encoding="utf-8")
