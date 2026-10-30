# grill 的三份证据由独立子会话产出（team 模式）

`select --mode team` 把选型包标记为"每份证据由独立子会话产出"：三个 fresh teammate 各带一张角色卡、各自的信息源隔离规则、各自只写一个文件；回收后做一轮交叉评审，落 `06-cross-review.md`。`sign` 在 team 模式下要求每份证据带 `Persona:` 行且不再是模板；没有 teammate 工具时退回 `--mode solo`（主代理代做并标注）。

**Considered Options**：单 agent 串行写三份（旧行为）——三份共享同一套偏好，人格退化成标题；只加提示词不隔离信息源——三个会话仍会搜同一批东西。

**Consequences**：一轮 grill 从 1 个会话变成 3+1 个，成本上升；换来证据独立性与可审计性（签字门能验"谁产出的"）。
