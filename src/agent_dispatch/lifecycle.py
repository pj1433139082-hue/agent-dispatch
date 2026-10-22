"""派单生命周期：sweep（判活巡检）与 repair（索引重建）。

按 ADR-0008：索引是投影、run 目录是事实；判活只看数据，不自动处置。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

class ScopeError(RuntimeError):
    """写域无法展开（git 不可用等）：调用方必须 fail-closed，不许静默少领。"""


ACTIVE = {"claimed", "running"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def runs_on_disk(root: Path) -> list[dict[str, object]]:
    runs_root = Path(root) / ".dispatch" / "runs"
    if not runs_root.is_dir():
        return []
    found: list[dict[str, object]] = []
    for entry in sorted(runs_root.iterdir()):
        run_file = entry / "run.json"
        if not entry.is_dir() or not run_file.is_file():
            continue
        try:
            data = json.loads(run_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data["_dir"] = entry
        found.append(data)
    return found


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def evidence_state(run_dir: Path) -> str | None:
    """证据优先的应然状态：review > closeout > verify；三样都缺就不下结论。"""
    review = _read_json(Path(run_dir) / "review.json")
    if review:
        verdict = str(review.get("verdict", "")).strip().lower()
        if verdict == "pass":
            return "done"
        if verdict == "fail":
            return "failed"
    closeout = _read_json(Path(run_dir) / "closeout.json")
    if str(closeout.get("status", "")) == "pass":
        return "review"
    verify = _read_json(Path(run_dir) / "verify.json")
    status = str(verify.get("status", ""))
    if status in {"passed", "degraded"}:
        return "review"
    if status == "failed":
        return "failed"
    return None


def _last_artifact(run_dir: Path) -> tuple[str, float | None]:
    newest_name = ""
    newest_ts: float | None = None
    for path in run_dir.rglob("*"):
        if not path.is_file() or path.name in {"run.json", "work-order.md"}:
            continue
        try:
            ts = path.stat().st_mtime
        except OSError:
            continue
        if newest_ts is None or ts > newest_ts:
            newest_ts = ts
            newest_name = path.relative_to(run_dir).as_posix()
    return newest_name, newest_ts


def sweep(root: Path) -> list[dict[str, object]]:
    """每条 active run 一行：年龄 / 最后产物 / 是否已有回执。只读。"""
    rows: list[dict[str, object]] = []
    now = _now()
    for data in runs_on_disk(root):
        state = str(data.get("state", ""))
        if state not in ACTIVE:
            continue
        directory = Path(data["_dir"])
        created = _parse(data.get("created_at"))
        age = int((now - created).total_seconds()) if created else None
        deadline = int(data.get("deadline_seconds") or 900)
        name, ts = _last_artifact(directory)
        idle = int(now.timestamp() - ts) if ts else None
        rows.append(
            {
                "ticket_id": str(data.get("ticket_id", "")),
                "run_id": str(data.get("run_id", "")),
                "state": state,
                "age_seconds": age,
                "last_artifact": name,
                "idle_seconds": idle,
                "has_receipt": (directory / "receipt.json").is_file(),
                "evidence_state": evidence_state(directory),
                "deadline_seconds": deadline,
                "over_deadline": bool(isinstance(age, int) and age > deadline),
            }
        )
    return rows


def _load_state(root: Path) -> dict[str, dict[str, object]]:
    path = Path(root) / ".dispatch" / "state.json"
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    tickets = loaded.get("tickets") if isinstance(loaded, dict) else None
    return dict(tickets) if isinstance(tickets, dict) else {}


def repair(root: Path, write: bool = False) -> dict[str, object]:
    """从 runs/*/run.json 反向重建索引；默认 dry-run。"""
    known = _load_state(root)
    latest: dict[str, dict[str, object]] = {}
    for data in runs_on_disk(root):
        ticket_id = str(data.get("ticket_id", ""))
        run_id = str(data.get("run_id", ""))
        if not ticket_id or not run_id:
            continue
        created = str(data.get("created_at", ""))
        previous = latest.get(ticket_id)
        if previous is None or created > str(previous.get("created_at", "")):
            latest[ticket_id] = {"run_id": run_id, "state": str(data.get("state", "")), "created_at": created}

    added = sorted(ticket_id for ticket_id in latest if ticket_id not in known)
    state_changed = sorted(
        ticket_id
        for ticket_id, entry in latest.items()
        if ticket_id in known and str(known[ticket_id].get("state", "")) != str(entry["state"])
    )
    evidence_mismatch = [
        {
            "ticket_id": ticket_id,
            "state_run": str(entry["state"]),
            "evidence": expected,
        }
        for ticket_id, entry in sorted(latest.items())
        if (expected := evidence_state(Path(root) / ".dispatch" / "runs" / str(entry["run_id"]))) is not None
        and expected != str(entry["state"])
    ]
    conflicts = [
        {
            "ticket_id": ticket_id,
            "state_run": str(known[ticket_id].get("run_id", "")),
            "disk_run": str(entry["run_id"]),
        }
        for ticket_id, entry in sorted(latest.items())
        if ticket_id in known and str(known[ticket_id].get("run_id", "")) != str(entry["run_id"])
    ]
    if write:
        merged = {ticket_id: dict(entry) for ticket_id, entry in known.items()}
        conflicted = {str(item["ticket_id"]) for item in conflicts}
        conflicted |= {str(item["ticket_id"]) for item in evidence_mismatch}
        for ticket_id, entry in latest.items():
            if ticket_id in conflicted:
                # 冲突票不写：index 与 disk 各执一词时，交给人裁决（ADR-0008 D3）
                continue
            merged[ticket_id] = {
                "run_id": entry["run_id"],
                "state": entry["state"],
                "updated_at": entry["created_at"],
            }
        state_path = Path(root) / ".dispatch" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"version": 1, "tickets": merged}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return {
        "runs": len(latest),
        "added": added,
        "state_changed": state_changed,
        "conflicts": conflicts,
        "evidence_mismatch": evidence_mismatch,
        "written": bool(write),
    }


LOCKS_DIRNAME = "locks"


def _lock_path(root: Path, path: str) -> Path:
    safe = path.replace("/", "__").replace("\\", "__").replace(":", "_")
    return Path(root) / ".dispatch" / LOCKS_DIRNAME / (safe + ".json")


def _read_lock(file: Path) -> dict[str, object] | None:
    if not file.is_file():
        return None
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _expired(data: dict[str, object], now: datetime) -> bool:
    stamp = _parse(data.get("expires_at"))
    return stamp is not None and stamp <= now


def expand_scope(root: Path, patterns: list[str]) -> list[str]:
    """把写域展开成文件清单：glob 复用 verify 的匹配语义，字面量原样保留（新文件也算）。"""
    import subprocess

    from .verify import path_matches_scope

    paths: set[str] = set()
    globby = [p for p in patterns if any(ch in p for ch in "*?[")]
    for item in patterns:
        if item not in globby:
            paths.add(item.strip())
    if globby:
        completed = subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=False
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "git ls-files failed").strip()
            raise ScopeError("cannot resolve the ticket write scope: " + detail)
        tracked = completed.stdout.splitlines()
        for pattern in globby:
            for candidate in tracked:
                if path_matches_scope(pattern, candidate):
                    paths.add(candidate)
    return sorted(item for item in paths if item)


def claim(
    root: Path,
    ticket_id: str,
    run_id: str,
    paths: list[str],
    *,
    ttl_seconds: int = 900,
) -> dict[str, object]:
    """为一次 run 主张若干文件；被别的活租约占着就冲突（不覆盖）。

    并发安全：用 O_CREAT|O_EXCL 原子占位，内容写临时文件再 os.replace，
    避免两个进程同时"先读后写"都以为自己拿到了锁。
    """
    import os

    now = _now()
    granted: list[str] = []
    conflicts: list[dict[str, object]] = []
    for path in sorted(set(paths)):
        file = _lock_path(root, path)
        file.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "path": path,
                "ticket_id": ticket_id,
                "run_id": run_id,
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
        won = False
        for _attempt in range(5):
            try:
                handle = os.open(str(file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                existing = _read_lock(file)
                if existing is None:
                    continue
                if str(existing.get("run_id", "")) == run_id:
                    won = True  # 自己已持有：续租
                    break
                if _expired(existing, now):
                    try:
                        file.unlink()
                    except OSError:
                        pass
                    continue
                conflicts.append(
                    {
                        "path": path,
                        "run_id": str(existing.get("run_id", "")),
                        "ticket_id": str(existing.get("ticket_id", "")),
                        "expires_at": str(existing.get("expires_at", "")),
                    }
                )
                break
            else:
                with os.fdopen(handle, "w", encoding="utf-8") as stream:
                    stream.write(payload)
                won = True
                break
        if won:
            granted.append(path)
    return {"granted": granted, "conflicts": conflicts, "ttl_seconds": ttl_seconds}


def release(root: Path, run_id: str) -> list[str]:
    """释放某个 run 的全部租约（run 结束/收口时调用）。"""
    directory = Path(root) / ".dispatch" / LOCKS_DIRNAME
    if not directory.is_dir():
        return []
    released: list[str] = []
    for file in sorted(directory.glob("*.json")):
        data = _read_lock(file)
        if data is None or str(data.get("run_id", "")) != run_id:
            continue
        released.append(str(data.get("path", "")))
        file.unlink(missing_ok=True)
    return released


def gc(root: Path, *, apply: bool = False) -> list[dict[str, object]]:
    """回收 ended run 的 worktree：干净就删，有改动就 HOLD。"""
    import subprocess

    rows: list[dict[str, object]] = []
    state = _load_state(root)
    for data in runs_on_disk(root):
        run_id = str(data.get("run_id", ""))
        ticket_id = str(data.get("ticket_id", ""))
        run_state = str(data.get("state", ""))
        if run_id not in {str(v.get("run_id", "")) for v in state.values()}:
            continue
        if run_state not in {"done", "failed"}:
            continue
        worktree = data.get("execution_root")
        if not worktree:
            continue
        directory = Path(str(worktree))
        if not directory.is_absolute():
            directory = Path(root) / directory
        if not directory.is_dir():
            continue
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=directory, capture_output=True, text=True, check=False
        ).stdout.strip()
        branch = str(data.get("worktree_branch", ""))
        landed = (Path(root) / ".dispatch" / "runs" / run_id / "landing.json").is_file()
        verdict = "HOLD" if dirty or not landed else "REMOVE"
        rows.append(
            {
                "ticket_id": ticket_id,
                "run_id": run_id,
                "state": run_state,
                "worktree": str(directory),
                "branch": branch,
                "dirty": bool(dirty),
                "landed": landed,
                "verdict": verdict,
            }
        )
        if apply and verdict == "REMOVE":
            subprocess.run(["git", "worktree", "remove", "--force", str(directory)], cwd=root, check=False, capture_output=True)
            if branch:
                subprocess.run(["git", "branch", "-D", branch], cwd=root, check=False, capture_output=True)
            release(root, run_id)
    return rows
