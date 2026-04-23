---
title: 'lens-work Rewrite — 17-Command Stable Surface'
status: 'complete'
module_name: 'Lens Workbench'
module_code: 'lens'
module_description: 'Governed developer workflow orchestration module: 17 retained commands covering feature lifecycle from workspace onboarding through execution, closure, and maintenance.'
architecture: 'multi-skill — one owning skill per retained command plus shared runtime primitives'
standalone: true
expands_module: ''
skills_planned:
  # Shared Infrastructure (Epic 1)
  - bmad-lens-batch
  - bmad-lens-adversarial-review
  # Navigation (Epic 2)
  - bmad-lens-preflight
  - bmad-lens-init-feature
  - bmad-lens-switch
  - bmad-lens-next
  # Constitution (Epic 3)
  - bmad-lens-constitution
  # Planning Conductors (Epic 4)
  - bmad-lens-preplan
  - bmad-lens-businessplan
  - bmad-lens-techplan
  - bmad-lens-finalizeplan
  - bmad-lens-expressplan
  # Execution and Closure (Epic 5)
  - bmad-lens-dev
  - bmad-lens-complete
  - bmad-lens-split-feature
  - bmad-lens-discover
  - bmad-lens-upgrade
  # Internal-only runtime dependencies
  - bmad-lens-git-orchestration
  - bmad-lens-bmad-skill
  - bmad-lens-feature-yaml
config_variables:
  - governance_repo_path
  - control_repo_path
  - target_projects_path
created: '2026-04-23T00:00:00Z'
updated: '2026-04-23T00:00:00Z'
source_feature: lens-dev-new-codebase-baseline
source_docs: TargetProjects/lens/lens-governance/features/lens-dev/new-codebase/lens-dev-new-codebase-baseline/docs
---

# Module Plan — Lens Workbench (lens-work Rewrite)

## Vision

`lens-work` is the LENS Workbench command surface and lifecycle orchestration module. It governs developer workflows from initial workspace setup through feature planning, execution, and closure. The rewrite reduces the published prompt surface from 54 stubs to exactly 17 retained commands while preserving 100% of user-observable behavior, all active governance state, and the full lifecycle schema (v4).

**Who uses it:** Development teams and solo maintainers who work inside a Lens-governed monorepo. The module is the enforcement layer that keeps governance, branching, and lifecycle phase transitions consistent across teams.

**Why this matters:** The previous codebase was patched ad hoc outside the governed Lens workflow — the very workflow it is supposed to enforce. This rewrite restores process integrity by rebuilding Lens through Lens itself. It is simultaneously a brownfield cleanup and a proof-of-concept that the workflow can govern its own evolution.

**Central invariant:** Stability, not new features. Every retained command must behave identically for existing users after the rewrite. Zero schema migrations. Zero broken active features on day 1.

---

## Architecture

**Decision: Multi-skill module — one owning skill per retained command, plus shared runtime primitives.**

The module is not a single agent with capabilities. Each of the 17 public commands has its own owning skill (`bmad-lens-{command}/SKILL.md`). Behind those skills are internal-only runtime dependencies that lose their public stubs but remain required at runtime.

**Why not a single agent?**

- The 17 commands span genuinely different domains: workspace validation, governance identity, lifecycle orchestration, execution in target repos, and schema compatibility. They are not the same kind of task.
- Users invoke commands independently; there is no expectation of persistent conversational context between invocations.
- Each skill needs its own execution semantics, parity gate, and dependency chain. A monolithic agent would make per-command regression impossible.

**Why not a workflow-per-command?**

- Commands are AI-orchestrated with script delegation, not pure procedural scripts. The owning SKILL.md for each command orchestrates the AI behavior while delegating deterministic operations (file mutation, git ops, schema reads) to Python scripts.
- This matches the existing system architecture and is the correct pattern for the Lens module family.

**Three-hop command resolution chain (invariant across all 17 commands):**

```
.github/prompts/lens-{command}.prompt.md       (stub — user entry point)
  → lens.core/_bmad/lens-work/prompts/lens-{command}.prompt.md  (full prompt)
    → skills/bmad-lens-{command}/SKILL.md  (owning skill)
      → scripts/ and sub-skill delegates as needed
```

