# Lens.Core.Src - Contribution Guide

**Date:** 2026-04-15

## Purpose

This guide summarizes the contributor rules that matter most when changing Lens.Core.Src. It is focused on source-of-truth boundaries, validation expectations, and release impact.

## Source-of-Truth Rules

- Make implementation changes in `TargetProjects/lens.core/src/Lens.Core.Src`.
- Do **not** edit `lens.core` directly. That repo is the pulled release payload.
- Treat `.github/prompts/` and `.github/skills/` as authored release-facing source, not disposable generated files.
- Keep `_bmad/lens-work/module.yaml`, prompt stubs, registries, and installer expectations consistent.

## Where to Change What

### Module behavior

Change `_bmad/lens-work/` when you are modifying lifecycle behavior, skills, prompts, contracts, templates, or scripts.

### Published adapter surface

Change `.github/` only when the release-facing GitHub Copilot surface itself must change.

### Documentation

Use the parent `docs/` folder in Lens.Core.Src for source-project guidance while authoring. Use `_bmad/lens-work/docs/` for shipped module-level technical reference material.

## Validation Expectations

Before pushing, validate the subsystem you changed.

### Good default checks

```bash
uv run _bmad/lens-work/scripts/validate-lens-bmad-registry.py
uv run --with pytest pytest _bmad/lens-work/scripts/tests/test-install.py -q
```

### For broader script changes

```bash
uv run --with pytest pytest _bmad/lens-work/scripts/tests -q
```

### After release promotion

From the outer control-repo root:

```bash
git -C lens.core pull
uv run ./lens.core/_bmad/lens-work/scripts/preflight.py
```

## Preflight Caveat

Do not rely on running `_bmad/lens-work/scripts/preflight.py` from the Lens.Core.Src root for final validation. In the current layout, that invocation resolves the wrong project root and fails looking for `TargetProjects/lens.core/_bmad/lens-work/lifecycle.yaml`. Use the outer control-repo root invocation against the pulled `lens.core` copy.

## Packaging Constraints

- Keep executable product files confined to approved script and installer locations.
- Remember that the promotion workflow overlays source `.github/` files on top of generated adapter output.
- Changes to `_module-installer/installer.js`, prompt stubs, registry files, and module manifests are coupled. Review them together.

## Review Checklist

- Does the change belong in Lens.Core.Src rather than `lens.core`?
- If a prompt or skill surface changed, are both the module and the published stub surface still aligned?
- If registry or manifest data changed, did you run the relevant validation?
- If release packaging changed, is the promotion workflow still coherent?
- If documentation changed, did you update the right doc layer: parent docs vs embedded module docs?

## Commit and Promotion Flow

1. Edit Lens.Core.Src.
2. Validate the changed surface.
3. Commit and push the source repo.
4. Wait for `.github/workflows/promote-to-release.yml` to succeed.
5. Pull the downstream `lens.core` copy.
6. Run workspace preflight.

## Related References

- [./development-guide.md](./development-guide.md)
- [./deployment-guide.md](./deployment-guide.md)
- [../development-guide.md](../development-guide.md)
- [../../../../.github/workflows/promote-to-release.yml](../../../../.github/workflows/promote-to-release.yml)

---

_Generated using the BMAD `document-project` workflow pattern for the Lens.Core.Src source project._