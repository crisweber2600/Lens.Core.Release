# LENS Workbench — Lifecycle Reference Guide

**Module:** lens-work v2.0  
**Purpose:** Human-readable reference for the lens-work lifecycle system

---

## Overview

The LENS Workbench manages software initiatives through a structured lifecycle of **phases** and **audience tiers**. All state is derived from git — branch existence, PR metadata, and committed artifacts. There is no secondary state store.

## Core Concepts

### Initiatives

An initiative is a unit of work scoped to a domain, service, or feature. Each initiative has its own branch topology in the control repo. **Initiative roots have variable segment counts depending on scope.**

| Scope | Example Root | Created By | Segments |
|-------|-------------|-----------|----------|
| Domain | `test` | `/new-domain` | 1 |
| Service | `test-worker` | `/new-service` | 2 |
| Feature | `test-worker-oauth` | `/new-feature` | 3 |

### Phases

Phases are sequential stages of planning and implementation. Each phase produces artifacts, and phase completion is marked by a merged PR from the phase branch to its audience branch.

| Phase | Agent | Artifacts Produced |
|-------|-------|--------------------|
| PrePlan | Mary (Analyst) | product-brief, research, brainstorm |
| BusinessPlan | John (PM) + Sally (UX) | prd, ux-design |
| TechPlan | Winston (Architect) | architecture |
| DevProposal | John (PM) | epics, stories, implementation-readiness |
| SprintPlan | Bob (Scrum Master) | sprint-status, story-files |

### Audience Tiers

Audiences represent levels of review and approval. Initiatives start at `small` and promote upward through PR-based gates.

| Audience | Role | Entry Gate | Phases Worked |
|----------|------|-----------|---------------|
| small | IC creation work | — | preplan, businessplan, techplan |
| medium | Lead review | Adversarial review (party mode) | devproposal |
| large | Stakeholder approval | Stakeholder approval | sprintplan |
| base | Ready for execution | Constitution gate | — (dev happens in target projects) |

> **Note:** Domains never have audience branches. Audiences apply only to service-level and feature-level initiatives. A domain branch is the bare root (e.g., `test`), with no `-small` suffix.

### Tracks

Tracks are predefined lifecycle profiles that determine which phases apply.

| Track | Phases | Use Case |
|-------|--------|----------|
| full | preplan → businessplan → techplan → devproposal → sprintplan | Complete lifecycle |
| feature | businessplan → techplan → devproposal → sprintplan | Known business context |
| tech-change | techplan → devproposal → sprintplan | Pure technical change |
| hotfix | techplan | Urgent fix |
| spike | preplan | Research only |
| quickdev | devproposal | Rapid execution |

## Branch Topology

### Naming Convention

```
{initiative-root}                          # Initiative root
{initiative-root}-{audience}               # Audience branch
{initiative-root}-{audience}-{phase}       # Phase branch
```

### Merge Flow

```
Phase branch → Audience branch     (phase completion PR)
Audience → Next audience           (promotion PR with gates)
```

### Lazy Branch Creation

Only `{root}` and `{root}-small` are created at init. Higher audience branches are created on-demand at promotion time.

## Commands Reference

### Phase Commands

| Command | Phase | Prerequisites |
|---------|-------|--------------|
| `/preplan` | PrePlan | On small audience, track includes preplan |
| `/businessplan` | BusinessPlan | preplan PR merged (if in track) |
| `/techplan` | TechPlan | businessplan PR merged (if in track) |
| `/devproposal` | DevProposal | Promoted to medium, techplan PR merged |
| `/sprintplan` | SprintPlan | Promoted to large, devproposal PR merged |
| `/dev` | Dev | Delegates to implementation agents in target projects |

### Utility Commands

| Command | Purpose |
|---------|---------|
| `/onboard` | Bootstrap control repo — provider auth, governance clone, profile, and TargetProjects auto-clone |
| `/status` | Show all initiatives with phases, audiences, and pending actions |
| `/next` | Recommend the next action based on lifecycle state |
| `/switch` | Checkout a different initiative's branch |
| `/help` | Command reference and module version info |

### Governance Commands

| Command | Purpose |
|---------|---------|
| `/promote` | Promote current audience to next tier with gate checks |
| `/sense` | On-demand cross-initiative overlap detection |
| `/constitution` | Resolve and display constitutional governance for current initiative |

## Authority Domains

| Domain | Location | Write Authority |
|--------|----------|----------------|
| Control Repo | `_bmad-output/lens-work/` | @lens writes initiative artifacts |
| Release Module | `bmad.lens.release/_bmad/lens-work/` | Module builder only (read-only at runtime) |
| Copilot Adapter | `.github/` | User only (not modified during initiative work) |
| Governance | `TargetProjects/lens/lens-governance/` | Governance leads only (via governance repo PRs) |

Cross-authority writes are **hard errors**, not warnings.

## Constitution Governance

### 4-Level Hierarchy

```
org/constitution.md              ← Level 1: universal defaults
{domain}/constitution.md         ← Level 2: domain-specific
{domain}/{service}/constitution.md  ← Level 3: service-specific
{domain}/{service}/{repo}/constitution.md  ← Level 4: repo-specific
```

Resolution uses **additive inheritance** — lower levels add requirements, never remove them.

### Compliance Checks

Constitution compliance is automatically checked at:
- Phase PR creation (informational)
- Promotion PR creation (can be hard gate per constitution)

## Cross-Initiative Sensing

Sensing detects overlapping initiatives at lifecycle gates:

| Overlap Type | Conflict Level |
|-------------|---------------|
| Same feature | 🔴 High |
| Same service | 🟡 Medium |
| Same domain | 🟢 Low |

Sensing runs automatically at `/new-*` (pre-creation) and `/promote` (pre-PR). Available on-demand via `/sense`. Default gate mode is informational; constitution can upgrade to hard gate.
