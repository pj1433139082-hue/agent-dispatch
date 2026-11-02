# 安全检查记录：agent-dispatch（2026-11-02）

> 来源：`~/security-audit-skill/agent-dispatch/run-1/`（security-audit 技能 standard 档）。
> 本文件是 `docs/selection/security-audit-fixes/` 取证链的输入——adversary 曾因此报告不在仓库内而判「证据不足」，现予入库。
>
> **本轮零 `confirmed`**：本机为 Windows 且无 OS 强制沙箱，无法做 bounded local reproduction。全部 3 条为 `needs_validation`，severity 为建议值。

## 一、三条 needs_validation

### F1 · land --from-commit merges bytes the verifier never hashed: the content bind collapses to a changed-file NAME set

- **fingerprint**: `agent-dispatch/from-commit-land-binds-only-the-file-name-set-to-the-review`
- **建议 severity**: medium
- **低信任主体**: Executor (controls the bytes committed under the reviewed path set; cannot call land itself)
- **越界**: true

**根因**：landing.py:89-104 _assert_reviewed_commit compares git diff --name-only base..commit against verify.json changed_files (landing.py:95,96,100). The from-commit branch at landing.py:255-260 skips _assert_reviewed_worktree (landing.py:66-86), which is the only content-hash check. verify.json already stores diff_hash at verify.py:802 and the review packet stores the same digest at packet.py:60,68; neither is read.

**证据**：
- `src/agent_dispatch/landing.py:89-104`
- `src/agent_dispatch/landing.py:255-260`
- `src/agent_dispatch/landing.py:66-86`
- `src/agent_dispatch/verify.py:208-232`
- `src/agent_dispatch/verify.py:802`
- `src/agent_dispatch/packet.py:60`
- `src/agent_dispatch/packet.py:68`
- `docs/adr/0017-error-paths-and-recovery.md:11`
- `docs/CHANGELOG-2026-10.md:112`

**阻塞原因**：No OS-enforced sandbox on this host (Windows, danger-full-access): the git commit/land reproduction cannot be bounded.

---

### F2 · repair promotes executor-writable run-directory evidence into ticket state 'done'; the review ledger is write-only

- **fingerprint**: `dispatch-run-facts-projection-laundering`
- **建议 severity**: medium
- **低信任主体**: Executor
- **越界**: true

