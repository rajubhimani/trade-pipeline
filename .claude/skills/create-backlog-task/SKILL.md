---
name: create-backlog-task
description: Add a new lightly-scoped idea as a task file in docs/tasks/backlog/ for the trade-pipeline project. Use when the user floats a "maybe later" or future enhancement that isn't ready to be worked yet but should still be on record. Functionally the same destination as add-task (all tasks live in backlog/ until done) — use this framing when the item is more idea than committed work.
tools: Read, Write, Glob
---

# Create Backlog Task

Creates a new task file under `docs/tasks/backlog/`, same location and format as `add-task`, but for
items that are more "worth remembering" than "ready to schedule." There is only one bucket for
not-yet-done work (`docs/tasks/backlog/`) — nothing here gets promoted to a different folder later;
it just gets picked up and worked (via `update-task` moving it to `in_progress`) whenever it's ready.

## Workflow

1. List `docs/tasks/backlog/` and `docs/tasks/completed/` (Glob `docs/tasks/**/T-*.md`) to find the
   highest existing `T-<n>` id across both.
2. Create `docs/tasks/backlog/T-<n>-<slug>.md`:

```markdown
# [todo] Idea title (area) — id: T-<n>

Added: YYYY-MM-DD
Notes: free text capturing *why* this might matter later — not just what it is.
```

3. Report the new task id and filename back to the user in one line.

## When to use this instead of add-task

Use this when the idea isn't scoped or prioritized yet. If the user is ready to commit to doing it
soon, `add-task` produces the identical result — either skill is fine, pick based on how the user
framed the request.