`light-preflight.py` fires at the stub level before the redirect on every invocation. Its exit-code interface is frozen and may not be altered.

### Memory Architecture

**Pattern: Shared structured-file state (no personal AI memory).**

This module does not use BMad personal memory. Lifecycle state is stored in well-defined governance files:

| State File | Owner | Purpose |
|---|---|---|
| `feature.yaml` | `bmad-lens-feature-yaml` | Canonical feature lifecycle state — phase, milestones, branches, team, dependencies |
| `feature-index.yaml` | `bmad-lens-init-feature` | Cross-feature directory — slugs, summaries, paths |
| `dev-session.yaml` | `bmad-lens-dev` | Resumable dev session state — task list, current task, branch, commit log |
| `lifecycle.yaml` | Frozen schema (v4) | Phase definitions, transition rules, blocker logic |
| `repo-inventory.yaml` | `bmad-lens-discover` | Local clone inventory synchronized from governance |
| `constitutions/` | `bmad-lens-constitution` | Org/domain/service/repo governance rules |

**Why structured files over AI memory:** All state must be readable by scripts, auditable in git history, and operable without an AI session. The governance model depends on this.

### Memory Contract

No curated AI memory files. All inter-skill communication happens through the governance files above, read and written by the Python ops scripts. Skills read current state at invocation; they never maintain session-local caches.

### Cross-Agent Patterns

**The user is the router.** Each skill is invoked independently. Skills do not call each other directly in the published surface — they call Python ops scripts, which read shared governance files.

**Conductor-to-delegate pattern (planning commands):**
- Planning conductor skills (`preplan`, `businessplan`, `techplan`, `finalizeplan`, `expressplan`) are thin orchestrators.
- They delegate to `bmad-lens-batch` for batch intake, `validate-phase-artifacts.py` for review-ready gating, `bmad-lens-bmad-skill` for BMAD generator invocations, and `bmad-lens-git-orchestration` for governance publication.
- No conductor duplicates batch, review-ready, or publish logic.

**Publish-before-author gate:**
- `businessplan`, `techplan`, `finalizeplan`, and `dev` all call `publish-to-governance --phase {prior-phase}` before beginning authoring work.
- This single entry hook is the only approved governance write path from planning phase skills.

**Exception — `discover`:**
- `discover` has an explicit auto-commit-to-main exception. It is the only skill that writes to governance-main directly, and this is documented as a governed exception.

---

## Skills

### bmad-lens-batch

**Type:** workflow (shared runtime primitive — no public stub)

**Core Outcome:** Every planning conductor handles batch intake and resume through one implementation.

**The Non-Negotiable:** Pass-1 must collect artifacts without mutation; pass-2 must resume cleanly with pre-approved context.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Pass-1 batch intake | Collects required artifacts in sequence, writes `{phase}-batch-input.md`, stops | Target phase, artifact checklist | `{phase}-batch-input.md` (no lifecycle mutation) |
| Pass-2 resume | Resumes with the batch input as pre-approved context; invokes downstream skill | `{phase}-batch-input.md` present in context | Downstream skill invoked with batch context |

**Design Notes:** Replaces copy-pasted `if mode is batch and batch_resume_context is absent...` blocks across all planning SKILL.md files. Invoked via `bmad-lens-batch --target {phase}`.

---

### bmad-lens-adversarial-review (internal)

**Type:** workflow (shared runtime primitive — no public stub)

**Core Outcome:** All planning conductors reach an identical adversarial review gate before phase completion.

**The Non-Negotiable:** Review is a mandatory lifecycle gate. Skills must not bypass it or inline their own.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Review gate | Loads constitution completion-review rules, runs adversarial review, blocks on failure | Phase artifacts, constitution `completion_review` rules | Pass/fail verdict; failure message with specific gaps |

---

### bmad-lens-preflight (WP-01)

**Type:** workflow

**Core Outcome:** User can validate workspace and onboarding state before starting or resuming any workflow.