**根因**：lifecycle.repair trusts .dispatch/runs/*/run.json with no digest/owner check (lifecycle.py:34-49) and derives state from evidence_state, which returns 'done' on review.json {'verdict':'pass'} alone (lifecycle.py:62-68). The evidence_mismatch guard is circular — it is computed by calling the same poisoned evidence_state (lifecycle.py:203). review.py:114-115 computes review_hash and appends to reviews.jsonl, but NO src/ module reads that ledger (only tests do), so the hash chain is write-only. The run directory is handed to the executor (DISPATCH_RUN_DIR auto.py:112, workorder.py:118) and src/ contains no ACL/read-only control.

**证据**：
- `src/agent_dispatch/lifecycle.py:34-49`
- `src/agent_dispatch/lifecycle.py:62-68`
- `src/agent_dispatch/lifecycle.py:196-214`
- `src/agent_dispatch/review.py:16`
- `src/agent_dispatch/review.py:114-115`
- `src/agent_dispatch/cli.py:2329`
- `src/agent_dispatch/cli.py:1561`
- `src/agent_dispatch/cli.py:2055`
- `src/agent_dispatch/cli.py:2365`
- `src/agent_dispatch/workorder.py:118`
- `src/agent_dispatch/auto.py:112`

**阻塞原因**：No OS-enforced sandbox; the executor-writes-review.json step cannot be observed.

---

### F3 · Acceptance criteria satisfied by self-declared 'command' evidence reach done with no degraded marker and no opt-in

- **fingerprint**: `agent-dispatch/receipt-command-evidence-passes-without-opt-in`
- **建议 severity**: medium
- **低信任主体**: Executor
- **越界**: true

**根因**：verify.py:331-350 records kind='command' evidence with attested=False, using the executor's self-reported command and exit_code and never re-running it (workorder.py:130 says so explicitly). verify.py:409 sets degraded only when ALL evidence of a criterion is attested, so command evidence never sets degraded. verify.py:793 then yields status 'passed' (no errors), and review.py:71-76 requires --accept-degraded only for 'degraded'. A ticket therefore reaches done with every acceptance criterion backed by executor prose plus a fabricated exit code, with nothing recorded.

**证据**：
- `src/agent_dispatch/verify.py:331-350`
- `src/agent_dispatch/verify.py:409`
- `src/agent_dispatch/verify.py:793`
- `src/agent_dispatch/review.py:71-76`
- `src/agent_dispatch/review.py:116-118`
- `src/agent_dispatch/workorder.py:130`

**阻塞原因**：No OS-enforced sandbox; the receipt->verify->review chain cannot be executed.

---

## 二、四条 rejected

### `agent-dispatch/receipt-note-evidence-satisfies-acceptance-without-opt-in`

REFUTED on verification. workorder.py:131 already states 'a criterion supported only by notes is degraded', so the 'advertises note without the consequence' premise is false. A note-only criterion yields degraded (verify.py:409) -> ticket goes to 'review', never 'done' (verify.py:816-821); reaching done requires an explicit, ledgered --accept-degraded (review.py:71-76,101,26). Not L0/L1-specific. The parent initially accepted this candidate and was corrected by an independent verifier; the real un-gated sink is kind='command' (filed as a separate record).

### `agent-dispatch/dispatch-issue-import/issue-number-path-join`

SELF-IMPACT. The issue JSON is either the operator's own --from-file fixture or gh output fetched under the operator's own credentials (tracker.py:41); the positional is typed by the operator (cli.py:567). Operator writing into their own repo crosses no boundary. The docstring invariant at tracker.py:40 does fail, but no lower-trust principal is on the controlling side. Empirically confirmed payload behaviour: '../tickets/01' FAILS (write_text does not create parents), '../../tickets/01' escapes, drive-less '/tmp/x' and absolute paths escape into existing dirs. Logged as hardening.

### `agent-dispatch/persona-absolute-path-injection`

SELF-IMPACT. The Persona field is authored by the dispatcher who receives the prompt (ticket.py:177-178, SKILL.md:131), and the injected text is bounded by MAX_PROMPT_CHARS=12000 (persona.py:23,271-272) and fingerprinted into run.json (persona.py:349-365).

### `agent-dispatch/evidence-path-dotdot`

SELF-IMPACT / hash-only. verify.py:276-281 admits '..' but the read is hash-only (verify.py:291-310 returns path+sha256, never the body) and the digest is always recomputed (verify.py:302-305). Executor already has shell in the same worktree. Effect is a hash oracle plus path disclosure into verify.json/packet. Hardening.

## 三、九条 hardening

1. verify.py:249-257 runs the Verify child with NO env=, while auto.py:107-118 gives the executor child seven DISPATCH_* variables. A Verify that reads DISPATCH_* passes for the executor and fails at the gate; cli.py:2462-2470 then tells the dispatcher to fix implementation or environment, and ADR-0012 D10 forbids weakening the criterion. This burns human time and is arguably the highest-value fix in the report.
2. ticket.py:213-219 fallback parser turns every bullet under '## Verification' into an executed shell command with no placeholder filter and no fence tracking (in_fence toggled at ticket.py:122-124, never consulted). Latent: no generator emits that section.
3. auto.py:159-161 unlinks review-result.json then accepts whatever appears; a same-uid executor outliving its invocation can pre-create it. Needs a per-invocation nonce echoed in review-result.json.
4. landing.py:239 run-branch-exists guard is disabled for from_commit, so the landed sha is never tied to run.data['worktree_branch'].
5. cli.py:2013 reads report['rows'] with action=='mismatch' but repair() returns 'evidence_mismatch' — the doctor mismatch warning is dead code.
6. dsh.py:44-49 accepts any scheme/host with no allowlist (urllib still rejects non-http and proxies are disabled at dsh.py:209); persisted base_url (dsh.py:416) is silently reused by every mutating verb.
7. guard.py:23-24 writes .git/hooks/pre-push regardless of core.hooksPath, and status reports installed:true for a hook git may never run.
8. verify.py:276-281 accepts '..' in evidence paths (hash-only read; no content disclosure).
9. auto.py:107-127 copies the whole parent environment into executor and reviewer children (documented design).

## 四、覆盖缺口

- DSH host-side behaviour of /api/task-board/action is outside this repository.
- Runtime behaviour of repair --write, land --from-commit and the receipt chain could not be observed (no sandbox).
- Concurrency between two dispatch processes over state.json was not analysed.

---

_完整报告见 `run-1/REPORT.md` / `FINDINGS-DETAIL.md` / `NEEDS-VALIDATION.md` / `findings.json` / `coverage-ledger.json`。_