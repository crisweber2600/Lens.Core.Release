# Architecture — LENS Workbench Module (lens-work)

> **Current Contract Notice (v4.0):** This document reflects the default schema 4 Lens model: `FinalizePlan` replaces the old `DevProposal` plus `SprintPlan` chain, and the active feature topology is the **2-branch control-repo model**. References to milestone branches apply only to legacy migration paths that explicitly opt out of the default topology.

**Generated:** 2026-04-01 | **Scan Level:** Deep | **Module Version:** 4.0.0

---

## 1. Executive Summary

The lens-work module implements a declarative, git-native lifecycle orchestration system for AI-driven initiative management. It follows a **contract-driven architecture** where all lifecycle behavior is derived from a single YAML contract (`lifecycle.yaml`), with no hardcoded semantics anywhere in the module.

The module operates as a **stateless orchestrator**: it reads state exclusively from git primitives (branches, commits, PRs, committed YAML state files), delegates work to specialized AI agents via workflows, and uses PRs as the sole gating mechanism for lifecycle progression.

---

## 2. Design Axioms

| Axiom | Statement | Implementation |
|-------|-----------|----------------|
| A1 | Git is the only source of truth | Shared feature state lives in committed `feature.yaml` and `feature-index.yaml`, with git branches and PR state providing runtime context |
| A2 | PRs are the only gating mechanism | Plan handoff and lifecycle advancement happen through explicit PR and review boundaries; no side-channel approval |
| A3 | Authority domains must be explicit | 4 authority domains; cross-authority writes are hard errors |
| A4 | Sensing must be automatic at lifecycle gates | Runs during initialization, review gates, and governance-sensitive lifecycle checks; constitutions can harden it into a blocking gate |
| A5 | The control repo is an operational workspace | NO executable code outside `scripts/` and `_module-installer/`; all behavior declarative |

---

## 3. Core Architecture Pattern: Contract-Driven Lifecycle

### 3.1 The Lifecycle Contract

`lifecycle.yaml` (schema 4) is the single source of truth for lifecycle behavior. It defines:

- **Fundamental Truths** — non-negotiable planning and governance axioms
- **Milestones** — `techplan`, `finalizeplan`, `dev-ready`, and optional `dev-complete`
- **Phases** — `preplan`, `businessplan`, `techplan`, `finalizeplan`, plus standalone `expressplan`
- **Tracks** — `full`, `feature`, `tech-change`, `hotfix`, `hotfix-express`, `spike`, `quickdev`, `express`
- **2-branch topology** — `{featureId}` plus `{featureId}-plan` in the control repo
- **Governance publication rules** — approved docs are mirrored to governance `main` at handoff or explicit publish steps

### 3.2 Phase-to-Milestone Mapping

```text
Milestone: techplan
  Phases: preplan -> businessplan -> techplan
  Agents: Mary -> John + Sally -> Winston

Milestone: finalizeplan
  Phase: finalizeplan
  Agent: Lens
  Entry gate: adversarial-review (party mode)

Milestone: dev-ready
  No phases
  Entry gate: constitution-gate

Milestone: dev-complete (optional)
  No phases
  Entry gate: dev-complete-validation
```

### 3.3 Branch Topology — Default 2-Branch Model

```text
{featureId}        ← approved feature branch in the control repo
{featureId}-plan   ← planning drafts and review reports in the control repo
governance main    ← canonical feature state plus mirrored approved docs
```

**Key insight:** milestone progression is tracked in `feature.yaml`, not by creating milestone branches for the default topology.

### 3.3.1 Feature-Only Branch Naming (v3.2)

Initiatives may use **feature-only** naming where the branch is just `{feature}` instead of the full `{domain}-{service}-{feature}` DSF pattern. This is enabled when:
- The initiative scope is `feature` and the feature name is unique across the workspace
- The `features.yaml` registry maps the short name back to the full domain/service path

