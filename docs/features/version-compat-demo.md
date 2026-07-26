# Feature: Old-vs-new Python version comparison demo

Status: shipped
Task: docs/tasks/completed/T-11-version-compat-demo.md

## Problem / motivation

The user's explicit learning goal: understand concretely how idiomatic Python code changes from 3.11
to 3.14, side by side, well enough to compare and explain it — not just read a feature list. The rest
of the codebase intentionally writes the 3.14-native form with a one-line fallback *comment*
(`../PYTHON_VERSION_NOTES.md` rule), which is right for production code but not enough for learning —
comments aren't runnable or provably correct.

## Scope

In: `src/trade_pipeline/common/version_compat_demo.py` — four paired old-way/new-way implementations
that are both real, both run, and are both exercised by tests proving they behave equivalently:

1. Generics: `TypeVar` + `Generic[T]` (3.11) vs `class Stack[T]` (3.12+, PEP 695) — the 3.12+ side is
   defined via `exec()` gated on `sys.version_info` so the module still imports on 3.11–3.13 without a
   `SyntaxError`.
2. Structured concurrency: `asyncio.gather(return_exceptions=True)` (works on any version) vs
   `asyncio.TaskGroup` + `except*` (3.11+, PEP 654) — both fan out over multiple coroutines; the
   TaskGroup version demonstrates automatic sibling cancellation on failure.
3. Immutable updates: `dataclasses.replace()` (always available) vs `copy.replace()` (3.13+) on a
   frozen, slotted dataclass.
4. Forward references: `from __future__ import annotations` (required on 3.11–3.13 for a class method
   to reference its own still-being-defined class) vs PEP 649 deferred annotations (3.14 default,
   import becomes unnecessary).

Out: a full survey of every 3.11→3.14 feature (free-threading, t-strings, `InterpreterPoolExecutor`,
`compression.zstd`) — those are used in-place elsewhere in the codebase (producer, enrichment,
Dagster job) as they get built, rather than duplicated here as isolated demos.

## Design

Each pair is genuinely runnable, not just described — the point is a reader can execute both sides
and see them produce equivalent results, then read the diff in approach. The 3.12+ generics section
uses `exec()` on a string precisely so `sys.version_info < (3, 12)` doesn't crash the whole module at
import time on an older interpreter — this is *not* a pattern used elsewhere in the codebase, it's
specific to keeping one demo module importable across the full version range.

## Python version notes

This is the one module explicitly designed to be run/compared across 3.11 vs 3.12+ vs 3.14 rather
than targeting one interpreter — see `../PYTHON_VERSION_NOTES.md` for the feature-by-version table
this demo is built from.

## Testing plan

`tests/common/test_version_compat_demo.py`, 8 tests, all passing:
- `StackOld` and `StackNew` (the latter skipped on <3.12 via `pytest.mark.skipif`) produce identical
  push/pop behavior.
- `fan_out_gather` and `fan_out_taskgroup` both handle a failing coroutine without raising out of the
  helper, and agree on results when all coroutines succeed.
- `move_old_way` (`dataclasses.replace`) and `move_new_way` (`copy.replace`) produce identical output
  and leave the original frozen instance untouched.
