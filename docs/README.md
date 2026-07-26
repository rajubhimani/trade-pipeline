# Docs index

Tracking system for the trade-pipeline project (source plan: `../faang_python_full_prep.html`).
Managed primarily via the `.claude/skills/` skills (`add-task`, `update-task`, `create-backlog-task`,
`create-feature`) — prefer those over hand-editing so format stays consistent.

- **tasks/backlog/** — one file per task (`T-<n>-<slug>.md`), from creation until done
  (`todo` / `in_progress` / `blocked`). Read this first for "what's next".
- **tasks/completed/** — task files moved here by `update-task` once status hits `done`. Changelog,
  not a todo list — each file keeps its `Completed:` date.
- **features/** — one spec doc per feature (`create-feature` skill), linked from its task file.
  Written *before or alongside* implementation so intent is on record, not reconstructed after.
- **ARCHITECTURE.md** — the 5-layer system design, and where Temporal/Dagster fit (and don't).
- **DECISIONS.md** — ADR-style rationale for non-obvious choices (Redis vs DB, RS256 vs HS256, etc).
- **PYTHON_VERSION_NOTES.md** — 3.11→3.14 feature-availability table, cited by code comments instead
  of guessed from memory.
