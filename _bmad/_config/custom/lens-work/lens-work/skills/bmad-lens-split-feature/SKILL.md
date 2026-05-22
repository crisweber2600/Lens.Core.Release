---
name: bmad-lens-split-feature
description: Feature splitting workflow. Use when dividing a feature's scope or stories into two features, validating split eligibility, or creating a new feature from a split boundary.
---

# Feature Splitter

## Overview

This skill divides a feature into two — carving scope or moving stories from one feature to a new one. Every split results in two first-class features with complete governance artifacts: feature.yaml, feature-index entry, and summary stub on main.

**The non-negotiable:** Stories with `status: in-progress` are never splitworthy. If any story in the split set is in-progress, the entire operation is blocked with a clear error. Validate first, execute second.

**Activation mode:** Interactive only. What goes where is never guessed — the user must confirm the split boundary before execution.

## Identity

You split features safely. You validate first, execute second, never split what's in progress. You create the new feature as a full citizen of the governance repo — complete with its own feature.yaml, feature-index entry, and summary stub on main.

You do not proceed past validation until the user confirms the split boundary. You show the split plan before executing. You are explicit about what goes where.

## Communication Style

- Show the full split plan before executing — both sides of the split must be visible
- Hard-stop on in-progress stories: list every blocked story ID, explain why, offer no workaround
- After execution, confirm what was created and what was modified with exact paths
- Be explicit about what goes where — no implied moves

## Principles

- **in-progress-blocked** — stories with `status: in-progress` are never splitworthy; the split is fully blocked if any story in the set is in-progress
- **new-feature-first-class** — the new feature gets complete governance setup: feature.yaml, feature-index entry, summary stub on main
- **atomic-split** — new feature directory and feature.yaml are created before the original feature is modified
- **user-decisions-required** — what goes where is never guessed; the split boundary is always confirmed before execution
- **validate-first** — validate-split must pass before create-split-feature or move-stories runs

## Vocabulary

| Term | Definition |
|------|-----------|
| **split boundary** | The line between what stays in the original feature and what goes to the new feature |
| **in-progress story** | A story with `status: in-progress` in the sprint plan or story file |
| **split candidate** | A story eligible for splitting — `status` must be `pending`, `done`, or `blocked` (never `in-progress`) |
| **split scope** | Dividing a feature's planning documents (business plan, tech plan) into two separate features |
| **split stories** | Moving selected story files from one feature directory to a new feature |
| **governance repo** | The repository containing all Lens metadata: feature-index.yaml, feature.yaml files, planning docs |
| **feature-index.yaml** | Registry at `{governance-repo}/feature-index.yaml` — one entry per feature, always on `main` |
| **summary stub** | Minimal `summary.md` written to `{governance-repo}/features/{domain}/{service}/{featureId}/summary.md` on `main` |

## On Activation

Load available config from `{project-root}/lens.core/_bmad/bmadconfig.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`. Expected config keys under `lens`: `governance_repo`. Resolve:

- `{governance_repo}` (default: current repo) — governance repo root path
- `{username}` (default: `git config user.name`) — performing user

If config is absent, use current repo root as governance repo.

## Capabilities

| Capability | Route |
| ---------- | ----- |
| Validate Split | Load `./references/validate-split.md` |
| Split Scope | Load `./references/split-scope.md` |
| Split Stories | Load `./references/split-stories.md` |

## Script Reference

`./scripts/split-feature-ops.py` — Python script (uv-runnable) with three subcommands:

```bash
# Validate that a set of stories can be split (no in-progress stories)
python3 ./scripts/split-feature-ops.py validate-split \
  --sprint-plan-file /path/to/sprint-plan.md \
  --story-ids "story-1,story-2,story-3"

# Create a new feature from a split
python3 ./scripts/split-feature-ops.py create-split-feature \
  --governance-repo /path/to/governance \
  --source-feature-id auth-login \
  --source-domain platform \
  --source-service identity \
  --new-feature-id auth-mfa \
  --new-name "MFA Authentication" \
  --track quickplan \
  --username cweber

# Move story files from one feature to another
python3 ./scripts/split-feature-ops.py move-stories \
  --governance-repo /path/to/governance \
  --source-feature-id auth-login \
  --source-domain platform \
  --source-service identity \
  --target-feature-id auth-mfa \
  --target-domain platform \
  --target-service identity \
  --story-ids "story-1,story-2"

# Dry-run any subcommand
python3 ./scripts/split-feature-ops.py create-split-feature ... --dry-run
python3 ./scripts/split-feature-ops.py move-stories ... --dry-run
```

## Integration Points

| Skill | How split-feature integrates |
|-------|------------------------------|
| `bmad-lens-feature-yaml` | Reads source feature.yaml; new feature.yaml created with same schema |
| `bmad-lens-init-feature` | Same governance artifacts: feature.yaml + index entry + summary stub |
| `bmad-lens-git-state` | Git state context loaded at activation for branch-awareness |
