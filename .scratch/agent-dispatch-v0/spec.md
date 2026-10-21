# Spec: 派单台 v0.1（agent-dispatch）

## Problem Statement

ask-matt 的 to-tickets 能回答“做什么、先后顺序”，但真正把工作交给 DSH Agent Teams 或 Codex 时，还缺四件事：每张票据由谁执行、允许写哪些文件、完成后拿什么证据、谁有权把状态改成 done。现有 DSH 任务看板只有提示词卡片和定时器，没有依赖边、assignee 和证据契约；多智能体并行时，写域冲突和“执行者自己验收自己”只能靠人盯。

## Solution

一个本地优先的 Python CLI：读取 ask-matt 风格的一票一文件 Markdown 票据，补齐 Dispatch 元数据；按 blocked-by 生成波次；渲染带写域、验收项和验证命令的 WorkOrder；执行独立 verify；把 receipt、命令退出码、git diff 写域和证据哈希写入 run 目录；最后由异体 reviewer 签署才进入 done。票据与状态都是 git 中的文件，不依赖云服务。

## User Stories

1. As a planner, I want to write one Markdown ticket per unit of work, so that the plan stays readable and reviewable in git.
2. As a planner, I want each ticket to declare its owner and risk level, so that dispatch knows who may execute it and how much autonomy it gets.
3. As a planner, I want each ticket to declare write scope and read scope, so that an agent cannot silently edit unrelated files.
4. As a planner, I want each ticket to declare verification commands, so that “done” means fresh commands passed, not that the agent said so.
5. As a planner, I want blocking edges between tickets, so that the CLI can compute the frontier and run independent work in parallel.
6. As a planner, I want a lint command with stable error codes, so that malformed tickets fail before an agent wastes a context window.
7. As a dispatcher, I want a plan command that prints topological waves, so that I can see what can run now and what waits.
8. As a dispatcher, I want same-wave write-scope conflicts surfaced, so that two agents are not sent to edit the same files.
9. As a dispatcher, I want a render command that produces a complete work order, so that the executing agent gets one self-contained brief.
10. As an executing agent, I want the work order to include acceptance criteria and a receipt schema, so that I know exactly what to return.
11. As an executing agent, I want to write only a receipt, so that I cannot unilaterally mark my own ticket done.
12. As a verifier, I want dispatch to run the declared commands itself, so that stale or fabricated receipts do not pass.
13. As a verifier, I want the actual git diff checked against write scope, so that out-of-scope edits fail the gate.
14. As a verifier, I want sha256 hashes for evidence files, so that later reviewers can detect tampering.
15. As a reviewer, I want self-review rejected, so that the implementer and the reviewer are different actors.
16. As a reviewer, I want a review record with verdict and notes, so that the decision is auditable.
17. As a maintainer, I want status as text and JSON, so that both humans and scripts can read the board.
18. As a maintainer, I want export adapters for DSH team, DSH board, Codex, and generic markdown, so that the same ticket graph can drive different runtimes.
19. As a maintainer, I want the CLI to run with only the Python standard library, so that it works on Windows and Linux without a dependency install.
20. As a maintainer, I want pytest coverage at the CLI seams, so that refactoring internals does not break the contract.

## Implementation Decisions

- **Ticket format**: one Markdown file per ticket, reusing ask-matt's heading, What to build, Blocked by, Status, and acceptance checkboxes. A Dispatch section carries Owner, Risk, Write scope, Read scope, and Verify. Repeated keys accumulate list values.
- **Runtime state**: tickets are authored input and are not mutated by runtime transitions. State lives in JSON under a dispatch directory; a run gets its own directory containing work order, receipt, verify result, review, and logs.
- **State machine**: ready → claimed → running → review → done, with failed on any gate failure. Rendering claims a ticket; starting marks it running; verify moves it to review; review moves it to done or failed. Dependencies that are not done make a ready ticket blocked in views, without a separate stored state.
- **Risk levels**: L0 read-only, L1 worktree, L2 sandboxed process, L3 host/GPU environment, L4 human approval required. v0.1 records the level and refuses L4 review without an explicit human reviewer identity; it does not implement sandboxing itself.
- **Verification**: commands are parsed as argv and run without a shell, with a timeout. Changed files come from git diff against the commit recorded at render time, plus untracked files. Cache and dispatch directories are ignored. Every remaining path must match a write-scope glob.
- **Receipt**: the executor writes a JSON receipt with ticket id, run id, status, summary, and evidence paths. The verifier does not trust the receipt's changed-files claim; it recomputes from git.
- **Evidence**: sha256 is computed for every evidence path. Missing evidence fails the gate. Command stdout/stderr are stored as logs and hashed in the verify record.
- **Review**: the reviewer must differ from both the ticket owner and the agent that claimed the run. A pass requires a previously passing verify record. Review notes and verdict are persisted.
- **Export**: v0.1 emits files/JSON only; it does not call DSH or Codex APIs. The adapters share one ticket snapshot so their content cannot drift.
- **Packaging**: Python 3.11+, standard library runtime, pytest as the only development dependency, console script named dispatch.

## Testing Decisions

- A good test drives a public interface and asserts observable output: CLI exit code, stdout JSON, files created, state transitions. It does not assert private helper calls.
- The primary seam is the CLI: tests invoke the installed module in a temporary project root with subprocesses. This covers argument parsing, file layout, and exit codes together.
- Two pure seams are tested directly because they are deterministic and high-risk: ticket parsing/linting and DAG wave computation.
- Verification tests use a real temporary git repository: commit a base, render, modify files, write receipts, run verify. This is slower but proves the gate against real git behavior rather than a mock.
- No test asserts exact timestamps, run ids, or absolute paths; those are normalized or pattern-matched.

## Out of Scope

- Web UI, multi-user accounts, permissions, and remote services.
- Container or cloud sandbox orchestration.
- Automatic merge, deploy, or release.
- Replacing DSH Agent Teams or Codex.
- Real model API calls.
- Multica, Wanman, or CubeSandbox integration.
- A graphical ticket editor.

## Further Notes

The tool is deliberately narrower than a platform: ask-matt decides what to do and in what order; agent-dispatch decides who may do it, where they may write, and what evidence moves it to done. The first real pilot is the T5 sub-agent collaboration contract in the existing 管家 workspace, after v0.1 passes its own gates.
