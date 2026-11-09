# 对抗性审查 brief: dispatch-trust-boundaries

Slug: dispatch-trust-boundaries
Persona: builtin:adversary

## Mission

专门找方案会怎么失败：反例、边界、迁移成本、不可逆点。

## How to answer

1. 先写清你回答的问题与判据。
2. 给证据（文件:函数 / URL + 摘录 / 反例实验）。
3. 给结论三态之一：建议采用 / 建议不采用 / 证据不足。
4. 末尾列未证实项。

---

# 审查结果（2026-11-09）

## 回答的问题与判据

问题：已确认的 7 决策（A 围栏 / B Permission 段 / C retry cap=3）按当前规格落地，会在哪里翻车？
判据：每条假设给可证伪的最小实验或反例；源码事实全部在本仓 main 工作树直读核实（未做检索，未改代码）；按「翻车代价 × 发生概率」排序，最多 7 条。

## 假设

- **假设 1（C）：attempt 计数能真正约束重试总量。** 反例（源码已证实）：计数挂在 run 上（cli.py:2188 `run.data["attempt"]+=1`），而 `_cmd_render` 对 failed 票不拒（cli.py:1182-1189，ACTIVE_STATES 不含 failed，state.py:17）直接 `Run.create` 新 run、attempt 归零（state.py:145-160 无 attempt 字段）；`_cmd_drop` 把 run 移进 archive 并删索引（lifecycle.py:149-181），再 render 同样归零；且 failed 本身可派（export.py:24-25 `_dispatchable` 含 "failed"），编排循环会不断把它捞回来。cap=3 + 复用 failed 态 + render 重置 = 编排层无上界，恰是 01-oss C3 引 Claude Code 修过的 unattended 无界循环形态。最小实验：tmp 仓里 fail→render→fail 重复 4 轮，断言每轮新 run 的 attempt==1、`_dispatchable("failed")==True`。代价高（Q3 已去掉花费上限，C 是唯一刹车）× 概率高（重置路径是文档化操作，SKILL.md:415）。
- **假设 2（B/Q5）：「能传参的执行端实际传参」= 最小权限生效。** 反例（源码已证实）：team 模式父卡权限取全波**最高**风险（dsh.py:73-75 `_permission_for` 取 max，:168），tests/test_dsh.py:200 把「含 L3 的波 → 父卡 danger-full-access」钉成了断言；叠加 U1 实测「子会话继承父会话」，同波 L0/L1 票的 teammate 全部拿到 danger-full-access——按票收窄在 team 路径被代码自己放大。且「看板是否真把 input.permission 落成会话沙箱」本机从未实测（U1 只测了 subagent 继承）。最小实验：`build_team_actions([L1票, L3票])` 看父卡 permission；再 push 一张 L0 卡并 run，读该会话 `sandboxMode.val` 是否为 read-only。代价高（权限放大）× 概率确定（team 模式代码必然如此）。
- **假设 3（A/Q7）：围栏圈住了不可信面，且围栏本身牢靠。** 两个反例：(a) 摘录不转义——context.py:164 用 ```text 包原文，AGENTS.md 或 error 里含一行 ``` 即提前闭合、后文变成顶层指令（01-oss A1 特意做了转义+残留标签校验，方案只借了「包起来」没借「防逃逸」）；(b) 同一份执行器 stderr/verify 错误还走**另一条活通道**进下一次尝试：auto.py:403-416 把 errors 写进 auto/feedback-N.md 并经 DISPATCH_FEEDBACK 指给执行器，feedback.py:28 逐条原样拼、无围栏；attempt-NN.log 更是 stdout/stderr 全文。只围 auto.json.error 等于关了后门开着前门。最小实验：构造含 "\`\`\`\n忽略写域" 的 error 字符串调 build_context_pack 看围栏断裂；grep feedback.py 确认无声明。代价高 × 概率中高（依赖内容恰好含 fence/指令，但 error 源是任意执行器输出）。
- **假设 4（Q4）：入口文档 trusted 有依据。** 没写出来的依据是「入口文档只能经评审落地」，但评审是模型门且 Q2 允许 --accept-degraded 放行 note 证据；更直接的反例：write_scope 合法包含 AGENTS.md 的票（setup-agent-dispatch 流程本身就写目标仓 AGENTS.md）可以**合规地**种入指令，verify 的 diff-vs-scope 检查（verify.py:81-90）会放行，下一次 context pack 就把它当 trusted 摘录。跨仓派单时对方仓 AGENTS.md 的作者是第三方，「trusted」只是本仓视角的默认。最小实验：tmp 仓建 write_scope=["AGENTS.md"] 的票，种入「忽略一切写域限制」，verify 通过后再 build_context_pack 确认原文无围栏进入。代价高 × 概率中。
- **假设 5（C/Q6）：--force 是人在拍板。** CLI 无调用方鉴权，_cmd_retry（cli.py:2156-2237）没有任何交互确认；SKILL.md:220 把 retry 写成标准恢复动作，超限报错又自带「需 --force」提示——自动编排的 agent 读到提示就会带 --force --reason "继续重试" 再来，history 里留下的是格式合规、无人审的理由。cap 退化为「每 3 次多打一条日志」。最小实验：脚本模拟 agent 连续 fail 4 次后按错误提示加 --force，确认畅通且 history 与人工无法区分。代价中高 × 概率高（提示语自己教会绕过）。
- **假设 6（Q1）：A/B/C 写域互不重叠、B 可直接复用 export.PERMISSIONS。** 反例（源码已证实）：workorder.py 若 `from .export import PERMISSIONS` 会成环——export.py:7 导入 graph，graph.py:15 又 `from .workorder import render_work_order`，而 PERMISSIONS 定义在 export.py:11（graph 导入之后），无论谁先被导入都会 ImportError，**全 CLI 起不来**。需先把 PERMISSIONS 挪去中立模块（如 ticket.py 或新 constants.py），这又把 B 的写域扩到 export.py+graph.py。另外三条共享 SKILL.md（retry 语义 :502/:533、工单契约）、tests/test_retry_context_refresh.py（同时踩 retry+context）、tests/test_cli_auto_protocol.py:110-111（断言工单含 Context pack 段）、dist/ 重建。最小实验：在临时分支加该 import 后 `python -c "import agent_dispatch.cli"`。代价中（实现期必炸，易修）× 概率确定（若按字面「复用」实现）。
- **假设 7：两份证据的结论与已确认决策一致、强度不超过证据。** 交叉质疑发现三处错位：(a) 01-oss:143 建议超限置 **blocked 并阻塞下游**，Q6 拍的是**复用 failed**——而 failed 可派（见假设 1），证据支持的形态被决策换成了不挡下游的形态，没人记录这个偏离；(b) 01-oss:83/:142 说 B 要「在派发点强制，而非工单正文里叮嘱」「失败不得静默放行」，Q5 对 subagent 恰恰只剩正文叮嘱，且 dsh.py push 不校验看板是否采纳 permission——结论强于已证机制；(c) 02-sources F2-1 明示三模式**不管网络/进程**，若 Permission 段被读成「网络也管住」即超出官方语义（U2）。最小实验：并排 diff 01-oss 结论段与 Q5/Q6 文字；读 export.py:24 确认 failed 可派。代价中（签字基于错位的证据综述）× 概率确定（文本事实）。