**The Non-Negotiable:** Zero lifecycle state mutation. If preflight runs and fails, it has not changed anything.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Workspace validation | Checks repo shape, required tooling, and `bmadconfig.yaml` presence | None (reads workspace) | Pass/fail report with remediation hints |
| Onboarding check | Validates governance repo access, user profile, and target-project-path config | None | Status per check; HTML readiness report for failed state |
| `light-preflight.py` gate | Fires at stub level before any redirect; blocks non-ready workspace | Exit-code contract (frozen) | 0 = proceed, non-0 = halt with reason |

**Activation Modes:** Interactive and headless.

**Tool Dependencies:** `preflight.py`, `light-preflight.py` (exit-code contract frozen — never alter).

**Design Notes:** The public `preflight` command is the face of `bmad-lens-onboard`. The onboard skill becomes internal; preflight exposes its behavior. Consolidating them reduces the public surface without changing what the user experiences.

---

### bmad-lens-init-feature (WP-02, WP-03, WP-04)

**Type:** workflow (backing skill for `new-domain`, `new-service`, `new-feature`)

**Core Outcome:** Users can create governance domains, services, and features with canonical identity and working context.

**The Non-Negotiable:** `new-feature` is the identity root. `featureId` formula, branch topology, and governance path conventions must be frozen and test-backed before any rewrite proceeds.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| `create-domain` | Scaffolds domain path, creates constitution stub, registers in governance | Domain slug | Domain directory, `domain.yaml`, constitution scaffold |
| `create-service` | Scaffolds service under existing domain, inherits constitution rules | Domain slug, service slug | Service directory, `service.yaml` |
| `create` (new-feature) | Creates feature with `featureId`, 2-branch topology, `feature.yaml`, `feature-index.yaml` registration, optional target-repo handoff | Domain, service, feature name, track | `feature.yaml`, branches, governance entry, optional `repo-inventory.yaml` update |

**Tool Dependencies:** `init-feature-ops.py` (subcommands: `create-domain`, `create-service`, `create`), `bmad-lens-git-orchestration` (branch creation), `bmad-lens-target-repo` (optional target repo provisioning).

**Design Notes:** Three public commands route to one owning skill. The public aliases are owned in stubs. Changing the internal routing path is permitted; changing the external command name is not.

---

### bmad-lens-switch (WP-05)

**Type:** workflow

**Core Outcome:** User can switch active feature context without unintended lifecycle mutation.

**The Non-Negotiable:** Must remain read-only. Any caching or shortcut added here must not introduce git-visible state changes.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Feature context switch | Loads feature summary, constitution context, and session conventions for selected feature | Feature slug or partial match | Console confirmation of active context; no file writes |

**Tool Dependencies:** `switch-ops.py`, `feature-index.yaml`.

---

### bmad-lens-next (WP-06)

**Type:** workflow

**Core Outcome:** User receives exactly one unblocked next action for the active feature.

**The Non-Negotiable:** Single-choice output. The handoff contract into the selected downstream skill must be pre-confirmed — the user does not re-confirm after `next` routes them.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Next action routing | Reads `feature.yaml` and blocker rules; returns the single unblocked next step | Active feature context | One recommended action with routing to owning skill |

**Tool Dependencies:** `next-ops.py suggest`, `lifecycle.yaml`, `feature.yaml`.

**Design Notes:** `next` is rewritten last among navigation commands because it depends on the phase-entry contracts of every downstream command being stable first.

---

### bmad-lens-constitution (WP-15)

**Type:** workflow

**Core Outcome:** Users can resolve applicable constitutional guidance for their current operating context.

**The Non-Negotiable:** **Bug fix first.** The org-level hard-fail bug must be fixed before any planning conductor (WP-07–WP-11) begins. Partial hierarchies must be treated as valid inputs.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Constitution resolution | Merges org/domain/service/repo constitutions additively; respects `gate_mode`; tolerates missing hierarchy levels | Operating context (domain, service, feature) | Resolved constitution document |
| Partial-hierarchy tolerance | Proceeds gracefully when org-level constitution is absent (currently hard-fails — fix required) | Partial hierarchy | Valid resolved output without error |

**Tool Dependencies:** Constitution resolution ops scripts.

