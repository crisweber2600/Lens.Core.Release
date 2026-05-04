---
name: lens-git-orchestration
description: "Git write operations for the Lens 2-branch control-repo model plus target-repo dev working-branch preparation."
---

# lens-git-orchestration

## Overview

Git write operations for the Lens 2-branch feature model. This skill creates and manages `{featureId}` + `{featureId}-plan` branches in the control repo, commits planning artifacts with structured messages, prepares the target repo working branch used by Dev, handles merges, and creates or reuses PRs. This is the WRITE counterpart to `lens-git-state`.

## Identity

I am the Git Orchestration skill for Lens — I handle all git write operations for the 2-branch control-repo topology and the repo-scoped target-repo branch preparation used by Dev. I am the WRITE counterpart to `lens-git-state` (which never writes). Every operation I perform is atomic, explicitly confirmed, and audit-logged via structured commit messages.

## Communication Style

- Confirm repo path, branch mode, branch names, and remote targets before writing
- Report every git operation outcome (branch created, pushed, PR URL, or branch reused)
- Surface errors clearly with the exact git message — never silently swallow failures
- When asked to commit, always show what will be staged before committing

## Principles

- **2-branch invariant in the control repo**: Every feature has exactly `{featureId}` (base) and `{featureId}-plan` (planning) branches in the control repo. Optional control-repo contributor branches (`{featureId}-dev-{username}`) remain separate from target-repo working branches.
- **Target-repo dev modes are separate**: `direct-default`, `feature-id`, and `feature-id-username` are target-repo working-branch modes only. They never change the control repo 2-branch invariant, and they may use a short `featureSlug` even when the control repo uses a composite `featureId`.
- **Governance main-only**: `feature.yaml` and all governance artifacts live on `main` in the governance repo. Branch topology only exists in the control repo and the selected target repo.
- **Atomic commits**: State file updates and artifact commits are always staged and committed together — never separately.
- **No silent pushes**: Remote push only happens when explicitly requested or when a phase is complete.
- **Read before write**: All precondition checks (branch existence, clean state, default branch resolution) run before any write.

## On Activation

