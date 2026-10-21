from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )


def test_select_lists_the_default_panel(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "select", "--list")
    assert result.returncode == 0, result.stderr
    for role_id in ("oss-scout", "search-scout", "adversary"):
        assert role_id in result.stdout


def test_select_writes_three_mandatory_briefs(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "select", "pipeline", "--title", "编排选型")
    assert result.returncode == 0, result.stderr

    pack = tmp_path / "docs" / "selection" / "pipeline"
    names = sorted(path.name for path in pack.iterdir())
    assert names == ["00-panel.json", "01-oss.md", "02-sources.md", "03-adversary.md", "99-summary.md"]

    panel = json.loads((pack / "00-panel.json").read_text(encoding="utf-8"))
    assert [role["id"] for role in panel["roles"]] == ["oss-scout", "search-scout", "adversary"]
    assert all(role["required"] for role in panel["roles"])
    assert "甲方签字" in (pack / "99-summary.md").read_text(encoding="utf-8")


def test_optional_roles_can_be_turned_on(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "select", "pipeline", "--with", "domain-owner,cost-keeper")
    assert result.returncode == 0, result.stderr
    pack = tmp_path / "docs" / "selection" / "pipeline"
    assert (pack / "04-domain.md").is_file()
    assert (pack / "05-cost.md").is_file()


def test_custom_role_can_carry_its_own_persona(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "select", "pipeline", "--add", "security:docs/personas/sec.md")
    assert result.returncode == 0, result.stderr
    pack = tmp_path / "docs" / "selection" / "pipeline"
    panel = json.loads((pack / "00-panel.json").read_text(encoding="utf-8"))
    custom = [role for role in panel["roles"] if role["id"] == "security"]
    assert custom and custom[0]["persona"] == "docs/personas/sec.md"
    assert any(path.name.startswith("91-security") for path in pack.iterdir())


def test_unknown_optional_role_is_rejected(tmp_path: Path) -> None:
    result = run_dispatch(tmp_path, "select", "pipeline", "--with", "nope")
    assert result.returncode == 1
    assert "unknown optional role" in result.stderr
