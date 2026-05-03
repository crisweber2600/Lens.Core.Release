---
name: bmad-lens-feature-yaml
description: Read, validate, update, and persist Lens feature.yaml state.
---

# bmad-lens-feature-yaml

## Overview

This skill is the sanctioned state boundary for Lens `feature.yaml` files in the governance repo. It reads lifecycle metadata, validates phase movement, applies small field updates without rebuilding the file from scratch, and handles dirty governance changes through explicit git operations.

## Capabilities

### read

Load a feature by `--feature-id` or `--feature-path` and return structured JSON containing identity fields, `phase`, `track`, `docs`, docs paths, `target_repos`, dependencies, milestones, and transition history.

```bash
uv run --script _bmad/lens-work/skills/bmad-lens-feature-yaml/scripts/feature-yaml-ops.py read \
  --governance-repo <governance-repo> \
  --feature-id <feature-id>
```

### validate

Validate a requested phase transition against the feature track and lifecycle contract. Missing `target_repos` is returned as a warning for implementation-impacting tracks instead of being silently ignored.

### update

Update only the requested fields: `phase`, `docs.path`, `docs.governance_docs_path`, `target_repos`, and `milestones`. Unknown fields and untouched fields remain in place.

### commit-dirty

Persist relevant governance repo changes before continuing: detect dirty state, pull with autostash, stage the requested paths, commit, push, and report the resulting SHA. This operation is CLI-backed and testable with mocked git subprocess calls.

## Script

All deterministic work runs through `./scripts/feature-yaml-ops.py`. The script emits JSON and exits non-zero for hard failures. Warning payloads exit zero so callers can surface non-blocking governance hygiene issues.