# Feature: CI-style Makefile targets + GitHub Actions

Status: shipped
Task: docs/tasks/completed/T-9-pytest-suite.md

## Problem / motivation

The pytest suite itself already exists and mirrors `src/` (`../CODING_STANDARDS.md`), so T-9's real
remaining gap is automation: the plan's Week 5 security track explicitly says to "add [pip-audit] to
your Makefile so this runs automatically in CI" — there's currently no `Makefile` and no CI at all, so
lint/test/audit only run when a human remembers to type the commands.

## Scope

In:
- `trade-pipeline/Makefile` — `install`, `lint`, `test`, `audit`, `check` (runs all three) targets,
  matching exactly the commands already documented in `../GIT_PRACTICES.md`'s pre-push checklist.
- `.github/workflows/ci.yml` — runs `make check` on push/PR to `develop` and `main`, using `uv` for
  environment setup, matrixed across Python 3.11–3.14 (this project's whole `requires-python` range,
  not just the newest interpreter) so version-compat regressions surface automatically.

Out:
- Docker-based integration/end-to-end CI (spinning up Kafka/Redis/Postgres in CI and running a real
  producer→consumer→API smoke test) — real infrastructure in CI is heavier than this project's current
  scope; unit/component tests with fakes are what CI runs. Tracked as a natural follow-up if the
  project grows a deployment target, not built now.
- Coverage thresholds/gates — `pytest-cov` is already a dev dependency; CI can report coverage without
  this feature needing to enforce a minimum.

## Design

- Makefile targets are thin wrappers around `uv run ...` — no logic lives in the Makefile itself, so
  running the same commands locally without `make` (e.g. on Windows without a `make` binary) still
  works identically.
- CI matrixes Python versions using `uv python install <version>` + `uv run --python <version>`,
  proving the `requires-python = ">=3.11,<3.15"` claim is actually true across the range, not just on
  whatever interpreter a developer happens to have active locally.
- `pip-audit` runs as its own CI step (not silently folded into `make check`'s exit code only) so a
  new vulnerability shows up as a distinctly-labeled failure, not a generic "check failed."

## Python version notes

This is the feature that actually *exercises* the 3.11–3.14 range in an automated way — every other
part of the codebase talks about version compatibility, this is what verifies it continuously.

## Testing plan

No new application code to unit test. Verified: each underlying command (`uv run ruff check .`,
`uv run pytest tests/ -q`, `uv run pip-audit`) runs clean directly (no local `make` binary on this
Windows dev machine, which is exactly the scenario the Makefile-as-thin-wrapper design accounts for —
CI runs on `ubuntu-latest` where `make` is present). The workflow YAML was parsed with PyYAML to catch
the classic GitHub Actions gotcha where an unquoted `on:` key gets coerced to the boolean `True` by a
YAML-1.1-compliant parser — fixed by quoting it as `"on":`, which GitHub's own parser also accepts.
