# 26: mutate_run 补 DISPATCH_* 环境（票 25 的未完成部分）

## What to build

票 25 给 `verify._run_command` 加了 `extra_env` 参数，但只接了**票面 Verify 复跑**一处（`verify.py:650`）。其余调用点仍是裸调用，env 不对称的问题只修了 1/5。

本票补齐 **`mutate_run` 的两处**：

- `verify.py:516` — `results.append(_run_command(command, directory, log, timeout))`（per-file 模式）
- `verify.py:542` — `_run_command(command, sandbox, sandbox / ".mutation.log", timeout)`（sandbox 模式）

这两处属于 `mutate_run(root, ticket, run, ...)`，**手上有 `run` 对象**，可以直接复用票 25 的 `_dispatch_env(run)`。

### 为什么不含 landing.py 的两处（这是本票的关键判断）

票 25 的验收原文要求「`mutate_run` / `_verify_after_landing` / `run_commands_on_branch` 四处调用点同样受益」。经核实，**后两个不该按同样方式接**：

| 调用点 | 函数签名 | 问题 |
|---|---|---|
| `landing.py:374` | `_verify_after_landing(root, branch, ticket)` | **没有 run 对象**；且它在 **integration 分支**的临时 worktree 上跑，不是 run 的 worktree |
| `landing.py:474` | `run_commands_on_branch(root, branch, commands, *, timeout)` | 同上 |

如果硬塞 `DISPATCH_EXECUTION_ROOT`，它会指向**错误的目录**（run 的 worktree 已经不存在或被 gc 了），比不设更糟——判据会以为自己在原 worktree 里。

**所以本票范围收窄为 `mutate_run` 两处**。landing 那两处若确实需要环境，应另开票单独定义「合入后分支上应该看到什么 env」，而不是复用 run 的那套。

## Blocked by: 25（代码在 #48，未合并前 render 会拿不到 extra_env）

**注意**：票 25 状态是 done，但代码在 `dispatch/land/25-...` 分支上（PR #48），**没合进 main**。本票必须等 #48 合并后再 render，否则 worktree 里 `_run_command` 还没有 `extra_env` 参数。

## Status: blocked-on-merge

## Dispatch

- Owner: implementer
- Risk: L1
- Persona: dispatcher.md
- Write scope: src/agent_dispatch/verify.py
- Write scope: tests/test_verify.py
- Read scope: src/agent_dispatch/auto.py
- Read scope: docs/specs/security-audit-fixes.md
- Verify: python -m pytest -q tests/test_verify.py tests/test_cli_mutate.py tests/test_cli_verify.py

## Acceptance

- [ ] `mutate_run` 的两处 `_run_command` 调用都传 `extra_env=_dispatch_env(run)`
- [ ] 新增测试：`mutate_run` 跑的 Verify 命令能读到 `DISPATCH_RUN_ID`
- [ ] 现有 mutate 测试不回归（含 per_file 与 sandbox 两种模式）
- [ ] `landing.py` 两处**保持不传**，并在 brief 里说明为什么（不是遗漏，是刻意）
