from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from agent_dispatch import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_skill_wrapper_runs_without_install(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "dispatch.py"), "--version"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"dispatch {__version__}"


def test_skill_wrapper_help_lists_dsh(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "dispatch.py"), "--help"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "dsh" in result.stdout
    assert "export" in result.stdout


def test_build_skill_produces_self_contained_directory(tmp_path: Path) -> None:
    output = tmp_path / "agent-dispatch-skill"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_skill.py"), "--output", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (output / "SKILL.md").is_file()
    assert (output / "scripts" / "dispatch.py").is_file()
    assert (output / "src" / "agent_dispatch" / "cli.py").is_file()
    assert (output / "references" / "ticket-contract.md").is_file()
    assert (output / "templates" / "ticket.md").is_file()

    version = subprocess.run(
        [sys.executable, str(output / "scripts" / "dispatch.py"), "--version"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert version.returncode == 0, version.stderr
    assert version.stdout.strip() == f"dispatch {__version__}"


def test_skill_frontmatter_has_name() -> None:
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "\nname: agent-dispatch\n" in text
    assert "description:" in text
