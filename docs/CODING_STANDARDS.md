# Coding standards

Project-specific conventions. General "write good code" advice is deliberately left out — this file
only covers decisions that aren't obvious from reading the code, so they don't need re-deriving (or
guessing) every session.

## Linting & formatting — ruff

`ruff` is the single tool for both linting and import sorting (see `trade-pipeline/pyproject.toml`
`[tool.ruff]`). Enabled rule sets: `E`, `F`, `I` (import order), `UP` (pyupgrade — flags outdated
syntax for the target Python version), `B` (bugbear), `C4` (comprehensions), `SIM` (simplify), `RUF`.

Run before every commit:
```
cd trade-pipeline
uv run ruff check .
uv run ruff check --fix .   # auto-fixes what it can
```

`target-version = "py311"` — ruff's `UP` rules upgrade syntax only as far as 3.11 allows project-wide
(e.g. `datetime.UTC` alias, which exists since 3.11). Do not let ruff "upgrade" code to a 3.12+-only
construct outside of the explicitly version-gated modules (see below) — it doesn't know about our
`requires-python = ">=3.11,<3.15"` floor per-construct, only per-target-version globally.

**Exception**: `src/trade_pipeline/common/version_compat_demo.py` has per-file ignores in
`pyproject.toml` (`UP035`, `UP040`, `F401`) — it deliberately keeps old-style `TypeVar`/`Generic` and a
`from __future__ import annotations` import specifically to demonstrate the pre-3.12 form side by side
with the modern one. Don't "clean up" that file to match the rest of the codebase's style; its whole
point is showing the contrast (see `docs/features/version-compat-demo.md`).

## Version-gated code

Rule (from `docs/PYTHON_VERSION_NOTES.md`): write the newest-Python-native form as the primary
implementation, with a one-line `# 3.11 fallback: ...` comment — don't write dead fallback code paths
unless the module's whole purpose is the comparison itself (only `version_compat_demo.py` qualifies).
Before claiming a feature is available on a given version, check the table in
`docs/PYTHON_VERSION_NOTES.md` — don't rely on memory.

**Exception — version-gated stdlib *modules*, not syntax**: the comment-only rule above assumes the
newer form still *imports* cleanly on older versions (true for syntax like `class Foo[T]` guarded
behind `exec()`, or a comment noting `copy.replace()` needs 3.13+). It is **not** true for a module
that plain doesn't exist pre-3.14, like `compression.zstd` — an unconditional `from compression import
zstd` breaks collection entirely on 3.11–3.13, which the CI matrix (`.github/workflows/ci.yml`) will
catch immediately. For these, write a real `try`/`except ImportError` runtime shim (see
`dagster_pipeline/archival.py`), not a comment — this was a real bug caught by CI, not a hypothetical.

## Testing

- `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"` — async test functions don't need a decorator).
- Prefer fakes over mocking libraries for simple interfaces (see `FakeRedis`/`FakeMessage` in
  `tests/consumer/test_dedup_consumer.py`) — a 10-line fake matching the exact subset of the real
  API used is easier to read and trust than a `unittest.mock.MagicMock` with asserted call patterns.
- SQLite in-memory (sync tests) / `aiosqlite` (async tests) stand in for Postgres in unit tests — real
  Postgres-only features (JSONB, arrays, etc.) aren't used, so this is safe. Real end-to-end tests
  against actual Docker Compose services are a separate, explicitly deferred task (see
  `docs/tasks/backlog/T-9-pytest-suite.md`), not something every unit test needs.
- Test file layout mirrors `src/trade_pipeline/` exactly — `tests/<package>/test_<module>.py`.
- When a security property is being tested (e.g. JWT `alg:none` / algorithm-confusion attacks in
  `tests/api/auth/test_jwt_tokens.py`), forge the attack payload by hand rather than through the
  library being tested if that library now defends against constructing it — a real attacker isn't
  using our code to attack us, so the test should simulate an external forgery, not rely on our own
  encode function refusing to cooperate.

## Documentation-first for new work

Before writing a new component, write (or update) its `docs/features/<slug>.md` spec — via the
`create-feature` skill — covering problem/scope/design/version-notes/testing plan. This exists so
long-running work doesn't drift or get re-derived (or hallucinated) from scratch each session; see
`docs/tasks/` for the task-tracking half of this workflow and `docs/GIT_PRACTICES.md` for commits.

## Security-sensitive code

- JWT: algorithm is always passed explicitly to `jwt.decode(..., algorithms=["RS256"])` — never
  derived from the token's own header. See `docs/DECISIONS.md` and
  `src/trade_pipeline/api/auth/jwt_tokens.py`.
- Secrets (RSA private keys, DB credentials) are never hardcoded or committed — loaded from
  environment variables or local-only files excluded via `.gitignore` (`keys/*.pem`). See
  `docs/GIT_PRACTICES.md`.
- Error responses returned to API clients never include stack traces, DB errors, or internal paths —
  full detail goes to `structlog` only. This is enforced at the global exception handler, not per-route.
