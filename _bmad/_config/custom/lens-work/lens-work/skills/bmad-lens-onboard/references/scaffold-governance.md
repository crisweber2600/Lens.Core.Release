# Scaffold Governance Repo

## Purpose

Create the governance repository directory structure and initialize `feature-index.yaml` on the `main` branch. This is the foundational step of first-run onboarding — it must complete before any features can be tracked.

## Prerequisites

- Preflight check passed (no failures)
- `--governance-dir` path does not already exist (or is empty)
- `--owner` is a valid username (kebab-safe: `^[a-z0-9][a-z0-9._-]{0,63}$`)
- Git is available on PATH

## Directory Structure Created

```
{governance-dir}/
├── features/                    # per-feature directories (initially empty)
├── users/
│   └── {owner}.md               # user profile placeholder
└── feature-index.yaml           # registry of all features
```

## feature-index.yaml Initial Content

Written to `{governance-dir}/feature-index.yaml`:

```yaml
version: "1"
features: []
```

This file is committed to the `main` branch on initialization. All future feature registrations append to the `features` list.

## Git Initialization

After writing the directory structure, the scaffold process:

1. `git init` in `{governance-dir}`
2. `git checkout -b main` (or `git symbolic-ref HEAD refs/heads/main` if git supports it)
3. `git add feature-index.yaml users/{owner}.md`
4. `git commit -m "chore: initialize Lens governance repo"`

The commit establishes `main` as the base branch, ensuring `feature-index.yaml` is always readable via `git show main:feature-index.yaml`.

## Output Contract

```json
{
  "status": "ok" | "error",
  "created": ["features/", "users/", "users/{owner}.md", "feature-index.yaml"],
  "feature_index_path": "{governance-dir}/feature-index.yaml",
  "message": "optional error message on failure"
}
```

## Dry-Run Behavior

When `--dry-run` is passed:
- No directories or files are created
- No git commands are run
- `created` list shows what **would** be created
- `status` is `"ok"` (dry-run is always a preview, not a test)

## Error Cases

| Condition | Status | Message |
|---|---|---|
| Directory already exists and is non-empty | `"error"` | "Directory already exists: {path}. Use an empty or non-existent path." |
| Path contains `..` traversal | `"error"` | "Path traversal not allowed in governance-dir" |
| Git not found on PATH | `"error"` | "git is not available. Install git and retry." |
| `--owner` missing | `"error"` | "--owner is required" |
| Git commit fails | `"error"` | "Git initialization failed: {stderr}" |
