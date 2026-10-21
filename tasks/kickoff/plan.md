# 项目启动方案

## 可执行任务

v0.1 按 tracer-bullet 垂直切片推进，每片都能独立演示；实现时每片先写失败测试再写最小实现。

1. **票据骨架与 lint**：建立 Markdown 票据格式、解析、字段校验、退出码；`dispatch new/lint/status` 可跑通。
2. **依赖图与分波**：解析 blocked-by，拓扑排序、环检测、同波写域冲突提示；`dispatch plan` 输出计划。
3. **工单渲染与认领**：`dispatch render` 生成 WorkOrder，写入 run 目录并把状态推进到 claimed/running。
4. **验证门禁**：`dispatch verify` 执行票据声明命令，核对 receipt、git diff 写域和证据哈希；通过才进入 review。
5. **复核门禁**：`dispatch review` 做异体复核，记录裁决，控制 review→done/failed。
6. **状态视图与导出**：`dispatch status --json`、`dispatch export` 适配 DSH team / DSH board / Codex / generic，补齐 README 与示例。

## 技术选择

- **语言与运行时**：Python 3.11+（本机 3.13.9），仅标准库；打包用 pyproject.toml，控制台入口 `dispatch`。理由：与现有 agent-workflow-framework 一致，跨 Windows/Linux，零安装依赖。
- **票据格式**：一票一文件的 Markdown，复用 ask-matt 的 `# NN: 标题`、`**What to build:**`、`**Blocked by:**`、验收 checkbox；另加 `## Dispatch` 段记录 Owner/Risk/Write scope/Read scope/Verify。理由：人可读、git 友好、与 to-tickets 产物直接兼容，不引入 YAML 解析依赖。
- **运行状态**：票据文件只读；运行状态与证据写入 `.dispatch/state/*.json`、`.dispatch/runs/<ticket>/<run-id>/`，JSON 为机器事实源。
- **状态机**：ready → claimed → running → review → done；失败进入 failed，外部阻塞用 blocked。agent 只写 receipt，不能直接改票据状态；只有 verify/review 命令能推进状态。
- **验证**：验证命令用 `subprocess` 以 argv 执行（不经 shell）；写域用 git diff（含未跟踪文件）核对，路径 glob 采用 POSIX 语义；证据文件计算 sha256。`.dispatch/`、缓存目录默认不计入写域。
- **复核**：review 必须由与执行者不同的 reviewer 签署；L0–L2 可自动验证后交人复核，L3 必须人工，L4 永远人工审批。
- **测试**：pytest 仅作为开发依赖；测试 seam 定在 CLI 公共入口与 `ticket.parse`、`graph.plan` 两个纯函数接口，不测私有实现。
- **仓库**：本地 E:/beikong-code/agent-dispatch；GitHub 仓库随后创建，默认分支 main，MIT 许可证；分支保护与必需检查用 github-repo-settings 流程配置。

## 风险

- **写域绕过**：glob 语义或 symlink 可能让改动越界。v0.1 以 git diff 的规范化相对路径为准，拒绝绝对路径与 `..`；symlink 场景记录为已知限制。
- **验证命令可信度**：票据是受信任输入，命令仍可能产生副作用。v0.1 只在项目根执行、无 shell、带超时；高风险票据走 L3/L4 人工门禁。
- **Windows 路径差异**：统一把 diff 路径转成 `/`，glob 使用 POSIX 语义；CI 只跑 Linux，Windows 本地跑同一套 pytest。
- **状态与票据漂移**：票据定义变更后旧 run 失效；run.json 记录票据内容哈希，verify 发现哈希不一致直接拒绝。
- **范围蔓延**：v0.1 不做 Web UI、多用户、自动合并、真实模型调用；这些留在后续版本。

## 验收方法

1. 在干净临时目录执行 `dispatch new`、`dispatch lint`、`dispatch plan`，检查退出码与输出。
2. 用故意缺字段、成环、未知依赖的票据验证 lint 拒绝；用正常票据验证 plan 波次与写域冲突提示。
3. `dispatch render` 生成 work-order.md，检查读写域、验收项、验证命令、receipt 契约齐全。
4. 用临时 git 仓库跑 `dispatch verify`：分别构造命令失败、改动越界、receipt 缺失、证据缺失、全部通过五种场景。
5. `dispatch review` 验证自审被拒、pass 后状态为 done；`dispatch status --json` 与 `dispatch export` 核对四种输出。
6. 运行全量 `python -m pytest -q`；按 README 快速开始从零复现一遍。

## 尚未做的事情

- 尚未初始化 Git、创建 GitHub 远端、配置分支保护。
- 尚未实现任何业务代码；本方案只定义 v0.1 范围与验收。
- 尚未接入 DSH 看板/Agent Teams 的真实 API；v0.1 只导出可被人工或脚本消费的 JSON/Markdown。
