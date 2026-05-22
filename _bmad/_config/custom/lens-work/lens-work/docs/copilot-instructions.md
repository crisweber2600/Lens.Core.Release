<!-- LENS-WORK ADAPTER -->
# LENS Workbench — Copilot Instructions

## Module Reference

This control repo uses the LENS Workbench module from the release payload:

- **Module path:** `lens.core/_bmad/lens-work/`
- **Lifecycle contract:** `lens.core/_bmad/lens-work/lifecycle.yaml`
- **Module version:** See `lens.core/_bmad/lens-work/module.yaml`

## Agent

The `@lens` agent is defined at `.github/agents/bmad-agent-lens-work-lens.agent.md` and references
the module agent at `lens.core/_bmad/lens-work/agents/lens.agent.md`.

## Skills (by path reference)

| Skill | Path |
|-------|------|
| bmad-lens-git-state | `lens.core/_bmad/lens-work/skills/bmad-lens-git-state/SKILL.md` |
| bmad-lens-git-orchestration | `lens.core/_bmad/lens-work/skills/bmad-lens-git-orchestration/SKILL.md` |
| bmad-lens-constitution | `lens.core/_bmad/lens-work/skills/bmad-lens-constitution/SKILL.md` |
| bmad-lens-sensing | `lens.core/_bmad/lens-work/skills/bmad-lens-sensing/SKILL.md` |
| bmad-lens-checklist | `lens.core/_bmad/lens-work/skills/bmad-lens-checklist/SKILL.md` |

## Important

- This adapter references module content by path — it NEVER duplicates it
- Do not copy skills, workflows, or lifecycle definitions into `.github/`
- Module updates propagate automatically through path references
<!-- /LENS-WORK ADAPTER -->