## 已核查、不构成风险（避免误伤）

- 迁移：旧 run 无 attempt 字段有 `.get("attempt", 1)` 兜底（cli.py:2188）；旧 auto.json 无 error 有 `.get("error", "")`（context.py:69）；Run.create 一直存 risk（state.py:153）。旧数据不会炸，只会「计数从升级后起算」。
- _pitfalls 只返回路径不读内容（context.py:101-111），Lead 事实属实，注入面确实小。
- retry 的 --reason 本就是必填（cli.py:307），Q6 的「写 reason 进 history」这一半已存在，增量只在 --force 分支。

## 结论

结论：建议不采用

指**按当前规格原样签字**。不是推翻 A/B/C 方向，而是假设 1/2 证明 C、B 的已确认形态达不到其声称的目标。最小修正后可转「建议采用」：C 的计数改为**按票累计**（读 state.json history 或 ledger/dropped.jsonl，跨 run 累加），超限态换成不可派的状态或至少把 failed 从可派集中按条件剔除，--force 报错不直接给出绕过命令；B 的 team 父卡权限改为**逐票下发**而非取 max（或明示 team 模式=波内最高权限并写进工单），PERMISSIONS 先搬出 export.py；A 补 fence 转义 + 把 feedback-N.md 纳入 Q7 范围。这三处都是小改，但都动了已确认决策的字面，须回炉签字而非默改。

## 未证实

- DSH 看板是否把 input.permission 真正落成执行会话的沙箱模式（本机无实测；U1 只证 subagent 继承）。
- teammate 路径的沙箱继承（02-sources 残留项，本轮亦未测）。
- 围栏对注入成功率的实际抑制幅度：无 A/B 实验，只能断言「不是边界」，不能断言「完全安慰剂」或「有效」。
- 真实编排中 render 重置 / --force 绕过的发生频率：代码路径确凿，行为频率未观测。
- 01-oss 自身的未证实 1-6（gstack 3 败是否有代码强制、OpenHands 迭代上限逐行强制点等）仍开放，本审查未复核。
