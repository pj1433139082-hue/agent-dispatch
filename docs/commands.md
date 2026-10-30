# dispatch 命令表（自动生成，勿手改）

由 `scripts/gen_command_table.py` 从 `--help` 生成；测试会比对，漂移即红。

| 命令 | usage |
|---|---|
| `align` | `dispatch align [-h] [--title TITLE] [--level LEVEL] [--preset {dispatch,model-contract,research}] [--root ROOT] [--json] slug` |
| `answer` | `dispatch answer [-h] --answers ANSWERS [--root ROOT] [--json] slug` |
| `assign` | `dispatch assign [-h] --persona PERSONA [--tickets TICKETS] [--root ROOT] [--by BY] [--json] ticket_id` |
| `auto` | `dispatch auto [-h] --executor EXECUTOR [--agent AGENT] [--resume] [--max-attempts MAX_ATTEMPTS] [--timeout TIMEOUT] [--verify-timeout VERIFY_TIMEOUT] [--until {review,land}] [--reviewer REVIEWER] [--reviewer-command REVIEWER_COMMAND] [--accept-degraded] [--human] [--tickets TICKETS] [--protocol {none,full}] [--env-hint ENV_HINT] [--require-brief] [--root ROOT] [--json] [--force] [--allow-unassigned-persona] ticket_id` |
| `brief` | `dispatch brief [-h] [--tickets TICKETS] [--root ROOT] [--check] [--approve NAME] [--json] ticket_id` |
| `checkpoint` | `dispatch checkpoint [-h] [--label LABEL] [--list] [--root ROOT] [--json] ticket_id` |
| `claim` | `dispatch claim [-h] [--ttl-minutes TTL_MINUTES] [--tickets TICKETS] [--root ROOT] [--json] ticket_id` |
| `closeout` | `dispatch closeout [-h] [--tickets TICKETS] [--root ROOT] [--json] ticket_id` |
| `confirm` | `dispatch confirm [-h] --by BY --via {dialog,card} [--note NOTE] [--force] [--root ROOT] slug` |
| `context` | `dispatch context [-h] [--tickets TICKETS] [--root ROOT] [--json] ticket_id` |
| `doctor` | `dispatch doctor [-h] [--root ROOT] [--tickets TICKETS] [--json] [--fix]` |
| `drop` | `dispatch drop [-h] [--reason REASON] [--root ROOT] [--json] ticket_id` |
| `dsh` | `dispatch dsh [-h] {push,status,outcome,update,archive,run,delete} ...` |
| `export` | `dispatch export [-h] --format {agent-team,dsh-team,dsh-board,codex,generic} [--tickets TICKETS] [--root ROOT] [--output OUTPUT]` |
| `gc` | `dispatch gc [-h] [--apply] [--root ROOT] [--json]` |
| `handoff` | `dispatch handoff [-h] [--to TO] [--root ROOT] [--tickets TICKETS] [--json] ticket_id` |
| `install-hooks` | `dispatch install-hooks [-h] [--root ROOT] [--force]` |
| `integrate` | `dispatch integrate [-h] --branch BRANCH --from BRANCHES [--into INTO] [--verify-all COMMAND] [--root ROOT] [--json]` |
| `land` | `dispatch land [-h] [--wave] [--dry-run] [--continue-on-error] [--into INTO] [--branch BRANCH] [--root ROOT] [--require-closeout] [--require-attestation] [--no-require-packet] [--verify] [--verify-all COMMAND] [--verify-all-timeout SECONDS] [--append] [--json] [ticket_id]` |
| `lint` | `dispatch lint [-h] [--tickets TICKETS] [--json]` |
| `mutate` | `dispatch mutate [-h] [--timeout TIMEOUT] [--per-file] [--root ROOT] [--json] ticket_id` |
| `new` | `dispatch new [-h] --title TITLE [--what WHAT] [--owner OWNER] [--risk {L0,L1,L2,L3,L4}] [--write-scope WRITE_SCOPE] [--verify VERIFY] [--depends-on DEPENDS_ON] [--persona PERSONA] [--by BY] [--tickets TICKETS] ticket_id` |
| `panel` | `dispatch panel [-h] --set ROLE=STATUS [--root ROOT] [--json] slug` |
| `personas` | `dispatch personas [-h] {list,show} ...` |
| `plan` | `dispatch plan [-h] [--tickets TICKETS] [--done ID] [--json]` |
| `questions` | `dispatch questions [-h] [--root ROOT] [--json] [--with-skipped] slug` |
| `release` | `dispatch release [-h] [--root ROOT] [--json] ticket_id` |
| `render` | `dispatch render [-h] [--tickets TICKETS] [--root ROOT] [--agent AGENT] [--allow-unassigned-persona] [--no-worktree] [--deadline-minutes DEADLINE_MINUTES] [--seat-cap SEAT_CAP] [--claim] [--with-context] [--require-brief] ticket_id` |
| `repair` | `dispatch repair [-h] [--root ROOT] [--write] [--json]` |
| `retry` | `dispatch retry [-h] --reason REASON [--root ROOT] [--json] ticket_id` |
| `review` | `dispatch review [-h] [--reviewer REVIEWER] --verdict {pass,fail} [--notes NOTES] [--human] [--self-reviewed] [--packet-hash PACKET_HASH] [--accept-degraded] [--root ROOT] ticket_id` |
| `review-packet` | `dispatch review-packet [-h] [--tickets TICKETS] [--root ROOT] [--json] ticket_id` |
| `review-window` | `dispatch review-window [-h] [--open] [--close] [--root ROOT] [--json] slug` |
| `roots` | `dispatch roots [-h] [--root ROOT] [--json]` |
| `seat` | `dispatch seat [-h] [--cap CAP] [--occupied OCCUPIED] [--inactive INACTIVE] [--agent AGENT] [--root ROOT] [--json]` |
| `select` | `dispatch select [-h] [--title TITLE] [--with WITH_ROLES] [--add ID[:PERSONA]] [--list] [--mode {solo,team}] [--root ROOT] [--json] [slug]` |
| `setup` | `dispatch setup [-h] [--root ROOT] [--tickets TICKETS] [--executor-mode {teammate,dsh,command}] [--default-reviewer DEFAULT_REVIEWER] [--json]` |
| `sign` | `dispatch sign [-h] --by BY [--note NOTE] --via {dialog,card} [--hold] [--reject] [--root ROOT] slug` |
| `spec` | `dispatch spec [-h] [--title TITLE] [--force] [--root ROOT] [--json] slug` |
| `stage` | `dispatch stage [-h] [--root ROOT] [--json] [--prompt] slug` |
| `start` | `dispatch start [-h] [--root ROOT] ticket_id` |
| `status` | `dispatch status [-h] [--tickets TICKETS] [--root ROOT] [--all] [--json]` |
| `sweep` | `dispatch sweep [-h] [--root ROOT] [--json]` |
| `tickets` | `dispatch tickets [-h] [--force] [--root ROOT] [--json] slug` |
| `verify` | `dispatch verify [-h] [--root ROOT] [--timeout TIMEOUT] [--allow-dirty PATH] [--allow-main-drift] ticket_id` |
| `wrap` | `dispatch wrap [-h] [--root ROOT] [--tickets TICKETS] [--json] [--fix]` |
