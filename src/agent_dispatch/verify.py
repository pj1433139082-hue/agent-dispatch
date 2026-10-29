"""Independent verification gate: commands, git diff, and evidence hashes."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .state import DispatchState, Run
from .ticket import Ticket

IGNORED_PREFIXES = (
    ".dispatch/",
    ".scratch/",
    ".dsh-hooks/",
    ".git/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
)
IGNORED_SUFFIXES = (".pyc", ".pyo")


def _normalize(path: str) -> str:
    value = path.replace("\\", "/").strip()
    while value.startswith("./"):
        value = value[2:]
    return value


def _glob_regex(pattern: str) -> re.Pattern[str]:
    out: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                # **/ 要能匹配"零层目录"（gitignore 语义）：src/**/*.py 也得命中 src/a.py
                if index + 2 < len(pattern) and pattern[index + 2] == "/":
                    out.append("(?:.*/)?")
                    index += 3
                    continue
                out.append(".*")
                index += 2
                continue
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
        index += 1
    out.append("$")
    return re.compile("".join(out))


def path_matches_scope(scope: str, path: str) -> bool:
    scope = _normalize(scope)
    path = _normalize(path)
    if not scope or not path:
        return False
    if scope.endswith("/"):
        scope = scope + "**"
    if not any(marker in scope for marker in "*?["):
        return path == scope or path.startswith(scope.rstrip("/") + "/")
    return bool(_glob_regex(scope).match(path))


def _ignored(path: str) -> bool:
    return path.startswith(IGNORED_PREFIXES) or path.endswith(IGNORED_SUFFIXES)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)


HOUSEKEEPING_PATHS = (".gitignore", ".gitattributes")


def housekeeping(path: str) -> bool:
    return path in HOUSEKEEPING_PATHS


HOST_OWNED_PREFIXES = (".agents/", ".claude/", ".codex/", ".cursor/", ".gemini/")


def host_owned(path: str) -> bool:
    return path.startswith(HOST_OWNED_PREFIXES)


PIPELINE_DOC_PREFIXES = (
    ".dispatch/",
    "docs/questions/",
    "docs/selection/",
    "docs/specs/",
    "tickets/",
)


def _pipeline_doc(path: str) -> bool:
    return path.startswith(PIPELINE_DOC_PREFIXES)


def _reparse_point(path: Path) -> bool:
    """符号链接 / Windows junction / 其它 reparse point。"""
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def link_in_path(root: Path, relative: str) -> str | None:
    """返回路径上第一个 reparse point（相对 root），没有则 None。"""
    root = Path(root)
    current = root
    for part in Path(relative).parts:
        current = current / part
        if _reparse_point(current):
            try:
                return str(current.relative_to(root)).replace("\\", "/")
            except ValueError:
                return str(current)
    return None


def changed_files(root: Path, base_commit: str) -> list[str]:
    if not base_commit:
        raise ValueError("run has no base commit; render inside a git repository")
    diff = _git(root, "diff", "--name-only", "-z", base_commit)
    if diff.returncode != 0:
        raise ValueError(diff.stderr.decode("utf-8", errors="replace").strip())
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if untracked.returncode != 0:
        raise ValueError(untracked.stderr.decode("utf-8", errors="replace").strip())
    paths = {
        _normalize(path)
        for payload in (diff.stdout, untracked.stdout)
        for path in payload.decode("utf-8", errors="replace").split("\0")
        if path
    }
    return sorted(path for path in paths if not _ignored(path))


def diff_digest(root: Path, base_commit: str) -> tuple[str, str]:
    """一次算出 (哈希, 可读文本)。哈希是唯一口径：tracked 二进制 diff + 未跟踪文件内容。"""
    if not base_commit:
        raise ValueError("run has no base commit; render inside a git repository")
    binary = _git(root, "diff", "--binary", "--no-color", base_commit)
    if binary.returncode != 0:
        raise ValueError(binary.stderr.decode("utf-8", errors="replace").strip())
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if untracked.returncode != 0:
        raise ValueError(untracked.stderr.decode("utf-8", errors="replace").strip())
    paths = [
        _normalize(raw)
        for raw in untracked.stdout.decode("utf-8", errors="replace").split("\0")
        if raw
    ]
    digest = hashlib.sha256()
    digest.update(binary.stdout)
    for path in sorted(path for path in paths if not _ignored(path)):
        candidate = root / path
        if candidate.is_file():
            digest.update(path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(candidate.read_bytes())
            digest.update(b"\0")
    text = _git(root, "diff", "--no-color", base_commit).stdout.decode("utf-8", errors="replace")
    for path in sorted(path for path in paths if not _ignored(path)):
        candidate = root / path
        if not candidate.is_file():
            continue
        body = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
        hunk = ["diff --git a/" + path + " b/" + path, "new file mode 100644", "--- /dev/null", "+++ b/" + path]
        hunk.extend("+" + line for line in body)
        text += "\n".join(hunk) + "\n"
    return digest.hexdigest(), text


def worktree_diff_hash(root: Path, base_commit: str) -> str:
    """Hash the reviewable worktree diff, including untracked file contents."""
    if not base_commit:
        raise ValueError("run has no base commit; render inside a git repository")
    diff = _git(root, "diff", "--binary", "--no-color", base_commit)
    if diff.returncode != 0:
        raise ValueError(diff.stderr.decode("utf-8", errors="replace").strip())
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if untracked.returncode != 0:
        raise ValueError(untracked.stderr.decode("utf-8", errors="replace").strip())
    digest = hashlib.sha256()
    digest.update(diff.stdout)
    for raw in sorted(
        path for path in untracked.stdout.decode("utf-8", errors="replace").split("\0") if path
    ):
        path = _normalize(raw)
        if _ignored(path):
            continue
        candidate = root / path
        if candidate.is_file():
            digest.update(path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(candidate.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_command(command: str, root: Path, log_path: Path, timeout: int) -> dict[str, object]:
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        exit_code = result.returncode
        body = f"$ {command}\n\n[stdout]\n{result.stdout}\n[stderr]\n{result.stderr}"
    except (OSError, ValueError) as error:
        exit_code = -1
        body = f"$ {command}\n\n[failed to start]\n{error}\n"
    except subprocess.TimeoutExpired as error:
        exit_code = -1
        body = f"$ {command}\n\n[timeout after {timeout}s]\n{error}\n"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(body, encoding="utf-8")
    return {
        "command": command,
        "exit_code": exit_code,
        "log": log_path.name,
        "log_hash": _sha256(log_path),
    }


def _evidence_path(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if Path(value).is_absolute():
        return None
    return value


def _evaluate_evidence(
    item: object, *, run_dir: Path, prefix: str, execution_root: Path | None = None
) -> tuple[dict[str, object] | None, str | None, bool]:
    """Return (record, error, attested) for one evidence item."""
    if not isinstance(item, dict):
        return None, f"{prefix} must be an object", False
    kind = item.get("kind")
    if kind == "file":
        value = _evidence_path(item.get("path"))
        if value is None:
            return None, f"{prefix}.path must be a non-empty relative path", False
        path = run_dir / value
        if not path.is_file() and execution_root is not None:
            candidate = Path(execution_root) / value
            if candidate.is_file():
                path = candidate
        if not path.is_file():
            return None, f"{prefix}: evidence file is missing: {value}", False
        digest = _sha256(path)
        supplied = item.get("sha256")
        if supplied is not None and supplied != digest:
            return None, f"{prefix}: file hash mismatch for {value}", False
        return (
            {"kind": "file", "path": value, "sha256": digest, "attested": False},
            None,
            False,
        )
    if kind == "inline":
        content = item.get("content")
        if not isinstance(content, str):
            return None, f"{prefix}.content must be a string", False
        digest = _sha256_text(content)
        supplied = item.get("sha256")
        if supplied is not None and supplied != digest:
            return None, f"{prefix}: inline hash mismatch", False
        return (
            {"kind": "inline", "sha256": digest, "attested": False},
            None,
            False,
        )
    if kind == "absent":
        value = _evidence_path(item.get("path"))
        if value is None:
            return None, f"{prefix}.path must be a non-empty relative path", False
        if (run_dir / value).exists():
            return None, f"{prefix}: absent evidence path exists: {value}", False
        return {"kind": "absent", "path": value, "attested": False}, None, False
    if kind == "command":
        command = item.get("command")
        exit_code = item.get("exit_code")
        expect_exit = item.get("expect_exit", 0)
        if not isinstance(command, str) or not command:
            return None, f"{prefix}.command must be a non-empty string", False
        if not isinstance(exit_code, int) or isinstance(exit_code, bool):
            return None, f"{prefix}.exit_code must be an integer", False
        if not isinstance(expect_exit, int) or isinstance(expect_exit, bool):
            return None, f"{prefix}.expect_exit must be an integer", False
        if exit_code != expect_exit:
            return None, (
                f"{prefix}: command evidence reports exit code {exit_code}, "
                f"expected {expect_exit}"
            ), False
        return (
            {"kind": "command", "command": command, "exit_code": exit_code, "attested": False},
            None,
            False,
        )
    if kind == "note":
        note = item.get("note")
        if not isinstance(note, str) or not note:
            return None, f"{prefix}.note must be a non-empty string", False
        return {"kind": "note", "note": note, "attested": True}, None, True
    return None, f"{prefix}.kind must be file, inline, absent, command or note", False


def _evaluate_criteria(
    receipt: dict[str, object], ticket: Ticket, run_dir: Path, execution_root: Path | None = None
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str], bool]:
    errors: list[str] = []
    records: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    degraded = False
    value = receipt.get("criteria")
    if not isinstance(value, list) or not value:
        return records, evidence, ["criteria must be a non-empty array"], False
    seen: set[int] = set()
    for index, item in enumerate(value, start=1):
        prefix = f"criteria[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        criterion_id = item.get("id")
        if not isinstance(criterion_id, int) or isinstance(criterion_id, bool) or criterion_id < 1:
            errors.append(f"{prefix}.id must be a positive integer")
            criterion_id = 0
        elif criterion_id in seen:
            errors.append(f"{prefix}.id is duplicated: {criterion_id}")
        else:
            seen.add(criterion_id)
        verdict = item.get("verdict")
        if verdict not in {"pass", "fail"}:
            errors.append(f"{prefix}.verdict must be pass or fail")
            verdict = "fail"
        if verdict == "fail":
            errors.append(f"{prefix} verdict is fail")
        items = item.get("evidence")
        item_records: list[dict[str, object]] = []
        if not isinstance(items, list) or not items:
            errors.append(f"{prefix}.evidence must be a non-empty array")
            items = []
        for evidence_index, evidence_item in enumerate(items, start=1):
            record, error, attested = _evaluate_evidence(
                evidence_item,
                run_dir=run_dir,
                prefix=f"{prefix}.evidence[{evidence_index}]",
                execution_root=execution_root,
            )
            if error:
                errors.append(error)
            if record is not None:
                record["criterion_id"] = criterion_id
                item_records.append(record)
                evidence.append(record)
        # degraded 的判据是「这条 criterion 的全部证据都是 note」，不是「某个前缀全是 note」：
        # 证据书写顺序不能改变结论（note 写在 file 前面时，file 已经提供了可复算物证）。
        degraded = degraded or (bool(item_records) and all(bool(entry.get("attested")) for entry in item_records))
        records.append(
            {
                "id": criterion_id,
                "verdict": verdict,
                "note": item.get("note", ""),
                "evidence": item_records,
            }
        )
    expected = set(range(1, len(ticket.acceptance) + 1))
    if seen != expected:
        errors.append(
            f"criteria ids must be exactly 1..{len(ticket.acceptance)} (one per Acceptance item), got {sorted(seen)}"
        )
    return records, evidence, errors, degraded


def _persona_state(root: Path, ticket: Ticket, run: Run, receipt: dict | None) -> tuple[dict[str, object], list[str]]:
    """人格绑定与回执核对：只影响 degraded，不让 verify 直接 failed。"""
    from .persona import persona_policy, persona_required, persona_source_path

    record: dict[str, object] = {
        "required": False,
        "bound": run.data.get("persona"),
        "waiver": run.data.get("persona_waiver"),
        "receipt": None,
        "issues": [],
    }
    issues: list[str] = []
    policy = persona_policy(root)
    bound = run.data.get("persona") if isinstance(run.data.get("persona"), dict) else None
    waiver = run.data.get("persona_waiver") if isinstance(run.data.get("persona_waiver"), dict) else None
    legacy = False
    if not bound and not waiver:
        skill = str(run.data.get("skill_version", ""))
        parts = skill.split(".")
        try:
            legacy = tuple(int(p) for p in parts[:3]) < (1, 8, 3)
        except ValueError:
            legacy = False
    required = (
        not legacy
        and persona_required(ticket.risk, policy)
        and not run.data.get("persona_waiver")
    )
    record["required"] = required
    record["legacy"] = legacy
    if bound:
        path = persona_source_path(root, str(bound.get("source", "")))
        if path is None or not Path(path).is_file():
            issues.append("persona source file is missing")
        else:
            actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
            if actual != str(bound.get("sha256", "")):
                issues.append("persona file changed after render")
    if isinstance(receipt, dict):
        reported = receipt.get("persona")
        if isinstance(reported, dict):
            record["receipt"] = reported
            if bound and str(reported.get("sha256", "")) != str(bound.get("sha256", "")):
                issues.append("receipt persona does not match the run binding")
            if not bound:
                issues.append("receipt reports a persona but the run has none")
        elif required:
            issues.append("receipt does not report the persona")
    elif required:
        issues.append("no receipt to attest the persona")
    record["issues"] = issues
    return record, issues


def verify_run(
    root: Path,
    ticket: Ticket,
    run: Run,
    timeout: int = 300,
    allow_main_drift: bool = False,
) -> tuple[dict[str, object], bool]:
    root = Path(root)
    run_dir = run.directory
    checks: list[dict[str, object]] = []
    errors: list[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            errors.append(f"{name}: {detail}")

    ticket_path = run.ticket_path
    if not ticket_path.is_file():
        check("ticket", False, f"ticket file is missing: {ticket_path}")
    else:
        actual_hash = hashlib.sha256(ticket_path.read_bytes()).hexdigest()
        expected_hash = str(run.data.get("ticket_hash", ""))
        check(
            "ticket",
            actual_hash == expected_hash,
            "ticket changed after render (revert the ticket, or retry/render again)" if actual_hash != expected_hash else "unchanged",
        )

    receipt_path = run_dir / "receipt.json"
    receipt: dict[str, object] | None = None
    receipt_kind = ""
    if not receipt_path.is_file():
        check(
            "receipt",
            False,
            "receipt.json is missing (the executor must write it into the run directory; "
            "if the executor script lives inside the worktree, it has to be committed BEFORE render, "
            "otherwise the run only sees the older snapshot — pass an absolute path instead)",
        )
    else:
        try:
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            check("receipt", False, f"receipt.json is not valid JSON: {error}")
        else:
            if not isinstance(payload, dict):
                check("receipt", False, "receipt.json must be an object")
            else:
                receipt = payload
                problems: list[str] = []
                if payload.get("status") != "done":
                    problems.append(f"status is {payload.get('status')!r}, expected 'done'")
                if payload.get("ticket_id") != ticket.id:
                    problems.append("ticket_id does not match")
                if payload.get("run_id") != run.id:
                    problems.append("run_id does not match")
                if not isinstance(payload.get("summary"), str) or not payload.get("summary"):
                    problems.append("summary is required")
                if "criteria" in payload:
                    receipt_kind = "criteria"
                elif isinstance(payload.get("evidence"), list) and payload.get("evidence"):
                    receipt_kind = "legacy"
                else:
                    problems.append("criteria must be a non-empty array (or legacy evidence)")
                check(
                    "receipt",
                    not problems,
                    "; ".join(problems) if problems else "valid receipt",
                )

    commands: list[dict[str, object]] = []
    if receipt is not None:
        for index, command in enumerate(ticket.verify, start=1):
            record = _run_command(
                command,
                run.execution_root,
                run_dir / "logs" / f"{index:02d}.log",
                timeout,
            )
            commands.append(record)
            check(
                f"command {index}",
                record["exit_code"] == 0,
                f"exit code {record['exit_code']}" if record["exit_code"] else "passed",
            )

    files: list[str] = []
    diff_hash = ""
    execution_root = run.execution_root
    try:
        files = changed_files(execution_root, str(run.data.get("base_commit", "")))
        diff_hash = worktree_diff_hash(execution_root, str(run.data.get("base_commit", "")))
    except ValueError as error:
        check("git diff", False, str(error))
    else:
        out_of_scope = [
            path
            for path in files
            if not any(path_matches_scope(scope, path) for scope in ticket.write_scope)
        ]
        house_only = [path for path in out_of_scope if housekeeping(path)]
        if house_only:
            out_of_scope = [path for path in out_of_scope if path not in house_only]
            checks.append(
                {
                    "name": "housekeeping (ignored)",
                    "ok": True,
                    "detail": "not ticket output: " + ", ".join(house_only),
                }
            )
        scope_detail = "out of scope: " + ", ".join(out_of_scope) if out_of_scope else "all changes in scope"
        host_paths = [path for path in out_of_scope if host_owned(path)]
        if host_paths:
            scope_detail += (
                " | these look like host-installed packages, not this ticket's output: "
                + ", ".join(host_paths)
                + " (add them to the write scope only if the ticket really ships them)"
            )
        check("write scope", not out_of_scope, scope_detail)
        links = sorted(
            {
                found
                for path in files
                if (found := link_in_path(execution_root, path)) is not None
            }
        )
        check(
            "symlink",
            not links,
            "write path goes through a symlink/junction, which can escape the repository: "
            + ", ".join(links)
            if links
            else "no symlink/junction in the changed paths",
        )
        if execution_root.resolve() != root.resolve():
            try:
                # 与**当前 HEAD**比较，而不是 run 的 base commit：主仓在 run 期间
                # 的正常提交不算作弊，只有当前仍脏的改动才说明有人在主仓上动手。
                main_files = changed_files(root, "HEAD")
                # 流水线自产文档（S1 问卷 / S2 选型 / S3 规格 / S4 票）不改执行根，
                # 它们留在主仓里属于正常，不该把 verify 判死；其它脏文件仍照拦。
                skipped_main = [path for path in main_files if _pipeline_doc(path)]
                main_files = [path for path in main_files if not _pipeline_doc(path)]
                if skipped_main:
                    checks.append(
                        {
                            "name": "main checkout (ignored)",
                            "ok": True,
                            "detail": "outside the write scope: " + ", ".join(skipped_main),
                        }
                    )
            except ValueError as error:
                check("main checkout", False, str(error))
            else:
                allowed = bool(main_files) and allow_main_drift
                if not main_files:
                    detail = "clean"
                elif allowed:
                    detail = "main checkout has uncommitted changes (allowed): " + ", ".join(main_files)
                else:
                    detail = (
                        "main checkout has uncommitted changes: "
                        + ", ".join(main_files)
                        + " (commit them first; dispatch setup writes .gitignore, so run: "
                        "git add .gitignore && git commit -m 'chore: ignore .dispatch'"
                        + ")"
                    )
                check("main checkout", not main_files or allow_main_drift, detail)
                files = sorted(set(files) | set(main_files))

    evidence: list[dict[str, object]] = []
    criteria: list[dict[str, object]] = []
    criteria_errors: list[str] = []
    degraded = False
    if receipt is not None:
        if receipt_kind == "criteria":
            criteria, evidence, criteria_errors, degraded = _evaluate_criteria(
                receipt, ticket, run_dir, run.execution_root
            )
        elif receipt_kind == "legacy":
            for item in receipt.get("evidence", []):
                if not isinstance(item, str) or not item:
                    criteria_errors.append("evidence entries must be non-empty strings")
                    continue
                candidate = Path(item)
                if candidate.is_absolute():
                    criteria_errors.append(f"absolute evidence path is not allowed: {item}")
                    continue
                path = run_dir / candidate
                if not path.is_file():
                    criteria_errors.append(f"evidence file is missing: {item}")
                    continue
                evidence.append({"kind": "file", "path": item, "sha256": _sha256(path), "attested": False})
    if criteria_errors:
        check("criteria", False, "; ".join(criteria_errors))

    persona_record, persona_issues = _persona_state(root, ticket, run, receipt)
    if persona_issues:
        degraded = True

    status = "failed" if errors else ("degraded" if degraded else "passed")
    record: dict[str, object] = {
        "run_id": run.id,
        "ticket_id": ticket.id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "receipt_kind": receipt_kind,
        "checks": checks,
        "changed_files": files,
        "diff_hash": diff_hash,
        "diff_scope": "tracked+untracked",
        "commands": commands,
        "criteria": criteria,
        "evidence": evidence,
        "degraded": degraded,
        "persona": persona_record,
        "errors": errors,
    }
    (run_dir / "verify.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    store = DispatchState(root)
    if status == "failed":
        run.set_state("failed")
        store.set_ticket(ticket.id, run.id, "failed")
    else:
        run.set_state("review")
        store.set_ticket(ticket.id, run.id, "review")
    return record, status != "failed"
