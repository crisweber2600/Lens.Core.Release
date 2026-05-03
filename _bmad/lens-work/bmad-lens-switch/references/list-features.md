# List Features

Discover and enumerate available features from `feature-index.yaml`.

## When to Use

- When the user asks "what features are available?", "list features", "show me what I can switch to"
- When helping the user select a target feature before switching
- When checking feature status across the repo

## Source

Feature list always reads from `feature-index.yaml` at the governance repo root. This file is always read from `main` — no branch switching is performed. The index is the authoritative source for listing and status filtering. During `list`, individual `feature.yaml` files may also be read when present to populate additional metadata such as `target_repo`; they are not the primary source for feature enumeration.

## Process

Run the list operation:

```bash
uv run --script {project-root}/{release_repo_root}/_bmad/lens-work/skills/bmad-lens-switch/scripts/switch-ops.py \
  list \
  --governance-repo {governance_repo}
```

Optional status filter (default: all non-archived features):

```bash
# Show all features including archived
uv run --script {project-root}/{release_repo_root}/_bmad/lens-work/skills/bmad-lens-switch/scripts/switch-ops.py \
  list \
  --governance-repo {governance_repo} \
  --status-filter all

# Show only archived/completed items
uv run --script {project-root}/{release_repo_root}/_bmad/lens-work/skills/bmad-lens-switch/scripts/switch-ops.py \
  list \
  --governance-repo {governance_repo} \
  --status-filter archived
```

## Output

Each feature entry includes a `num` field (1-indexed integer) for menu selection:

```json
{
  "status": "pass",
  "mode": "features",
  "features": [
    {
      "num": 1,
      "id": "auth-login",
      "domain": "platform",
      "service": "identity",
      "status": "active",
      "owner": "cweber",
      "summary": "User authentication flow with JWT tokens"
    },
    {
      "num": 2,
      "id": "user-profile",
      "domain": "platform",
      "service": "identity",
      "status": "businessplan-complete",
      "owner": "amelia",
      "summary": "User profile management and preferences"
    }
  ],
  "total": 2
}
```

## Display Format

Present results as a numbered menu grouped by domain/service. Use `→` to mark the currently active feature (if any):

```
Available features (2):

PLATFORM / IDENTITY
  1  auth-login             active                 cweber    User authentication flow with JWT tokens
  2  user-profile           businessplan-complete  amelia    User profile management and preferences

Enter a number to switch, or q to cancel:
```

When the user enters a valid number, resolve the feature id at that position and proceed with the switch flow. On `q` or any non-numeric input, cancel with no changes.

If a question tool is unavailable, render the menu and STOP. Do not auto-select a feature from branch names, open files, or recent activity.

## Domain Fallback (no features yet)

When `feature-index.yaml` does not exist, the script falls back to scanning `features/` for `domain.yaml` and `service.yaml` files. The result shape changes to `mode: "domains"`:

```json
{
  "status": "pass",
  "mode": "domains",
  "domains": [
    {
      "id": "lens.core",
      "name": "Lens Core",
      "domain": "lens.core",
      "status": "active",
      "owner": "crisweber2600",
      "services": [
        {
          "id": "lens.core-src",
          "name": "Src",
          "service": "src",
          "status": "active",
          "owner": "crisweber2600"
        }
      ]
    }
  ],
  "total_domains": 1,
  "total_services": 1,
  "message": "No features initialized yet. Showing domain/service inventory from governance repo."
}
```

Present domain fallback results as an inventory grouped by domain:

```
No features initialized yet. Domain/service inventory (1 domain, 1 service):

LENS.CORE — Lens Core
  src   active   crisweber2600

Run /new-feature to create the first feature.
```

## Errors

| Error | Exit code | Cause |
|-------|-----------|-------|
| `Failed to parse feature-index.yaml: ...` | 1 | YAML parse error in existing index |
