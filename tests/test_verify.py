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


def test_dispatch_env_matches_the_executor_contract(tmp_path: Path) -> None:
    """H: verify must see the same DISPATCH_* variables the executor gets (auto.py:108-118)."""
    from agent_dispatch.verify import _dispatch_env

    class FakeRun:
        id = "run-01"
        directory = tmp_path / "runs" / "run-01"
        execution_root = tmp_path / "worktrees" / "run-01"
        ticket_path = tmp_path / "tickets" / "01.md"
        data = {"ticket_id": "01"}

    env = _dispatch_env(FakeRun())

    assert env["DISPATCH_TICKET_ID"] == "01"
    assert env["DISPATCH_RUN_ID"] == "run-01"
    assert env["DISPATCH_RUN_DIR"] == str(FakeRun.directory)
    assert env["DISPATCH_EXECUTION_ROOT"] == str(FakeRun.execution_root)
    assert env["DISPATCH_WORK_ORDER"] == str(FakeRun.directory / "work-order.md")
    assert env["DISPATCH_TICKET_PATH"] == str(FakeRun.ticket_path)
    assert "DISPATCH_ATTEMPT" not in env, "verify has no attempt concept; do not invent one"


def test_run_command_passes_extra_env(tmp_path: Path) -> None:
    """The verify child actually sees the injected values.

    用 sys.executable 跑一段 Python 而不是 `echo %VAR%`：后者只在 cmd.exe 下展开，
    在 POSIX 的 /bin/sh 里会原样输出 `%VAR%`，测试就变成 Windows 专有的了。
    """
    script = tmp_path / "show_env.py"
    script.write_text("import os\nprint(os.environ.get(\"DISPATCH_RUN_ID\", \"\"))\n", encoding="utf-8")
    log = tmp_path / "logs" / "01.log"

    record = _run_command(
        f'"{sys.executable}" "{script}"',
        tmp_path,
        log,
        30,
        extra_env={"DISPATCH_RUN_ID": "run-42"},
    )

    assert record["exit_code"] == 0
    assert "run-42" in log.read_text(encoding="utf-8")

def test_mutate_run_passes_dispatch_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """票 26：mutate_run 复跑的判据也要看到 DISPATCH_*。

    只验「有没有把 env 传下去」，不验 git 行为——所以拦 _run_command 而不是伪造
    整个 subprocess。
    """
    from agent_dispatch import verify as verify_mod

    captured: list[tuple[str, dict[str, str]]] = []

    class FakeResult:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(verify_mod.subprocess, "run", lambda *a, **k: FakeResult())

    def fake_run_command(command, root, log_path, timeout, extra_env=None):
        captured.append((command, dict(extra_env or {})))
        return {"command": command, "exit_code": 0}

    monkeypatch.setattr(verify_mod, "_run_command", fake_run_command)

    class FakeRun:
        id = "run-77"
        directory = tmp_path / "runs" / "run-77"
        execution_root = tmp_path / "worktrees" / "run-77"
        ticket_path = tmp_path / "tickets" / "77.md"
        data = {"ticket_id": "77", "base_commit": "deadbeef", "use_worktree": True}

    (tmp_path / "runs" / "run-77").mkdir(parents=True)  # mutate_run 会写 mutation.json
    ticket = type("T", (), {"id": "77", "verify": ("true",)})()

    verify_mod.mutate_run(tmp_path, ticket, FakeRun(), timeout=30)

    assert captured, "mutate_run 应该复跑过票面判据"
    _command, extra_env = captured[0]
    assert extra_env["DISPATCH_RUN_ID"] == "run-77"
    assert extra_env["DISPATCH_TICKET_ID"] == "77"
