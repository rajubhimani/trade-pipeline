---
name: create-feature
description: Scaffold a new feature for the trade-pipeline project — creates a feature spec doc under docs/features/ and a linked task file in docs/tasks/backlog/. Use when the user wants to start a new component or capability (e.g. "add a refresh-token endpoint", "build the Dagster archival job").
tools: Read, Write, Glob
---

# Create Feature

Scaffolds a new feature: a short spec doc plus a linked task, so implementation work always starts
from a written-down intent instead of an ad-hoc chat instruction (prevents drift/hallucination across
a long-running project).

## Workflow

1. Pick a short kebab-case slug for the feature (e.g. `refresh-token-rotation`).
2. Check `docs/features/` doesn't already have `<slug>.md`. If it does, tell the user and offer to
   update it instead (don't overwrite silently).
3. Glob `docs/tasks/**/T-*.md` to find the highest existing `T-<n>` id across `backlog/` and
   `completed/`.
4. Write `docs/features/<slug>.md` with this structure:

```markdown
# Feature: <Title>

Status: draft
Task: T-<n>  (docs/tasks/backlog/T-<n>-<slug>.md)

## Problem / motivation
<why this is needed — pull from docs/ARCHITECTURE.md or the user's request>

## Scope
<what's in, explicitly what's out>

## Design
<key decisions — components touched, data flow, any new dependency>

## Python version notes
<does this rely on any 3.12+/3.14-only feature? check docs/PYTHON_VERSION_NOTES.md before claiming
availability>

## Testing plan
<what pytest coverage this needs — unit vs integration, any fakes/containers needed>
```

Fill in each section based on context gathered from the user and the existing docs — don't leave
placeholders in the written file.

5. Create `docs/tasks/backlog/T-<n>-<slug>.md`:

```markdown
# [todo] <Title> (<area>) — id: T-<n>

Added: YYYY-MM-DD
Notes: see docs/features/<slug>.md for full spec.
Feature doc: docs/features/<slug>.md
```

6. Report the feature doc path and task filename back to the user in one line.

## Notes

When the linked task later reaches `done` via `update-task`, its file moves from
`docs/tasks/backlog/` to `docs/tasks/completed/` — update this feature doc's `Status:` line to
`shipped` at that point (the `update-task` skill checks for a matching feature doc but does not edit
it; do that part yourself if you're the one marking it done).
