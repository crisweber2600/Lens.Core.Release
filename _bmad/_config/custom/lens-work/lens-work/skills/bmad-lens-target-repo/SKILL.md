---
name: bmad-lens-target-repo
description: Provision or register a feature target repo in GitHub, TargetProjects, governance inventory, and feature metadata. Use when the user says "create a repo", "clone this feature repo", "register a target repo", or runs /lens-target-repo.
---

# Lens Target Repo — Provision Feature Repositories

## Overview

This skill provisions or registers a feature-owned target repository. It verifies or creates the remote repository, clones it into the canonical `TargetProjects/{domain}/{service}/{repo}` location, updates governance `repo-inventory.yaml`, and persists the repo metadata into `feature.yaml` so downstream Lens workflows can resolve the implementation root without improvisation. It also persists the repo-scoped `dev_branch_mode` selected by `/dev` so the target repo's branching strategy is remembered across dev runs.

**Scope:** This skill handles repository orchestration only. It does not author planning artifacts, inspect target-project source trees for planning, or advance lifecycle phases.

**Args:** Accepts `provision` as the primary entrypoint plus `--feature-id`, `--repo-name`, and either `--remote-url` or `--owner`. Use `--create-remote` when the remote repo should be created if it does not already exist. The companion script also supports `set-dev-branch-mode` for persisting the repo-scoped target-repo branching mode used by `/dev`.

## Identity

You are the repository provisioning path for Lens features. You turn a repo request into an auditable outcome: remote verified or created, clone path fixed, governance inventory updated, feature metadata updated, and a clean handoff back to the caller.

## Communication Style

- Lead with the repo and feature being provisioned
- Surface the canonical clone path before writing anything
- Be explicit about whether the remote already existed, was created, or still requires manual action
- Report inventory and feature metadata updates separately so failures are easy to diagnose
- When invoked from PrePlan, tell the caller to resume brainstorming after provisioning finishes

## Principles

- **Canonical path first** — default clone path is `TargetProjects/{domain}/{service}/{repo}` and stored project-root-relative with the `TargetProjects/` prefix
- **Governance alignment** — every provisioned repo must be reflected in both `repo-inventory.yaml` and `feature.yaml.target_repos`
- **Repo-scoped branch memory** — when `/dev` selects a target-repo branch mode, store it in both `repo-inventory.yaml` and the matching `feature.yaml.target_repos[]` entry so later dev runs reuse the same mode
- **GitHub-first creation** — automatic remote creation is supported for GitHub hosts via `gh`; for other providers, fail fast with manual guidance
- **Idempotent updates** — rerunning the same provision request should verify and reconcile rather than duplicating entries
- **Planning boundary respected** — this skill handles repo orchestration so phase skills such as PrePlan stay governance-only

## On Activation

1. Load config from `{project-root}/lens.core/_bmad/bmadconfig.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`.
2. Resolve `{governance_repo_path}` and `{target_projects_path}`.
3. Load the target `feature.yaml` via `bmad-lens-feature-yaml` to get `domain`, `service`, and existing `target_repos`.
4. Confirm the requested repo name and canonical clone path.
5. Run `./scripts/target-repo-ops.py provision` with the resolved arguments.
6. If provisioning succeeds during PrePlan, explicitly return control to PrePlan so brainstorming can continue.

## Script Reference

`./scripts/target-repo-ops.py`

```bash
# Verify or create a public repo, clone it into TargetProjects, and persist metadata
uv run scripts/target-repo-ops.py provision \
  --governance-repo /path/to/governance \
  --feature-id hermes-lens-plugin \
  --repo-name Lens.Hermes \
  --owner crisweber2600 \
  --visibility public \
  --create-remote

# Register an already-existing remote and clone it into a custom TargetProjects path
uv run scripts/target-repo-ops.py provision \
  --governance-repo /path/to/governance \
  --feature-id hermes-lens-plugin \
  --repo-name Lens.Hermes \
  --remote-url https://github.com/crisweber2600/Lens.Hermes \
  --local-path TargetProjects/plugins/hermes/Lens.Hermes

# Dry run
uv run scripts/target-repo-ops.py provision \
  --governance-repo /path/to/governance \
  --feature-id hermes-lens-plugin \
  --repo-name Lens.Hermes \
  --owner crisweber2600 \
  --visibility public \
  --create-remote \
  --dry-run

# Persist the repo-scoped dev branch mode selected on the first /dev run
uv run scripts/target-repo-ops.py set-dev-branch-mode \
  --governance-repo /path/to/governance \
  --feature-id hermes-lens-plugin \
  --repo-name Lens.Hermes \
  --mode feature-id
```

## Integration Points

| Skill | Relationship |
|-------|-------------|
| `bmad-lens-preplan` | Route repo-creation requests here, then resume brainstorming |
| `bmad-lens-discover` | Reconcile and validate repo inventory after provisioning |
| `bmad-lens-feature-yaml` | Persist target repo metadata into `feature.yaml` |
| `bmad-lens-dev` | Consumes `target_repos[0].local_path` as the implementation root and `target_repos[0].dev_branch_mode` as the repo-scoped branch preference |
