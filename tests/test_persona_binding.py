from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBE = (
    'python -c "import pathlib, sys; '
    "sys.exit(0 if pathlib.Path('src/01.py').is_file() else 1)"
    '"'
)


def ticket_text(risk: str = "L2") -> str:
    return f"""# 01: A

**What to build:** Ship A.
**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: {risk}
- Write scope: src/01.py
- Verify: {PROBE}

## Acceptance

- [ ] A works.
"""


def git(tmp_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=tmp_path, text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


def run_dispatch(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "agent_dispatch", *args],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=False,
    )


def only_run(tmp_path: Path) -> Path:
    return sorted((tmp_path / ".dispatch" / "runs").iterdir())[0]


def prepare(tmp_path: Path, risk: str = "L2", assign: bool = True) -> Path:
    directory = tmp_path / "tickets"
    directory.mkdir()
    (directory / "01-a.md").write_text(ticket_text(risk), encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "l2", "require_brief": False}), encoding="utf-8"
    )
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    if assign:
        assigned = run_dispatch(tmp_path, "assign", "01", "--persona", "adversary")
        assert assigned.returncode == 0, assigned.stdout + assigned.stderr
        git(tmp_path, "add", "-A")
        git(tmp_path, "commit", "-q", "-m", "assign persona")
    rendered = run_dispatch(tmp_path, "render", "01", "--tickets", str(directory))
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    assert run_dispatch(tmp_path, "start", "01").returncode == 0
    run_dir = only_run(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    (run_dir / "evidence").mkdir()
    (run_dir / "evidence" / "proof.txt").write_text("proof\n", encoding="utf-8")
    worktree = Path(str(run["execution_root"]))
    if not worktree.is_absolute():
        worktree = tmp_path / worktree
    (worktree / "src").mkdir()
    (worktree / "src" / "01.py").write_text("print('done')\n", encoding="utf-8")
    write_receipt(run_dir, run)
    return run_dir


def write_receipt(run_dir: Path, run: dict, persona: dict | None = None) -> None:
    payload = {
        "ticket_id": "01",
        "run_id": run["run_id"],
        "status": "done",
        "summary": "implemented",
        "criteria": [
            {
                "id": 1,
                "verdict": "pass",
                "evidence": [{"kind": "file", "path": "evidence/proof.txt"}],
            }
        ],
    }
    if persona is not None:
        payload["persona"] = persona
    (run_dir / "receipt.json").write_text(json.dumps(payload), encoding="utf-8")


def test_render_records_the_persona_fingerprint(tmp_path: Path) -> None:
    run_dir = prepare(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    persona = run["persona"]
    assert persona["name"] == "对抗性审查"
    source = tmp_path / persona["source"]
    import hashlib
    assert persona["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_verify_degrades_when_the_persona_file_changed_after_render(tmp_path: Path) -> None:
    run_dir = prepare(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    persona_file = tmp_path / run["persona"]["source"]
    persona_file.write_text(persona_file.read_text(encoding="utf-8") + "\n补一句。\n", encoding="utf-8")
    write_receipt(run_dir, run, run["persona"])
    result = run_dispatch(tmp_path, "verify", "01")
    assert result.returncode == 2, result.stdout + result.stderr
    record = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))
    assert "persona file changed after render" in record["persona"]["issues"]


def test_verify_degrades_when_a_required_receipt_omits_the_persona(tmp_path: Path) -> None:
    run_dir = prepare(tmp_path)
    result = run_dispatch(tmp_path, "verify", "01")
    assert result.returncode == 2, result.stdout + result.stderr
    record = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))
    assert "receipt does not report the persona" in record["persona"]["issues"]


def test_verify_passes_when_the_receipt_reports_the_bound_persona(tmp_path: Path) -> None:
    run_dir = prepare(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    write_receipt(run_dir, run, {"source": run["persona"]["source"], "sha256": run["persona"]["sha256"]})
    result = run_dispatch(tmp_path, "verify", "01")
    assert result.returncode == 0, result.stdout + result.stderr


def test_policy_off_records_a_waiver_instead_of_refusing(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01-a.md").write_text(ticket_text("L2"), encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "off", "require_brief": False}), encoding="utf-8"
    )
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    result = run_dispatch(tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets"))
    assert result.returncode == 0, result.stdout + result.stderr
    run = json.loads((only_run(tmp_path) / "run.json").read_text(encoding="utf-8"))
    assert run["persona_waiver"]["source"] == "policy=off"


def test_allow_unassigned_persona_flag_records_a_waiver(tmp_path: Path) -> None:
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "01-a.md").write_text(ticket_text("L2"), encoding="utf-8")
    (tmp_path / ".dispatch").mkdir()
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "l2", "require_brief": False}), encoding="utf-8"
    )
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    refused = run_dispatch(tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets"))
    assert refused.returncode == 6
    allowed = run_dispatch(
        tmp_path, "render", "01", "--tickets", str(tmp_path / "tickets"), "--allow-unassigned-persona"
    )
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    run = json.loads((only_run(tmp_path) / "run.json").read_text(encoding="utf-8"))
    assert run["persona_waiver"]["source"] == "flag"


def test_legacy_runs_without_persona_binding_are_not_degraded(tmp_path: Path) -> None:
    run_dir = prepare(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    run.pop("persona", None)
    run["skill_version"] = "1.8.2"
    (run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
    write_receipt(run_dir, run)

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))
    assert record["persona"]["legacy"] is True


def test_receipt_with_the_right_hash_but_wrong_source_is_degraded(tmp_path: Path) -> None:
    run_dir = prepare(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    write_receipt(run_dir, run, {"source": "personas/someone-else.md", "sha256": run["persona"]["sha256"]})

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 2, result.stdout + result.stderr
    record = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))
    assert "receipt persona source does not match the run binding" in record["persona"]["issues"]


def test_persona_requirement_is_frozen_at_render(tmp_path: Path) -> None:
    run_dir = prepare(tmp_path)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    (tmp_path / ".dispatch" / "config.json").write_text(
        json.dumps({"persona_policy": "off", "require_brief": False}), encoding="utf-8"
    )
    write_receipt(run_dir, run)

    result = run_dispatch(tmp_path, "verify", "01")

    assert result.returncode == 2, result.stdout + result.stderr
    record = json.loads((run_dir / "verify.json").read_text(encoding="utf-8"))
    assert record["persona"]["required"] is True
