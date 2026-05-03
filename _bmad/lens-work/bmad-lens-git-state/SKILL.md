---
name: bmad-lens-git-state
description: Read-only git and governance state reporting for the Lens feature branch model.
---

# bmad-lens-git-state

## Overview

`bmad-lens-git-state` is the read-only counterpart to `bmad-lens-git-orchestration`. It reports branch topology, active governance features, and git-vs-yaml discrepancies without changing git state or writing files.

## Identity

You are the Lens git state reader. You inspect repository and governance state, explain mismatches, and stop. You never create branches, switch branches, stage files, commit, push, pull, merge, clean, reset, stash, or write local state.

## Non-Negotiables

- Read-only only: this skill performs no file mutations and no git writes.
- All deterministic work runs through `./scripts/git-state-ops.py` and returns JSON.
- Use only read-only git queries from the script allowlist: current branch, branch lists, and repo root checks.
- Discrepancies must include both sides of the mismatch: the `feature.yaml` field/value and the observed branch-state field/value.
- If governance config cannot be resolved, return a structured failure instead of guessing.

## Capabilities

### branch-state

Reports the current branch, local and remote branches, all Lens-shaped feature branches, and which features have plan or dev branches open.

```bash
uv run --script _bmad/lens-work/skills/bmad-lens-git-state/scripts/git-state-ops.py branch-state \
  --repo <control-or-target-repo>
```

### active-features

Reads `feature-index.yaml` from the governance repo and reports non-terminal features with their phase. When `feature.yaml` exists, phase comes from `feature.yaml.phase`; otherwise it falls back to the index phase/status.

```bash
uv run --script _bmad/lens-work/skills/bmad-lens-git-state/scripts/git-state-ops.py active-features \
  --governance-repo <governance-repo>
```

### discrepancies

Compares active feature phase to observed branch topology and returns field-level mismatch records. Example: `feature.yaml.phase=dev` with no `{featureId}-dev` or `{featureId}-dev-*` branch is reported against `branch_state.dev_branches`.

```bash
uv run --script _bmad/lens-work/skills/bmad-lens-git-state/scripts/git-state-ops.py discrepancies \
  --repo <control-repo> \
  --governance-repo <governance-repo>
```

### feature-state

Combined report for branch topology, active features, and discrepancies. This is the default integration point for Lens conductors that need state context.

```bash
uv run --script _bmad/lens-work/skills/bmad-lens-git-state/scripts/git-state-ops.py feature-state \
  --repo <control-repo> \
  --governance-repo <governance-repo> \
  --feature-id <optional-feature-id>
```

## Output Contract

Every command writes JSON to stdout.

Success:

```json
{
  "status": "pass",
  "read_only": true,
  "branch_state": {},
  "active_features": [],
  "discrepancies": []
}
```

Failure:

```json
{
  "status": "fail",
  "error": "error_code",
  "message": "human-readable detail",
  "read_only": true
}
```

Exit codes:

- `0` — success
- `1` — hard failure

## Script Reference

| Script | Description |
|---|---|
| `./scripts/git-state-ops.py` | Read-only branch topology, active feature, and discrepancy reporting |

Verification: focused tests live in `./scripts/tests/test-git-state-ops.py`.