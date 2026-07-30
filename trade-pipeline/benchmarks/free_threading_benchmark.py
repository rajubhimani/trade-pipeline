"""CPU-bound threads-vs-processes benchmark: standard Python 3.14 vs the
free-threaded 3.14t build (PEP 703).

Not part of the trade-pipeline application — a standalone learning script
for the plan's Week 3 CPython-internals study (see
../../python_full_prep.html and docs/features/free-threaded-benchmark.md
for real measured results). Run the identical script under both
interpreters to see the GIL's effect on CPU-bound multithreading directly:

    uv run --python 3.14  python benchmarks/free_threading_benchmark.py
    uv run --python 3.14t python benchmarks/free_threading_benchmark.py

On the standard (GIL) build, N CPU-bound threads run no faster than 1 —
the GIL only lets one thread execute Python bytecode at a time, so threads
just take turns. On 3.14t, threads scale close to `min(workers, cpu_count)`,
similar to `multiprocessing`/`ProcessPoolExecutor` but without the
IPC/pickling overhead of separate processes.
"""

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


def cpu_bound_work(n: int) -> int:
    """A pure-Python busy loop — deliberately not numpy/C-accelerated, so
    what's measured is the interpreter's own bytecode execution (and
    therefore GIL contention), not time spent inside a C extension that
    already releases the GIL on its own.
    """
    total = 0
    for i in range(n):
        total += i * i
    return total


def run(executor_cls, workers: int, n: int) -> float:
    start = time.perf_counter()
    with executor_cls(max_workers=workers) as executor:
        list(executor.map(cpu_bound_work, [n] * workers))
    return time.perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--n", type=int, default=20_000_000, help="loop iterations per worker")
    args = parser.parse_args()

    # sys._is_gil_enabled() (3.13+, free-threaded builds only meaningfully
    # return False) — reports the *actual* runtime state, not just which
    # build this is: a 3.14t interpreter can still re-enable the GIL
    # (PYTHON_GIL=1, or a loaded extension that isn't free-threading-safe).
    gil_enabled = getattr(sys, "_is_gil_enabled", lambda: True)()
    print(f"Python {sys.version.split()[0]}  GIL enabled: {gil_enabled}  workers={args.workers}")

    single = run(ThreadPoolExecutor, 1, args.n)
    print(f"1 thread        : {single:.2f}s (baseline)")

    threads = run(ThreadPoolExecutor, args.workers, args.n)
    print(f"{args.workers} threads      : {threads:.2f}s  (speedup {single / threads:.2f}x)")

    processes = run(ProcessPoolExecutor, args.workers, args.n)
    print(f"{args.workers} processes    : {processes:.2f}s  (speedup {single / processes:.2f}x)")


if __name__ == "__main__":
    main()
