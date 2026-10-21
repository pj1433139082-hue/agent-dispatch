from __future__ import annotations

from agent_dispatch.verify import path_matches_scope


def test_exact_path_matches_scope() -> None:
    assert path_matches_scope("src/agent_dispatch/verify.py", "src/agent_dispatch/verify.py")


def test_glob_matches_nested_file() -> None:
    assert path_matches_scope("src/**", "src/agent_dispatch/verify.py")


def test_single_star_does_not_cross_directories() -> None:
    assert not path_matches_scope("src/*.py", "src/agent_dispatch/verify.py")


def test_unrelated_path_does_not_match() -> None:
    assert not path_matches_scope("src/**", "tests/test_verify.py")
