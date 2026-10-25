"""跑全量测试：把 tests/*.py 按文件分给 N 个进程并行跑（只用标准库）。

用法：
    python scripts/test_parallel.py            # 默认 4 个 worker
    python scripts/test_parallel.py -j 8       # 8 个
    python scripts/test_parallel.py -k filter  # 透传给每个 worker 的 -k
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def chunks(items: list[Path], parts: int) -> list[list[Path]]:
    """按文件大小做 LPT 均衡：大的先放，谁先空谁接下一个。"""
    parts = max(1, min(parts, len(items)))
    buckets: list[list[Path]] = [[] for _ in range(parts)]
    loads = [0] * parts
    def weight(item: Path) -> int:
        text = item.read_text(encoding="utf-8", errors="ignore")
        return 12 * text.count("def test_") + item.stat().st_size // 200

    for path in sorted(items, key=weight, reverse=True):
        lightest = loads.index(min(loads))
        buckets[lightest].append(path)
        loads[lightest] += weight(path)
    return [bucket for bucket in buckets if bucket]


def run_worker(files: list[Path], extra: list[str]) -> tuple[int, str, float]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    command = [
        sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
        *[str(path.relative_to(ROOT)) for path in files], *extra,
    ]
    started = time.time()
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    return result.returncode, (result.stdout + result.stderr), time.time() - started


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-j", "--jobs", type=int, default=4)
    parser.add_argument("-k", "--keyword", default="")
    args = parser.parse_args(argv)

    files = sorted((ROOT / "tests").glob("test_*.py"))
    if not files:
        print("no tests found")
        return 1
    extra = ["-k", args.keyword] if args.keyword else []
    groups = chunks(files, args.jobs)
    started = time.time()
    failures = 0
    with futures.ThreadPoolExecutor(max_workers=len(groups)) as pool:
        jobs = [pool.submit(run_worker, group, extra) for group in groups]
        for index, job in enumerate(futures.as_completed(jobs), start=1):
            code, output, elapsed = job.result()
            tail = [line for line in output.strip().splitlines() if line.strip()]
            summary = tail[-1] if tail else "(no output)"
            print(f"worker {index}: exit={code} {elapsed:.0f}s | {summary[:120]}")
            if code != 0:
                failures += 1
                print(output[-1500:])
    total = time.time() - started
    print(f"\n{len(files)} files in {total:.0f}s, {failures} failing worker(s)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
