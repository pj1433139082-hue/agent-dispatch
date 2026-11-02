# 24: 收口票面自述 status: done 的第三来源

## What to build

`export.py:39-42` 明写「票据文件自己声明的 done 也算数：不然「文件里写了 done、但没有 run」会一直显示 ready」。这在"无 run / 无索引行"时让票显示已完成并**解锁下游**。

这是交叉评审补出的第四个 done 旁路（oss 与 adversary 都漏了）。

`SKILL.md:240` 已有口径：票面 `**Status:**` 只是**作者标记**，不是事实。本票把该口径落到 `status_document`。

**Blocked by:** None
**Status:** ready-for-agent

## Dispatch

- Owner: implementer
- Risk: L1
- Persona: dispatcher.md
- Write scope: src/agent_dispatch/export.py
- Write scope: tests/test_export.py
- Read scope: src/agent_dispatch/ticket.py
- Read scope: src/agent_dispatch/graph.py
- Verify: python -m pytest -q tests/test_export.py tests/test_status_from_ticket_file.py tests/test_status_unlanded.py

## Acceptance

- [ ] `status_document` 的 done 集合默认只来自 `states`（state.json），不并入票面自述
- [ ] 无 run 的票 + 票面 `status: done` → 不再出现在 done 集合、不解锁下游
- [ ] 保留显式豁免开关（如 `--include-declared-done`）供迁移场景
- [ ] `dispatch status` 对这类票给出可操作的下一步提示
