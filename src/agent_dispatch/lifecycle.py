"""派单生命周期：sweep（判活巡检）与 repair（索引重建）。

按 ADR-0008：索引是投影、run 目录是事实；判活只看数据，不自动处置。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

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
        "written": bool(write),
    }