**`features.yaml`** (control-repo root) maps feature names to their domain/service context:
```yaml
features:
  auth:
    domain: foo
    service: bar
    initiative_root: auth
  payments:
    domain: billing
    service: core
    initiative_root: payments
```

Sensing resolves feature-only names via this registry during overlap detection and state derivation.

### 3.4 Promotion Flow

```text
{featureId}-plan drafts
  ↓ [phase completion + reviewed predecessor publication]
FinalizePlan review and plan PR readiness
  ↓ [plan PR: {featureId}-plan -> {featureId}]
Approved feature branch
  ↓ [final PR: {featureId} -> main]
Implementation complete
```

---

## 4. Agent Architecture

### 4.1 Primary Agent: `@lens`

The LENS Workbench agent is the single entry point for all user interaction. In v4 it operates as a **thin entry shell** that routes users into real Lens skills instead of acting as a giant workflow router.

**Dual Representation Pattern:**
- `lens.agent.md` — Runtime source (markdown, human-readable, menu-driven)
- `lens.agent.yaml` — Validator-compatible structured companion (IDE validation)

**Activation Sequence (10 steps):**
1. Load persona from the agent file
2. Attempt to load `bmadconfig.yaml`; if missing, continue in limited mode and direct the user to `/onboard`
3. Load `lifecycle.yaml` so lifecycle terms and gates stay grounded
4. Load `module-help.csv` for discovery context without expanding it into the shell menu
5. Explain that `@lens` is a thin shell and that real work is delegated to Lens skills
6. Show the compact shell menu only: Help, Next, Status, Onboard, Init Feature, Chat, Dismiss
7. Direct users to `/lens-help` for command discovery and `/lens-next` for the best next step
8. **STOP and WAIT** for user input
9. Execute only real skill files when a menu item is selected
10. If no shell entry matches, answer directly when possible or redirect to `/lens-help`

### 4.2 Skill Delegation Model

| Skill | Type | Purpose | Operations |
|-------|------|---------|------------|
| `bmad-lens-feature-yaml` | Read/Write | Canonical feature-state operations | create, read, validate, update `feature.yaml` |
| `bmad-lens-git-state` | Read-only | Branch and PR state queries for the 2-branch model | active feature, branch state, merge readiness |
| `bmad-lens-git-orchestration` | Write | Branch creation, commits, pushes, PR management | create branches, commit docs, open/update PRs |
| `bmad-lens-constitution` | Read-only | Governance resolution and compliance | resolve constitutions, explain rules, validate gates |
| `bmad-lens-sensing` | Read-only | Cross-feature overlap detection | feature overlap checks, governance-sensitive drift detection |
| `bmad-lens-help` / `bmad-lens-next` / `bmad-lens-dashboard` | User-facing | Discovery, lifecycle routing, and portfolio reporting | contextual help, next-action recommendation, dashboard reporting |

---

## 5. Command Surface Architecture

### 5.1 Active Command Path

The live v4 execution surface is:

- published `lens-*.prompt.md` entry points
- generated IDE prompt and agent stubs
- registered `bmad-lens-*` skills in `module.yaml`
- supporting scripts and references used by those skills

This keeps `@lens` intentionally small while the real behavior lives in skills that are versioned, tested, and directly invocable.

### 5.2 Publication and Installation

`module.yaml` declares the authoritative prompt, skill, and adapter surfaces. `_module-installer/installer.js` and `scripts/install.py` must publish matching `.github/agents`, `.github/prompts`, and other IDE command stubs. If those files drift, stale router behavior can be regenerated even when the source skills are correct.

### 5.3 Historical Workflow References

Some retained documentation still references the older workflow tree for migration context. In Lens.Core.Src those workflow paths are not the active runtime surface and should not be treated as executable routes.

---

## 6. Authority Domains

