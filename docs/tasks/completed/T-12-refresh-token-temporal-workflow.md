# [completed] Refresh-token rotation as a Temporal workflow (component-3, learning) — id: T-12

Added: 2026-07-26
Completed: 2026-07-26
Notes: mentioned as a candidate in docs/ARCHITECTURE.md; not required for the auth flow to work, but a
good second Temporal example beyond enrichment. Low priority relative to T-5/T-6. Caught and fixed a
real bug during verification: raising a plain domain exception from workflow code hangs the workflow
instead of failing it — see feature doc.
Feature doc: docs/features/refresh-token-temporal-workflow.md
