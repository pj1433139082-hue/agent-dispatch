from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKELETON = """# Spec: demo

## Problem Statement

（从问卷来：甲方现在卡在哪）

## Solution

（一句话说清做完之后甲方能做什么）

## User Stories

1. As a ... I want ... so that ...

## Delivery standard

每一行一条可验收项；需要命令的写成 checkbox + verify 注释。

- [ ] （可命令化的验收项） <!-- verify: <命令> -->
- [ ] （人工核对项）

## Implementation Decisions

- 

## Testing Decisions

- 

## Out of Scope

- 
"""

FILLED = """# Spec: demo

## Problem Statement

甲方要把流程先问清楚再动手，避免做错方向。

## Solution

产出一套可验收的票据集，每张票能独立跑通。

## User Stories

1. 作为甲方，我希望每张票的验收命令能自己跑通。

## Delivery standard

- [ ] 生成两张票且 lint 通过。 <!-- verify: python -c "print(1)" -->

## Implementation Decisions

- 票放 tickets/，状态放 .dispatch/。

## Testing Decisions

- 每条命令可复跑、无网络。

## Out of Scope

- 不做 CI 集成。
"""


def run_dispatch(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "agent_dispatch", *args], cwd=cwd, env=env, text=True, capture_output=True, check=False)


def make_spec(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "docs" / "specs" / "demo.md"
    target.parent.mkdir(parents=True)
    target.write_text(body, encoding="utf-8")
    return target


def test_confirm_rejects_an_empty_spec(tmp_path: Path) -> None:
    make_spec(tmp_path, SKELETON)

    result = run_dispatch(tmp_path, "confirm", "demo", "--by", "甲方", "--via", "dialog")

    assert result.returncode == 1
    assert "还没写完" in result.stderr
    assert "Delivery standard" in result.stderr


def test_confirm_accepts_a_filled_spec(tmp_path: Path) -> None:
    make_spec(tmp_path, FILLED)

    result = run_dispatch(tmp_path, "confirm", "demo", "--by", "甲方", "--via", "dialog")

    assert result.returncode == 0, result.stderr
    text = (tmp_path / "docs" / "specs" / "demo.md").read_text(encoding="utf-8")
    assert "- spec_sha256：" in text


def test_editing_the_spec_after_confirm_requires_reconfirming(tmp_path: Path) -> None:
    make_spec(tmp_path, FILLED)
    assert run_dispatch(tmp_path, "confirm", "demo", "--by", "甲方", "--via", "dialog").returncode == 0
    (tmp_path / "docs" / "specs" / "demo.md").write_text(FILLED.replace("两张票", "三张票"), encoding="utf-8")

    result = run_dispatch(tmp_path, "tickets", "demo")

    assert result.returncode == 1
    assert "confirm the spec first" in result.stdout + result.stderr
