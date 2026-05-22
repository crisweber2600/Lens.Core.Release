# Lens.Core.Src - Development Guide

**Date:** 2026-04-15
**Scan Level:** Exhaustive full rescan

## Purpose

This guide is for contributors working on the source-authoritative Lens.Core.Src repository, not for consumers using the downstream `lens.core` release payload.

## Prerequisites

| Requirement | Why it matters |
| --- | --- |
| Git | Source control, release workflow triggers, and downstream sync |
| Python 3.11+ | Operational scripts and test execution |
| `uv` | Recommended script and pytest runner |
| Node.js | Required for `_module-installer/installer.js` and release packaging |
| GitHub access | Needed to push source changes and observe promotion results |

## Working Model

- Make changes in `TargetProjects/lens.core/src/Lens.Core.Src`.
- Do not patch `lens.core` directly; it is a pulled release artifact.
- If you change prompt stubs or release-facing adapter files, keep the `.github/` source tree authoritative.
- If you change module behavior, prefer `_bmad/lens-work/`.
- Keep module manifests, prompt stubs, registry files, and installer expectations aligned.

## Common Commands

Run these from the Lens.Core.Src project root unless noted otherwise.

### Local execution model

There is no long-running application process to start from this source root. Local execution is script-driven:

- run installer and bootstrap scripts in dry-run mode while iterating
- run targeted pytest files for the script or contract area you changed
- rely on the promotion workflow to validate packaging and release assembly

### Installer and setup checks

```bash
uv run _bmad/lens-work/scripts/install.py --dry-run
uv run _bmad/lens-work/scripts/setup-control-repo.py --dry-run
```

### Focused script validation

```bash
uv run --with pytest pytest _bmad/lens-work/scripts/tests/test-install.py -q
```

### Broader script test pass

```bash
uv run --with pytest pytest _bmad/lens-work/scripts/tests -q
```

### Focused contract and registry validation

```bash
uv run _bmad/lens-work/scripts/validate-lens-bmad-registry.py
uv run --with pytest pytest _bmad/lens-work/scripts/tests/test-phase-conductor-contracts.py -q
```

### Control-repo preflight after release sync

Run this from the outer control-repo workspace root after the promotion workflow succeeds and `lens.core/` has been pulled:

```bash
uv run ./lens.core/_bmad/lens-work/scripts/preflight.py
```

### Source-root preflight caveat

When you are iterating directly in `Lens.Core.Src`, the source-root form now resolves the outer control-repo root correctly:

```bash
uv run _bmad/lens-work/scripts/preflight.py
```

Use the outer control-repo root invocation against `./lens.core/...` for release/promotion validation, and use the source-root form for focused source-side checks when you are already in `Lens.Core.Src`.

## Typical Change Paths

### Add or change a skill

1. Update or add `_bmad/lens-work/skills/<skill>/SKILL.md`.
2. Register or adjust the skill entry in `_bmad/lens-work/module.yaml` if needed.
3. Add related prompt or adapter surface changes if the command becomes user-visible.
4. Validate affected scripts or prompt mappings.

### Add or change a prompt

1. Update the module prompt under `_bmad/lens-work/prompts/` if behavior changes.
2. Update the checked-in release-facing stub under `.github/prompts/` when it is part of the published payload.
3. Verify the promotion workflow and installer expectations still match.

### Add or change adapter surface files

1. Update `.github/agents/`, `.github/prompts/`, or `.github/skills/` only when the published release surface itself must change.
2. Keep the files thin and aligned with the module implementation paths.
3. Re-run registry validation and inspect the promotion workflow implications.

### Add or change a script

1. Modify the relevant file under `_bmad/lens-work/scripts/`.
2. Add or update tests under `_bmad/lens-work/scripts/tests/`.
3. Run the targeted pytest subset before pushing.

## Source-to-Release Workflow

1. Edit and validate the source tree in Lens.Core.Src.
2. Commit and push the source repo.
3. Watch `.github/workflows/promote-to-release.yml` for success.
4. Pull the downstream `lens.core/` copy in the control repo.
5. Run preflight from the workspace root.

## Contributor Constraints

- Treat source docs, prompt stubs, and skill wrappers as first-class product assets.
- Keep changes minimal and aligned with existing manifest and contract structure.
- Avoid introducing executable files outside approved script and installer locations.
- Prefer targeted validation for the exact subsystem you changed rather than relying only on broad end-to-end checks.

## Existing Deep References

- [./contribution-guide.md](./contribution-guide.md)
- [../development-guide.md](../development-guide.md)
- [../script-integration.md](../script-integration.md)
- [../preflight-strategy.md](../preflight-strategy.md)
- [../../scripts/README.md](../../scripts/README.md)

## Notes and Constraints

- Source docs and prompt stubs are part of the product surface; treat them as first-class code.
- Validation should be targeted to the area you changed rather than relying only on broad end-to-end checks.
- The parent project exists to publish a release artifact, so packaging and overlay correctness matter as much as script correctness.

---

_Generated using the BMAD `document-project` workflow pattern for the Lens.Core.Src source project._