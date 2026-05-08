---
name: bmad-lens-postflight
description: Core postflight conductor. Takes one Lens session closeout and enforces commit, push, and clean-state verification across touched repos.
---

# /lens-postflight

## Overview

`/lens-postflight` is a session closeout flow for Lens work.
It inspects the touched Lens repos, commits and pushes qualifying changes,
and proves that the target, control, and governance repos are clean before the
run finishes.

This skill is a thin conductor. It orchestrates cleanup only.

## Non-Negotiables

- End-of-session closeout is mandatory when the workspace has touched repos with changes.
- Never leave target, control, or governance repo changes uncommitted or unpushed after postflight completes.
- Never tell the user to commit, push, or clean repos manually when the required automation commands are available.
- A successful `/lens-postflight` run requires every touched repo to be committed, pushed, and verified clean.
- If a touched repo cannot be committed, pushed, or proven clean, stop with a structured blocker.
- Do not sweep unrelated user edits into the closeout commit. If the current repo state cannot be safely attributed to this session, stop and ask for guidance.
- Never create, add, remove, or use a sibling git worktree for this flow. Use the canonical workspace checkouts only.

## Required Inputs

Collect these fields before execution when they are not already resolvable from the active Lens context:

- `feature_id` or active feature context
- `session_summary`

If any required field is missing and cannot be resolved locally, ask only for the missing fields and stop until complete.

## On Activation

1. Resolve the workspace root and the standard Lens repos that may need closeout:
   - `control_repo = {project-root}`
   - `governance_repo = {project-root}/TargetProjects/lens/lens-governance`
   - `target_repo = {project-root}/TargetProjects/lens-dev/new-codebase/lens.core.src`
2. Resolve the active feature context if available, but do not require it when the session closeout is purely repo-state driven.
3. Inspect `git status --short` in each repo that may have session changes.
4. For every touched repo with changes, stage and commit the changes with a conventional commit message that summarizes the session closeout.
5. Push every touched repo after a successful commit.
6. Verify `git status --short` is empty in the target, control, and governance repos.
7. If any repo remains dirty after commit and push, stop with a structured blocker and report the exact repo and state.
8. If no repo had changes, record a no-op closeout, but still verify that all three repos are clean.

## Closeout Rules

- The target repo, control repo, and governance repo must not contain a dirty state after postflight finishes.
- If a repo contains untracked, modified, staged, or partially committed changes that are not safe to attribute to this session, stop instead of absorbing them into the closeout.
- If a push fails, stop and surface the exact blocking command or remote error.
- If the session created work in more than one repo, complete the closeout for every touched repo before responding.
- Do not leave a repo committed but unpushed when a push command is available.

## Execution Contract

1. Confirm the workspace is the canonical Lens control workspace and the standard repos are resolvable.
2. Determine whether the session touched the target, control, or governance repo by checking their working-tree state.
3. For each touched repo, stage the session changes, create one conventional commit, and push the branch.
4. If a repo is already clean, leave it unchanged and record that it required no closeout commit.
5. Re-run `git status --short` on the target, control, and governance repos after all pushes complete.
6. If any of those repos still shows changes, stop with a blocker rather than reporting success.

## Output Contract

Return:

- touched repos
- commit hashes
- push status
- clean-state verification summary
- any blocker reason if postflight could not complete