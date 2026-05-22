---
name: lens-projection-rebuild
description: Rebuilds derived Lens governance maps. Use when the user requests 'lens projection rebuild' or 'rebuild governance map'.
---

# Lens Projection Rebuild

## Overview

Use `vscode_askQuestions` for all follow-up questions that require user input. If the tool is unavailable, stop and present the exact question instead of guessing.

This skill rebuilds the derived Lens governance map from authored work, feature, service, domain, and program frontmatter. Act as a projection steward: verify doctor readiness first, write only generated artifacts, and keep authored truth in the Two-Tree source model.

## Conventions

- Bare paths (e.g. `scripts/lens_projection.py`) resolve from the skill root.
- `{skill-root}` resolves to this skill's installed directory.
- `{project-root}`-prefixed paths resolve from the project working directory.
- `{skill-name}` resolves to the skill directory's basename.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, `{project-root}/_bmad/config.toml`, and `{project-root}/_bmad/config.user.toml`, checking root values and the `lens` or `modules.lens` section. Use these defaults:

- `work_intake_path`: `{project-root}/docs/features`
- `feature_archive_path`: `{project-root}/docs/features`
- `landscape_root`: `{project-root}/docs`
- `reporting_output_path`: `{project-root}/_bmad-output/lens`
- `freshness_threshold_hours`: `24`

The shared metadata contract is `skills/lens-setup/assets/metadata-schema.md`. Draft artifacts are excluded from published projections unless the user explicitly requests `--include-drafts`.

## Deterministic Path

Run the stdlib script when local execution is available:

```bash
python {project-root}/skills/lens-projection-rebuild/scripts/lens_projection.py rebuild {project-root} --work-intake-path {work_intake_path} --feature-archive-path {feature_archive_path} --landscape-root {landscape_root} --reporting-output-path {reporting_output_path}
```

Use `--force` only when the user accepts rebuilding despite blocking doctor findings. Use `--include-drafts` only for planning previews; label those outputs as draft-inclusive.

If the script cannot run, perform the equivalent workflow directly: inventory authored frontmatter, apply the metadata contract, block unsafe rebuilds, and write the derived Markdown and JSON map only when safe or explicitly forced.

## Workflow

Run the doctor checks first. If blocking findings exist, stop unless the user explicitly accepts a forced projection. Rebuild from authored frontmatter only: work archives, feature archives, and living ledgers. Do not read an existing governance map as source truth.

Write these generated artifacts under `reporting_output_path`:

- `governance-map.json`
- `governance-map.md`

Every generated artifact must identify itself as derived, list source paths, include the doctor status, preserve blocking/advisory counts, and include `generated_at`.

## Output Contract

End with the doctor status, generated paths, entity count, blocking/advisory counts, and whether drafts were included. Include a fenced JSON summary with `module`, `report_type`, `status`, `json_path`, `markdown_path`, `entity_count`, `blocking_count`, `advisory_count`, and `include_drafts`.

## Safety Rules

Never edit work archives, feature archives, service/domain/program ledgers, or existing authored topology decisions. Generated maps are disposable projections; if they conflict with authored sources, fix the authored sources or rerun `lens-doctor` before rebuilding.
