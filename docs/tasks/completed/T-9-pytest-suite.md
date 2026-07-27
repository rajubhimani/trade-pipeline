# [done] pytest suite scaffold + CI-style Makefile targets (testing) — id: T-9

Added: 2026-07-26
Completed: 2026-07-26
Notes: The pytest suite itself already existed and mirrors src/ (built incrementally across T-3
through T-8, 69 tests). Remaining scope was automation: trade-pipeline/Makefile (install/lint/test/audit/check
targets, thin wrappers over `uv run ...` so they work identically without `make`, e.g. on Windows) and
.github/workflows/ci.yml running the same checks on push/PR to main and develop, matrixed across
Python 3.11-3.14 (this project's full requires-python range) so version-compat claims are continuously
verified, not just asserted.
Caught and fixed the classic GitHub Actions YAML gotcha where an unquoted `on:` key gets parsed as
boolean True by YAML-1.1 parsers (quoted as "on": instead) — verified via PyYAML before trusting it.
Feature doc: docs/features/ci-and-makefile.md
