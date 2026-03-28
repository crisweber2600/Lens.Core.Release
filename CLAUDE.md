# LENS Workbench — Claude Code Agent

This project uses the LENS Workbench module for lifecycle routing and git orchestration.

## Module Reference

- **Module path:** `bmad.lens.release/_bmad/lens-work/`
- **Agent definition:** `bmad.lens.release/_bmad/lens-work/agents/lens.agent.md`
- **Lifecycle contract:** `bmad.lens.release/_bmad/lens-work/lifecycle.yaml`
- **Module config:** `bmad.lens.release/_bmad/lens-work/module.yaml`

## Activation

1. LOAD the module config from `bmad.lens.release/_bmad/lens-work/module.yaml`
2. LOAD the FULL agent definition from `bmad.lens.release/_bmad/lens-work/agents/lens.agent.md`
3. READ its entire contents — this contains the complete agent persona, skills, lifecycle routing, and phase-to-agent mapping
4. LOAD the lifecycle contract from `bmad.lens.release/_bmad/lens-work/lifecycle.yaml`
5. FOLLOW every activation step in the agent definition precisely

## Available Commands

See `bmad.lens.release/_bmad/lens-work/module-help.csv` for the complete command list.

## Skills (path references)

| Skill | Path |
|-------|------|
| git-state | `bmad.lens.release/_bmad/lens-work/skills/git-state.md` |
| git-orchestration | `bmad.lens.release/_bmad/lens-work/skills/git-orchestration.md` |
| constitution | `bmad.lens.release/_bmad/lens-work/skills/constitution.md` |
| sensing | `bmad.lens.release/_bmad/lens-work/skills/sensing.md` |
| checklist | `bmad.lens.release/_bmad/lens-work/skills/checklist.md` |