I create and manage branches for Lens features — I enforce the control repo 2-branch model (`featureId` + `featureId-plan`), prepare the target repo working branch for Dev, and commit planning artifacts. I do not modify `feature.yaml` (that is `lens-feature-yaml`'s job) and I do not query state (use `lens-git-state`).

Load available config from `{project-root}/lens.core/_bmad/config.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`. Resolve:
- `{governance_repo}` — path to the governance repo (required)
- `{control_repo}` — path to the control/working repo (defaults to governance_repo)
- `{username}` — used for control-repo dev branch naming and for the target-repo `feature/{featureId}-{username}` mode
- `{default_branch}` — optional override for the repo default branch; otherwise detect the remote default branch and fall back to `main`

## Capabilities

### create-feature-branches

**Outcome:** `{featureId}` and `{featureId}-plan` branches exist in the control repo and are pushed to remote with tracking set up.

**Process:**
1. Validate `{featureId}` — must be lowercase alphanumeric + hyphens, no slashes.
2. Confirm `feature.yaml` exists for this feature in the governance repo.
3. Confirm neither branch already exists (fail with a clear message if either does).
4. Resolve the control repo default branch, honoring `{default_branch}` when explicitly supplied.
5. Create `{featureId}` from the resolved default branch, push with `--set-upstream`.
6. Create `{featureId}-plan` from `{featureId}`, push with `--set-upstream`.
7. Report branch names, parent, and remote tracking refs.

Load `./references/create-feature-branches.md` for full guidance.

### commit-artifacts

**Outcome:** One or more files are staged and committed to the current branch with a structured commit message.

**Process:**
1. Verify the working directory is on the correct control-repo branch (`{featureId}` or `{featureId}-plan`).
2. Show files that will be staged — wait for confirmation.
3. Stage specified files with `git add`.
4. Commit with message format: `[{PHASE}] {featureId} — {description}`.
5. If `--push` flag is given, immediately push to remote after commit.

Load `./references/commit-artifacts.md` for full guidance.

### create-dev-branch

**Outcome:** Optional control-repo contributor branch `{featureId}-dev-{username}` is created from `{featureId}` and pushed.

**Process:**
1. Confirm `{featureId}` base branch exists.
2. Confirm `{featureId}-dev-{username}` does not already exist.
3. Create from `{featureId}`, push with `--set-upstream`.
4. Report branch name, parent, and remote ref.

Load `./references/create-dev-branch.md` for full guidance.

### prepare-dev-branch

**Outcome:** The selected target repo is checked out to the working branch used for the current Dev cycle, and the caller receives the resolved base branch plus whether a final PR is required.

**Modes:**
- `direct-default` — checkout and pull the target repo default branch; no final PR is required.
- `feature-id` — create or reuse `feature/{featureSlug}` from the target repo default branch. When no explicit `featureSlug` is supplied, it falls back to `{featureId}`.
- `feature-id-username` — create or reuse `feature/{featureSlug}-{username}` from the target repo default branch. When no explicit `featureSlug` is supplied, it falls back to `{featureId}`.

**Process:**
1. Resolve the target repo default branch, honoring `{default_branch}` when explicitly supplied.
2. Fail on a dirty worktree unless `--dry-run` is set.
3. For `direct-default`: checkout the default branch and pull it.
4. For branch modes: reuse the local branch when it already exists, reuse the remote branch when only the remote exists, otherwise create the working branch from the default branch and push with `--set-upstream`.
5. Return `working_branch`, `base_branch`, `requires_pr`, and whether the branch was created or reused.

This capability is the target-repo counterpart to the Dev skill's repo-scoped branch mode selection. It prepares `feature/{featureSlug}` or `feature/{featureSlug}-{username}` without affecting control-repo topology.

### merge-plan

**Outcome:** `{featureId}-plan` branch is merged into `{featureId}` via PR or direct merge in the control repo.

**Process:**
1. Confirm both branches exist and are clean.
2. Determine merge strategy: `pr` (default) or `direct`.
3. For `pr`: create or reuse a GitHub PR from `{featureId}-plan` → `{featureId}`, optionally enable auto-merge, then return the PR URL.
4. For `direct`: merge with `--no-ff`, commit message `[MERGE] {featureId} — merge plan into base`.
5. Optionally delete `{featureId}-plan` after a successful merge.

Load `./references/merge-plan.md` for full guidance.

### create-pr

**Outcome:** A PR exists between two named branches, with optional auto-merge enabled when requested.

**Process:**
1. For repos under `TargetProjects/`, load governance `repo-inventory.yaml` and require the matching entry's `feature_base_branch`.
2. If `feature_base_branch` is missing, ask the user which branch PRs should merge into, update `repo-inventory.yaml`, and retry. Do not fall back to `main` or remote default branch for TargetProjects PRs.
3. Confirm base and head branches exist. For TargetProjects repos, the base must match `feature_base_branch`; explicit `--base` or `--target-branch` values cannot override it.
4. Reuse an existing open PR for the same head/base pair when one already exists.
5. Otherwise create the PR with the provided or default title/body.
6. If `--auto-merge` was requested, attempt to enable it and report whether GitHub accepted it.

Load `./references/create-pr.md` for full guidance.

### push

**Outcome:** Current branch (or named branch) is pushed to remote.

**Process:**
1. Confirm branch name and remote target.
2. Run `git push` (with `--set-upstream` if no tracking ref exists yet).
3. Report remote ref, commit SHA, and success or failure.

Load `./references/push.md` for full guidance.

### publish-to-governance

**Outcome:** Reviewed planning artifacts staged in the control repo docs path are mirrored into the feature's governance docs folder on `main` by the publish CLI. Agents do not hand-copy or patch governance docs directly.

**Process:**
1. Resolve the feature's staged docs path from `feature.yaml.docs.path` (fallback: `docs/{domain}/{service}/{featureId}`).
2. Resolve the governance mirror path from `feature.yaml.docs.governance_docs_path` (fallback: `features/{domain}/{service}/{featureId}/docs`).
3. Select the phase artifact set (or explicit artifact overrides).
4. Invoke the CLI-backed publish step, either through this skill or directly via `uv run {project-root}/lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py publish-to-governance --governance-repo {governance_repo} --control-repo {control_repo} --feature-id {feature_id} --phase {phase}`.
5. Do not create governance files or directories directly with tool calls or patches; the publish CLI performs that copy into the mirror path.
6. Return copied source and destination paths so the caller can stage and commit them in governance as needed.

Load `./references/publish-to-governance.md` for full guidance.

## Script Reference

All git write operations run through `./scripts/git-orchestration-ops.py`. This includes control-repo branch management, target-repo `prepare-dev-branch`, PR creation, and governance publishing. Requires Git 2.28+ and `gh` CLI (for PR operations) on the PATH.

**Exit codes:**
- `0` — success
- `1` — hard error (precondition failed, git error, repo not found)
- `2` — partial success with warnings (for example: pushed but PR creation skipped)

**Dry-run mode:** Add `--dry-run` to any subcommand to print all git commands that would be executed without running them.