| Domain | Location | Owner | Operations |
|--------|----------|-------|------------|
| Domain 1 (Control Repo) | `docs/lens-work/initiatives/` | `@lens` agent | Write initiative artifacts |
| Domain 2 (Release Module) | `{release_repo_root}/lens.core/_bmad/lens-work/` | Module builder only | Read-only at runtime |
| Domain 3 (Copilot Adapter) | `.github/` | User only | Not modified during initiative work |
| Domain 4 (Governance) | `TargetProjects/lens/lens-governance/` | Governance leads only | Cross-repo PRs |

**Rule:** Cross-authority writes are hard errors, not warnings.

---

## 7. Constitutional Governance (4-Level Hierarchy)

```
lens-governance/constitutions/
├── org/constitution.md              ← Level 1: org-wide defaults
├── {domain}/constitution.md         ← Level 2: domain-specific
├── {domain}/{service}/constitution.md  ← Level 3: service-specific
└── {domain}/{service}/{repo}/constitution.md  ← Level 4: repo-specific
```

**Merge rules (additive inheritance):**
- `required_artifacts` — Union (lower levels add requirements)
- `required_gates` — Union
- `gate_mode` — Lower overrides upper (hard > informational)
- `permitted_tracks` — Intersection (lower levels can only restrict)
- `additional_review_participants` — Union

**Caching:** Two-layer cache (session + file) with branch-aware TTL (alpha: 15min, beta: 1hr, other: daily).

---

## 8. Integration Architecture

### 8.1 Provider Adapter Pattern

Scripts detect the git provider from remote URL and route API calls accordingly:

| Provider | Detection | Auth | PR API |
|----------|-----------|------|--------|
| GitHub | `github.com` in remote URL | `GITHUB_PAT` → `GH_TOKEN` → `profile.yaml` | REST API v3 |
| Azure DevOps | `dev.azure.com` in remote URL | `GH_ENTERPRISE_TOKEN` | REST API |

### 8.2 Governance Repository Integration

- **Access:** Read-only at runtime via sibling clone at `TargetProjects/lens/lens-governance`
- **Note:** Current implementation uses a local clone, NOT a git remote (no `git show governance:path`)
- **Reads:** Constitutional rules, closed initiative artifacts, governance inventory
- **Writes:** Only via governance repo PRs (not via lens-work)

### 8.3 IDE Adapter Integration (VS Code / Copilot)

Generated by `_module-installer/installer.js` at CI/CD time:
- `.github/copilot-instructions.md` — Copilot instructions
- `.github/agents/bmad-agent-lens-work-lens.agent.md` — Thin agent wrapper
- `.github/skills/**/SKILL.md` — Skill path references
- `.github/prompts/lens-*.prompt.md` — Prompt stubs

All references are by **PATH** (not duplicated content), updated on module version bump.

### 8.4 Release Pipeline

```
Source (bmad.lens.src)
    ↓ [push to master changing bmad.lens.src/lens.core/_bmad/lens-work/**]
CI/CD Pipeline (promote-to-release.yml)
    ↓ [build → overlay → package → installer.js]
Release (lens.core) alpha branch
    ↓ [auto PR]
Release beta branch
```

---

## 9. State Management

### 9.1 Feature State (`feature.yaml`)

The committed governance feature file is the canonical shared state for active Lens features. `feature-index.yaml` provides portfolio visibility, while git branches and PRs provide supporting runtime context.

```yaml
featureId: hermes-lens-plugin
domain: plugins
service: hermes
phase: businessplan-complete
track: full
milestones:
  businessplan: '2026-04-14T03:00:00Z'
  techplan: null
links:
  pull_request: null
updated: '2026-04-14T03:00:00Z'
```

### 9.2 State Derivation Rules

| Query | Source | Derivation |
|-------|--------|------------|
| Active feature | Current branch plus governance lookup | Branch or explicit feature id resolves to `feature.yaml` |
| Current phase | `feature.yaml` → `phase` | Direct read |
| Phase gate readiness | `feature.yaml` milestones plus `lifecycle.yaml` | Milestone presence and lifecycle gate rules drive routing |
| Portfolio status | `feature-index.yaml` on governance `main` | Domain and portfolio views without branch switching |
| Pause and resume state | `feature.yaml` pause fields | `paused_from`, `pause_reason`, and `paused_at` restore context |

