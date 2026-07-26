---
name: add-task
description: Add a new task file to docs/tasks/backlog/ for the trade-pipeline project. Use when the user asks to add/create a task, schedule work, or track a new to-do item. All tasks live in the backlog from creation until done, so this is the single entry point for new work items (see create-backlog-task for the same operation framed as "just an idea").
tools: Read, Write, Glob
---

# Add Task

Creates a new task file under `docs/tasks/backlog/`. One file per task — never appends into an
existing file, never edits another task's file.

## Workflow

1. List `docs/tasks/backlog/` and `docs/tasks/completed/` (Glob `docs/tasks/**/T-*.md`) to find the
   highest existing `T-<n>` id across both — ids are never reused even after a task is completed.
2. Ask the user (or infer from context) for: task title, area (short parenthetical tag, e.g.
   `component-2`, `setup`, `testing`, `docs`), and any notes.
3. Create `docs/tasks/backlog/T-<n>-<slug>.md` (kebab-case slug from the title) with this exact shape:

```markdown
# [todo] Task title (area) — id: T-<n>

Added: YYYY-MM-DD
Notes: free text
```

Add a `Feature doc: docs/features/<slug>.md` line only if that file already exists.

4. Do not touch any other file in `docs/tasks/`.
5. Report the new task id and filename back to the user in one line.
