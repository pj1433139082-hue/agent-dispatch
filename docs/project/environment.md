# 运行环境与实际入口

技术选择与版本约束以 `tasks/kickoff/plan.md` 为准；本页只记录实际核验。

## 实际核验记录

| 检查项 | 实际版本/位置或结果 | 状态 | 命令与证据位置 | 核验时间 |
|---|---|---|---|---|
| 操作系统 | Windows，`win32` | 通过 | 本机运行环境 | 2026-10-21 |
| 运行时解释器 | Python 3.13.9（Anaconda 默认安装的 `python.exe`） | 通过 | `python -V` | 2026-10-21 |
| 兼容解释器 | CPython 3.11.15（Astral） | 通过 | `py -V:Astral/CPython3.11.15 -m compileall -q src tests` | 2026-10-21 |
| 运行时依赖 | 无第三方依赖（标准库） | 通过 | `pyproject.toml` 的 `dependencies = []` | 2026-10-21 |
| 开发依赖 | pytest>=8 | 通过 | `pyproject.toml` 的 `[project.optional-dependencies].dev` | 2026-10-21 |
| 全量测试 | 70 个测试通过，退出码 0 | 通过 | `python -m pytest -q`（项目根目录） | 2026-10-21 |
| 干净安装 | 临时 venv 中 `pip install --no-deps .` 成功；v0.2 重新构建后复核 | 通过 | 构建 wheel `agent_dispatch-0.2.0-py3-none-any.whl` | 2026-10-21 |
| 控制台入口 | `dispatch --version` 输出 `dispatch 0.2.0` | 通过 | 临时 venv 的 `Scripts/dispatch.exe` | 2026-10-21 |
| 系统 PATH | 当前系统 Python 未安装本包，直接执行 `dispatch` 为 ENOENT | 未执行/不适用 | 需按 README 在 venv 中 `pip install -e ".[dev]"` | 2026-10-21 |
| CI | v0.1 的 Ubuntu + Python 3.11 run success；v0.2 待推送后重跑 | 部分 | GitHub Actions `test` job | 2026-10-21 |

## 安装与运行

```bash
# 在项目根目录
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest -q
.venv/Scripts/dispatch --version
```

Windows 下使用 `.venv\Scripts\`；Linux/macOS 使用 `.venv/bin/`。若不想建 venv，可直接用 `python -m agent_dispatch`，但需先把 `src` 放入 `PYTHONPATH` 或安装包。
