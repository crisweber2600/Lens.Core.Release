# Lens.Core.Src - Component Inventory

**Date:** 2026-04-15

## Overview

Lens.Core.Src is composed of source assets rather than runtime services. The exhaustive scan focused on what is actually published, what is implemented, what validates the system, and what remains intentionally absent.

## Parent-Level Components

| Component Area | Count | Key Paths | Purpose |
| --- | --- | --- | --- |
| Copilot agent source | 1 file | `.github/agents/` | Checked-in GitHub Copilot agent wrapper |
| Prompt stub source | 28 files | `.github/prompts/` | Published prompt surface shipped into the release payload |
| Skill redirect wrappers | 5 folders | `.github/skills/` | Thin redirect skills for checklist, constitution, git-state, git-orchestration, and sensing |
| Source instructions | 2 files | `.github/copilot-instructions.md`, `.github/lens-work-instructions.md` | Contributor and adapter guidance |
| Release workflow | 1 file | `.github/workflows/promote-to-release.yml` | Build and release orchestration |

## Module Core Components

| Component Area | Count | Key Paths | Purpose |
| --- | --- | --- | --- |
| Config bridge | 1 file | `_bmad/bmadconfig.yaml` | Maps Lens wrapper expectations to the module |
| Module manifest | 1 file | `_bmad/lens-work/module.yaml` | Defines published skills, prompts, scripts, and metadata |
| Lifecycle contract | 1 file | `_bmad/lens-work/lifecycle.yaml` | Defines lifecycle phases, tracks, and promotion rules |
| Module config | 1 file | `_bmad/lens-work/bmadconfig.yaml` | Canonical runtime config template |
| Help registry | 1 file | `_bmad/lens-work/module-help.csv` | Command/help metadata |
| Asset registry | 1 file | `_bmad/lens-work/assets/lens-bmad-skill-registry.json` | Published prompt-to-skill mapping |

## Published Behavior Surface

### Skills

- **43** skill directories under `_bmad/lens-work/skills/`
- Includes lifecycle skills, utility skills, governance skills, and BMAD wrapper skills
- Representative examples:
  - `bmad-lens-next`
  - `bmad-lens-dashboard`
  - `bmad-lens-switch`
  - `bmad-lens-complete`
  - `bmad-lens-document-project`

### Prompts

- **28** checked-in prompt stubs under `.github/prompts/`
- **58** module prompt files under `_bmad/lens-work/prompts/`
- The `.github/` prompts are release-facing stubs; the module prompts are the authored implementation surface

### Agents

- `.github/agents/bmad-agent-lens-work-lens.agent.md` is the release-facing wrapper
- `_bmad/lens-work/agents/lens.agent.md` and `lens.agent.yaml` are the authored runtime definitions

## Automation and Validation Components

### Operational scripts

- **17** top-level script files under `_bmad/lens-work/scripts/`
- Main groups:
  - installation and adapter setup
  - control-repo bootstrap
  - PR and git/provider automation
  - lifecycle state derivation
  - artifact and registry validation

Representative scripts:

- `install.py`
- `setup-control-repo.py`
- `preflight.py`
- `create-pr.py`
- `derive-next-action.py`
- `validate-phase-artifacts.py`
- `validate-lens-bmad-registry.py`

### Executable test surface

- **9** Python test modules plus `README.md` under `_bmad/lens-work/scripts/tests/`
- Test modules present:
  - `test-adversarial-review-contracts.py`
  - `test-batch-mode-contracts.py`
  - `test-create-pr.py`
  - `test-install.py`
  - `test-phase-conductor-contracts.py`
  - `test-preflight.py`
  - `test-setup-control-repo.py`
  - `test-store-github-pat.py`
  - `test-validate-phase-artifacts.py`

### Contract reference surface

- **8** markdown contract files under `_bmad/lens-work/tests/contracts/`
- Covers branch parsing, governance, provider adapters, sensing, topology, and planning handoffs

## Documentation and Template Components

### Embedded module docs

- **21** top-level markdown docs under `_bmad/lens-work/docs/` before this shipped source-project bundle was added
- Covers architecture, source tree, lifecycle, onboarding, development, adapter reference, pipeline flow, configuration, and version notes

### Template assets

- **11** authored template files under `_bmad/lens-work/assets/templates/`
- Includes templates for architecture, PRD, epics, stories, product brief, readiness, user profile, and planning artifacts

## Packaging Components

### Installer

- `_bmad/lens-work/_module-installer/installer.js`
- Generates or refreshes IDE adapter surfaces during release packaging

### Workflow packaging

- `.github/workflows/promote-to-release.yml`
- Builds a clean BMAD install, overlays source content, validates the resulting `.github/` payload, commits to release `alpha`, and manages PR flow toward `beta`

## Components Not Present by Design

- No browser UI component library
- No HTTP controller or API route layer
- No ORM or database model layer
- No frontend state management store

These omissions are expected because the project publishes workflow assets and source packaging logic, not an interactive application runtime.

## Extension Points

- Add or modify behavior under `_bmad/lens-work/skills/` and matching prompts.
- Change release-facing adapter behavior in `.github/`.
- Adjust packaging logic in `_module-installer/installer.js` or `.github/workflows/promote-to-release.yml`.
- Extend validation with new scripts or tests under `_bmad/lens-work/scripts/` and `_bmad/lens-work/scripts/tests/`.

---

_Generated using the BMAD `document-project` workflow pattern for the Lens.Core.Src source project._