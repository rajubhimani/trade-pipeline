# Git practices

## Branching

- `main` — stable, always green (tests pass). Only receives merges from `develop`, never direct pushes.
- `develop` — active work happens here. All day-to-day commits and pushes land on this branch.
- Feature branches (optional, for anything risky/large): `feature/<slug>`, branched from `develop`,
  merged back via PR when ready. Not required for small, incremental changes — use judgment.

Merge `develop` → `main` deliberately (e.g. when a component is feature-complete and tested), not on
every commit.

## Commit messages — Conventional Commits

Format: `<type>(<optional scope>): <short summary>`

Types used in this project:

| Type | When |
|---|---|
| `feat` | New capability (a new endpoint, a new module, a new component) |
| `fix` | Bug fix |
| `docs` | Documentation only (docs/, README, comments-as-docs) |
| `test` | Adding or fixing tests, no production code change |
| `refactor` | Code change that doesn't change behavior (e.g. moving `Trade` into `common/db_models.py`) |
| `chore` | Tooling, dependency bumps, config (pyproject.toml, .gitignore, ruff config) |
| `style` | Formatting only, no logic change |

Rules:
- Summary line ≤ 72 chars, imperative mood ("add X", not "added X" or "adds X").
- Body (optional, blank line after summary): explain *why*, not what — the diff already shows what.
- Reference the task id when relevant, e.g. `feat(api): add JWT RS256 token helpers (T-5)`.
- Every commit authored by Claude Code includes a `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`
  trailer.

Examples from this project's actual history:
```
feat(consumer): add Postgres sink with unique-constraint dedup backstop (T-4b)
refactor(common): move Trade ORM model out of postgres_sink into db_models
chore(deps): add cryptography, aiosqlite, httpx for JWT + async API testing
docs(tasks): move T-4/T-4b to completed, update dedup-consumer feature doc
```

## What never gets committed

- `keys/*.pem` — RSA keypairs are local dev secrets, generated fresh per environment (see
  `trade-pipeline/README.md` for the `openssl genrsa` commands). Enforced via `.gitignore` at both the
  repo root and `trade-pipeline/`.
- `.venv/`, `__pycache__/`, build artifacts.
- Anything a `git status` review after a broad `git add -A` looks suspicious — check file contents
  before committing, not just the filename, per this project's standing security practice.

`uv.lock` **is** committed — it's what makes the dependency graph reproducible across the 3.11-3.14
version range this project targets.

## Before pushing

1. `cd trade-pipeline && uv run ruff check .` — must pass clean.
2. `uv run pytest tests/ -q` — must pass.
3. `git status` after staging — confirm nothing unexpected is included.
4. Push to `develop`, not `main`, unless explicitly promoting a stable checkpoint.

## Remote

Private GitHub repo: `rajubhimani/faang-python-prep`. HTTPS remote (not SSH — no SSH key configured in
this environment), authenticated via `gh auth login`.
