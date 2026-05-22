# What's New in LENS Workbench — v2.0 to v4.0

**Date:** April 2, 2026
**Audience:** New and existing LENS users, module developers

This guide summarizes every significant change from the initial v2.0 release through the current v4.0, organized by version milestone. Use the table of contents to jump to the version you're upgrading from.

---

## Table of Contents

- [Version Timeline](#version-timeline)
- [v3.2.1 → v4.0 — Module Audit & Best-Practice Upgrade](#v321--v40--module-audit--best-practice-upgrade)
- [v2.0 → v2.x — Foundation & Hardening](#v20--v2x--foundation--hardening-mar-9-23-2026)
- [v2.x → v3.0 — Milestone Architecture](#v2x--v30--milestone-architecture-mar-31-2026)
- [v3.0 → v3.1 — Lifecycle Improvements](#v30--v31--lifecycle-improvements-apr-1-2026)
- [v3.1 → v3.2 — Express Track & Feature Mobility](#v31--v32--express-track--feature-mobility-apr-1-2026)
- [v3.2 → v3.2.1 — Quality & Documentation Hardening](#v32--v321--quality--documentation-hardening-apr-1-2026)
- [Migration Guide](#migration-guide)
- [Commit Reference](#commit-reference)

---

## Version Timeline

| Version | Schema | Date | Theme | Commits |
|---------|--------|------|-------|---------|
| **2.0** | 2 | Mar 9 | Initial release — git-native lifecycle, 5 skills, audience-based promotion | 1 |
| **2.x** | 2 | Mar 9–23 | Hardening — /dev workflow, discover, preflight, constitution enforcement, scripts | ~70 |
| **3.0** | 3 | Mar 31 | Milestone model — milestones replace audiences as promotion backbone, initiative-state.yaml, LENS_VERSION guard | ~20 |
| **3.1** | 3.1 | Apr 1 | 10 lifecycle improvements — dashboard, templates, gate collapsing, sensing, branch cleanup | 1 (batch) |
| **3.2** | 3.2 | Apr 1 | Express track, retrospective, feature mobility, onboarding docs | 2 |
| **3.2.1** | 3.2 | Apr 1 | Quality scan remediation — i18n, efficiency, docs, path correctness | 1 |
| **4.0** | 3.4 | Apr 2 | Module audit & best-practice upgrade — 125-prompt validation, 44 new stubs, CI/CD fixes | 1 |

---

## v3.2.1 → v4.0 — Module Audit & Best-Practice Upgrade

A comprehensive audit and upgrade pass that brought the module manifest, prompt inventory, adapter stubs, help registry, and CI/CD pipeline into full alignment. Every prompt path was validated end-to-end with zero broken references.

### Module Manifest

- Bumped `module.yaml` `schema_version` from 3.2 to 3.4
- Added 3 missing prompts to the `module.yaml` prompts section
- Added 18 missing `stub_prompts` to the `module.yaml` GitHub Copilot adapter

### Prompt Completeness

- Created **21 missing Lens Next prompt files** to close gaps between declared and on-disk prompts
- Created **44 missing GitHub Copilot adapter stubs** (76 total stubs now synced and validated)

### Workflow Fixes

- Standardized 5 `SKILL.md` name prefixes to `lens-work-*` for consistency
- Created missing `utility/profile/SKILL.md`
- Removed deprecated `includes/size-topology.md`
- Added **OpenCode** as a fifth IDE adapter with `.opencode/commands/` Lens command stubs

### Help Registry Fixes

- Resolved **16 menu code collisions** in `module-help.csv` (zero remaining)

### CI/CD Pipeline Fixes (`promote-to-release.yml`)

- Fixed version extraction bug
- Fixed IDE list mismatch between pipeline and module manifest
- Fixed prompt overlay deletion bug
- Fixed Output Folder `sed` bug
- Fixed `.yaml` word-boundary match
- Fixed PR body wds omission

### Validation

- Dry-run validated all **125 prompts** across the module
- Validated all **160 path references** — 0 broken
- Validated all **36 workflows** — all step chains intact

---

## v2.0 → v2.x — Foundation & Hardening (Mar 9–23, 2026)

The initial v2.0 release established the core contract-driven architecture. The rapid v2.x hardening period (70+ commits over 2 weeks) stabilized all user-facing workflows and added critical missing capabilities.

### v2.0 Baseline Capabilities

- **Lifecycle contract** (`lifecycle.yaml` schema v2) — declarative phases, audiences, tracks
- **5 skills** — git-state, git-orchestration, constitution, sensing, checklist
- **7 router workflows** — init-initiative, preplan, businessplan, techplan, devproposal, sprintplan, dev
- **6 utility workflows** — onboard, status, next, switch, help, module-management
- **3 governance workflows** — compliance-check, cross-initiative, resolve-constitution
- **13 prompts** — one per user-facing command
- **4 cross-platform scripts** — install, create-pr, setup-control-repo, store-github-pat
- **4 IDE adapters** — github-copilot, cursor, claude, codex
- **Audience-based promotion** — small → medium → large → base
- **4 tracks** — full, feature, tech-change, hotfix

### New Features Added in v2.x

#### /dev Workflow — Epic-Level Implementation Loop
*Commits: `fa9e54f`, `e978e57`, `45478bd`, `e0ef6d8`, `e752885`, `685c5a5`, `ad6c971`*

The `/dev` command was skeletal in v2.0. The v2.x series fleshed it out into a complete implementation orchestration system:

- Epic-level branching with per-story sub-branches in target repos
- Target repo validation before dev phase begins
- Enforced target-repo-only writes (no control repo modifications during dev)
- PR merge-wait gates — agent stops until story PR is merged before proceeding
- Auto-push and epic PR creation after all stories in an epic are merged
- Story chaining with per-epic stops

#### /discover Workflow — Repository Intelligence
*Commits: `e27ec8a`, `c308a21`, `1debb3d`, `74894d5`, `5501297`, `6dc2aaf`*

New workflow for exploring and documenting target project repositories:

- Fetch and checkout most-recent-commit branches per repo (local + remote)
- Documentation generation routed to `Docs/{domain}/{service}/{repo}/`
- LanguageDetector, ContextGenerator, StateManager enhancements
- DiscoveryReport with prompt and module registration

#### Preflight System
*Commits: `74609e6`, `0753147`, `f67f500`, `9486c23`, `1119c25`*

- Mandatory preflight checks on all commands
- Alpha/beta channels: always-pull rule (git pull before every operation)
- Constitution caching with skip_constitution support for performance
- Shared `workflows/includes/preflight.md` include replacing embedded blocks

#### Adversarial Review Gates
*Commits: `7b99c4a`, `24dcea7`*

- Adversarial-review entry gate enforced after promotion
- Gate blocking on negative review verdict (hard stop, not advisory)

#### Promotion Fixes
*Commits: `fb23e15`, `d915a9c`, `9711827`*

- Target audience branches created from initiative root (not phase branch)
- `large → base` promotion aligned with size-topology convention
- Mandatory phase completion epilogue — PR creation required at phase end

#### Constitution Enforcement
*Commits: `3f4713b`*

- Constitution checks enforced across all lens-work workflows (previously spotty)

#### Script Improvements
*Commits: `1709af5`, `2873047`, `6a668e4`*

- Script-based PR creation and promotion checks added to lens-work
- Enterprise GitHub support with per-repo owner flags in setup scripts
- URL parse fix for dotted repo names on Windows bash

#### Router Workflow Stabilization
*Commits: `716e212`, `dbf8c57`, `f907d7a`, `4328a95`, `57ea8b6`, `def2f08`, `7aa39e3`*

- All router workflows aligned with reference implementation
- BusinessPlan batch flow completed with push+PR and artifact gate
- Phase 1 and Phase 2 routers modernized and validated

#### Other v2.x Changes

- `/next` upgraded from recommendation-only to execute-actions mode (`ba1f914`)
- `/switch` includes remote initiative branches in selection (`9c09f12`)
- Domain/service scopes skip track collection, scaffold TargetProjects folders (`359fe52`)
- Iteration renamed to initiative in branch naming (`55140ce`)
- `state.yaml` references removed — git-derived state only (`8520ae7`)
- BMAD path migration from v6.0.4 to v6.2.0 (`0a8d853`)

---

## v2.x → v3.0 — Milestone Architecture (Mar 31, 2026)

**Breaking change: schema v2 → v3.** This release replaced the audience-based promotion model with a milestone-based architecture. All existing workflows were rewritten.

### Core Architecture Change

| Concept | v2 | v3 |
|---------|----|----|
| **Promotion backbone** | Audiences (small → medium → large → base) | Milestones (techplan → devproposal → sprintplan → dev-ready → dev-complete) |
| **Branch naming** | `{root}-{audience}` | `{root}-{milestone}` |
| **State storage** | Git-derived (branch + PR only) | `initiative-state.yaml` (committed YAML) + git-derived |
| **Phase → scope mapping** | Phases mapped to audiences | Phases mapped to milestones |
| **Version guard** | None | `LENS_VERSION` file with preflight check |

### Schema v3 — Milestone Model
*Commits: `5b99e11`, `27c0d15`*

```yaml
# lifecycle.yaml v3 key changes
schema_version: 3
milestones:
  techplan:
    role: "Technical feasibility"
    phases: [preplan, businessplan, techplan]
  devproposal:
    role: "Implementation readiness"
    phases: [devproposal]
    entry_gate: adversarial-review
  sprintplan:
    role: "Sprint execution plan"
    phases: [sprintplan]
    entry_gate: stakeholder-approval
  dev-ready:
    role: "Execution baseline"
    phases: []
  dev-complete:
    role: "Execution complete"
    phases: []
    optional: true
```

### Initiative State (YAML-First)
*Commits: `a7f5930`, `60777f1`, `e9d8601`*

New committed state file (`initiative-state.yaml`) replaces pure git-derived state:

```yaml
initiative_root: foo-bar-auth
scope: feature
phase: techplan
phase_status: in-progress
milestone: techplan
track: full
artifacts:
  preplan: { status: complete, committed_at: "2026-03-31T..." }
```

Operations added to git-orchestration:
- `create-initiative-state` — scaffold initial state at init
- `update-initiative-state` — atomic updates (phase, milestone, artifacts)

### LENS_VERSION Preflight Guard
*Commit: `6fb56bb`*

- `LENS_VERSION` file written at module install
- Preflight checks version compatibility before every command
- Blocks execution if control repo version is too old for the module

### All Router Workflows Rewritten for Milestones
*Commits: `2745f4a` through `e05cc61` (Stories 2.1–2.7)*

Every router workflow updated from audience-based to milestone-based model:
- Preplan, BusinessPlan, TechPlan, DevProposal, SprintPlan
- git-orchestration updated for milestone branch operations
- SprintPlan now batch-creates all dev-story artifacts per epic

### Governance Publication
*Commits: `b518687`, `06413c1`, `e0ef675`*

- `publish-to-governance` operation added to git-orchestration
- Milestone-promotion workflow publishes artifacts to governance repo
- Sensing reads governance historical context (dual-read bootstrapping)

### /close Workflow
*Commits: `a3707e7`, `acae548`*

New router workflow for ending initiatives:
- Close with `completed`, `abandoned`, or `superseded` status
- Tombstone publication to governance for historical record
- Closed initiatives filtered from live sensing conflict detection (`b1e7de8`)

### Sensing Improvements
*Commits: `2d70f52`, `a3d5821`, `7a85135`*

- Structured sensing report with governance historical context
- Graceful downgrade when governance directory is missing
- `scan-governance-history` returns `available: true` with empty list instead of error

### /lens-upgrade Workflow
*Commits: `9e0cf05`, `31a58b5`*

- `--dry-run` flag for previewing migrations
- YAML schema migration with version detection
- Initiative-state creation for pre-v3 initiatives

### New Prompts
*Commits: `059daf1`, `23d88a0`, `007aaff`*

- `lens-work.close.prompt.md` — `/close` command
- `lens-work.module-management.prompt.md` — `/module-management` command
- `lens-work.compliance-check.prompt.md` — compliance gate trigger

### Documentation Overhaul
*Commits: `d907562`, `401d7cd`, `54ba06b`*

- All docs updated from v2 to v3.0 terminology
- Lifecycle visual guide added with Mermaid diagrams
- Lifecycle improvement roadmap documented

---

## v3.0 → v3.1 — Lifecycle Improvements (Apr 1, 2026)

**Schema change: v3 → v3.1 (backward-compatible).** Ten improvements implemented in a single batch commit. All new features are additive — no breaking changes.

*Commit: `1d18af4`*

### 1. Promote Semantics (Approval-Only)

`/promote` became strictly an approval-verification action. The happy path auto-creates PRs via `auto_advance_promote`; `/promote` confirms the merged PR and transitions the milestone.

### 2. Branch Cleanup (Squash-and-Delete)

Automatic squash-merge and deletion of source milestone branches after promotion. Reduces long-lived branch count from 5 to 2 (root + dev-ready). Initiative root and dev-ready branches are always preserved.

### 3. Hotfix-Express Track

New `hotfix-express` track with informational-only gates. Bypasses constitution gate and adversarial review. Requires explicit `permit_hotfix_express` constitution capability.

### 4. Parallel Phase Execution

Constitution-controlled parallel execution of `businessplan + techplan` within the techplan milestone. PRD must be committed first (dependency gate). All parallel phases must complete before milestone promotion.

### 5. Artifact Validation Hooks

Per-artifact structural validation at commit time. Checks required sections, word counts, cross-references. Three severities: FAIL, WARN, PASS. Constitution can override validators per domain.

### 6. Content-Aware Sensing

Sensing now compares actual artifact content (section-headers + content blocks), not just scope names. Similarity above 0.7 threshold triggers HIGH CONTENT OVERLAP. Reduces false positives from domain-level alerts.

### 7. /dashboard Command

New `/dashboard` (DB) command showing all active initiatives:
- Mermaid Gantt timeline grouped by domain/service
- Summary table: initiative, track, phase, milestone, blocking PRs, sensing alerts
- Stale PR warnings (>48h), ready-to-promote recommendations

### 8. Artifact Templates

Eight starter templates in `assets/templates/` that agents load as scaffolds:
- product-brief, prd, ux-design, architecture, epics, stories, implementation-readiness, sprint-status

### 9. Dev-Complete Milestone

Optional milestone tracking whether all planned stories are in terminal state and all epic branches are merged to develop in target repos.

### 10. Gate Collapsing (Schema)

Constitution-controlled gate collapsing to reduce PR chains for small features. Small features (≤3 stories): single PR. Medium features (≤8 stories): two PRs. Requires `collapse_gates` constitution capability.

### 6 New Constitution Capabilities

| Capability | Default | Purpose |
|-----------|---------|---------|
| `permit_hotfix_express` | false | Allow hotfix-express track |
| `enable_parallel_phases` | false | Allow parallel phase execution |
| `collapse_gates` | false | Allow gate collapsing |
| `artifact_validator_overrides` | — | Override per-artifact validation |
| `template_overrides` | — | Override artifact templates per domain |
| `content_sensing_mode` | informational | Override content sensing severity |

---

## v3.1 → v3.2 — Express Track & Feature Mobility (Apr 1, 2026)

**Schema change: v3.1 → v3.2.** This release focuses on reducing ceremony for small work, adding post-initiative learning, and enabling feature mobility across organizational structures.

*Commits: `cc57679`, `917e890`*

### Express Track & /expressplan Command

New `express` track for small features, solo work, and quick turnaround:

| Aspect | Express Track |
|--------|--------------|
| **Command** | `/expressplan` |
| **Phases** | 1 (expressplan — combines all planning) |
| **Milestone Branches** | 0 (feature branch only) |
| **PRs** | 0 |
| **Steps** | 5 (preflight → plan → review → epics-stories → dev-ready) |
| **Gate Behavior** | Uses `collapse_gates` constitution capability |
| **Auto-advance** | devproposal → sprintplan collapsed |

The express track is ideal for features where the full ceremony of separate milestone branches and PR reviews is disproportionate to the work involved.

### /retrospective Command

New post-initiative review workflow (`/retrospective`, 4 steps):

1. **Gather** — Collect initiative artifacts, timeline, sensing alerts, PR history
2. **Analyze** — What worked well, what didn't, systemic patterns
3. **Report** — Generate structured retrospective artifact
4. **Actions** — Extract actionable improvements for future initiatives

Output: `retrospective.md` committed to the initiative folder.

### /log-problem Command

New utility workflow for recording issues and friction points during active initiatives. Creates structured problem entries with context (current phase, milestone, branch state) for retrospective review.

### /move-feature Command

Reclassify a feature initiative to a different domain/service. Updates:
- Branch names (if using DSF naming)
- `initiative-state.yaml` scope references
- `features.yaml` registry entry
- Governance inventory references

### /split-feature Command

Split a feature initiative into multiple child initiatives:
- Creates new initiative branches for each child
- Copies relevant artifacts (selectively)
- Updates parent initiative state to reference children
- Maintains sensing relationships between parent and children

### Feature-Only Branch Naming

Initiatives can now use short feature-only branch names (e.g., `auth` instead of `foo-bar-auth`) when the feature name is unique across the workspace.

**`features.yaml`** (control-repo root) maps feature names to their domain/service context:

```yaml
features:
  auth:
    domain: foo
    service: bar
    initiative_root: auth
```

Sensing resolves feature-only names via this registry. This reduces cognitive overhead and simplifies branch management.

### Gate Collapsing Implementation

The v3.1 gate collapsing schema is now fully implemented:
- `collapse_gates` constitution capability controls enablement
- Express track uses collapsed gates by default
- devproposal → sprintplan auto-advance when gates are collapsed
- Milestone-promotion step-02 reads constitution for collapsing rules

### Constitution Updates

New constitution capabilities for v3.2:
- `branching_strategy` — control DSF vs feature-only naming
- `stakeholder_gate` — fine-grained stakeholder review configuration
- `collapse_gates` — now fully implemented (schema introduced in v3.1)

### Sensing Enhancements

- `features.yaml` resolution for feature-only branch names
- Feature-only names resolved to full domain/service path during overlap detection

### Onboarding Documentation

Four new documentation files for first-time users:
- **GETTING-STARTED.md** — 3-step quick start, track selection guide, key commands
- **onboarding-checklist.md** — Step-by-step with troubleshooting
- **configuration-examples.md** — Sample configs for solo dev, teams, enterprise
- **index.md** — Updated documentation hub with quick reference table

### New Files Summary (v3.2)

| Category | Files Added |
|----------|-------------|
| Workflows | `router/expressplan/` (6 files), `router/retrospective/` (6 files), `utility/log-problem/` (3 files), `utility/move-feature/` (3 files), `utility/split-feature/` (3 files) |
| Prompts | 5 new: expressplan, retrospective, log-problem, move-feature, split-feature |
| Documentation | GETTING-STARTED.md, onboarding-checklist.md, configuration-examples.md |
| Skills Updated | constitution, git-orchestration, sensing |

---

## v3.2 → v3.2.1 — Quality & Documentation Hardening (Apr 1, 2026)

A comprehensive quality scan identified 379 issues (4 critical, 62 high, 293 medium, 20 low) across the module. This patch resolves all actionable findings across 6 remediation phases. No schema changes — fully backward compatible.

### Critical & High Fixes

- **Path convention enforcement** — `{project-root}` used for `lens.core/_bmad/` paths; release module references now use `{release_repo_root}` variable (defined in `bmadconfig.yaml`, defaults to `lens.core`); `docs/` is workspace-relative
- **Path convention enforcement** — `{project-root}` used for `lens.core/_bmad/` paths; release module references now use `{release_repo_root}` variable (defined in `bmadconfig.yaml`, defaults to `lens.core`); `docs/` is workspace-relative
- **Bare `_bmad` references** — Fixed 20+ documentation references that omitted the required repo prefix (`lens.core/` or `bmad.lens.src/`)
- **Configurable release repo path** — Added `release_repo_root` to `bmadconfig.yaml`; all prompts, workflows, skills, and docs now reference `{release_repo_root}` instead of hardcoded `lens.core/`
- **Agent activation refactored** — Replaced defensive padding (caps, emoji, negation patterns) in `lens.agent.md` step 2 with direct outcome-focused language
- **Shell lint** — Fixed SC2034 (`export SKIP_CONSTITUTION` for cross-script consumption), SC2043 (shellcheck directive for intentional single-item loop), SC2168 (`local` outside function scope)

### Internationalization

- All 26 prompt files now include `communication_language` and `document_output_language` frontmatter variables, enabling non-English agent interaction

### Efficiency Improvements

- **Lifecycle caching** — Documented session cache convention for `lifecycle.yaml` reads
- **Parallel execution** — Independent reads in init-initiative step-03 can now run concurrently
- **Constitution caching** — Preflight Step 5 checks session cache before resolving
- **Check-dirty reorder** — Moved from step-04 to step-01 for earlier git state detection
- **Output contracts** — Added explicit `OUTPUT CONTRACT` sections to preflight steps
- **Batch initiative loading** — Status workflow step-03 uses `git-state.load-initiative-configs` for batch loading

### Clarity Improvements

- **Dev prompt consolidation** — 3 redundant write-scope warnings collapsed to single `WRITE-SCOPE INVARIANT` callout
- **Preflight strategy extraction** — Verbose pull strategy rationale moved to `docs/preflight-strategy.md`
- **Constitution substeps** — Deep 3-level nesting in preflight Step 5 refactored into linear substeps 5a–5d
- **Minor prompt improvements** — Enhanced discover, init-initiative, move-feature, sprintplan, expressplan, help, and lens.agent.md

### Documentation

- **Core workflow details** — `docs/architecture.md` now documents the 3 core workflows (phase-lifecycle, audience-promotion, milestone-promotion) with trigger and purpose
- **Branching strategy reference** — `docs/configuration-examples.md` now includes a branching strategy comparison table (trunk-based, pr-per-milestone, pr-per-epic)
- **Help/bmad-help distinction** — help SKILL.md now clarifies that `/help` is LENS-specific while `/bmad-help` is a cross-module meta-command
- **Governance-aware discover** — discover workflow.md documents that Step 4 accesses the governance repo via sibling clone
- **Prompt naming guide** — New `prompts/README.md` documents the `lens-work.{command}.prompt.md` naming convention and menu trigger mapping
- **Skill archetypes** — README.md documents internal delegation vs workflow skill patterns with CIS/TEA dependency descriptions
- **Deferred items backlog** — TODO.md updated with new workflows, script extraction candidates, and enhancement roadmap

### Script Extraction

Nine new Python scripts extracted from workflow markdown into standalone executables:

| Script | Source Workflow | Purpose |
|--------|---------------|---------|
| `scan-active-initiatives` | status/step-03 | Scan initiative-state.yaml files, output table/json/csv |
| `load-command-registry` | help | Parse module-help.csv, group by category, fuzzy matching |
| `derive-initiative-status` | status/step-03-derive-state | Derive milestone/phase/PR state per initiative |
| `validate-phase-artifacts` | core/phase-lifecycle/step-02 | Check required artifacts per phase from lifecycle.yaml |
| `plan-lifecycle-renames` | upgrade/step-02 | Scan v2 audience branches, build rename plan to v3 milestones |
| `validate-feature-move` | move-feature/step-01 | Validate move target, check conflicts, verify scope |
| `bootstrap-target-projects` | onboard/step-03 | Clone/verify repos from governance repo-inventory.yaml |
| `derive-next-action` | next/step-02 | Apply lifecycle decision rules, return next command or gate |
| `run-preflight-cached` | preflight | Timestamp-cached wrapper around preflight.py (TTL-based) |

### New Workflows

Five new workflow directories with full step-driven architecture, SKILL.md, and prompt files:

| Command | Menu Code | Category | Purpose |
|---------|-----------|----------|---------|
| `/approval-status` | AS | Utility | Show pending promotion PR approval state and review status |
| `/rollback-phase` | RB | Utility | Safely revert to previous milestone while preserving git history |
| `/pause-epic` | PE | Utility | Suspend in-flight epic state to initiative-state.yaml |
| `/resume-epic` | RE | Utility | Resume paused epic with re-sensing and validation |
| `/audit-all-initiatives` | AA | Governance | Aggregate compliance dashboard across all active initiatives |
| `/profile` | PF | Utility | View and edit onboarding profile settings |

### UX & Safety Enhancements

**First-Run Experience:**
- Pre-init scope explainer in `/new-initiative` — detects empty/ambiguous scope, shows domain/service/feature explanation with examples
- Config load failure diagnosis — missing fields enumerated with `/onboard` link
- LENS_VERSION mismatch — shows both versions (control repo vs release module) with `/lens-upgrade` link

**Governance Improvements:**
- Sensing soft gate — high-severity overlaps (same feature name in same service) pause with proceed/rename/abort options
- Constitution-aware track filtering — `/new-initiative` filters tracks by governance; blocked tracks marked ⛔
- Sensing advisory guidance — per-overlap action recommendations (rename, merge, adjust scope, review)

**Lifecycle Improvements:**
- `/next` preview — shows recommended action and waits for confirmation before auto-executing
- Status health indicators — stuck detection (PR open >7 days), completeness badges (phases complete: 3/5)
- Pre-sprintplan readiness summary — epic/story completeness scan warns if >20% stories are missing

**Safety Improvements:**
- Move-feature in-flight work safeguards — detects active branches, open PRs that would be orphaned
- Branch-state validation before constitution load — preflight warns of branch mismatch, offers switch
- Governance repo requirements documented in architecture.md §12

### Architecture & Integration

**Batch PR Status Queries:**
- Status workflow step-03 now collects all `{head, base}` tuples across initiatives before querying
- Single `git-orchestration.batch-query-pr-status` call replaces N sequential PR queries (previously 5 initiatives × 4 phases = 20 calls)

**Parallel Sensing + Constitution:**
- Init-initiative step-03 restructured to use `invoke_async` for concurrent sensing and constitution resolution
- Both operations are read-only and independent — parallel execution reduces latency

**Context Propagation:**
- Preflight now publishes `session.preflight_result` with `{remote_url, provider, auth_status, sync_status, timestamp}`
- Downstream workflows reference session context instead of re-deriving provider and remote info
- Formal OUTPUT CONTRACT section added to preflight.md documenting all guaranteed session variables

### New & Modified Files (v3.2.1)

| Category | Changes |
|----------|--------|
| Prompts | All 26 updated (i18n headers); `prompts/README.md` added; 6 new prompt files for new workflows |
| Workflows | 20+ updated (preflight, init-initiative, expressplan, sprintplan, discover, help, status, dashboard, move-feature, next, cross-initiative + step files); 5 router workflows updated (`inputs: []`); 6 new workflow directories (approval-status, rollback-phase, pause-epic, resume-epic, audit-all, profile) |
| Documentation | 8 updated (architecture §12 governance requirements, configuration-examples, GETTING-STARTED, onboarding-checklist, pipeline-source-to-release, copilot-repo-instructions, README); 1 added (preflight-strategy.md) |
| Agents | lens.agent.md, lens.agent.yaml updated (7 new menu items: AS, RB, PE, RE, AA, PF + config diagnostics) |
| Scripts | All scripts converted to cross-platform Python (`.py`); `promote-branch` removed (v3.4+) |
| Meta | TODO.md updated — all enhancement roadmap items tracked; module-help.csv updated (6 new entries) |

---

## Migration Guide

### v2.x → v3.0 (Breaking)

1. Run `/lens-upgrade` — migrates lifecycle.yaml schema v2 → v3
2. Existing initiatives get `initiative-state.yaml` files created automatically
3. Audience branches (`{root}-small`, `{root}-medium`, etc.) are no longer used
4. New milestone branches will be created as you progress through phases

### v3.0 → v3.1 (Non-breaking)

1. Update module version — `schema_version: 3` → `schema_version: 3.1`
2. All new features are additive and disabled-by-default
3. Enable opt-in features via constitution capabilities as needed
4. `/dashboard` available immediately with no configuration

### v3.1 → v3.2 (Non-breaking)

1. Update module version — `schema_version: 3.1` → `schema_version: 3.2`
2. New commands available immediately: `/expressplan`, `/retrospective`, `/log-problem`, `/move-feature`, `/split-feature`
3. Feature-only naming: create `features.yaml` at control-repo root when ready
4. Gate collapsing now fully functional — enable via `collapse_gates` constitution capability

### v3.2 → v3.2.1 (Non-breaking)

No migration needed. All changes are additive documentation, i18n headers, and internal quality fixes. Prompt frontmatter additions (`communication_language`, `document_output_language`) are ignored if not configured in `bmadconfig.yaml`.

---

## Commit Reference

### Version Boundary Commits

| Version | Commit | Date | Description |
|---------|--------|------|-------------|
| v2.0 | `786749b` | Mar 9 | Initial commit: lens-work module source |
| v3.0 | `5b99e11` | Mar 31 | Schema v3 lifecycle.yaml |
| v3.0 docs | `d907562` | Apr 1 | Update all docs to v3.0 |
| v3.1 | `1d18af4` | Apr 1 | v3.1 — implement all 10 lifecycle improvements |
| v3.2 | `cc57679` | Apr 1 | Express track, retrospective, feature mobility |
| v3.2.1 | `53aff78` | Apr 1 | Quality scan remediation — 65 files, 6 phases |

### Total Commits by Phase

| Phase | Commits | Key Contributors |
|-------|---------|-----------------|
| v2.0 initial | 1 | Cris Weber |
| v2.x hardening | ~70 | Cris Weber, electricm0nk (beta contributions) |
| v3.0 milestone model | ~20 | Cris Weber |
| v3.1 improvements | 3 | Cris Weber |
| v3.2 express & mobility | 2 | Cris Weber |
| v3.2.1 quality hardening | 1 | Cris Weber |
| **Total** | **~97** | |

### Stats at a Glance

| Metric | v2.0 | v3.2 |
|--------|------|------|
| Schema version | 2 | 3.2 |
| Skills | 5 | 5 |
| Workflows | 16 | 35 |
| Prompts | 13 | 32 |
| Agent menu items | ~15 | 28 |
| Tracks | 4 | 8 |
| Phases | 5 | 6 |
| Milestones | — | 5 |
| Scripts | 5 | 15 |
| IDE adapters | 4 | 5 |
| Documentation files | 5 | 22 |
| Template assets | 0 | 8 |
| Constitution capabilities | 0 | 9 |
