# [completed] Full-stack docker-compose, `make up` (component-1/3/4 ops) — id: T-24

Added: 2026-07-26
Completed: 2026-07-26
Notes: Not from the original plan — user asked directly whether docker-compose should wire in the
Dockerfile and for a `make up` that brings up everything. Supersedes the earlier "compose is infra
only" decision (see docs/DECISIONS.md). Caught and fixed a real bug during verification: JWT key path
defaults broke under the Dockerfile's non-editable install.
Feature doc: docs/features/full-stack-compose.md
