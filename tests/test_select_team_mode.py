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


def pack(tmp_path: Path, mode: str = "team") -> Path:
    result = run_dispatch(tmp_path, "select", "demo", "--mode", mode)
    assert result.returncode == 0, result.stdout + result.stderr
    return tmp_path / "docs" / "selection" / "demo"


def test_select_mode_team_is_recorded_in_the_panel_and_summary(tmp_path: Path) -> None:
    directory = pack(tmp_path, "team")
    panel = json.loads((directory / "00-panel.json").read_text(encoding="utf-8"))
    assert panel["mode"] == "team"
    summary = (directory / "99-summary.md").read_text(encoding="utf-8")
    assert "team" in summary


def test_sign_refuses_a_team_pack_whose_evidence_has_no_persona_line(tmp_path: Path) -> None:
    directory = pack(tmp_path, "team")

    result = run_dispatch(tmp_path, "sign", "demo", "--by", "lead", "--via", "card")

    assert result.returncode == 1
    assert "team 模式下证据不可签字" in (result.stdout + result.stderr)


def test_sign_accepts_a_team_pack_where_each_file_declares_its_persona(tmp_path: Path) -> None:
    directory = pack(tmp_path, "team")
    personas = {
        "01-oss.md": "builtin:oss-scout",
        "02-sources.md": "builtin:search-scout",
        "03-adversary.md": "builtin:adversary",
    }
    for name, persona in personas.items():
        (directory / name).write_text(
            "# 证据\n\nPersona: " + persona + "\n\n结论：建议采用\n", encoding="utf-8"
        )
    (directory / "06-cross-review.md").write_text("# 交叉评审\n\n- 反驳：…\n", encoding="utf-8")
    assert run_dispatch(tmp_path, "review-window", "demo", "--open").returncode == 0
    assert run_dispatch(tmp_path, "review-window", "demo", "--close").returncode == 0

    result = run_dispatch(tmp_path, "sign", "demo", "--by", "lead", "--via", "card")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Signed demo" in result.stdout


def test_solo_packs_keep_the_old_sign_behaviour(tmp_path: Path) -> None:
    pack(tmp_path, "solo")

    result = run_dispatch(tmp_path, "sign", "demo", "--by", "lead", "--via", "card")

    assert result.returncode == 0, result.stdout + result.stderr


def test_sign_refuses_a_team_pack_without_a_cross_review(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "select", "demo", "--mode", "team").returncode == 0
    directory = tmp_path / "docs" / "selection" / "demo"
    for name, persona in (("01-oss.md", "builtin:oss-scout"), ("02-sources.md", "builtin:search-scout"), ("03-adversary.md", "builtin:adversary")):
        (directory / name).write_text("# 证据\n\nPersona: " + persona + "\n\n结论：方案可评\n", encoding="utf-8")
    assert run_dispatch(tmp_path, "review-window", "demo", "--open").returncode == 0
    assert run_dispatch(tmp_path, "review-window", "demo", "--close").returncode == 0

    result = run_dispatch(tmp_path, "sign", "demo", "--by", "lead", "--via", "card")

    assert result.returncode == 1
    assert "06-cross-review" in (result.stdout + result.stderr)
