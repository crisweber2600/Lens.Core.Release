# LENS Workbench Module — v4.0.0

**Module Code:** `lens-work`
**Type:** Standalone BMAD Module
**Schema Version:** 4

## Overview

LENS Workbench v4 is a skills-first control-repo module for feature-first planning and delivery. The `@lens` agent is now a thin entry shell that routes users into real Lens skills for setup, help, next-step routing, planning conductors, governance, and execution handoff.

## Design Principles

- **Git is the only source of truth** — no secondary state stores, no git-ignored runtime state
- **Reviewed artifacts and PRs gate progression** — phase handoff and lifecycle advancement happen through explicit review boundaries
- **Authority domains are explicit** — every file belongs to exactly one domain
- **Sensing is automatic** — cross-initiative awareness is checked at initialization and lifecycle review gates
- **Declarative contracts plus focused tooling** — lifecycle behavior stays in YAML, with scripts limited to focused install/bootstrap/PR helpers

## Module Structure

```
lens-work/
├── bmadconfig.yaml        # Source defaults for installed Lens configuration
├── lifecycle.yaml         # Lifecycle contract and gate semantics
├── module.yaml            # Module identity, skills, prompts, installers, adapters
├── module-help.csv        # Help and discovery registry
├── agents/                # Thin-shell Lens agent definitions
├── skills/                # Active bmad-lens-* skill surface
├── prompts/               # Published lens-*.prompt.md entry points
├── scripts/               # Install/bootstrap and PR helper tooling
├── docs/                  # Human-readable reference documentation
├── bmad-lens-work-setup/  # Legacy setup assets retained for compatibility
├── _module-installer/     # CI/CD adapter generator
├── .claude-plugin/        # Distribution manifest
└── tests/                 # Focused contract and script tests
```

## Active Skill Surface

- **Planning conductors** — `preplan`, `businessplan`, `techplan`, `adversarial-review`, `finalizeplan`, `expressplan`, `dev`, `complete`
- **Lifecycle utilities** — `init-feature`, `target-repo`, `next`, `batch`, `switch`, `help`, `pause-resume`, `retrospective`
- **Governance and reporting** — `constitution`, `sensing`, `audit`, `dashboard`, `approval-status`, `rollback`, `profile`
- **Setup and migration** — `setup`, `migrate`, `upgrade`, `document-project`, with `onboard` retained only as a deprecated bridge

## Scripts

PR creation and authentication use cross-platform scripts with REST API + PAT. **No `gh` CLI required.**

| Script | Purpose |
|--------|--------|
| `create-pr.py` | PR creation via GitHub REST API (no gh CLI) |
| `store-github-pat.py` | Secure PAT setup into environment variables (run outside AI chat) |

PAT resolution: `GITHUB_PAT` env var → `GH_TOKEN` env var → `profile.yaml` → URL-only fallback

## Getting Started — New Control Repo

A **control repo** is your local workspace for running LENS Workbench. The setup script bootstraps everything: it clones this release module, copies the IDE adapter, sets up your governance repo, and writes the configuration files that Lens setup and initialization prompts use.

### Step 1: Create and clone your control repo

```bash
# Create a new repo on GitHub (e.g., myproject.src), then clone it:
git clone https://github.com/your-username/myproject.src.git
cd myproject.src
```

### Step 2: Clone the release module

```bash
# macOS / Linux / Git Bash:
git clone --branch beta https://github.com/your-username/lens.core.git

# Windows PowerShell:
git clone --branch beta https://github.com/your-username/lens.core.git
```

### Step 3: Run the setup script

Run with **no arguments** to enter the interactive wizard:

```bash
uv run lens.core/_bmad/lens-work/scripts/setup-control-repo.py
```

The wizard auto-detects your GitHub username, walks you through each setting with smart defaults, and asks for confirmation before making changes.

> **For CI / scripted use**, pass `--org` to skip the wizard:
>
> ```bash
> uv run lens.core/_bmad/lens-work/scripts/setup-control-repo.py --org your-username
> ```

The setup script will:

1. **Pull latest** for `lens.core` (or clone if first run)
2. **Copy `.github/`** from the release module — installs the GitHub Copilot adapter
3. **Clone your governance repo** (auto-creates it as a private repo if `gh` CLI is available)
4. **Create output directories** — `docs/lens-work/initiatives/`, `.lens/`, and `.lens/personal/`
5. **Write `.lens/governance-setup.yaml`** — stores governance repo coordinates for preflight and initialization prompts
6. **Write `.lens/LENS_VERSION`** — version compatibility file read by preflight
7. **Update `.gitignore`** — excludes cloned repos and personal data

### Step 4: Store your GitHub PAT

> **Run this in your terminal, not in AI chat.** PATs should never be typed into a chat interface.

```bash
uv run lens.core/_bmad/lens-work/scripts/store-github-pat.py
```

### Step 5: Initialize your first scope

Open VS Code with GitHub Copilot Chat and type:

```text
/new-project
```

Use `/new-project` for the combined bootstrap flow, or run `/new-domain`, `/new-service`, and `/new-feature` individually when you want explicit control over each scaffold step.

### Step 6 (Optional): Install additional IDE adapters

GitHub Copilot is ready after setup. For other IDEs, run the module installer:

```bash
uv run lens.core/_bmad/lens-work/scripts/install.py --ide cursor   # single IDE
uv run lens.core/_bmad/lens-work/scripts/install.py --all-ides  # all supported IDEs
```

