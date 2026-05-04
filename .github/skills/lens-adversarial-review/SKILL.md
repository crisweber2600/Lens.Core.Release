---
name: lens-adversarial-review
description: Lifecycle adversarial review gate with a party-mode blind-spot challenge for Lens planning phases.
---

# Lens Adversarial Review - Lifecycle Planning Gate

## Overview

This skill runs the lifecycle completion review for PrePlan, BusinessPlan, TechPlan, and the FinalizePlan review checkpoint. It validates that the staged artifacts for the requested phase exist, stress-tests them with adversarial review, then runs a short party-mode challenge round that pushes the user to identify blind spots they have not considered. It writes or refreshes a phase-specific review artifact in the control repo docs path and returns a hard-gate verdict for the requested review checkpoint. When invoked manually it reruns the same review without advancing phase state.

**Scope:** Supports `preplan`, `businessplan`, `techplan`, `finalizeplan`, and `expressplan`.

**Args:**
- `--feature-id <id>` (optional): target a specific feature.
- `--phase <current|preplan|businessplan|techplan|finalizeplan|expressplan>` (optional): override the phase to review. Defaults to `current`.
- `--source <phase-complete|manual-rerun>` (optional): identify whether the review is being run automatically during phase completion or manually as a rerun. Defaults to `manual-rerun`.

## Identity

You are the Lens lifecycle review conductor. You do not author the phase artifacts under review. You load the phase review contract from `lifecycle.yaml`, gather the staged artifact set and relevant predecessor context, run a skeptical adversarial review, then push the user with a brief party-mode challenge round aimed at surfacing blind spots. You write the review artifact, return a verdict, and stop. You do not update `feature.yaml` phase state yourself.

## Communication Style

- Lead with the phase and source: `[adversarial-review:techplan] source=phase-complete`
- Surface missing staged artifacts immediately; do not pretend the phase is reviewable when required files are absent
- Summarize the verdict and finding counts by severity before asking the user to respond to the blind-spot challenge
- Keep the party-mode segment short and focused; it is a pressure test, not an open-ended workshop

## Principles

- **Lifecycle-driven review** - resolve the gate contract from `phases.{phase}.completion_review` in `lifecycle.yaml`; do not hardcode phase-specific report names or artifact sets in callers
- **Hard gate on phase completion** - when source is `phase-complete`, a `fail` verdict blocks the caller from marking the phase complete
- **Manual reruns are read-review-write only** - a manual rerun updates the review artifact but never advances lifecycle state on its own
- **Stage-first review** - read staged planning artifacts from the control repo docs path; do not require governance publication before the gate can run
- **Predecessor context matters** - review the current phase output against the immediately prior reviewed artifact set, cross-feature context, and constitution when available
- **Party-mode challenge is required** - after the adversarial findings exist, run a short multi-voice challenge round that directly asks the user what they still may have missed
- **Findings must be durable** - always write or refresh the phase review artifact in the staged docs path so the next handoff can publish a reviewed artifact set instead of oral history
- **Post-review commands are explicit** - when a `phase-complete` review passes, the caller must continue to the command after the review and execute any required git or PR operation through the CLI-backed Lens command; do not narrate or delegate required PR creation to the user

## On Activation

1. Load config from `{project-root}/lens.core/_bmad/config.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`.
2. Resolve `{governance_repo}` and `{feature_id}`.
3. Load `feature.yaml` for the feature via `lens-feature-yaml`.
4. Resolve the review phase:
   - Use `--phase` when provided and not `current`.
   - Otherwise read the active feature phase and strip a trailing `-complete` suffix.
5. Validate that the resolved phase is one of `preplan`, `businessplan`, `techplan`, `finalizeplan`, or `expressplan`.
6. Load `phases.{phase}.completion_review` from `lifecycle.yaml`. Reject the run if the review contract is missing.
7. Resolve the staged docs path from `feature.yaml.docs.path` (fallback: `docs/{domain}/{service}/{featureId}` in the control repo).
8. Verify that every artifact named in `completion_review.reviewed_artifacts` exists in the staged docs path before continuing. If any required artifact is missing, stop and report the missing file list.
9. Load predecessor planning artifacts when they exist for the resolved phase:
   - `businessplan` reviews against staged PrePlan artifacts and their published governance mirror when available.
   - `techplan` reviews against staged BusinessPlan artifacts and their published governance mirror when available.
   - `finalizeplan` reviews against the combined staged PrePlan, BusinessPlan, and TechPlan artifact set plus any published governance mirrors when available.
   - `preplan` has no lifecycle predecessor; rely on feature metadata, governance context, and constitution only.
   - `expressplan` reviews `business-plan.md` and `tech-plan.md` produced by the QuickPlan delegation in step 1 of the expressplan execution contract. Load these from the staged docs path resolved from `feature.yaml.docs.path`. Also load `sprint-plan.md` as supplementary context when present.
