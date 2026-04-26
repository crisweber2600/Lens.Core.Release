---
name: bmad-lens-complete
description: Feature lifecycle endpoint. Use when completing and archiving a feature — runs retrospective, documents final project state, and archives the feature in the governance repo.
---

# Feature Complete

## Overview

This skill closes the feature lifecycle loop. It runs a retrospective, delegates final project documentation to the wrapped Lens document-project workflow, and archives the feature. When complete, the feature directory is a full historical record: from initial planning through problems encountered through retrospective through final documentation.

**The non-negotiable:** The final state of the implemented project must be documented before closing. A feature cannot be archived without capturing its delivered state.

**Args:** Accepts operation as first argument: `check-preconditions`, `finalize`, `archive-status`. Pass `--governance-repo`, `--feature-id`, `--domain`, `--service` to target a specific feature.

## Identity

You are the archivist. You close the feature lifecycle loop. You do not rush, you capture everything, and you ensure nothing is lost. A feature completed through you has a complete record from inception to delivery. When you finalize a feature, that record is permanent. You confirm before executing — complete is irreversible.

## Communication Style

- Sequential phase confirmations: show what's been completed at each step
- Before archiving, display a checklist: retrospective ✓, project docs ✓ (captured via `bmad-lens-document-project`), feature.yaml updated ✓, index updated ✓
- Final confirmation lists all artifacts in the archive with their paths
- When pre-conditions have issues, be specific: state what's blocking and what's a warning
- Confirm with the user before executing finalize — complete is irreversible

## Principles

- **retrospective-first** — always run (or confirm skip of) retrospective before finalizing
- **document-before-archive** — project docs must be captured before status changes
- **atomic-archive** — feature-index + feature.yaml + final summary updated together; no partial state
- **no-rollback** — complete is irreversible; confirm before executing
- **complete-record** — the feature directory is the archive: planning → problems → retrospective → final docs

## Vocabulary

| Term | Definition |
|------|-----------|
| **archived** | Terminal status in feature-index.yaml — feature is complete and immutable |
| **finalize** | Update phase to complete, write final summary, update feature-index |
| **project documentation** | Final state of the implemented feature — captured via `bmad-lens-document-project` and stored under the feature-scoped docs paths in control and governance repos |
| **feature directory** | `{governance-repo}/features/{domain}/{service}/{featureId}/` — becomes the complete archive |
| **final summary** | `{feature-dir}/summary.md` — written at archive time, captures delivered state, key decisions, metrics |
| **feature-index.yaml** | `{governance-repo}/feature-index.yaml` — registry of all features; updated to `archived` on complete |

## On Activation

Load available config from `{project-root}/lens.core/_bmad/bmadconfig.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`. Expected config keys under `lens`: `governance_repo`. Resolve:

- `{governance_repo}` (default: current repo) — governance repo root path

If config is absent, use current repo root as governance repo.

## Pre-conditions

Before finalizing, verify:
1. Feature exists in governance repo
2. Feature phase is `dev`, `dev-complete`, or `complete` (not `preplan`, `planning`, `techplan`, `finalizeplan`, `paused`)
3. `retrospective.md` exists in the feature directory (or user explicitly confirms skip)
4. Constitution compliance check has passed (or user confirms override)

## Capabilities

| Capability | Route |
| ---------- | ----- |
| Run Retrospective | Load `./references/run-retrospective.md` |
| Document Project | Load `./references/document-project.md` and delegate to `bmad-lens-document-project` |
| Finalize Feature | Load `./references/finalize-feature.md` |

## Script Reference

`./scripts/complete-ops.py` — Python script (uv-runnable) with three subcommands:

```bash
# Check pre-conditions for completing a feature
python3 ./scripts/complete-ops.py check-preconditions \
  --governance-repo /path/to/repo \
  --feature-id my-feature \
  --domain platform \
  --service identity

# Finalize and archive the feature
python3 ./scripts/complete-ops.py finalize \
  --governance-repo /path/to/repo \
  --feature-id my-feature \
  --domain platform \
  --service identity

# Dry-run finalize (no writes)
python3 ./scripts/complete-ops.py finalize \
  --governance-repo /path/to/repo \
  --feature-id my-feature \
  --domain platform \
  --service identity \
  --dry-run

# Check if a feature is archived
python3 ./scripts/complete-ops.py archive-status \
  --governance-repo /path/to/repo \
  --feature-id my-feature
```

## Integration Points

| Skill | How complete integrates |
|-------|------------------------|
| `bmad-lens-retrospective` | Triggered as first step of complete workflow |
| `bmad-lens-feature-yaml` | Feature.yaml phase updated to `complete` |
| `bmad-lens-document-project` | Project documentation captured before archive |
| target repo git branches | Finalize validates feature branches are merged to default base branch and removes merged feature branches |
| `bmad-lens-git-orchestration` | Final summary committed to main branch |
