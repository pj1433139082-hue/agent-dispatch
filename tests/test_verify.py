from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from agent_dispatch.verify import _run_command, path_matches_scope


def test_exact_path_matches_scope() -> None:
    assert path_matches_scope("src/agent_dispatch/verify.py", "src/agent_dispatch/verify.py")


def test_glob_matches_nested_file() -> None:
    assert path_matches_scope("src/**", "src/agent_dispatch/verify.py")


def test_single_star_does_not_cross_directories() -> None:
    assert not path_matches_scope("src/*.py", "src/agent_dispatch/verify.py")


def test_unrelated_path_does_not_match() -> None:
    assert not path_matches_scope("src/**", "tests/test_verify.py")


def test_run_command_uses_a_shell_so_chaining_works(tmp_path: Path) -> None:
    command = f'"{sys.executable}" -c "print(1)" && echo chain-ok'

    record = _run_command(command, tmp_path, tmp_path / "log.txt", timeout=30)

    assert record["exit_code"] == 0
    body = (tmp_path / "log.txt").read_text(encoding="utf-8")
    stdout = body.split("[stdout]\n", 1)[1].split("\n[stderr]\n", 1)[0]
    assert "chain-ok" in stdout


@pytest.mark.skipif(os.name != "nt", reason="backslash paths are a Windows shell concern")
def test_run_command_preserves_windows_backslash_paths(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "smoke.py").write_text("print('ok')\n", encoding="utf-8")
    command = f'"{sys.executable}" tests\\smoke.py'

    record = _run_command(command, tmp_path, tmp_path / "log.txt", timeout=30)

    assert record["exit_code"] == 0


def test_double_star_slash_matches_zero_directories() -> None:
    assert path_matches_scope("src/**/*.py", "src/a.py")
    assert path_matches_scope("src/**/*.py", "src/x/y/b.py")
    assert not path_matches_scope("src/**/*.py", "tests/a.py")
