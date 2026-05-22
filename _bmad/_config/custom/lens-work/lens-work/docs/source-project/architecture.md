# Lens.Core.Src - Architecture

**Date:** 2026-04-15
**Type:** Monolith source project
**Architecture Pattern:** Source-authoritative module plus adapter overlay
**Scan Level:** Exhaustive full rescan

## Executive Summary

Lens.Core.Src is the authoring repository for the LENS Workbench payload. Its architecture is built around a strict separation between implementation and publication:

- `_bmad/lens-work/` contains the authoritative module implementation.
- `.github/` contains the published adapter surface and the workflow that packages the release.

The project exists to author, validate, and promote a toolkit. It does not run a service of its own.

## System Role

Lens.Core.Src sits in the middle of the control-repo lifecycle:

1. Contributors edit source in Lens.Core.Src.
2. The promotion workflow builds a clean release payload and overlays the authored source assets.
3. Lens.Core.Release receives the published payload.
4. Consuming control repos pull `lens.core/` and execute workflows from that downstream copy.

That makes Lens.Core.Src the source of truth for both behavior and packaging.

## Architectural Layers

### 1. Adapter surface

The `.github/` tree is the release-facing GitHub adapter layer.

- `agents/` exposes the Copilot agent wrapper.
- `prompts/` publishes checked-in prompt stubs.
- `skills/` publishes thin wrapper skills.
- `workflows/promote-to-release.yml` packages the release.

### 2. Module core

The `_bmad/lens-work/` tree is the real product.

- `module.yaml` defines the module surface.
- `lifecycle.yaml` defines the lifecycle contract.
- `skills/` and `prompts/` hold the user-facing behavior model.
- `scripts/` hold operational automation.
- `assets/templates/` hold planning and documentation templates.
- `docs/` hold the embedded reference library.

### 3. Configuration and registry layer

The module relies on checked-in configuration instead of mutable application state.

- `_bmad/bmadconfig.yaml` bridges Lens wrapper expectations to the module.
- `_bmad/lens-work/bmadconfig.yaml` is the authoritative config template.
- `_bmad/lens-work/module-help.csv` and `assets/lens-bmad-skill-registry.json` keep the published command surface aligned.

### 4. Packaging and promotion layer

The release workflow is part of the architecture, not just an operational add-on.

- It validates the source tree for required files and declarative-only constraints.
- It installs a fresh BMAD framework into a clean build workspace.
- It overlays `_bmad/lens-work/` as custom content.
- It runs `_module-installer/installer.js` to generate IDE adapters.
- It overlays checked-in `.github/` source assets so authored prompt and skill stubs win.
- It publishes the result into Lens.Core.Release.

## Authored Source vs Generated Output

The exhaustive scan confirmed an important distinction:

- `_bmad/lens-work/` is authored source.
- `.github/` contains authored release-facing assets that overlay generated adapter output.
- The downstream `lens.core/` repo is release output and should not be edited directly.

## State Architecture

This project intentionally avoids service-backed runtime state.

- **Authoritative state** is held in git, YAML manifests, prompt files, skill files, registry files, and documentation.
- **Workflow state** for consuming control repos is reconstructed from lifecycle files and git primitives.
- **Release state** is produced by the promotion workflow and release branch history.

There is no database schema, no ORM layer, and no API server state to document.

## Execution Model

At runtime in a consuming control repo, the flow is:

1. A user invokes a published prompt or agent.
2. The adapter surface resolves to a module prompt, skill, or workflow.
3. Module manifests and lifecycle contracts determine routing.
4. Python scripts handle install, PR, validation, preflight, and other operational work.

Lens.Core.Src itself exists to author and validate that flow before publication.

## Release Architecture

The release path is structurally important enough to treat as part of the system design.

- **Trigger surface:** `_bmad/lens-work/**`, `.github/agents/**`, `.github/prompts/**`, `.github/skills/**`, and the workflow itself.
- **Build workspace:** a clean `build-output/` BMAD install.
- **Overlay model:** source module content first, then source `.github/` assets.
- **Publication flow:** commit to release `alpha`, then open or update PR flow toward `beta`.

## Validation Strategy

Validation happens at four levels:

- Targeted pytest and script checks in `_bmad/lens-work/scripts/tests/`
- Contract references in `_bmad/lens-work/tests/contracts/`
- Registry and surface consistency checks such as `validate-lens-bmad-registry.py`
- Control-repo preflight after pulling the published downstream payload

## Design Constraints

- No executable product files outside approved script and installer locations.
- `.github/` prompt and skill stubs are release-authoritative and must remain aligned with generated output.
- Packaging logic and module registry changes are coupled and should be changed together when needed.
- Validation from the source root is not identical to validation from the outer control-repo root.

## Recommended Reading

- [../architecture.md](../architecture.md)
- [../pipeline-source-to-release.md](../pipeline-source-to-release.md)
- [../copilot-adapter-reference.md](../copilot-adapter-reference.md)
- [../lifecycle-reference.md](../lifecycle-reference.md)

---

_Generated using the BMAD `document-project` workflow pattern for the Lens.Core.Src source project._