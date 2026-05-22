# LENS Workbench — Component Inventory

This inventory summarizes the active lens-work surfaces in the editable source module.

---

## Core Contract Files

| Component | File | Purpose |
|-----------|------|---------|
| Lifecycle contract | `_bmad/lens-work/lifecycle.yaml` | Source of truth for phases, milestones, tracks, topology, and gates |
| Module manifest | `_bmad/lens-work/module.yaml` | Published prompts, skills, adapters, and installer contract |
| Help registry | `_bmad/lens-work/module-help.csv` | User-facing command metadata |
| Primary agent | `_bmad/lens-work/agents/lens.agent.md` | Main Lens runtime persona and routing instructions |
| Installer | `_bmad/lens-work/_module-installer/installer.js` | Canonical adapter generation logic |
| Standalone installer | `_bmad/lens-work/scripts/install.py` | Alternate adapter generation path |

---

## Active Planning Surface

### Phase and Review Commands

| Command | Backing Surface | Purpose |
|---------|-----------------|---------|
| `/preplan` | `skills/bmad-lens-preplan/SKILL.md` | Product brief, research, brainstorm |
| `/businessplan` | `skills/bmad-lens-businessplan/SKILL.md` | PRD and UX design |
| `/techplan` | `skills/bmad-lens-techplan/SKILL.md` | Architecture and technical design |
| `/adversarial-review` | `skills/bmad-lens-adversarial-review/SKILL.md` | Lifecycle review gate |
| `/finalizeplan` | `skills/bmad-lens-finalizeplan/SKILL.md` | Final planning bundle and PR handoff |
| `/expressplan` | `skills/bmad-lens-expressplan/SKILL.md` | Combined planning pass before FinalizePlan |
| `/dev` | `skills/bmad-lens-dev/SKILL.md` | Target-project implementation handoff |
| `/complete` | `skills/bmad-lens-complete/SKILL.md` | Retrospective, documentation gate, archival |

### Feature Utility Commands

| Command | Backing Surface | Purpose |
|---------|-----------------|---------|
| `/new-domain`, `/new-service`, `/new-feature` | init-feature family | Scope creation |
| `/new-project` | prompt plus init stack | Combined bootstrap flow |
| `/target-repo` | `skills/bmad-lens-target-repo/SKILL.md` | Repo provisioning and registration |
| `/dashboard` | `skills/bmad-lens-dashboard/SKILL.md` | Cross-feature state reporting |
| `/next` | `skills/bmad-lens-next/SKILL.md` | Next-action routing |
| `/batch` | `skills/bmad-lens-batch/SKILL.md` | Two-pass batch intake |
| `/switch` | `skills/bmad-lens-switch/SKILL.md` | Feature context switching |
| `/discover` | `skills/bmad-lens-discover/SKILL.md` | Repo inventory reconciliation |
| `/retrospective`, `/log-problem` | retrospective and problem logging skills | Feedback capture |
| `/move-feature`, `/split-feature` | move and split skills | Feature reshaping |
| `/approval-status`, `/rollback`, `/profile`, `/module-management` | operational skills | Approval, rollback, profile, and module support |

### Governance Commands

| Command | Backing Surface | Purpose |
|---------|-----------------|---------|
| `/constitution` | constitution skill | Governance resolution |
| `/sensing` | sensing skill | Cross-initiative overlap detection |
| `/audit` | audit skill | Compliance scanning |

---

## Prompt Publication Surface

The active prompt family is the published `lens-*.prompt.md` surface declared in `module.yaml`.

Representative prompts:

- `lens-preplan.prompt.md`
- `lens-businessplan.prompt.md`
- `lens-techplan.prompt.md`
- `lens-finalizeplan.prompt.md`
- `lens-expressplan.prompt.md`
- `lens-dev.prompt.md`
- `lens-complete.prompt.md`
- `lens-discover.prompt.md`
- `lens-quickplan.prompt.md`

Legacy `lens-work.*` prompt aliases are not part of the active publication surface.

---

## Generated Adapter Surfaces

| Adapter | Generated Files |
|---------|-----------------|
| GitHub Copilot | `.github/agents/`, `.github/prompts/`, `.github/skills/`, `lens-work-instructions.md` |
| Cursor | `.cursor/commands/` |
| Claude Code | `.claude/commands/` |
| Codex | `.codex/commands/`, `AGENTS.md` |
| OpenCode | `.opencode/commands/` |

All generated adapters must stay aligned with:

- `_bmad/lens-work/module.yaml`
- `_bmad/lens-work/_module-installer/installer.js`
- `_bmad/lens-work/scripts/install.py`

---

## Validation Surfaces

| Validation | File |
|------------|------|
| Installer tests | `_bmad/lens-work/scripts/tests/test-install.py` |
| Phase conductor contracts | `_bmad/lens-work/scripts/tests/test-phase-conductor-contracts.py` |
| Lens BMAD registry coverage | `_bmad/lens-work/scripts/validate-lens-bmad-registry.py` |

---

## Legacy Surfaces Retained for Reference

| Surface | Status | Notes |
|---------|--------|-------|
| `skills/bmad-lens-devproposal/` | Deprecated | Replaced by `FinalizePlan` |
| `skills/bmad-lens-sprintplan/` | Deprecated | Replaced by `FinalizePlan` |
| `skills/bmad-lens-lessons/` | Deprecated | Superseded by current memory and review workflows |

These directories remain in the source tree only to support migration context and historical lookup. They are not part of the active v4 command path.