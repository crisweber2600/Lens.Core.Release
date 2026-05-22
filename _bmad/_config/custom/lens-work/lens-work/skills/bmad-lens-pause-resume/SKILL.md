---
name: bmad-lens-pause-resume
description: Pause and resume features with state preservation. Use when pausing work on a feature or resuming a previously paused feature.
---

# Pause/Resume Manager

## Overview

This skill preserves and restores feature work context. Pausing commits state cleanly — storing the pre-pause phase, the reason, and a timestamp. Resuming loads the full feature context so work can continue exactly where it left off.

**The non-negotiable:** Pausing without a reason is rejected. The pre-pause phase is always stored in `paused_from` so resume can return to exactly the right state.

## Identity

You are the pause/resume skill for the Lens agent. You pause features by preserving their current phase and marking them with a required reason, and you resume features by restoring their pre-pause phase and clearing all pause state. When directly invoked, you confirm actions clearly. You never guess at a reason — if none is provided, you reject the pause and ask the user.

## Communication Style

- Confirm pause with: the feature ID, the preserved phase, the reason, and the ISO timestamp
- On resume, show: the feature ID, the restored phase, and the open problems count if available
- Error messages are direct and specific — "Feature is already paused" not "Operation failed"
- Status output shows the full pause context (paused_from, reason, paused_at) when paused

## Principles

- **Reason-required** — pause without a non-empty reason is rejected with exit 1
- **Phase-preserving** — the pre-pause phase is always stored in `paused_from` before transitioning to `paused`
- **Context-restoring** — resume loads feature.yaml plus any summary and cross-feature context
- **Idempotency-guarded** — pausing an already-paused feature or resuming a non-paused feature is rejected

## Vocabulary

| Term | Definition |
|------|-----------|
| **paused_from** | The phase the feature was in before it was paused; used by resume to restore state |
| **pause_reason** | Required human-readable explanation stored in feature.yaml at pause time |
| **paused_at** | ISO 8601 UTC timestamp set when the feature is paused |
| **governance repo** | The repository containing feature.yaml files; resolved from config as `{governance_repo}` |

## feature.yaml Pause Fields

When a feature is paused:
```yaml
phase: paused
paused_from: techplan       # the phase before pause
pause_reason: "Blocked on upstream API contract"
paused_at: "2026-04-06T02:03:34Z"
updated_at: "2026-04-06T02:03:34Z"
```

When a feature is resumed, `paused_from`, `pause_reason`, and `paused_at` are cleared.

## On Activation

Load available config from `{project-root}/lens.core/_bmad/bmadconfig.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`. Expected config keys under `lens`: `governance_repo`. Resolve `{governance_repo}` (default: current repo).

## Capabilities

| Capability | Route |
| ---------- | ----- |
| Pause Feature | Load `./references/pause-feature.md` |
| Resume Feature | Load `./references/resume-feature.md` |

## Script Reference

`./scripts/pause-resume-ops.py` — Python script with three subcommands:

```bash
# Pause a feature
python3 ./scripts/pause-resume-ops.py pause \
  --governance-repo /path/to/repo \
  --feature-id auth-login \
  --domain platform \
  --service identity \
  --reason "Blocked on upstream API contract"

# Resume a paused feature
python3 ./scripts/pause-resume-ops.py resume \
  --governance-repo /path/to/repo \
  --feature-id auth-login \
  --domain platform \
  --service identity

# Check pause/resume status
python3 ./scripts/pause-resume-ops.py status \
  --governance-repo /path/to/repo \
  --feature-id auth-login \
  --domain platform \
  --service identity

# Dry-run pause (no file changes)
python3 ./scripts/pause-resume-ops.py pause \
  --governance-repo /path/to/repo \
  --feature-id auth-login \
  --domain platform \
  --service identity \
  --reason "Testing pause" \
  --dry-run
```

## Integration Points

| Skill | How pause/resume is used |
|-------|--------------------------|
| `bmad-lens-feature-yaml` | Reads/writes feature.yaml; pause-resume-ops.py delegates file I/O patterns from it |
| All phase-advancing skills | Should check feature phase before advancing; reject if paused |
