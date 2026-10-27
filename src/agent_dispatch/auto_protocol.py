"""`--protocol full`：auto 裸跑时缺的那几件。

按 ADR-0010：auto 保持"单步推进器"，协议件由开关挂上来，逻辑复用既有模块，
不在这里复制一份 context / checkpoint / closeout。
"""

from __future__ import annotations

import json
from pathlib import Path

from .brief import approval_status
from .checkpoints import publish as publish_checkpoint
from .closeout import write as write_closeout
from .context import build_context_pack
from .state import Run
from .ticket import Ticket

FENCE = chr(96) * 3


class ProtocolError(RuntimeError):
    """协议前置不满足，auto 不应开跑。"""


def prepare(
    root: Path,
    ticket: Ticket,
    run: Run,
    *,
    env_hint: str = "",
    require_brief: bool = False,
) -> dict[str, object]:
    """跑前：检查 brief 门、注入 context pack 与环境前置。"""
    if require_brief:
        ok, why = approval_status(root, ticket)
        if not ok:
            raise ProtocolError("brief 未通过：" + why)

    pack = build_context_pack(root, ticket)
    (run.directory / "context.md").write_text(pack, encoding="utf-8")
    work_order = run.directory / "work-order.md"
    if work_order.is_file():
        work_order.write_text(
            work_order.read_text(encoding="utf-8") + "\n## Context pack\n\n" + pack,
            encoding="utf-8",
        )

    hint = env_hint.strip()
    if hint:
        run.data["env_hint"] = hint
        (run.directory / "run.json").write_text(
            json.dumps(run.data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if work_order.is_file():
            work_order.write_text(
                work_order.read_text(encoding="utf-8")
                + "\n## Environment prerequisites\n\n"
                + "Satisfy these first; if they are missing, exit 2 and say so.\n"
                + "Do not borrow another project's dependencies.\n\n"
                + FENCE + "bash\n"
                + hint
                + "\n" + FENCE + "\n",
                encoding="utf-8",
            )
    return {"context": True, "env_hint": bool(hint), "brief_gate": require_brief}


def checkpoint(run: Run, attempt: int) -> Path:
    """每个 attempt 的 verify 之后发一代。"""
    return publish_checkpoint(run, "attempt-" + str(attempt))


def closeout(root: Path, ticket: Ticket, run: Run) -> dict[str, object]:
    """收口：票面 / brief / diff 对照。"""
    _path, report = write_closeout(root, ticket, run)
    return report
