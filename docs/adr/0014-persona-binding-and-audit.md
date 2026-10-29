# 人格绑定与审计：run 记事实，verify 只降级不拒绝

票面的 `Persona:` 只是**意图**；`render` 把角色卡字节的 `sha256` 连同来源写进 `run.json.persona`。没有绑人格时，按 `persona_policy=off` 或显式 `--allow-unassigned-persona` 记 `persona_waiver`（带来源与时间），不再静默通过。`verify` 对三类情况判 **degraded**：角色卡在 render 后被改、L2+ 的新 run 回执没自报 persona、回执 persona 与绑定不一致。`status` 显示绑定 / 豁免，`wrap` 只对"该绑却没绑、也没豁免"的未落地 run 报 issue；v1.8.2 及以前的 run 视为 legacy，不追溯。

**Considered Options**：直接 fail 被否——人格改动常见是补一句话，fail 会把小改升级成事故；删除 `persona_policy: off` 被否——会打断现有项目与测试，改为"可关但留痕"。

**Consequences**：L2+ 的自动执行从此需要在回执里自报 persona（`{"persona": {"source", "sha256"}}`），否则降级；老 run 不判降级；`status` 多一个 hint，`wrap` 多一类 issue。