**Design Notes:** This skill is a shared runtime dependency called by all planning conductors. The public `constitution` command is tier 5, but the internal resolution engine must be fixed in Sprint 3 (Story 3.1) before Sprint 4 planning work can start. This is the hard prerequisite constraint in the rewrite.

---

### bmad-lens-preplan (WP-07)

**Type:** workflow

**Core Outcome:** Users can create preplan artifacts (brainstorm, research, product brief) for active features.

**The Non-Negotiable:** Rewrite as a thin conductor. All batch, review-ready, and review-gate logic must be delegated — never inlined.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Brainstorm facilitation | Invokes `bmad-brainstorming` via `bmad-lens-bmad-skill`; produces `brainstorm.md` | Feature context | `brainstorm.md` in staged docs |
| Research orchestration | Invokes domain and market research skills; produces `research.md` | Brainstorm output | `research.md` |
| Product brief authoring | Invokes `bmad-product-brief`; produces `product-brief.md` | Research output | `product-brief.md` |
| Phase completion gate | Validates review-ready state via `validate-phase-artifacts.py`; runs adversarial review via `bmad-lens-adversarial-review` | All three preplan artifacts | Pass/fail; phase-complete transition in `feature.yaml` |
| Batch mode | Delegates to `bmad-lens-batch --target preplan` for all intake and resume | Batch context flag | `preplan-batch-input.md` (pass 1), then normal flow (pass 2) |

**Tool Dependencies:** `validate-phase-artifacts.py`, `bmad-lens-batch`, `bmad-lens-adversarial-review`, `bmad-lens-bmad-skill`, `bmad-lens-constitution`, `bmad-lens-feature-yaml`.

---

### bmad-lens-businessplan (WP-08)

**Type:** workflow

**Core Outcome:** Users can create PRD and UX design artifacts for active features.

**The Non-Negotiable:** Publish reviewed preplan artifacts to governance before authoring begins. No direct governance file writes except through the publish-before-author hook.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Publish preplan artifacts | Invokes `publish-to-governance --phase preplan` at entry | Reviewed preplan artifacts | Governance publication; audit entry |
| PRD authoring | Invokes `bmad-create-prd` via `bmad-lens-bmad-skill` | Product brief, research | `prd.md` |
| UX design authoring | Invokes `bmad-create-ux-design` via `bmad-lens-bmad-skill` | PRD | `ux-design.md` |
| Phase completion gate | `validate-phase-artifacts.py` + adversarial review + phase transition | Both artifacts | Phase-complete in `feature.yaml` |
| Batch mode | `bmad-lens-batch --target businessplan` | Batch flag | Resume contract |

**Tool Dependencies:** `bmad-lens-git-orchestration` (publish hook), `bmad-lens-bmad-skill`, `bmad-lens-batch`, `bmad-lens-adversarial-review`, `bmad-lens-constitution`.

---

### bmad-lens-techplan (WP-09)

**Type:** workflow

**Core Outcome:** Users can create architecture artifacts for active features.

**The Non-Negotiable:** Architecture generator must reference `prd.md` — this is a hard `must_reference` rule enforced in the parity gate.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Publish businessplan artifacts | `publish-to-governance --phase businessplan` at entry | Reviewed businessplan artifacts | Governance publication |
| Architecture authoring | Invokes `bmad-create-architecture` via `bmad-lens-bmad-skill` with `prd.md` + `ux-design.md` as required references | PRD, UX design | `architecture.md` |
| Phase completion gate | `validate-phase-artifacts.py` + adversarial review + phase transition | `architecture.md` | Phase-complete |
| Batch mode | `bmad-lens-batch --target techplan` | Batch flag | Resume contract |

**Tool Dependencies:** `validate-phase-artifacts.py`, `bmad-lens-git-orchestration`, `bmad-lens-batch`, `bmad-lens-adversarial-review`, `bmad-lens-constitution`.

---

### bmad-lens-finalizeplan (WP-10)

**Type:** workflow

**Core Outcome:** Users can consolidate planning outputs, generate the plan bundle, and open plan/final PRs.

