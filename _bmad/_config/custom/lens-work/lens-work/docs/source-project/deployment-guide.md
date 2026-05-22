# Lens.Core.Src - Deployment Guide

**Date:** 2026-04-15
**Scan Level:** Exhaustive full rescan

## What "Deployment" Means Here

Lens.Core.Src does not deploy an application server. Its deployment path is source promotion into the release repository so control repos can pull the updated `lens.core` payload.

## Promotion Trigger

The release path is defined in `.github/workflows/promote-to-release.yml`.

The workflow is triggered by pushes that touch the source module and adapter surface used for release packaging:

- `_bmad/lens-work/**`
- `.github/agents/**`
- `.github/prompts/**`
- `.github/skills/**`
- `.github/workflows/promote-to-release.yml`

## Promotion Flow

1. Checkout the source repository.
2. Read the module version from `_bmad/lens-work/module.yaml`.
3. Validate the source payload for required files and disallowed executable content.
4. Prepare or repair the Lens.Core.Release working branch state.
5. Build a clean BMAD install into `build-output/`.
6. Overlay `_bmad/lens-work/` as custom module content.
7. Run `_bmad/lens-work/_module-installer/installer.js` to generate IDE adapters.
8. Overlay checked-in `.github/` source assets so authored agent, prompt, and skill stubs remain authoritative.
9. Validate the resulting `.github/` payload and registry alignment.
10. Commit the payload to release `alpha`.
11. Open or reuse the `alpha` to `beta` pull request flow.

## Release Branch Model

- `alpha` is the promotion target written by the workflow.
- `beta` is the branch the workflow targets for review via pull request.
- The workflow attempts to preserve `alpha` history and only resets from `beta` when histories diverge.

## Operational Checklist

### Before push

- Make sure changes live in `TargetProjects/lens.core/src/Lens.Core.Src`.
- Validate the specific scripts, prompts, or registries you changed.
- Confirm any checked-in `.github/` stubs stay aligned with installer expectations.
- Confirm that module manifests and published prompt/skill surfaces remain consistent.

### After push

- Wait for the promotion workflow to complete successfully.
- Pull the downstream `lens.core` repository copy in the control workspace.
- Run workspace preflight against the pulled release payload.
- Review the release PR if the workflow opened or updated one.

## Common Failure Modes

### Source/published prompt drift

The source `.github/prompts/` files are release-authoritative inputs. If the generated release output diverges from them, promotion can fail or publish stale prompt text.

### Missing required module files

The workflow checks for core module files such as `lifecycle.yaml`, `module.yaml`, `module-help.csv`, `README.md`, and `_module-installer/installer.js`.

### Disallowed executable content

The workflow rejects unexpected executable files outside the approved script and installer locations.

### Broken installer assumptions

Changes to `_module-installer/installer.js`, prompt generation, or module registration can break the packaging step even if source docs still look valid.

### Source-root validation confusion

Running preflight from the source root is not the same as validating the pulled release payload from the outer control-repo root. Use the latter for final validation.

## Verification After Promotion

From the outer control-repo root:

```bash
git -C lens.core pull
uv run ./lens.core/_bmad/lens-work/scripts/preflight.py
```

## Related References

- [../../../../.github/workflows/promote-to-release.yml](../../../../.github/workflows/promote-to-release.yml)
- [../pipeline-source-to-release.md](../pipeline-source-to-release.md)
- [../copilot-adapter-reference.md](../copilot-adapter-reference.md)
- [./contribution-guide.md](./contribution-guide.md)

---

_Generated using the BMAD `document-project` workflow pattern for the Lens.Core.Src source project._