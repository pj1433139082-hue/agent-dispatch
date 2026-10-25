"""从 CLI 的 --help 生成 docs/commands.md，防止文档与参数漂移。

用法：
    python scripts/gen_command_table.py           # 重写 docs/commands.md
    python scripts/gen_command_table.py --check   # 只比对，不一致 exit 1
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / "scripts" / "dispatch.py"
TARGET = ROOT / "docs" / "commands.md"


def help_text(*args: str) -> str:
    result = subprocess.run([sys.executable, str(DISPATCH), *args, "--help"], text=True, capture_output=True, check=False)
    return result.stdout or result.stderr


def usage_block(text: str) -> str:
    lines = text.splitlines()
    collected: list[str] = []
    for line in lines:
        if line.startswith("usage:"):
            collected = [line.strip()]
            continue
        if collected:
            if not line.strip() or line.rstrip().endswith(":") and not line.startswith(" "):
                break
            collected.append(line.strip())
    usage = " ".join(collected)
    usage = re.sub(r"^usage:\s*", "", usage)
    return re.sub(r"\s+", " ", usage).strip()


def subcommands() -> list[str]:
    text = help_text()
    match = re.search(r"\{([^}]+)\}", text)
    if not match:
        return []
    return sorted(item.strip() for item in match.group(1).split(",") if item.strip())


def render() -> str:
    rows = ["# dispatch 命令表（自动生成，勿手改）", "", "由 `scripts/gen_command_table.py` 从 `--help` 生成；测试会比对，漂移即红。", "",
            "| 命令 | usage |", "|---|---|"]
    for name in subcommands():
        usage = usage_block(help_text(name)).replace("|", "\\|")
        rows.append(f"| `{name}` | `{usage}` |")
    rows.append("")
    return "\n".join(rows)


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if not TARGET.is_file():
            print("docs/commands.md is missing; run python scripts/gen_command_table.py")
            return 1
        current = TARGET.read_text(encoding="utf-8")
        if current.replace("\r\n", "\n") != text:
            print("docs/commands.md is stale; run python scripts/gen_command_table.py")
            return 1
        print("docs/commands.md is up to date")
        return 0
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
