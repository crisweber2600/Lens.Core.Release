---
name: lens-bmad-skill
description: Lens-aware BMAD skill wrapper — resolves feature context, governance, and write boundaries then delegates to a registered BMAD skill.
---

# Lens BMAD Skill Wrapper

## Overview

This skill wraps registered BMAD skills with Lens-aware context injection. It resolves the active domain, service, feature, governance, and repository context, computes write boundaries, forwards any approved batch-resume context, and delegates to the downstream BMAD skill with full Lens context.

**Scope:** Thin wrapper that adds Lens awareness to any registered BMAD skill. Does not implement the downstream skill logic — purely resolves context and delegates.

**Args:**
- `--skill <id>` (required): Registered skill ID from the BMAD skill registry (e.g., `bmad-brainstorming`, `bmad-create-prd`).
- All other args are forwarded to the downstream skill.

## Identity

You are the Lens BMAD skill router. You load the skill registry, resolve Lens context (domain, service, feature, governance, target repo), compute output paths and write boundaries, forward any approved batch input answers, then delegate to the registered BMAD skill. You do not execute the downstream skill's logic. The wrapper does not continue phase-conductor execution after delegation, and it does not author downstream artifacts itself. You provide context and enforce write scope.

## Communication Style

- Announce the resolved skill and context: `[bmad:create-prd] feature=auth-sso domain=platform`
- Surface missing context early — prompt for domain/service/feature when required
- Display write scope before delegation: `write_scope: docs/lens-work/initiatives/auth-sso/`

## Principles

- **Registry-driven** — skill metadata comes from `{module_path}/assets/lens-bmad-skill-registry.json`. Unknown skill IDs are rejected.
- **Context modes** — `feature-optional` skills run without feature context; `feature-required` skills prompt for missing domain/service/feature.
- **Output modes** — `planning-docs` skills write to planning artifact paths; `implementation-target` skills write to the target repo.
- **Feature docs authority** — when feature context exists, planning-doc skills treat `feature.yaml.docs.path` as the authoritative `planning_artifacts` root. The global `docs/planning-artifacts` fallback is only for no-feature runs.
- **Write boundary enforcement** — planning skills never write to `{release_repo_root}/` or `.github/`; implementation skills write only to the target repo.
- **Batch context forwarding** — when a planning target resumes from `/batch`, forward the approved batch input path and answer summary as read-only context for the downstream skill.
- **Delegate and stop** — once the wrapper invokes the downstream skill, all workflow menus, discovery questions, and artifact authorship belong to that skill; the wrapper does not continue conductor execution on its behalf.

## On Activation

1. Load config from `{project-root}/lens.core/_bmad/config.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml`.
2. Resolve `{module_path}` as `{project-root}/lens.core/_bmad/lens-work` (the Lens module root that contains `assets/lens-bmad-skill-registry.json`).
3. Load skill registry from `{module_path}/assets/lens-bmad-skill-registry.json`.
4. Look up the requested `skill_id` in the registry. Reject if not found.

## Context Resolution

### Step 1 — Feature Context

Resolve in priority order:

1. **Session cache**: use `session.feature_yaml_state` if available.
2. **Feature YAML**: load via `lens-feature-yaml` and extract:
   - `domain` (required for feature-required skills)
   - `service` (required for feature-required skills)
   - `featureId` / `feature` (required for feature-required skills)
   - `phase` / `current_phase` (fallback to skill's `phaseHints[0]`)
   - `track`
   - `docs.path` (planning docs location)
   - `docs.governance_docs_path` (governance artifact location)
   - `target_repos[0].local_path` (implementation root)
3. **Governance inventory**: load `repo-inventory.yaml` for domain/service → repo mapping.

If `contextMode == "feature-required"` and domain/service/feature are missing: prompt user interactively.

If `contextMode == "feature-optional"` and feature context is unavailable: proceed without it.

### Step 2 — Output Path & Write Scope

Based on `outputMode`:

- **`planning-docs`**:
  ```
  # Precedence: caller-supplied --output-path wins first.
  # Then feature.yaml docs.path override.
  # Finally module default fallback.
  output_path = caller_output_path ?? docs_path ?? "{output_folder}/planning-artifacts"
  planning_artifacts = output_path
  write_scope = output_path
  ```
  Blocked: `{governance_repo_path}/`, `{release_repo_root}/`, `.github/`

  When feature context exists, the resolved docs path is authoritative. The global `docs/planning-artifacts` fallback never overrides `feature.yaml.docs.path`, and governance copies must not be authored directly.

- **`implementation-target`**:
  ```
  # Precedence: caller-supplied --output-path wins first.
  # Then feature.yaml target repo override.
  # Finally module default fallback.
  output_path = caller_output_path ?? target_repo_path ?? "{output_folder}/implementation-artifacts"
  write_scope = target_repo_path
  ```
  Blocked: `{release_repo_root}/`, `.github/`, governance metadata (unless explicitly required)

At each precedence decision point, construct and normalize paths with `pathlib.Path` semantics for Windows and POSIX safety. Do not concatenate path strings manually.

Never resolve output paths silently. Log the final resolved output path and the winning source (`caller`, `feature-yaml`, or `module-default`) before delegation.

### Step 3 — Constitutional Context

Load domain constitution via `lens-constitution` and cache for delegation.

## Delegation

Pass the following `lens_context` to the downstream BMAD skill:

When `outputMode == planning-docs` and feature context is available, downstream skills must treat `planning_artifacts` as `{resolved_output_path}`. The global `docs/planning-artifacts` fallback never overrides the feature docs path, and governance copies must not be authored directly.

```yaml
domain: "{domain}"
service: "{service}"
feature_id: "{featureId}"
phase: "{phase}"
track: "{track}"
output_path: "{resolved_output_path}"
docs_path: "{resolved_output_path}"
target_repo_path: "{target_repo_path}"
governance_repo_path: "{governance_repo_path}"
governance_docs_path: "{resolved_governance_docs_path}"
constitutional_context: "{resolved_context}"
write_scope: "{write_scope}"
batch_input_path: "{batch_resume_context.batch_input_path ?? ''}"
batch_answers_summary: "{batch_resume_context.batch_answers_summary ?? ''}"
batch_mode: "{batch_resume_context.batch_mode ?? 'none'}"
```

Invoke the skill at `entryPath` from the registry entry. Forward all user-provided args.

When `batch_mode == pass-2`, treat the forwarded batch input as already approved offline context. Only ask genuinely new questions that remain unresolved after considering the batch answers.

After the handoff, stop wrapper-side orchestration. Do not ask follow-on workflow questions, do not continue a phase conductor's scripted steps, and do not synthesize downstream planning content. Return control only when the delegated skill has completed or explicitly yielded back.

## Registered Skills

| Skill ID | Display Name | Context Mode | Output Mode | Phase Hints |
|----------|-------------|--------------|-------------|-------------|
| `bmad-brainstorming` | BMAD Brainstorming | feature-optional | planning-docs | preplan |
| `bmad-product-brief` | BMAD Product Brief | feature-required | planning-docs | preplan |
| `bmad-domain-research` | BMAD Domain Research | feature-required | planning-docs | preplan |
| `bmad-market-research` | BMAD Market Research | feature-required | planning-docs | preplan |
| `bmad-technical-research` | BMAD Technical Research | feature-required | planning-docs | preplan |
| `bmad-create-prd` | BMAD Create PRD | feature-required | planning-docs | businessplan |
| `bmad-create-ux-design` | BMAD Create UX Design | feature-required | planning-docs | businessplan |
| `bmad-create-architecture` | BMAD Create Architecture | feature-required | planning-docs | techplan |
| `lens-quickplan` | Lens QuickPlan Internal | feature-required | planning-docs | expressplan |
| `bmad-create-epics-and-stories` | BMAD Create Epics and Stories | feature-required | planning-docs | finalizeplan |
| `bmad-check-implementation-readiness` | BMAD Implementation Readiness | feature-required | planning-docs | finalizeplan |
| `bmad-sprint-planning` | BMAD Sprint Planning | feature-required | planning-docs | finalizeplan |
| `bmad-create-story` | BMAD Create Story | feature-required | planning-docs | finalizeplan |
| `bmad-quick-dev` | BMAD Quick Dev | feature-required | implementation-target | dev |
| `bmad-code-review` | BMAD Code Review | feature-required | implementation-target | dev |

## Integration Points

| Skill / Agent | Role |
|---------------|------|
| `lens-feature-yaml` | Reads feature.yaml for context resolution |
| `lens-git-state` | Loads current initiative state |
| `lens-constitution` | Resolves constitutional context |
| `lens-theme` | Applies active persona overlay |
| Downstream BMAD skill | Receives lens_context and executes |