---

## 10. Testing Strategy

### 10.1 Contract Tests (4 files)

| Test File | Skill | Test Cases | Format |
|-----------|-------|-----------|--------|
| `branch-parsing.md` | `git-state` | 20+ cases: root extraction, audience detection, phase suffix, edge cases | Table-driven markdown |
| `governance.md` | `constitution` | 4-level hierarchy merge, additive inheritance, language overlay | Specification-based |
| `provider-adapter.md` | `git-orchestration` | PR creation, branch hooks, response parsing | Interface contract |
| `sensing.md` | `sensing` | Live branch conflicts, historical context, overlap classification | Table-driven markdown |

### 10.2 Validation Points

1. **Declarative-only scan** — No forbidden executables outside `scripts/` and `_module-installer/`
2. **Required files** — `lifecycle.yaml`, `module.yaml`, etc. must exist
3. **Manifest validation** — Embedded `.github/` payload has required agents, prompts, skills
4. **Configuration validation** — `module.yaml`, `bmadconfig.yaml` well-formed

---

## 11. Configuration Management

### 11.1 Module Configuration (`module.yaml`)

```yaml
code: lens
module_version: "4.0.0"
type: standalone
global: false
lifecycle:
  file: lifecycle.yaml
  schema_version: 4
dependencies:
  - core
optional_dependencies:
  - cis
  - tea
```

### 11.2 Runtime Configuration (`bmadconfig.yaml`)

Template with `{project-root}` variable resolution:
- `target_projects_path` — Where target repos live (default: `../TargetProjects`)
- `default_git_remote` — Provider identifier (default: `github`)
- `lifecycle_contract` — Path to lifecycle.yaml
- `initiative_output_folder` — Initiative artifacts output
- `personal_output_folder` — User-specific workspace files

### 11.3 Install Questions

| Question | Default | Purpose |
|----------|---------|---------|
| `target-projects-path` | `../TargetProjects` | Where to find/create target repos |
| `default-git-remote` | `github` | Git provider selection |
| `ides` | `github-copilot` | IDE adapter targets |

---

## 12. Governance Repository Requirements

Commands and skills that resolve constitutions or read shared feature state require access to the governance repository. The governance repo is cloned into a configured path during `setup-control-repo` (default: `TargetProjects/lens/lens-governance`).

### 12.1 Governance Access by Command

| Command | Governance Access | What It Reads or Writes |
|---------|-------------------|-------------------------|
| `/new-domain`, `/new-service`, `/new-feature`, `/new-project` | Required | Constitution hierarchy, feature-index updates, and feature scaffolding |
| `/dashboard` | Read-only | `feature-index.yaml` and dashboard data sources on governance `main` |
| `/next` | Read-only | `feature.yaml` plus `lifecycle.yaml` gate rules |
| `/sensing`, `/audit` | Required | Constitution hierarchy, feature registry, and overlap policies |
| `/move-feature`, `/split-feature` | Required | Existing and target feature paths plus registry updates |
| `/pause-resume`, `/rollback`, `/complete` | Required | `feature.yaml` updates and closeout metadata |
| `/finalizeplan`, `/approval-status` | Read-only | Lifecycle contract, PR linkage, and governance metadata |
| `/profile`, `/help`, `/onboard` | None | Local config and module metadata only |

### 12.2 Failure Modes

When governance access is required but unavailable:

1. **Clone missing** — Preflight detects missing governance path → directs to `setup-control-repo`
2. **Stale clone** — Constitution may reference outdated rules → preflight warns if governance HEAD is >7 days behind remote
3. **Network offline** — Governance reads from local clone succeed; PR-based operations fail gracefully with retry guidance
