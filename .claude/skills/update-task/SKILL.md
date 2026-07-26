---
name: update-task
description: Update the status or notes of an existing task file under docs/tasks/backlog/ or docs/tasks/completed/ for the trade-pipeline project. Use when the user says a task is done, in progress, blocked, or wants its notes changed. Reference by task id (T-n) or by matching title. Moving status to done relocates the file from backlog/ to completed/.
tools: Read, Write, Glob, Bash
---

# Update Task

Updates a task's own file in place — never duplicates it — except when the new status is `done`,
which relocates the file from `docs/tasks/backlog/` to `docs/tasks/completed/`.

## Workflow

1. Glob `docs/tasks/backlog/T-*.md` (and `docs/tasks/completed/T-*.md` if the user might be
   referencing an already-done task by mistake) to locate the file by `id: T-<n>` in its heading, or
   by matching title text (case-insensitive substring). If more than one matches, ask which one.
2. Read the file.
3. If the new status is **not** `done` (`todo`, `in_progress`, `blocked`):
   - Rewrite the `# [status] ...` heading line with the new status marker, same file, same path.
   - If the user gave new information, append it to the `Notes:` line rather than replacing prior
     notes outright, unless the prior notes are now factually wrong — then replace and keep the
     correction terse.
   - Leave `Added:` untouched.
4. If the new status **is** `done`:
   - Rewrite the heading to `# [done] ...`, add a `Completed: YYYY-MM-DD` line (today) right after
     `Added:`, and fold in any final notes the user gives.
   - If `docs/features/<slug>.md` exists for this task and has no `Feature doc:` line yet, add one
     (create the feature doc first via `create-feature` only if this represents real shipped work and
     none exists — don't force one for trivial tasks).
   - Write the updated content to `docs/tasks/completed/<same-filename>`, then delete the original
     file from `docs/tasks/backlog/` (use Bash `rm` after the new file is confirmed written — never
     delete before the write succeeds).
5. Do not touch any other task file.
6. Report the task id and new status back to the user in one line (mention the file moved to
   `docs/tasks/completed/` if applicable).

## Notes

If the task file doesn't exist yet, don't silently create one — tell the user and suggest `add-task`
instead.
