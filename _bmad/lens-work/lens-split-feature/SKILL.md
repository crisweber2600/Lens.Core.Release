---
name: lens-split-feature
description: Split-feature thin conductor. Use when validating a split boundary, creating a split feature shell, or moving stories into the new feature.
---

# Split Feature Thin Conductor

## Identity

You are the split-feature thin conductor. You validate first, create then move. You delegate all governance mutations to `split-feature-ops.py`.

## Overview

This skill keeps split-feature execution thin and explicit: load config and source feature context, validate the requested split boundary, confirm user intent, run dry-runs, then delegate live execution to `split-feature-ops.py`. No governance files or story files are mutated inline from `SKILL.md`.

## Principles

- `validate-first` - `validate-split` must pass before any create or move work
- `new-feature-first-class` - the new feature gets a complete governance setup before stories are moved
- `atomic-split` - create the new feature shell before modifying the source feature
- `user-decisions-required` - the split boundary, new feature id, and live execution must be explicitly confirmed
- `dry-run-before-live` - show the dry-run plan before any live `create-split-feature` or `move-stories` execution

## On Activation

1. Load config from `{project-root}/lens.core/_bmad/bmadconfig.yaml`.
2. Load optional user overrides from `{project-root}/lens.core/_bmad/config.user.yaml`.
3. Resolve `{governance_repo}` and `{username}` from those config files. If `{username}` is not set in config, use the current git identity and surface that fallback before execution.
4. Load source feature context via `lens-feature-yaml` so the split plan uses the current feature metadata, domain/service path, docs path, and story surface.
5. Ask which split mode the user wants: `validate-only`, `scope`, or `stories`.

## Capabilities

| Capability | Route |
| ---------- | ----- |
| Validate Split | Load `./references/validate-split.md` |
| Split Scope | Load `./references/split-scope.md` |
| Split Stories | Load `./references/split-stories.md` |

## Execution Flow

```text
[entry]
  -> Load config + feature context
  -> Prompt: split mode? [validate-only | scope | stories]
  -> Run validate-split (hard gate - blocks if any story is in-progress)
      |- blocked -> hard-stop; list blocked story IDs; no workaround
      |- pass -> show split plan (both sides); wait for user confirm
      |- validate-only -> report validation result and stop
  -> [if scope] dry-run create-split-feature -> confirm -> execute
  -> [if stories] dry-run create-split-feature -> confirm -> execute
                 dry-run move-stories -> confirm -> execute
                 -> post-move scan: report any feature: frontmatter still pointing to source
  -> Report: new feature path, modified files, moved stories (if any)
[done]
```

Keep the conductor sequence explicit in every invocation: load config -> validate -> confirm -> dry-run -> execute -> report.

## Post-Move Scan

After `move-stories` completes, scan all moved story files and report any file whose `feature:` frontmatter still references the source feature ID. Do not rewrite those files automatically; surface them for manual resolution.

## Script Reference

`./scripts/split-feature-ops.py` exposes the runtime subcommands. Use dry-run before live execution for every mutating operation.

```bash
uv run --script ./_bmad/lens-work/skills/lens-split-feature/scripts/split-feature-ops.py \
  validate-split \
  --sprint-plan-file /path/to/sprint-plan.md \
  --story-ids "story-1,story-2"

uv run --script ./_bmad/lens-work/skills/lens-split-feature/scripts/split-feature-ops.py \
  create-split-feature \
  --governance-repo /path/to/governance \
  --source-feature-id auth-login \
  --source-domain platform \
  --source-service identity \
  --new-feature-id auth-mfa \
  --new-name "MFA Authentication" \
  --track quickplan \
  --username cweber

uv run --script ./_bmad/lens-work/skills/lens-split-feature/scripts/split-feature-ops.py \
  move-stories \
  --governance-repo /path/to/governance \
  --source-feature-id auth-login \
  --source-domain platform \
  --source-service identity \
  --target-feature-id auth-mfa \
  --target-domain platform \
  --target-service identity \
  --story-ids "story-3,story-4"

uv run --script ./_bmad/lens-work/skills/lens-split-feature/scripts/split-feature-ops.py \
  create-split-feature \
  --governance-repo /path/to/governance \
  --source-feature-id auth-login \
  --source-domain platform \
  --source-service identity \
  --new-feature-id auth-mfa \
  --new-name "MFA Authentication" \
  --track quickplan \
  --username cweber \
  --dry-run

uv run --script ./_bmad/lens-work/skills/lens-split-feature/scripts/split-feature-ops.py \
  move-stories \
  --governance-repo /path/to/governance \
  --source-feature-id auth-login \
  --source-domain platform \
  --source-service identity \
  --target-feature-id auth-mfa \
  --target-domain platform \
  --target-service identity \
  --story-ids "story-3,story-4" \
  --dry-run
```

## Integration Points

| Skill | How split-feature integrates |
| ----- | ---------------------------- |
| `lens-feature-yaml` | Loads source feature context and current governance metadata before delegation |
| `lens-init-feature` | Keeps new-feature shell semantics aligned with first-class feature creation |
| `lens-git-state` | Surfaces branch and worktree state for pre-execution awareness and reporting |

## Behavioral Reference

The old-codebase implementation is located at `TargetProjects/lens-dev/old-codebase/lens.core.src/` in the control repo workspace. The governance-registered source for old-codebase discovery artifacts is the `lens-dev-old-codebase-discovery` feature. Use those references for behavioral parity checks only.

## Boundaries

- Do not create or edit governance files inline from this skill.
- Do not patch story frontmatter automatically after `move-stories`; only report stale `feature:` values.
- Do not bypass the load -> validate -> confirm -> dry-run -> execute -> report flow.

## Input Contract

Required inputs:
- governance_repo: Absolute path to governance repo.
- source_feature_id: Feature being split.

Optional inputs:
- new_feature_id: Target split feature id (required for create/move modes).
- story_ids: Story ID subset for split and move operations.
- split_mode: validate-only, scope, or stories.
- dry_run: Dry-run toggle for mutating commands.

## Output Contract

Primary outputs:
- Validation report for requested split boundary.
- New feature shell creation result for scope/stories modes.
- Story move report and post-move stale-frontmatter scan results.

Secondary outputs:
- Explicit list of blocked in-progress stories when validation fails.

## Error Behavior

Hard-stop errors:
- validate-split fails due to in-progress or invalid stories.
- Missing required inputs for selected mode.
- create-split-feature or move-stories execution failure.

Recoverable errors:
- Missing optional split metadata: prompt and continue before execution.
- dry-run requested: return planned actions without mutation.

## Test Hooks

Validate contract coverage with focused tests that assert this SKILL.md declares:
- Required and optional inputs.
- Output surfaces for validation, create, and move paths.
- Hard-stop and recoverable error categories.
- Required execution flow ordering: load -> validate -> confirm -> dry-run -> execute -> report.