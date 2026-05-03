---
feature: lens-dev-new-codebase-finalizeplan
doc_type: story-completion-notes
status: draft
updated_at: 2026-04-30T00:00:00Z
---

# FinalizePlan Story Completion Notes

## Confirmations

- Express track constitution permission confirmed in `TargetProjects/lens/lens-governance/constitutions/lens-dev/new-codebase/constitution.md`. Frontmatter includes `permitted_tracks: [quickplan, full, hotfix, tech-change, express, expressplan]`, and the Tracks section states the service additionally permits `express` and `expressplan`.
- Prerequisite skills/scripts confirmed present in this target worktree:
  - `_bmad/lens-work/skills/bmad-lens-adversarial-review/SKILL.md`
  - `_bmad/lens-work/skills/bmad-lens-bmad-skill/SKILL.md`
  - `_bmad/lens-work/skills/bmad-lens-git-orchestration/SKILL.md`
  - `_bmad/lens-work/scripts/validate-phase-artifacts.py`
- No governance repo or control repo docs edits were made for this implementation. The constitution was read only.

## Publish CLI Gap

`_bmad/lens-work/skills/bmad-lens-git-orchestration/scripts/git-orchestration-ops.py` currently maps `PHASE_ARTIFACTS["expressplan"]` to legacy artifact slugs: `product-brief`, `prd`, `architecture`, `epics`, `stories`, `sprint-status`, and `review-report`.

It does not directly map the hyphenated express-track outputs `business-plan.md` and `tech-plan.md`. This is an out-of-scope tracked gap for this story. Until the CLI mapping is updated, publish-to-governance may be a no-op or partial publish for express-track features unless explicit artifact overrides or compatible legacy files are present.

## Scope Notes

- FinalizePlan, ExpressPlan, and QuickPlan are implemented as conductor-only SKILL.md files.
- QuickPlan remains internal-only and has no public prompt stub.
- The `bmad-lens-bmad-skill` registered skills table and `assets/lens-bmad-skill-registry.json` now include `bmad-lens-quickplan` as an internal wrapper target.