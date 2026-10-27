from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def help_commands() -> set[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    out = subprocess.run(
        [sys.executable, "-m", "agent_dispatch", "--help"],
        cwd=ROOT, env=env, text=True, capture_output=True, check=True,
    ).stdout
    match = re.search(r"\{([a-z0-9,\-]+)\}", out)
    assert match, out
    return {item.strip() for item in match.group(1).split(",") if item.strip()}


def skilling_commands() -> set[str]:
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    start = text.find("## 命令速查")
    assert start >= 0, "SKILL.md 缺「命令速查」小节"
    end = text.find("\n## ", start + 1)
    section = text[start:] if end < 0 else text[start:end]
    return set(re.findall(r"^\| `([a-z][a-z-]*)", section, re.MULTILINE))


def test_every_cli_command_is_documented() -> None:
    missing = sorted(help_commands() - skilling_commands())
    assert missing == [], "SKILL.md 漏了这些命令：" + ", ".join(missing)


def test_every_documented_command_exists() -> None:
    # SKILL.md 里可能提到 `seat` 这类历史命令，只断言它至少出现在 --help 里
    extra = sorted(skilling_commands() - help_commands())
    assert extra == [], "SKILL.md 写了但 CLI 没有：" + ", ".join(extra)
