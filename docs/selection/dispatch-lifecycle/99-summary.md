# 选型结论: 派单生命周期（seat / sweep / repair / deadline）

## 汇总

| 角色 | 结论 | 证据位置 | 未证实项 |
|---|---|---|---|
| 开源借鉴侦察 | 建议采用 lease-TTL + projection-rebuild | `01-oss.md` | Windows pid 身份；DSH 是否暴露 pid |
| 搜索取证 | 8 条事实：6 证实 / 2 未证实 | `02-sources.md` | 同上 |
| 对抗性审查 | **需补证据**（#1/#2 判活口径、#4 repair 不删条） | `03-adversary.md` | — |
| 成本守护 | 建议采用（200 行、零依赖、无外部服务） | `05-cost.md` | 1000 run 遍历耗时 |

## 决策（lead 建议）

- **采用**：`seat`（带年龄的租约列表，occupied 显式给）、`sweep`（只读三列：age / idle / has-receipt，**不自动 kill**）、`repair`（从 runs 重算，**只做并集 + 冲突报告，不删条目**）、`render --env-hint`（环境前置写进 work-order，缺则 exit 2）。
- **不采用**：外部编排引擎；"按产物判活"；"到 deadline 自动 kill"。

## 签字前必须补的两个实验

1. **判活口径**：造"进程在、工具调用不涨、产物不涨"的假活场景，sweep 必须显示 idle 增长且不自动处置。
2. **repair 不删条**：造"state 有、disk 无"的条目，repair 后该条目仍在，并出现在冲突/孤立报告里。

## 甲方签字

- 签字人：潘杰（甲方）
- 日期：2026-10-22
- 备注：口头「选型通过」；两实验（判活口径 / repair 不删条）作为实现验收项
- 选择：☑ 通过　☐ 有保留通过　☐ 打回

## 与 ADR 的关系

结论已写入 `docs/adr/0008-dispatch-lifecycle-and-state-recovery.md`（D1–D5）；本包是它的证据面。