**The Non-Negotiable:** The 3-step contract (publish → review → commit/PR) must execute in exact order. Skipping or reordering steps invalidates the release gate.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Publish techplan artifacts | `publish-to-governance --phase techplan` at entry | Reviewed techplan artifacts | Governance publication |
| Final adversarial review | Hard-stop adversarial review gate on full planning set | All planning artifacts | Pass/fail; no bundle without passing review |
| Bundle generation | Invokes `bmad-lens-bmad-skill` to generate the planning bundle | Planning artifact set | `planning-bundle.md` or equivalent |
| Commit, push, and PR | `bmad-lens-git-orchestration` commit/push, opens plan PR and final PR | Bundle output | Two PRs in target topology; `dev-ready` milestone stamp in `feature.yaml` |
| Batch mode | `bmad-lens-batch --target finalizeplan` | Batch flag | Resume contract |

**Tool Dependencies:** `bmad-lens-git-orchestration`, `bmad-lens-adversarial-review`, `bmad-lens-bmad-skill`, `bmad-lens-feature-yaml`.

**Design Notes:** Highest dependency fan-out in the planning family. Must be built last among planning commands.

---

### bmad-lens-expressplan (WP-11)

**Type:** workflow

**Core Outcome:** Users on the express track can complete compressed planning and produce an equivalent finalizeplan bundle.

**The Non-Negotiable:** The internal `bmad-lens-quickplan` skill must be retained. Removing its prompt stub without keeping the skill causes a silent break in expressplan.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Express-track gate check | Reads `feature.yaml` `track` field; blocks if feature is not on express track | Feature context | Gate pass/fail |
| QuickPlan delegation | Delegates to `bmad-lens-quickplan` via `bmad-lens-bmad-skill` | Express-eligible feature | Compressed planning output |
| Review hard-stop | Mandatory adversarial review gate — cannot be skipped even on express track | Planning output | Pass/fail |
| Finalizeplan bundle reuse | Reuses finalizeplan bundle generation contract | Reviewed output | Same bundle format as full track |
| Batch mode | `bmad-lens-batch --target expressplan` | Batch flag | Resume contract |

**Tool Dependencies:** `bmad-lens-quickplan` (internal, no public stub), `bmad-lens-adversarial-review`, `bmad-lens-finalizeplan`, `bmad-lens-git-orchestration`.

---

### bmad-lens-dev (WP-12)

**Type:** workflow

**Core Outcome:** Users can execute governed development work in target repositories after planning completion.

**The Non-Negotiable:** All code writes must go to target repos only. Governance files (feature.yaml, etc.) may be updated via the approved ops path but never by ad hoc file edits from within the dev skill.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Publish finalizeplan artifacts | `publish-to-governance --phase finalizeplan` at entry | Reviewed plan bundle | Governance publication |
| Dev branch preparation | `bmad-lens-git-orchestration prepare-dev-branch` — creates or resumes dev branch in target repo | `feature.yaml`, target repo path | Dev branch ready |
| Constitution load | Loads and resolves constitution for target repo | Operating context | Active constitution constraints |
| Session initialization / resume | Creates or resumes `dev-session.yaml` — task list, current task, branch, commit log | Dev-ready feature state | `dev-session.yaml` |
| Task execution | AI-orchestrated implementation via subagent per task; per-task commits in target repo | Task from `dev-session.yaml` | Code changes, commit history |
| Adversarial code review | Review gate after all tasks complete | Completed implementation | Pass/fail; final PR opened on pass |

**Tool Dependencies:** `bmad-lens-git-orchestration`, `dev-session.yaml`, `bmad-lens-adversarial-review`, `bmad-lens-constitution`, `bmad-lens-feature-yaml`.

**Design Notes:** `dev` is the only skill that directly modifies target repo code. Constitution and governance files are updated only through the approved ops scripts.

---

### bmad-lens-complete (WP-13)

**Type:** workflow

**Core Outcome:** Users can close and archive a feature with retrospective and final documentation in the correct order.

**The Non-Negotiable:** Retrospective → document project → archive. The ordering is not negotiable. Archive is atomic and terminal.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Retrospective | Invokes `bmad-lens-retrospective`; produces retrospective output | Completed feature | `retrospective.md` |
| Final documentation | Invokes `bmad-lens-document-project`; produces project docs | Retrospective + implementation artifacts | `project-documentation.md` |
| Archive | Transitions `feature.yaml` to terminal archived state; removes from `feature-index.yaml` active list | Final docs complete | Feature archived; no further mutations |

