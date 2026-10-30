from __future__ import annotations

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


def pack_with_adversary(tmp_path: Path, conclusion: str) -> Path:
    assert run_dispatch(tmp_path, "select", "demo", "--mode", "solo").returncode == 0
    directory = tmp_path / "docs" / "selection" / "demo"
    (directory / "03-adversary.md").write_text(
        "# 对抗审查\n\n结论：" + conclusion + "\n", encoding="utf-8"
    )
    return directory


def test_pass_signature_is_refused_when_the_adversary_found_insufficient_evidence(tmp_path: Path) -> None:
    pack_with_adversary(tmp_path, "证据不足（缺安装期证据）")

    result = run_dispatch(tmp_path, "sign", "demo", "--by", "lead", "--via", "card")

    assert result.returncode == 1
    assert "证据不足" in (result.stdout + result.stderr)


def test_pass_signature_with_a_note_is_accepted(tmp_path: Path) -> None:
    pack_with_adversary(tmp_path, "证据不足（缺安装期证据）")

    result = run_dispatch(
        tmp_path, "sign", "demo", "--by", "lead", "--via", "card",
        "--note", "补 pip download --only-binary=:all: 证据后再进 S3",
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_hold_signature_is_accepted_without_a_note(tmp_path: Path) -> None:
    pack_with_adversary(tmp_path, "证据不足（缺安装期证据）")

    result = run_dispatch(tmp_path, "sign", "demo", "--by", "lead", "--via", "card", "--hold")

    assert result.returncode == 0, result.stdout + result.stderr


def test_template_adversary_does_not_trigger_the_gate(tmp_path: Path) -> None:
    assert run_dispatch(tmp_path, "select", "demo", "--mode", "solo").returncode == 0

    result = run_dispatch(tmp_path, "sign", "demo", "--by", "lead", "--via", "card")

    assert result.returncode == 0, result.stdout + result.stderr
