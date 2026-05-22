# Lens.Core.Src - Source Tree Analysis

**Date:** 2026-04-15

## Overview

Lens.Core.Src has a compact parent tree and a dense module subtree. The exhaustive scan confirmed that almost all product logic lives under `_bmad/lens-work/`, while `.github/` exists as the adapter and promotion surface that must remain aligned with the module.

## Annotated Directory Structure

```text
Lens.Core.Src/
├── .github/                                  # Checked-in GitHub adapter and promotion assets
│   ├── agents/
│   │   └── bmad-agent-lens-work-lens.agent.md
│   ├── prompts/                              # 28 checked-in prompt stubs
│   ├── skills/                               # 5 thin redirect wrappers
│   ├── copilot-instructions.md
│   ├── lens-work-instructions.md
│   └── workflows/
│       └── promote-to-release.yml
├── _bmad/
│   ├── bmadconfig.yaml                           # Lens config bridge
│   └── lens-work/                            # Authoritative module source
│       ├── agents/
│       ├── assets/
│       │   ├── lens-bmad-skill-registry.json
│       │   └── templates/                    # 11 authored templates
│       ├── docs/                             # 21 embedded reference docs + this source-project bundle
│       ├── prompts/                          # 58 module prompt files
│       ├── scripts/                          # 17 top-level operational scripts
│       │   ├── tests/                        # 9 Python tests + README
│       │   ├── install.py
│       │   ├── preflight.py
│       │   ├── setup-control-repo.py
│       │   └── ...
│       ├── skills/                           # 43 skill directories
│       ├── tests/
│       │   └── contracts/                    # 8 contract markdown files
│       ├── _module-installer/
│       │   └── installer.js
│       ├── README.md
│       ├── TODO.md
│       ├── bmadconfig.yaml
│       ├── lifecycle.yaml
│       ├── module-help.csv
│       └── module.yaml
├── docs/                                     # Parent-level source-project documentation output in source repo
└── .gitignore
```

## Critical Directories

### `.github/`

**Purpose:** Release-facing adapter layer and CI/CD entry point.

**Contains:**

- Agent wrapper source
- Prompt stubs that ship in the release payload
- Thin skill redirect wrappers
- The source promotion workflow

### `_bmad/`

**Purpose:** Source root for the module and bridge configuration.

**Contains:** `_bmad/bmadconfig.yaml` plus the `lens-work` module directory.

### `_bmad/lens-work/`

**Purpose:** Core product implementation.

**Contains:** Manifests, lifecycle contract, agents, prompts, skills, scripts, templates, tests, and deep documentation.

### `_bmad/lens-work/scripts/`

**Purpose:** Operational automation.

**Contains:** install, preflight, setup-control-repo, create-pr, state derivation, artifact validation, and registry validation scripts plus their tests.

### `_bmad/lens-work/tests/contracts/`

**Purpose:** Markdown contract references that define expected behavior for topology, provider adapters, governance, sensing, and planning handoffs.

### `docs/`

**Purpose:** Parent-level documentation for the editable source project.

## Entry Points

- **Published prompt surface:** `.github/prompts/*.prompt.md`
- **Primary module manifest:** `_bmad/lens-work/module.yaml`
- **Lifecycle contract:** `_bmad/lens-work/lifecycle.yaml`
- **Primary agent implementation:** `_bmad/lens-work/agents/lens.agent.md`
- **Installer path:** `_bmad/lens-work/scripts/install.py`
- **Release-time adapter generator:** `_bmad/lens-work/_module-installer/installer.js`
- **Promotion pipeline:** `.github/workflows/promote-to-release.yml`

## File Organization Patterns

- Parent-level files describe packaging and adapter concerns.
- Module-level files under `_bmad/lens-work/` hold the real logic and contracts.
- Embedded technical documentation is concentrated under `_bmad/lens-work/docs/`.
- Operational tests are split between executable pytest files in `scripts/tests/` and reference contracts in `tests/contracts/`.
- Template assets live under `_bmad/lens-work/assets/templates/` and support planning/document-generation workflows.

## Configuration and Registry Files

- `_bmad/bmadconfig.yaml`: bridge configuration used by Lens wrapper flows.
- `_bmad/lens-work/bmadconfig.yaml`: authoritative module config template.
- `_bmad/lens-work/module.yaml`: skill, prompt, script, and dependency registry.
- `_bmad/lens-work/module-help.csv`: command/help registry.
- `_bmad/lens-work/assets/lens-bmad-skill-registry.json`: published prompt-to-skill mapping.
- `.github/workflows/promote-to-release.yml`: source-to-release build and publication definition.

## Development Notes

- The parent tree is intentionally small because the actual product is nested under `_bmad/lens-work/`.
- When deciding where to edit behavior, prefer `_bmad/lens-work/` for implementation and `.github/` only for checked-in adapter or release-surface files.
- The downstream `lens.core/` repo in the control workspace is output, not source.

---

_Generated using the BMAD `document-project` workflow pattern for the Lens.Core.Src source project._