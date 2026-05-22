# Project Overview — LENS Workbench Module (lens-work)

**Generated:** 2026-04-01 | **Scan Level:** Deep | **Module Version:** 4.0.0

---

## Executive Summary

**lens-work** is the core lifecycle orchestration module for the BMAD (Build Measure Analyze Design) platform. It provides a declarative, git-native, feature-first lifecycle system that coordinates planning, governance, and delivery through published prompts and registered Lens skills.

The module is a **CLI/Toolkit** — a command-driven BMAD module with published prompt entry points, cross-platform scripts, declarative YAML contracts, and IDE adapter integration. It is deployed into control repos and orchestrates work across governance and target project repositories.

**Key Design Philosophy:** "Git is the only source of truth. PRs are the only gating mechanism. The control repo is an operational workspace, not a code repo."

---

## Tech Stack Summary

| Category | Technology | Version | Justification |
|----------|-----------|---------|---------------|
| Meta-Framework | BMAD | v3.2 | AI agent orchestration platform |
| Contract Schema | YAML | 3.2 | Declarative lifecycle contract (`lifecycle.yaml`) |
| Scripts (Unix) | Bash | 4+ | Cross-platform operational scripts |
| Scripts (Windows) | PowerShell | 5+ | Cross-platform operational scripts |
| CI/CD Installer | Node.js | 16+ | `_module-installer/installer.js` (no npm deps) |
| Version Control | Git | 2.28+ | Single source of truth for all state |
| Primary Provider | GitHub REST API | v3 | PR creation, branch management (no `gh` CLI) |
| Secondary Provider | Azure DevOps REST API | — | Enterprise support, provider-agnostic adapter |
| Visualization | Mermaid | — | Gantt timelines, architecture diagrams |
| IDE Integration | VS Code / Copilot | — | Agent stubs, prompt files, skill references |

---

## Architecture Type Classification

- **Repository Type:** Monolith (single cohesive module)
- **Architecture Pattern:** Declarative contract-driven with skills-first prompt routing
- **State Model:** Governance `feature.yaml` and `feature-index.yaml` plus git branch and PR state
- **Agent Model:** Thin-shell `@lens` entry agent plus registered `bmad-lens-*` skills

---

## Repository Structure

```
lens-work/
├── agents/             # Thin-shell Lens agent definitions (.md + .yaml)
├── skills/             # Active bmad-lens-* skills for planning, governance, and reporting
├── prompts/            # User-facing lens-*.prompt.md entry points
├── scripts/            # Cross-platform Python operational scripts
├── docs/               # Reference and source-project documentation
├── tests/              # Focused script and contract tests
├── assets/             # Template and registry assets
├── _module-installer/  # CI/CD adapter generator (Node.js)
├── bmad-lens-work-setup/ # Legacy setup compatibility assets
├── lifecycle.yaml      # THE CONTRACT — single source of truth
├── module.yaml         # Module metadata, skill registry, prompts, adapters
├── bmadconfig.yaml     # Runtime configuration template
└── module-help.csv     # Command/help registry
```

---

## Module Dependencies

| Dependency | Type | Purpose |
|-----------|------|---------|
| `core` | Required | BMAD core infrastructure (workflow framework, skill routing, agent activation) |
| `cis` | Optional | Creative Innovation Suite (agents: Mary, Winston) |
| `tea` | Optional | Test Engineering Academy |

---

## Links to Detailed Documentation

- [Architecture](./architecture.md)
- [Understanding Your LENS Workspace](./understanding-your-workspace.md)
- [Source Tree Analysis](./source-tree-analysis.md)
- [Development Guide](./development-guide.md)
- [Lifecycle Reference](./lifecycle-reference.md) (existing)
- [Script Integration](./script-integration.md) (existing)
- [Pipeline Source to Release](./pipeline-source-to-release.md) (existing)
- [Copilot Adapter Reference](./copilot-adapter-reference.md) (existing)