**Tool Dependencies:** `bmad-lens-retrospective` (internal), `bmad-lens-document-project` (internal), `bmad-lens-feature-yaml`.

---

### bmad-lens-split-feature (WP-14)

**Type:** workflow

**Core Outcome:** Users can split an existing feature into a new first-class feature while preserving governance integrity and eligible work movement.

**The Non-Negotiable:** The three-subcommand script surface (`validate-split`, `create-split-feature`, optional `move-stories`) is load-bearing and must not be collapsed into a single opaque implementation.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| `validate-split` | Checks in-progress blockers; returns dry-run split proposal | Source feature, proposed target | Split feasibility report |
| `create-split-feature` | Creates new feature with canonical identity derived from source; creates summary stub | Validated split proposal | New `feature.yaml`, summary stub, governance registration |
| `move-stories` (optional) | Moves selected story files from source to target | Story identifiers | Updated story locations; source and target `feature.yaml` updated |

**Tool Dependencies:** `split-feature-ops.py` (subcommands: `validate-split`, `create-split-feature`, `move-stories`), `feature-index.yaml`.

---

### bmad-lens-discover (WP-16)

**Type:** workflow

**Core Outcome:** Users can synchronize the repository inventory between governance and local clones.

**The Non-Negotiable:** The governance-main auto-commit exception must be preserved. `discover` is the only approved path for direct governance-main commits. This exception is documented and intentional.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Local clone scan | Scans `target_projects_path` for cloned repos | User profile, target path | Detected repo list |
| Inventory sync | Reconciles detected repos against `repo-inventory.yaml` in governance | Detected repos | Updated `repo-inventory.yaml` |
| Auto-commit to governance-main | Commits inventory changes directly to governance-main (explicit exception) | Updated inventory | Committed governance-main diff |

**Tool Dependencies:** `repo-inventory.yaml`, user profile config.

---

### bmad-lens-upgrade (WP-17)

**Type:** workflow

**Core Outcome:** Users can invoke upgrade behavior that preserves v4 → v4 no-op compatibility while routing to the migration engine when the schema actually changes.

**The Non-Negotiable:** v4 → v4 must always be a no-op. The migration router must not fire unless schema divergence is detected.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Version detection | Reads `module.yaml` and `lifecycle.yaml` schema version | Current installation | Current vs target version |
| No-op path | Returns "already current" when v4 → v4 | Matching version | `[LENS:UPGRADE]` commit semantics with no mutation |
| Migration routing | Invokes `bmad-lens-migrate` when real schema divergence is detected | Version mismatch | Migration report |

**Tool Dependencies:** `lifecycle.yaml` migration table, `module.yaml`, `bmad-lens-migrate` (internal).

---

### bmad-lens-git-orchestration (internal)

**Type:** workflow (shared runtime primitive — no public stub)

**Core Outcome:** All branch creation, governance publication, dev branch prep, and PR operations route through one implementation.

**The Non-Negotiable:** No planning-phase skill may write to governance files directly. All governance writes go through this skill's ops script.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| `publish-to-governance` | Mirrors reviewed artifacts to governance before authoring begins | Prior phase, feature ID | Governance publication; audit entry |
| Branch creation | Creates feature and dev branches with canonical naming | Feature ID, branch type | Branches created in target/governance repos |
| `prepare-dev-branch` | Sets up dev branch in target repo for implementation | Feature context | Dev branch ready |
| Commit/push/PR | Commits artifacts, pushes, opens PRs in correct topology | Artifacts, PR template | Commits, PRs with correct labels/targets |

---

### bmad-lens-bmad-skill (internal)

**Type:** workflow (delegation router — no public stub)

**Core Outcome:** Planning conductors can invoke any BMAD generator skill without embedding the invocation details.

**The Non-Negotiable:** Wrapper prompts (`lens-bmad-*.prompt.md`) are removed from the public surface. The router skill remains. Removing the router silently breaks all planning conductors.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Generator routing | Routes to named BMAD generator skill with context | Target skill name, context | Generator output |

