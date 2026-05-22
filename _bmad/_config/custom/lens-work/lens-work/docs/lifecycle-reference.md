# LENS Workbench — Lifecycle Reference Guide

**Module:** lens-work v4.0  
**Schema:** 4  
**Purpose:** Human-readable reference for the current Lens lifecycle contract

---

## Overview

Lens-work now operates on a **feature-first, 2-branch control-repo model**.

- Planning work happens on `{featureId}-plan`.
- Approved feature state and published artifacts live on `{featureId}` and governance `main`.
- `feature.yaml` tracks the current phase and milestone.
- `FinalizePlan` replaces the old `DevProposal` and `SprintPlan` chain.

Legacy audience-tier and milestone-branch terminology remains relevant only for migration support. The active lifecycle contract is defined by [lifecycle.yaml](../lifecycle.yaml).

## Core Concepts

### Phases

| Phase | Owner | Primary Outputs | Notes |
|-------|-------|-----------------|-------|
| `preplan` | Mary (Analyst) | `product-brief`, `research`, `brainstorm` | Starts the full track |
| `businessplan` | John (PM) + Sally (UX) | `prd`, `ux-design` | Skips research on the `feature` track |
| `techplan` | Winston (Architect) | `architecture` | Auto-advances to `finalizeplan` |
| `finalizeplan` | Lens | `review-report`, `epics`, `stories`, `implementation-readiness`, `sprint-status`, `story-files` | Replaces `devproposal` plus `sprintplan` |
| `expressplan` | Lens | `business-plan`, `tech-plan`, `sprint-plan`, `expressplan-adversarial-review` | Standalone express-track phase that hands off into `finalizeplan` |

`/dev` is not a lifecycle phase. It is the implementation handoff command after `dev-ready`.

### Milestones

| Milestone | Phases | Gate |
|-----------|--------|------|
| `techplan` | `preplan`, `businessplan`, `techplan` | Adversarial review at phase completion |
| `finalizeplan` | `finalizeplan` | Party-mode adversarial review |
| `dev-ready` | none | Constitution gate before implementation |
| `dev-complete` | none | Optional execution-completion validation |

### Tracks

| Track | Phases | Start Command | Use Case |
|-------|--------|---------------|----------|
| `full` | `preplan -> businessplan -> techplan -> finalizeplan` | `/preplan` | Full planning lifecycle |
| `feature` | `businessplan -> techplan -> finalizeplan` | `/businessplan` | Known business context |
| `tech-change` | `techplan -> finalizeplan` | `/techplan` | Technical change with minimal business planning |
| `hotfix` | `techplan` | `/techplan` | Urgent fix with minimal planning |
| `hotfix-express` | `techplan` | `/techplan` | Critical fix with expedited governance |
| `spike` | `preplan` | `/preplan` | Research only |
| `quickdev` | `finalizeplan` | `/finalizeplan` | Jump straight to implementation packaging |
| `express` | `expressplan -> finalizeplan` | `/expressplan` | Combined planning with a FinalizePlan handoff |

## Branch Topology

### Default 2-Branch Model

```text
Control repo:
  {featureId}        -> approved feature branch
  {featureId}-plan   -> planning drafts and review reports

Governance repo:
  main               -> canonical feature state and mirrored approved docs
```

### Artifact Mapping

| Location | Contents |
|----------|----------|
| `{featureId}-plan` | `drafts/**`, `reviews/**` |
| `{featureId}` | `feature.yaml`, `artifacts/**` |
| governance `main` | `feature.yaml`, `feature-index.yaml`, `features/{domain}/{service}/{featureId}/summary.md`, mirrored approved docs |

### Phase Mapping

| Phase | Branch | Folder |
|-------|--------|--------|
| `preplan` | `plan` | `drafts/` |
| `businessplan` | `plan` | `drafts/` |
| `techplan` | `plan` | `drafts/` |
| `finalizeplan` | `plan` | `drafts/` |
| `expressplan` | `code` | `artifacts/` |

Milestones are logical checkpoints in `feature.yaml`, not separate control-repo branches.

## Command Reference

### Planning and Execution Commands

| Command | Purpose |
|---------|---------|
| `/preplan` | Run PrePlan |
| `/businessplan` | Run BusinessPlan |
| `/techplan` | Run TechPlan |
| `/finalizeplan` | Run FinalizePlan |
| `/expressplan` | Run ExpressPlan |
| `/dev` | Hand off implementation to target-project workflows |
| `/complete` | Finalize and archive a completed feature |

### Feature Utility Commands

| Command | Purpose |
|---------|---------|
| `/new-domain` | Create a domain container |
| `/new-service` | Create a service container |
| `/new-feature` | Create a feature with lifecycle state |
| `/new-project` | Bootstrap domain, service, feature, and target-repo setup in one flow |
| `/target-repo` | Provision or register a target repo |
| `/dashboard` | Show portfolio state and cross-feature reporting |
| `/next` | Resolve the next unblocked action |
| `/batch` | Generate or resume batch intake |
| `/switch` | Switch active feature context |
| `/discover` | Sync repo inventory with `TargetProjects/` |
| `/retrospective` | Generate a retrospective |
| `/log-problem` | Capture a problem report |
| `/move-feature` | Relocate a feature |
| `/split-feature` | Split a feature |
| `/approval-status` | Show promotion PR approval state |
| `/rollback` | Roll back a phase safely |
| `/profile` | View or edit onboarding profile |
| `/module-management` | Check module version and update guidance |
| `/help` | Show contextual help |

### Governance Commands

| Command | Purpose |
|---------|---------|
| `/constitution` | Resolve constitutional governance |
| `/sensing` | Run cross-initiative overlap detection |
| `/audit` | Run the compliance audit surface |

## Promotion and Gate Semantics

- `techplan` completes on the plan branch and auto-advances to `/finalizeplan`.
- `finalizeplan` runs the final planning review, prepares the plan PR, and then packages downstream implementation artifacts.
- The plan PR is `{featureId}-plan -> {featureId}` in the control repo.
- The final implementation PR is `{featureId} -> main`.
- Governance publication happens at phase handoff or explicit publish steps, never by directly patching governance docs.

## Authority Domains

| Domain | Location | Authority |
|--------|----------|-----------|
| Control repo planning | `docs/` plus feature-scoped staged artifacts | Lens workflows |
| Release payload | `lens.core/_bmad/lens-work/` | Module/release pipeline |
| Copilot adapter | `.github/` | Installer plus release overlay |
| Governance repo | `TargetProjects/lens/lens-governance` | Governance workflows and explicit publish tooling |

## Legacy Note

`DevProposal` and `SprintPlan` are legacy v3 lifecycle surfaces. They remain on disk only for migration/reference purposes and are not part of the active v4 planning path.