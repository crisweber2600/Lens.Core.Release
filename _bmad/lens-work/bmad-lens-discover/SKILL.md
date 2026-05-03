---
name: bmad-lens-discover
description: Sync local TargetProjects repositories with governance repo-inventory.yaml. Use when the user runs discover or needs to reconcile local repo clones with governance inventory.
---

# Discover

## Overview

`bmad-lens-discover` reconciles the governance repository inventory with local repositories under `TargetProjects/`. The skill orchestrates user confirmation, optional clone/register actions, validation, and the one approved governance-main auto-commit exception. The companion script, `scripts/discover-ops.py`, owns deterministic disk and YAML operations only.

The command is intentionally narrow:

- `discover-ops.py scan` reports missing inventory entries on disk, untracked local repositories, already cloned repositories, and summary counts.
- `discover-ops.py add-entry` appends untracked repositories to `repo-inventory.yaml` and is idempotent by `remote_url`.
- `discover-ops.py validate` verifies required inventory fields before any governance commit is attempted.
- The skill performs git clone and git add/commit/push orchestration inline. It does not delegate the auto-commit exception to a helper script.

## On Activation

Resolve configuration in this order:

1. Read `.lens/governance-setup.yaml` from the workspace root; if it contains `governance_repo_path`, use it.
2. Fall back to `bmadconfig.yaml` and read `governance_repo_path` from the Lens Work config. In source repos, use the local Lens Work config; in installed workspaces, use the release module Lens Work config when present.
3. Resolve `target_projects_path` from config when available. Otherwise use `TargetProjects` under the workspace root.

If `governance_repo_path` cannot be resolved, stop with `config_missing` and tell the user to run the Lens onboarding or domain/service setup flow before discover.

Required derived paths:

- `{inventory_path}` = `{governance_repo_path}/repo-inventory.yaml`
- `{target_root}` = resolved `target_projects_path`
- `{discover_script}` = `{project-root}/_bmad/lens-work/skills/bmad-lens-discover/scripts/discover-ops.py`

## Modes

### Interactive Mode

Interactive mode is the default. Scan first, show the planned actions, and ask for confirmation before clone or registration work.

Sample output:

```text
[discover] Scanning TargetProjects against repo-inventory.yaml...

Missing from disk (1):
  Lens.Hermes  https://github.com/example/Lens.Hermes

Untracked on disk (1):
  TargetProjects/plugins/notify/Lens.Notify

Clone missing repos and register untracked repos? [Y/n]
```

If the user confirms, clone missing repositories, register untracked repositories with an `origin` remote, validate the inventory, and run the hash-gated auto-commit block.

### Headless Mode

With `--headless` or `-H`, do not ask confirmation prompts. Execute all detected actions immediately:

1. Clone every `missing_from_disk` entry that has a `remote_url` and `local_path`.
2. Register every `untracked` entry that has a resolvable `remote_url`.
3. Validate the updated inventory.
4. Run the auto-commit guard.

### Dry-Run Mode

With `--dry-run`, scan and print the same action summary, but do not mutate files, do not clone repositories, and do not run `git add`, `git commit`, or `git push`. Dry-run mode exits after reporting the planned work.

### No-Op Path

When `scan` returns zero `missing_from_disk` and zero `untracked`, report:

```text
[discover] Nothing to do - all repos are cloned and registered.
```

No `add-entry` calls are made and no governance commit is attempted. If the pre/post hash block is reached during orchestration, equal hashes must also skip commit.

## Script Subcommands

Run script commands with `uv run --script` from the source repo root.

### scan

```bash
uv run --script _bmad/lens-work/skills/bmad-lens-discover/scripts/discover-ops.py scan \
  --inventory-path {inventory_path} \
  --target-root {target_root} \
  --json
```

`scan` accepts both top-level `repositories:` and legacy `repos:` inventory keys. It walks `{target_root}` up to three levels deep and detects directories containing `.git`. All local path comparisons use resolved filesystem paths.

### add-entry

```bash
uv run --script _bmad/lens-work/skills/bmad-lens-discover/scripts/discover-ops.py add-entry \
  --inventory-path {inventory_path} \
  --name {repo_name} \
  --remote-url {remote_url} \
  --local-path {local_path} \
  --json
```

`add-entry` is idempotent by `remote_url`. If the same `remote_url` already exists, it returns `{ "added": false, "reason": "already_exists" }` and leaves `repo-inventory.yaml` byte-for-byte unchanged. Any mutation writes the canonical top-level `repositories:` key.

### validate

```bash
uv run --script _bmad/lens-work/skills/bmad-lens-discover/scripts/discover-ops.py validate \
  --inventory-path {inventory_path} \
  --json
```

`validate` requires every entry to include `name` and `remote_url`. It returns `{ "valid": true, "errors": [] }` or structured errors with `index`, `name`, `remote_url`, and `issue`.

## Orchestration

1. Resolve config and exact paths.
2. Run `scan --json`.
3. If no work is detected, print the no-op message and stop.
4. In interactive mode, show planned clone/register actions and ask for confirmation.
5. In dry-run mode, show planned actions and stop before any writes.
6. Capture the pre-mutation SHA-256 hash of `repo-inventory.yaml`.
7. Clone each `missing_from_disk` repo with `git clone {remote_url} {resolved_local_path}` when confirmed or headless.
8. For each untracked repo, read `git -C {repo_path} remote get-url origin`. If a remote exists, call `add-entry` with the scan result values.
9. Run `validate --json`; stop and surface errors if validation fails.
10. Capture the post-mutation SHA-256 hash of `repo-inventory.yaml`.
11. Run the auto-commit guard below.

Repos without an `origin` remote are out of scope for this feature. Surface them as skipped registrations with a follow-up note rather than inventing a remote URL.

## Auto-Commit (Governance-Main Exception)

This section is the only approved direct governance-main commit pattern for discover. Keep it inline in this skill so the exception remains visible and auditable.

Algorithm:

1. Before any `add-entry` calls, compute `pre_hash = sha256(repo-inventory.yaml bytes)`.
2. After all `add-entry` calls and `validate`, compute `post_hash = sha256(repo-inventory.yaml bytes)`.
3. If `pre_hash == post_hash`, print `[discover] Nothing to do - inventory unchanged.` and do not run any git commit command.
4. If `pre_hash != post_hash`, run exactly this governance sequence:

```bash
git -C {governance_repo_path} add repo-inventory.yaml
git -C {governance_repo_path} commit -m "[discover] Sync repo-inventory.yaml"
git -C {governance_repo_path} push
```

No empty commit is allowed on a no-op run. The commit message must be exactly `[discover] Sync repo-inventory.yaml`.

## Out of Scope

- Creating remote repositories.
- Guessing a `remote_url` for local repos with no `origin` remote.
- Committing any governance files other than `repo-inventory.yaml`.
- Moving or renaming local repositories.

## Focused Regression

Run from the target source repo root:

```bash
uv run --with pytest pytest _bmad/lens-work/skills/bmad-lens-discover/scripts/tests/ -q
uv run --script _bmad/lens-work/skills/bmad-lens-discover/scripts/discover-ops.py --help
```