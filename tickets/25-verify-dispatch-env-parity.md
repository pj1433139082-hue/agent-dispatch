# 25: verify 子进程补 DISPATCH_* 环境，消除判据不对称

## What to build

`auto.py:107-118` 给 executor 注入七个 `DISPATCH_*` 变量；`verify.py:249-257` **不传 `env=`**，Verify 子进程继承 CLI 进程环境。

后果：一条依赖 `DISPATCH_RUN_DIR` 之类的 Verify 命令**对执行者通过、对门禁失败**。而 `cli.py:2462-2470` 会告诉 dispatcher「修实现或修环境」，ADR-0012 D10 又禁止弱化判据——人在这里打转。

这条不跨安全边界，但可能是本批最省真实时间的一条。

**Blocked by:** 23
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Persona: dispatcher.md
- Write scope: src/agent_dispatch/verify.py
- Write scope: tests/test_verify.py
- Read scope: src/agent_dispatch/auto.py
- Read scope: docs/adr/0012-verify-must-run-in-the-execution-environment.md
- Verify: python -m pytest -q tests/test_verify.py tests/test_cli_verify.py tests/test_cli_auto.py

## Acceptance

- [ ] `verify._run_command` 接受并传入与 executor 一致的 `DISPATCH_*`（RUN_DIR/EXECUTION_ROOT/TICKET_ID/RUN_ID/WORK_ORDER/TICKET_PATH/ATTEMPT）
- [ ] 其余环境保持继承语义（不改 `os.environ` 行为）
- [ ] 新增测试：一条读取 `DISPATCH_RUN_DIR` 的 Verify 在 verify 与 auto 两条路径下都能通过
- [ ] `mutate_run` / `_verify_after_landing` / `run_commands_on_branch` 四处调用点同样受益（同源修复）