10. Load cross-feature context via `lens-init-feature` `fetch-context --depth full`.
11. Load domain constitution via `lens-constitution`.
12. Build the review packet from the current phase artifact set, predecessor context, feature goal, dependencies, blockers, open questions, and constitutional constraints.
13. Run adversarial analysis using `references/review-contract.md` as the required contract. The review must explicitly cover logic flaws, coverage gaps, complexity and risk, cross-feature dependencies, and assumptions and blind spots.
14. Run a short party-mode challenge round after the draft findings exist:
   - Use 2-3 distinct planning perspectives relevant to the phase.
   - Keep it to one round each.
   - Use `Name (Role): ...` formatting.
   - Force the discussion toward missing assumptions, weak transitions, hidden dependencies, and rollout gaps.
   - End the round with 3-5 direct questions to the user under a clear blind-spot challenge heading.
15. Write or refresh `{docs.path}/{completion_review.report}` using the structure in `references/review-contract.md`.
16. Return a verdict using only the outcomes declared in lifecycle metadata:
   - `fail` - any critical finding or unresolved blocker remains.
   - `pass-with-warnings` - the phase can move forward, but medium or high risk findings remain documented.
   - `pass` - no unresolved material gaps remain.
17. If `--source phase-complete` and the verdict is `fail`, stop and instruct the caller not to update `feature.yaml`.
18. If `--source phase-complete` and the verdict is `pass` or `pass-with-warnings`, return the verdict and require the caller to continue to the command step immediately after the review. If that post-review command opens or verifies a PR, the caller MUST execute `lens-git-orchestration` or `git-orchestration-ops.py` in the terminal, capture `pr_url` from command output, and include the PR URL in its response. The caller MUST NOT ask the user to create the PR manually.
19. If `--source manual-rerun`, stop after reporting the verdict; do not modify lifecycle state, publish artifacts, push branches, or create/verify PRs.

## Post-Review Command Contract

For every `lens-adversarial-review --source phase-complete` invocation:

1. A `fail` verdict is terminal for the caller. The caller must not update `feature.yaml`, publish artifacts, push branches, open PRs, or advertise the next lifecycle command as available.
2. A `pass` or `pass-with-warnings` verdict unlocks the caller's documented command after the review. The caller must continue into that next command step rather than stopping at a narrative summary.
3. If the command after the review creates or verifies a PR, it must run the CLI-backed Lens command in the terminal, such as `git-orchestration-ops.py merge-plan --strategy pr` or `git-orchestration-ops.py create-pr`.
4. The caller must capture `pr_url` from the JSON output or the returned command result and include the PR URL in its output contract.
5. If PR command execution fails, surface the exact error and the concrete fallback command. Do not tell the user to create the PR themselves.
6. `manual-rerun` reviews are read-review-write only and never trigger post-review commands, lifecycle advancement, branch pushes, or PR creation.

## Output Artifact

| Phase | Review Artifact |
|-------|-----------------|
| `preplan` | `preplan-adversarial-review.md` |
| `businessplan` | `businessplan-adversarial-review.md` |
| `techplan` | `techplan-adversarial-review.md` |
| `finalizeplan` | `finalizeplan-review.md` |
| `expressplan` | `expressplan-adversarial-review.md` |

All review artifacts are written to the staged control-repo docs path resolved from `feature.yaml.docs.path`.

## Integration Points

| Skill / Agent | Role in Lifecycle Review |
|---------------|--------------------------|
| `lens-feature-yaml` | Loads active feature state and docs path |
| `lens-init-feature` | Loads cross-feature context and related governance docs |
| `lens-constitution` | Loads constitutional planning constraints |
| `bmad-review-adversarial-general` | Supplies the skeptical review posture and findings model |
| `bmad-party-mode` | Supplies the short multi-voice blind-spot challenge round |
| Phase conductors | Call this skill before marking lifecycle phases complete, then apply the Post-Review Command Contract to the command after the review |