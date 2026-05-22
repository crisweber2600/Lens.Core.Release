---
applyTo: "**"
---

# Repository Topology — BMAD Control Repo

> ⚠️ **Partial Update Notice (v4.0):** Audience tier references reflect the v3.x promotion model. The current architecture uses **2-branch topology** (schema 3.4).

This workspace is a **BMAD control repo** that orchestrates planning and development across multiple nested repositories. Understanding this topology is critical — every agent, prompt, and workflow must respect these boundaries.

## Three Repository Zones

### 1. Control Repo (workspace root)

The top-level workspace. This is an **operational workspace**, not a code repo. It contains:

- `.github/` — Copilot adapter stubs (agents, skills, prompts) that reference the release module by path
- `.lens/` — Local-only universal Lens state (`governance-setup.yaml`, `repo-inventory.yaml`, `.preflight-cache`, `.preflight-timestamp`, `.github-hashes`)
- `.lens/personal/` — Local-only personal profile and context files (`profile.yaml`, `context.yaml`)
- `docs/` — All lens-work initiative artifacts, organized as `docs/{domain}/{service}/{feature}/`
- `setup-control-repo.py` — Bootstrap script

**Write rules:** Planning phase prompts write initiative artifacts here (under `docs/{domain}/{service}/{feature}/`). The `/dev` prompt writes ONLY state-tracking files here (`docs/` sprint-status, state).

### 2. Release Repo (`lens.core/`)

A **git submodule** containing the BMAD framework release payload. This is the **authority** for all module definitions.

- `lens.core/_bmad/lens-work/` — The lens-work module: lifecycle contract, skills, workflows, prompts, scripts, agents, docs
- `lens.core/_bmad/bmm/`, `lens.core/_bmad/core/`, `lens.core/_bmad/cis/`, etc. — Other BMAD modules
- `lens.core/_bmad/_config/` — Global manifests (agent, workflow, task, tool, files)

**Write rules:** NEVER modify files in `lens.core/`. It is read-only reference material. All `lens.core/_bmad/` path references in prompts and workflows resolve relative to `lens.core/`, NOT the workspace root.

### 3. TargetProjects

Contains **cloned code repositories** organized by `{domain}/{service}/{repo}`. The base path is configured in `lens.core/_bmad/lens-work/bmadconfig.yaml` as `target_projects_path` (default: `../TargetProjects`).

Each subfolder is an independent git repo with its own `.git/`, branches, and remotes.

**Write rules:** The `/dev` prompt writes ALL implementation code here — file creation, modification, commits, pushes, and PRs happen exclusively in the target repo resolved from the initiative config.

## Path Resolution Rules

| Reference Pattern | Resolves To |
|---|---|
| `lens.core/_bmad/lens-work/...` in a prompt or workflow | `lens.core/_bmad/lens-work/...` |
| `lens.core/_bmad/_config/...` | `lens.core/_bmad/_config/...` |
| `docs/...` | Workspace root `docs/...` (control repo) |
| `{target_projects_path}/{domain}/{service}/{repo}/` | The cloned code repo for that initiative |
| `.github/prompts/*.prompt.md` | Published Lens Next stub files (`lens-*.prompt.md`) — always follow the redirect to `lens.core/_bmad/lens-work/prompts/...` |
| `.github/skills/*/SKILL.md` | Stub files — always follow the redirect to the referenced `lens.core/_bmad/.../SKILL.md` path |

## The `/dev` Prompt — Strict Write Scope

When `lens-dev.prompt.md` is executed:

1. **Implementation code** (new files, edits, commits, branches, PRs) goes ONLY in the target repo under the configured `target_projects_path`
2. **State tracking** (sprint-status, initiative state) goes ONLY in `docs/`
3. **NEVER modify** the control repo root, `.github/`, `lens.core/`, or any other repo

This is enforced by the dev workflow's "Write Scope — Target Repo Only" rule: before implementing any task, verify the working directory is inside the target repo. If verification fails, implementation is blocked.

## Lens-Work Lifecycle Summary

The lens-work module manages a 4-phase planning lifecycle plus an express entrypoint in the default schema 4 model:

| Phase | Agent | Branch |
|---|---|---|
| PrePlan | Mary (Analyst) | `{featureId}-plan` |
| BusinessPlan | John (PM) + Sally (UX) | `{featureId}-plan` |
| TechPlan | Winston (Architect) | `{featureId}-plan` |
| FinalizePlan | Lens | `{featureId}-plan` |
| ExpressPlan | Lens | `{featureId}` |

- **FinalizePlan** replaces the old `DevProposal` plus `SprintPlan` chain.
- **Dev** is not a lifecycle phase — it is a delegation command that hands off to implementation agents in target projects.
- **Git is the only source of truth** — branch state, PR metadata, and committed artifacts determine lifecycle state.
- **PRs are the only gating mechanism** — no side-channel approvals.

## Key Conventions

- All `.github/prompts/` and `.github/skills/` files are **stubs** that redirect to full implementations in `lens.core/`
- Never duplicate module content into `.github/` — module updates propagate through path references
- The `lens.core/` submodule branch matters: on `alpha`, run full preflight at most once per hour; on `beta`, run full preflight at most once every 3 hours
- Initiative artifacts live at the feature-scoped staged docs path resolved from `feature.yaml.docs.path` (fallback: `docs/{domain}/{service}/{feature}/`)
- Lens-work universal local state lives at `.lens/`, and personal config lives at `.lens/personal/`
