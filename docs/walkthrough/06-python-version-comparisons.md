[Index](README.md) · ← Previous: [Enrichment](05-enrichment.md) · Next → [Testing & tooling](07-testing-and-tooling.md)

---

# Python version comparisons

**File**: [`src/trade_pipeline/common/version_compat_demo.py`](../../trade-pipeline/src/trade_pipeline/common/version_compat_demo.py)
**Feature doc**: [docs/features/version-compat-demo.md](../features/version-compat-demo.md)
**Reference table**: [docs/PYTHON_VERSION_NOTES.md](../PYTHON_VERSION_NOTES.md)
**Tests**: [`tests/common/test_version_compat_demo.py`](../../trade-pipeline/tests/common/test_version_compat_demo.py) (8 tests)

## Why this file is different from the rest of the codebase

Everywhere else in this project, version-gated code is written in its **3.14-native form only**, with
a one-line `# 3.11 fallback: ...` comment (see [CODING_STANDARDS.md](../CODING_STANDARDS.md)). This
one module is the deliberate exception: both the old and new form are real, runnable, and tested side
by side — built specifically so the old-vs-new contrast can be read and executed, not just described.

## The four comparisons

### 1. Generics: `TypeVar` vs `class Foo[T]`

- [`StackOld`](../../trade-pipeline/src/trade_pipeline/common/version_compat_demo.py#L26) — the 3.11
  way: `TypeVar` + `Generic[T]` base class boilerplate.
- `StackNew` (built via `exec()` on a string, gated on `sys.version_info >= (3, 12)`) — the 3.12+ way:
  `class Stack[T]:` with no `TypeVar`/`Generic` needed at all. It's `exec`'d conditionally so this
  module can still be *imported* on 3.11–3.13 without a `SyntaxError`, even though `StackNew` itself
  is only usable on 3.12+.

### 2. Structured concurrency: `gather()` vs `TaskGroup`

- [`fan_out_gather`](../../trade-pipeline/src/trade_pipeline/common/version_compat_demo.py#L65) — any
  version; `return_exceptions=True` collects every result including exceptions, no cancellation of
  siblings.
- [`fan_out_taskgroup`](../../trade-pipeline/src/trade_pipeline/common/version_compat_demo.py#L73) —
  3.11+; if any task raises, all siblings are cancelled automatically and the exception surfaces via
  `except*` — structured concurrency, no manual bookkeeping.
- This is the general-purpose version of the comparison; [page 5](05-enrichment.md) explains why the
  hand-rolled enrichment code specifically picks `gather()` over `TaskGroup` (partial-results
  requirement).

### 3. Immutable updates: `dataclasses.replace()` vs `copy.replace()`

- [`move_old_way`](../../trade-pipeline/src/trade_pipeline/common/version_compat_demo.py#L103) — always
  available, `dataclasses.replace()`.
- [`move_new_way`](../../trade-pipeline/src/trade_pipeline/common/version_compat_demo.py#L109) — 3.13+,
  `copy.replace()` — works on more than just dataclasses (anything with `__replace__`).
- The rest of the codebase actually uses `copy.replace()` as its primary form — see
  [`TradeEvent`](../../trade-pipeline/src/trade_pipeline/common/models.py#L15)'s docstring.

### 4. Forward references: `from __future__ import annotations` vs deferred annotations

- The whole module has `from __future__ import annotations` at the top — required on 3.11–3.13 for
  [`Node.next(self) -> Node`](../../trade-pipeline/src/trade_pipeline/common/version_compat_demo.py#L126)
  to reference its own still-being-defined class without quoting the type.
- On 3.14, PEP 649 makes annotations deferred by default, so that import becomes unnecessary — noted
  inline rather than duplicated as a second code path, since there's nothing to *run* differently, just
  an import to omit.

## Why it's tested, not just read

[`tests/common/test_version_compat_demo.py`](../../trade-pipeline/tests/common/test_version_compat_demo.py)
runs both sides of comparisons 1–3 and asserts they produce equivalent behavior (e.g.
`test_taskgroup_all_succeed_matches_gather_all_succeed`,
`test_move_old_and_new_produce_same_result`) — proof the "modern" form is a drop-in behavioral
replacement, not just shorter syntax that might work differently.

---
[Index](README.md) · ← Previous: [Enrichment](05-enrichment.md) · Next → [Testing & tooling](07-testing-and-tooling.md)
