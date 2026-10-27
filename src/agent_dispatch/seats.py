"""Seat accounting for executor dispatch.

The platform caps a team at a fixed number of members and counts inactive ones,
so "spawn failed: limit reached" is a planning problem, not a runtime surprise.
This module answers one question before you spawn: how many seats are left, and
which inactive members can be reclaimed first.
"""

from __future__ import annotations

DEFAULT_CAP = 8


def check(cap: int = DEFAULT_CAP, occupied: int = 0, inactive: list[str] | None = None) -> dict[str, object]:
    if cap < 1:
        raise ValueError("cap must be at least 1")
    if occupied < 0:
        raise ValueError("occupied must not be negative")
    reclaimable = [name for name in (inactive or []) if name.strip()]
    free = cap - occupied
    verdict = "ok" if free > 0 else ("reclaim" if reclaimable else "blocked")
    advice = {
        "ok": "可以直接派单",
        "reclaim": "先回收 inactive 成员再派单：" + "、".join(reclaimable),
        "blocked": "名额已满且没有可回收成员：排队等回执，或把任务改到下一波",
    }[verdict]
    return {
        "cap": cap,
        "occupied": occupied,
        "free": free,
        "inactive": reclaimable,
        "verdict": verdict,
        "advice": advice,
    }
