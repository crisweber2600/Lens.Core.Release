---
name: lens-upgrade
description: Lens module upgrade conductor for schema/version migrations. Use when the user requests upgrade, migrate module version, or reconcile legacy topology.
---

# Lens Upgrade Skill

## Overview

This skill manages Lens module upgrades and migration routing. It checks current module schema/version compatibility, determines whether a direct in-place upgrade is valid, and routes legacy layouts to the migration path when needed.

This skill does not perform direct governance writes. It orchestrates checks, plans migration actions, and reports deterministic next steps.

## Input Contract

Required inputs:
- control_repo: Absolute path to the control repository.
- governance_repo: Absolute path to the governance repository.

Optional inputs:
- dry_run: When true, emit planned actions without mutating state.
- target_version: Explicit version target for validation.

Preconditions:
- Both repositories are readable and synchronized.
- Lens module configuration can be loaded from the control repo module path.

## Output Contract

Primary outputs:
- Upgrade decision: no-op, in-place upgrade, or legacy migration route.
- Structured migration/upgrade action plan.
- Compatibility report including detected schema and topology.

Secondary outputs:
- Blocking issues list for unresolved prerequisites.
- Suggested follow-up command for next step execution.

## Error Behavior

Hard-stop errors:
- Missing control/governance repository paths.
- Unreadable or invalid module configuration.
- Unsupported schema combination with no migration path.

Recoverable errors:
- Version mismatch requiring user confirmation in non-headless mode.
- Optional target_version not provided: use default target and continue.

Never apply upgrade actions when preconditions fail.

## Test Hooks

Validate this contract with focused tests that assert:
- Required input keys are documented.
- Output contract includes decision and action-plan fields.
- Hard-stop and recoverable error categories are explicit.
- Governance direct-write prohibition is documented.

## Execution Flow

1. Load module config and current version/schema details.
2. Detect topology/schema compatibility state.
3. Choose route: no-op, in-place upgrade, or lens-migrate handoff.
4. Emit action plan (or execute when approved outside dry-run).
5. Return structured report with next command guidance.

## Integration Points

- lens-module-management: baseline module version/status checks.
- lens-migrate: legacy branch/topology migration route.
- lens-git-state: repository cleanliness checks before upgrade actions.
- lens-git-orchestration: optional follow-up git-safe operations.