> **Full setup details:** See [`scripts/README.md`](scripts/README.md) for parameter reference, generated file documentation, re-run behavior, and troubleshooting.

---

## Installation (IDE Adapters)

The setup script above handles the initial GitHub Copilot adapter automatically. The commands below are for **adding or updating IDE adapters** after setup.

### Quick Install (default — GitHub Copilot adapter only)

```bash
uv run lens.core/_bmad/lens-work/scripts/install.py
```

### Multi-IDE Install

```bash
uv run lens.core/_bmad/lens-work/scripts/install.py --all-ides
```

### Update Existing Adapters

```bash
uv run lens.core/_bmad/lens-work/scripts/install.py --update
```

See `module.yaml` `install_questions` for configuration options (target projects path, default git provider, IDE selection).

## Quick Start

1. **Bootstrap the control repo** — run `setup-control-repo.py`
2. **Initialize scope** — use `/new-project` or the `/new-domain` + `/new-service` + `/new-feature` sequence
3. **Begin planning** — use `/preplan` or `/expressplan`
4. **Use `/next` for routing** — let Lens recommend the single best next step
5. **Use `/dashboard` and `/switch` for visibility** — review portfolio state and load a different feature context when needed

## Components

### Agent

- `LENS` — thin-shell entry agent for Lens Workbench
- Runtime source: `agents/lens.agent.md`
- Structured companion for validation and tooling: `agents/lens.agent.yaml`

### Published Surface

- Prompt entry points: `prompts/lens-*.prompt.md`
- Skill registry: `module.yaml` `skills:` entries
- Generated adapters: `_module-installer/installer.js` and `scripts/install.py`

> See `module.yaml` for the complete manifest of active skills, prompts, scripts, and adapter surfaces.


## Commands

`@lens` exposes only a compact shell menu. Use `/help` for command discovery and `/next` for the recommended next step.

Representative command surface:
`/onboard`, `/new-project`, `/new-domain`, `/new-service`, `/new-feature`, `/preplan`, `/businessplan`, `/techplan`, `/adversarial-review`, `/finalizeplan`, `/expressplan`, `/dev`, `/complete`, `/next`, `/batch`, `/switch`, `/discover`, `/constitution`, `/sensing`, `/audit`, `/approval-status`, `/rollback`, `/profile`, `/dashboard`, `/log-problem`, `/move-feature`, `/split-feature`, `/lens-upgrade`, `/document-project`

## Configuration

Configuration is carried in `bmadconfig.yaml`.

- In source, `bmadconfig.yaml` acts as the template for BMAD agent activation and module defaults.
- In installed control repos, `bmadconfig.yaml` is the runtime materialized config file.

Install-time values are sourced from `module.yaml` install questions:

| Variable | Purpose | Default |
|----------|---------|---------|
| `target-projects-path` | Where repos are cloned | `../TargetProjects` |
| `default-git-remote` | Git provider (GitHub, GitLab, Azure DevOps) | `github` |
| `ides` | IDE adapters to install | `github-copilot` |

The install-question keys use validator-friendly kebab-case. During installation, the module installer maps them into the existing runtime `bmadconfig.yaml` keys `target_projects_path` and `default_git_remote`, and derives `governance_repo_path` as `${target_projects_path}/lens/lens-governance` so new initiatives write metadata into the governance repo by default.


## Documentation

See the [docs/](docs/) folder for detailed reference:

- [Lifecycle Reference](docs/lifecycle-reference.md) — Phases, milestones, tracks
- [Lex Persona](docs/lex-persona.md) — Governance voice used by `@lens`
- [Copilot Adapter Reference](docs/copilot-adapter-reference.md) — Agent stub architecture
- [Copilot Adapter Templates](docs/copilot-adapter-templates.md) — Template patterns
- [Script Integration Summary](docs/script-integration.md) — PAT-based PR and promotion script integration notes
- [Pipeline: Source to Release](docs/pipeline-source-to-release.md) — CI/CD promotion
- [copilot-instructions.md](docs/copilot-instructions.md) — Copilot agent instructions
- [copilot-repo-instructions.md](docs/copilot-repo-instructions.md) — Repo-specific Copilot instructions

## Dependencies

- **Required:** `core` — BMAD core infrastructure (party-mode workflow, shared tasks, base agent definitions)
- **Optional:** `cis` — Creative Innovation Suite (brainstorming, design thinking, storytelling skills used during planning), `tea` — Test Engineering Academy (test design and automation skills used during implementation readiness and downstream delivery)

## Author

LENS Workbench is part of the BMad Method ecosystem. See the [BMad Method](https://github.com/bmad-code-org/BMAD-METHOD) for more information.



## Known Issues & Next Steps

- Token efficiency: Some prompts and instructions could be compressed for lower token usage.
- Menu categorization: Opportunity to group menu items by lifecycle phase for clarity.
- First-run detection: Logic could be refined for more robust onboarding.
- Sensing workflow: Prompt and step consolidation for efficiency.
- ~~Workflow validation: Deep validation and migration to step-driven execution.~~ ✅ DONE
- Dual agent representation: `.md` runtime source and `.yaml` structured companion pattern to be documented.

See [TODO.md](TODO.md) for the full checklist and next steps.

# Updated: Jul 2025