---

### bmad-lens-feature-yaml (internal)

**Type:** workflow (shared schema enforcement — no public stub)

**Core Outcome:** All `feature.yaml` reads and writes use one implementation. No skill performs raw YAML edits to feature state.

**The Non-Negotiable:** `feature.yaml` is the identity root. Concurrent or incorrect writes break active features. One owner.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Phase transition | Writes new phase, timestamp, and transition record | Current state, target phase | Updated `feature.yaml` |
| Milestone stamping | Writes milestone timestamps (e.g., `dev-ready`) | Milestone name | Updated `feature.yaml` |
| State read | Returns current feature state as structured object | Feature ID | Feature state |
| `feature-index.yaml` sync | Keeps index consistent with feature mutations | Feature update | Updated `feature-index.yaml` entry |

---

## Configuration

| Variable | Prompt | Default | Result Template | User Setting |
|---|---|---|---|---|
| `governance_repo_path` | Path to the local governance repository root | `./` (detected from workspace) | `governance_repo: "{value}"` | Yes |
| `control_repo_path` | Path to the local control repo (lens.core) root | `./` (auto-detected) | `control_repo: "{value}"` | Yes |
| `target_projects_path` | Root path for target project clones (used by `discover`) | `./TargetProjects` | `target_projects_path: "{value}"` | Yes |

These three paths are the minimum configuration required for `discover`, `publish-to-governance`, and branch operations. All other behavior uses paths derived from these three.

---

## External Dependencies

| Dependency | Type | Skills that need it | Setup skill handling |
|---|---|---|---|
| Python 3.12+ with `uv` | CLI tool | All script-delegating skills | Check and prompt on preflight; block if absent |
| Git 2.40+ | CLI tool | `bmad-lens-git-orchestration`, all branch operations | Check on preflight |
| GitHub CLI (`gh`) | CLI tool | PR creation in `bmad-lens-finalizeplan`, `bmad-lens-dev` | Check on preflight; provide install link if absent |

No MCP server dependencies. All external integrations are CLI-based and must be present before the first command runs.

---

## UI and Visualization

**Phase readiness HTML report** — `preflight` produces an HTML report when workspace validation fails, listing each failed check with remediation hints. This is the only structured visual output in the module. No dashboards or web apps are needed for day-1 parity.

Post-parity candidates (not in scope for this rewrite):
- Feature lifecycle dashboard showing all active features with phase and blocker state
- Sprint board view driven by `sprint-status.yaml`
- Constitution diff viewer for org/domain/service/repo merges

---

## Setup Extensions

Beyond config collection, the setup skill should:

1. **Run preflight** — verify Python, `uv`, Git, and `gh` are available; block if not.
2. **Scaffold module directory** — create `lens.core/_bmad/lens-work/` with the correct 17-command topology, `module-help.csv`, `agents/lens.agent.md`, and `lifecycle.yaml`.
3. **Validate command surface** — assert exactly 17 prompt stubs in `.github/prompts/`.
4. **Write `bmadconfig.yaml`** — with the three configured paths.

---

## Integration

**Standalone:** `lens-work` provides complete value on its own. It is the primary governance and lifecycle tool for the workspace. No parent module.

**Relation to BMad core:** Planning conductors delegate to BMad generators (`bmad-create-prd`, `bmad-create-architecture`, etc.) via `bmad-lens-bmad-skill`. If the BMad core module is not installed, planning conductors will degrade gracefully — they can operate in direct-author mode without the generator scaffolding.

---

## Creative Use Cases

- **Self-governance:** The rewrite itself is being tracked and executed through `lens-work`. Every story in this plan is a `lens-work` feature in a Lens-governed repo. The tooling is governing its own evolution.
- **Parallel feature branches:** `new-feature` + `switch` + `next` can manage many parallel features simultaneously, with `next` always routing to the single unblocked action across all of them.
- **Compressed timelines:** `expressplan` was added for small-scope features where the full 4-phase planning sequence is disproportionate. The same review and bundle contracts apply, just compressed.
- **Post-mortem branching:** `split-feature` handles scope creep gracefully — when a feature outgrows its original bounds mid-dev, the work-in-progress can be formally split rather than mutated ad hoc.

