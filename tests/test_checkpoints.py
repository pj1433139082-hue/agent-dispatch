from __future__ import annotations

import json
import subprocess
from pathlib import Path

from agent_dispatch.checkpoints import checkpoints_dir, list_generations, publish
from agent_dispatch.state import Run


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@e.com", *args],
        cwd=repo, text=True, capture_output=True, check=True,
    ).stdout.strip()


def make_run(tmp_path: Path) -> tuple[Path, Run]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
    run_dir = repo / ".dispatch" / "runs" / "R1"
    run_dir.mkdir(parents=True)
    data = {
        "run_id": "R1",
        "ticket_id": "01",
        "ticket_path": "tickets/01.md",
        "base_commit": base,
        "execution_root": str(repo),
    }
    (run_dir / "run.json").write_text(json.dumps(data), encoding="utf-8")
    return repo, Run(repo, run_dir, data)


def test_publish_writes_an_immutable_generation(tmp_path: Path) -> None:
    repo, run = make_run(tmp_path)

    target = publish(run, "after-edit")

    assert target.name == "001-after-edit"
    assert (target / "checkpoint.json").is_file()
    assert (target / "diff.patch").read_text(encoding="utf-8").strip()
    assert (target / "status.txt").is_file()
    assert "a.txt" in (target / "restore.md").read_text(encoding="utf-8")
    manifest = json.loads((target / "checkpoint.json").read_text(encoding="utf-8"))
    assert manifest["files"][0]["path"] == "a.txt"
    assert len(manifest["files"][0]["sha256"]) == 64
    current = json.loads((checkpoints_dir(run) / "current.json").read_text(encoding="utf-8"))
    assert current["generation"] == "001-after-edit"


def test_second_publish_never_overwrites_the_first(tmp_path: Path) -> None:
    _, run = make_run(tmp_path)
    first = publish(run, "step one")
    second = publish(run, "step two")

    assert first.name == "001-step-one"
    assert second.name == "002-step-two"
    assert first.is_dir() and second.is_dir()
    manifest = json.loads((second / "checkpoint.json").read_text(encoding="utf-8"))
    assert manifest["parent"] == "001-step-one"

    generations = list_generations(run)
    assert [item["generation"] for item in generations] == ["001-step-one", "002-step-two"]
    assert [item["current"] for item in generations] == [False, True]
