# Python 3.11 → 3.14 reference (condensed from the prep plan)

Kept as a standalone doc so implementation code can cite it instead of re-deriving/hallucinating
version facts. Source of truth for "why this syntax" comments in code.

| Feature | 3.11 | 3.12 | 3.13 | 3.14 | Use in this project |
|---|---|---|---|---|---|
| `asyncio.TaskGroup` / `except*` | added | yes | yes | yes | consumer + enrichment use TaskGroup as the default; `gather()` kept alongside as the pre-3.11 comparison |
| `class Stack[T]` type params | no (`TypeVar`) | added | yes | yes | `common/` generic containers use `[T]`; a `TypeVar` version is kept as a comment for 3.11 comparison |
| `@typing.override` | no | added | yes | yes | used on any subclass overriding a base method (e.g. enrichment client adapters) |
| Deferred annotations default (PEP 649) | needs `from __future__ import annotations` | needs it | needs it | default | modules targeting 3.14 omit the future-import; a note is left where 3.11 compat needs it added back |
| Free-threaded build (PEP 703/779) | no | no | experimental | stable (opt-in binary) | not used for prod code paths; mentioned only in `docs/DECISIONS.md` GIL discussion |
| `t-strings` (PEP 750) | no | no | no | yes | used in `api/` for the "safe templating" example only — not a general SQL string builder |
| `concurrent.futures.InterpreterPoolExecutor` (PEP 734) | no | no | no | yes | candidate for CPU-bound archival compression; plain `multiprocessing` kept as the 3.11-compatible fallback |
| `compression.zstd` | no | no | no | yes (stdlib) | cold-storage archival; `zstandard` PyPI package is the fallback import for <3.14 |
| `copy.replace()` | no | no | added | yes | used on frozen dataclasses (e.g. `TradeEvent`) instead of `dataclasses.replace()` |
| `tomllib` | yes (stdlib) | yes | yes | yes | used for any TOML config reading, no third-party `toml` dep |

## Rule for writing code in this repo

When a feature is version-gated:
1. Write the 3.14-native version as the primary implementation.
2. Add a one-line comment: `# 3.11 fallback: <alternative>` — do not write the fallback as dead code
   unless it's specifically the point of a demo module (see `common/version_compat_demo.py`).
3. Never claim a feature exists on a version without checking this table first.