---

## Ideas Captured

*Raw synthesis from the feature planning docs — preserved for context.*

- The 54 → 17 reduction is not about removing capability; it's about removing stubs that had no owning behavior and were confusing the discovery surface.
- The three shared utility extractions (batch, validate-phase-artifacts, publish-to-governance) are the actual architecture win of this rewrite — they eliminate the category of "same bug fixed in 4 places."
- The constitution hard-fail bug is a canary: if the shared resolution engine can hard-fail on a valid partial hierarchy, then every planning conductor that calls it inherits that fragility. Fix the engine, not the callers.
- `light-preflight.py` is the most load-bearing frozen contract in the module. Its exit-code semantics must never change because every prompt stub fires it.
- The `discover` auto-commit exception is not a bug — it is the only command that writes inventory state, and it must do so directly. Every attempt to route it through `publish-to-governance` would break its semantics.
- `split-feature` was almost removed in early scope discussions because it is complex. Keeping it was the right call: it is the only safe escape valve for features that expand mid-execution without forcing a history rewrite.

---

## Build Roadmap

The sprint sequencing from `sprint-status.yaml` is the authoritative build order. It directly reflects the architectural dependency tiers.

**Sprint 1 — Shared Foundation (Stories 1.1–1.4)**
1. `bmad-lens-init-feature` stub scaffold + 17-command surface (Story 1.1)
2. `validate-phase-artifacts.py` shared utility (Story 1.2) — requires 1.1
3. `bmad-lens-batch` 2-pass contract (Story 1.3) — requires 1.1
4. `publish-to-governance` entry hook (Story 1.4) — requires 1.1

**Sprint 2 — Navigation Entry Points (Stories 2.1–2.3, 2.5)**
5. `bmad-lens-preflight` (Story 2.1)
6. `bmad-lens-init-feature` new-domain (Story 2.2)
7. `bmad-lens-init-feature` new-service (Story 2.3) — requires 2.2
8. `bmad-lens-switch` (Story 2.5) — requires 2.4

**Sprint 3 — Identity Root + Constitution Bug Fix (Stories 2.4, 2.6, 3.1)**
9. `bmad-lens-init-feature` new-feature (Story 2.4) — requires 2.2, 2.3
10. `bmad-lens-next` (Story 2.6) — requires 2.1, 2.4, 2.5
11. **`bmad-lens-constitution` bug fix** (Story 3.1) — prerequisite for all Sprint 4+ planning work

**Sprint 4 — Planning Conductors I (Stories 4.1–4.3)**
12. `bmad-lens-preplan` (Story 4.1) — requires 1.2, 1.3, 3.1
13. `bmad-lens-businessplan` (Story 4.2) — requires 1.4, 3.1, 4.1
14. `bmad-lens-techplan` (Story 4.3) — requires 1.4, 3.1, 4.2

**Sprint 5 — Planning Conductors II (Stories 4.4–4.5)**
15. `bmad-lens-finalizeplan` (Story 4.4) — requires 1.2, 1.3, 1.4, 3.1, 4.3
16. `bmad-lens-expressplan` (Story 4.5) — requires 1.3, 3.1, 4.4

**Sprint 6 — Execution and Closure (Stories 5.1–5.2, 5.4)**
17. `bmad-lens-dev` (Story 5.1)
18. `bmad-lens-complete` (Story 5.2)
19. `bmad-lens-discover` (Story 5.4)

**Sprint 7 — Split-Feature and Release Gate (Stories 5.3, 5.5)**
20. `bmad-lens-split-feature` (Story 5.3)
21. `bmad-lens-upgrade` + regression gate (Story 5.5)

**Next steps:**

1. Build each skill using **Build an Agent (BA)** or **Build a Workflow (BW)** — share this plan document as context
2. Start with **Sprint 1, Story 1.1** — invoke **Build a Workflow (BW)** for the scaffold and 17-command surface setup
3. When all skills are built, return to **Create Module (CM)** to scaffold the module infrastructure
