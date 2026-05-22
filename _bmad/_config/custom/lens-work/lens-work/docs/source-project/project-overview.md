# Lens.Core.Src - Project Overview

**Date:** 2026-04-15
**Type:** CLI/toolkit source module
**Architecture:** Source-authoritative BMAD module with adapter overlay and release promotion pipeline
**Scan Level:** Exhaustive full rescan

## Executive Summary

Lens.Core.Src is the editable source project behind the LENS Workbench release payload. Contributors change the module, prompts, packaging logic, and release-facing adapter assets here. Those changes are promoted into Lens.Core.Release and later pulled into control repos as `lens.core`.

The project has two source layers:

- `.github/` is the checked-in adapter and release surface.
- `_bmad/lens-work/` is the authoritative module source.

This is not a service or UI application. It publishes lifecycle orchestration assets and operational tooling.

## Project Classification

- **Repository Type:** Monolith
- **Primary Project Type:** CLI/toolkit module
- **Core Pattern:** Declarative contract plus script-assisted orchestration
- **Primary State Model:** Git plus checked-in manifests and prompt/skill sources
- **Packaging Model:** Source tree overlay onto a clean BMAD install during release promotion

## Source Layers

### `.github/` adapter layer

The `.github/` tree is the release-facing surface for GitHub Copilot and promotion automation.

- **1** checked-in agent wrapper under `.github/agents/`
- **28** checked-in prompt stubs under `.github/prompts/`
- **5** thin skill wrapper folders under `.github/skills/`
- **1** source-of-truth release workflow under `.github/workflows/promote-to-release.yml`

These files are not a second implementation. They are a published adapter layer that points to or overlays the module content.

### `_bmad/lens-work/` module layer

The `_bmad/lens-work/` tree is the product core.

- **43** skill directories under `_bmad/lens-work/skills/`
- **58** prompt files under `_bmad/lens-work/prompts/`
- **17** top-level operational scripts under `_bmad/lens-work/scripts/`
- **9** Python test modules plus a test README under `_bmad/lens-work/scripts/tests/`
- **8** contract documents under `_bmad/lens-work/tests/contracts/`
- **11** authored templates under `_bmad/lens-work/assets/templates/`
- **21** top-level embedded markdown reference docs under `_bmad/lens-work/docs/` before this shipped source-project bundle was added

## Key Manifests and Contracts

| File | Role |
| --- | --- |
| `_bmad/bmadconfig.yaml` | Bridge config used by Lens wrapper flows |
| `_bmad/lens-work/module.yaml` | Module identity, version, published skills, prompts, scripts, and dependencies |
| `_bmad/lens-work/lifecycle.yaml` | Lifecycle contract and phase model |
| `_bmad/lens-work/bmadconfig.yaml` | Authoritative module configuration template |
| `_bmad/lens-work/module-help.csv` | Command/help registry |
| `_bmad/lens-work/assets/lens-bmad-skill-registry.json` | Published command and wrapper registry |
| `.github/workflows/promote-to-release.yml` | Source-to-release build and publication workflow |

## Technology Stack Summary

| Category | Technology | Purpose |
| --- | --- | --- |
| Contracts | YAML | Lifecycle, module, and configuration manifests |
| Knowledge assets | Markdown | Prompts, skills, docs, contract references, and templates |
| Automation | Python | Install, validation, preflight, PR, and lifecycle helper scripts |
| Packaging | Node.js | `_module-installer/installer.js` generates IDE adapter surfaces |
| CI/CD | GitHub Actions | Promotion from Lens.Core.Src to Lens.Core.Release |
| Source of truth | Git | Branch, PR, manifest, and artifact history |

## Key Capabilities

- Publishes the Lens command surface through checked-in prompt stubs and module prompts.
- Defines the `lens-work` lifecycle contract, registries, and module metadata.
- Ships installation, bootstrap, validation, PR, and preflight tooling.
- Carries a deep built-in documentation set under `_bmad/lens-work/docs/`.
- Promotes source changes through a controlled release workflow into Lens.Core.Release.

## Existing Documentation Landscape

The module already ships a full embedded doc set under `_bmad/lens-work/docs/`. This `source-project/` bundle is the shipped copy of the parent-level guide for contributors working on Lens.Core.Src itself.

## Working Rules

- Edit `TargetProjects/lens.core/src/Lens.Core.Src`, not the pulled `lens.core` payload.
- Treat `.github/prompts/` and `.github/skills/` as release-facing authored source, not disposable generated output.
- Keep `_bmad/lens-work/module.yaml`, module prompts, registry files, installer expectations, and checked-in prompt stubs aligned.
- Use targeted script validation locally, then rely on the promotion workflow and downstream preflight for end-to-end verification.

## Common Commands

From the Lens.Core.Src root:

```bash
uv run _bmad/lens-work/scripts/install.py --dry-run
uv run _bmad/lens-work/scripts/setup-control-repo.py --dry-run
uv run _bmad/lens-work/scripts/validate-lens-bmad-registry.py
uv run --with pytest pytest _bmad/lens-work/scripts/tests/test-install.py -q
```

From the outer control-repo root after promotion and downstream sync:

```bash
uv run ./lens.core/_bmad/lens-work/scripts/preflight.py
```

## Documentation Map

Start with [index.md](./index.md) for this embedded source-project bundle. Then continue into the embedded module docs through [../index.md](../index.md).

---

_Generated using the BMAD `document-project` workflow pattern for the Lens.Core.Src source project._