---
name: lens-map-audit
description: Audits LENS/BMAD knowledge maps. Use when the user requests 'lens map audit', 'audit topology map', or 'validate Lens ledgers'.
---

# Lens Map Audit

## Overview

Use `vscode_askQuestions` for all follow-up questions that require user input. If the tool is unavailable, stop and present the exact question instead of guessing.

This skill validates LENS/BMAD feature archives and living ledgers against the Lens Two-Tree knowledge model. Act as a topology governance reviewer: distinguish blocking inconsistencies from advisory cleanup, protect authored truth from generated projections, and produce a report that can guide a projection rebuild or downstream reporting snapshot.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, `{project-root}/_bmad/config.toml`, and `{project-root}/_bmad/config.user.toml`, checking both root values and the `lens` or `modules.lens` section. If config is missing, let the user know `lens-setup` can configure Lens at any time. Use these defaults:

- `work_intake_path`: `{project-root}/docs/features`
- `feature_archive_path`: `{project-root}/docs/features`
- `landscape_root`: `{project-root}/docs`
- `reporting_output_path`: `{project-root}/_bmad-output/lens`
- `freshness_threshold_hours`: `24`
- `lens_mode`: `auto`

Support interactive, yolo, and headless use. In headless mode, infer paths from config/defaults, write the report, and return compact JSON with `status`, `report_path`, `blocking_count`, `advisory_count`, and `projection_rebuild_ready`.

## Source Model

Audit Markdown and YAML-bearing artifacts under the work intake path, feature archive, and landscape root. Treat frontmatter as canonical when present. Use the shared metadata contract at `{project-root}/skills/lens-setup/assets/metadata-schema.md` when available. Recognize these metadata keys when available: `stable_id`, `entity_type`, `title`, `work_id`, `belongs_to`, `status`, `publication_state`, `lifecycle_stage`, `updated_at`, `source_feature`, `related_to`, `extends`, `promotion_status`, `salmon_upstream`, `links`, `replaces`, `lens_feature_id`, `lens_track`, `lens_phase`, `lens_docs_path`, `lens_constitution_root`, `lens_feature_yaml_path`, `lens_constitution_status`, and `lens_preflight_status`.

The living tree is the service/domain/program ledger structure, typically `{project-root}/docs/<program>/<domain>/<service>/ledger/` or a shallower landscape path. The work/feature tree is `{work_intake_path}/<work-id>/` or `{feature_archive_path}/<feature-id>/` and remains the permanent historical record. Derived governance maps are projections and must not be treated as authored truth.

## Audit Lens

Classify findings as:

- **Blocking:** duplicate published `stable_id`, missing required metadata on published governed entities, broken `belongs_to` references, cycles in parentage, parent/entity type mismatches, broken local links, completed published features whose required ledger target cannot be resolved, blocked Lens preflight or constitution status, or contradictions that would make a projection rebuild unsafe.
- **Advisory:** draft parent gaps, stale `updated_at` values beyond `freshness_threshold_hours`, incomplete optional metadata, completed-but-unpromoted feature knowledge with an otherwise clear target, absent `source_feature` breadcrumbs, Salmon signals that need review, or report formatting issues that do not change the map.

Use "unknown" instead of guessing when metadata is absent. Do not fabricate parentage or stable IDs to make the map look complete.

## Workflow

First identify the audit scope and whether the user wants Markdown only or an HTML-capable report. If a previous Lens audit exists in `reporting_output_path`, use it only as comparison context; re-read current source artifacts before judging.

If Lens context is present, read the latest Lens preflight output or run `lens-preflight` before relying on constitution-root, lifecycle, or constitution status. Treat Lens wrapper-provided constitution status as an input signal; do not resolve constitutions or update constitution data inside map audit.

Inventory governed entities by stable ID, file path, entity type, status, publication state, parent reference, lifecycle stage, and outbound links. Build an in-memory parent graph from `belongs_to`, then check duplicate IDs, missing parents, orphaned nodes, cycles, invalid local links, and source feature references. Separately scan completed work archives and feature archives for promotion signals and stale living ledgers for freshness warnings. Draft artifacts may be audited but must be excluded from published projection readiness unless the user explicitly requests a draft-inclusive preview.

Produce `{reporting_output_path}/map-audit-{date}.md`. If HTML-capable output is requested, write Markdown that can be rendered directly: stable headings, tables, anchors, severity badges as text, and no source write-backs. Include a fenced `json` summary block for Lens UI ingestion.

## Report Contract

The report must include:

- Scope, source paths, timestamp, and config values used
- Executive verdict: `PASS`, `PASS_WITH_ADVISORIES`, or `BLOCKED`
- Projection rebuild readiness with the exact blocking reasons when false
- Blocking findings table with stable ID, path, problem, impact, and recommended fix
- Advisory findings table with the same fields
- Entity inventory grouped by program, domain, service, feature, and unknown
- Completed-but-unpromoted feature list
- Broken link and orphan appendix
- Machine-readable summary block:

```json
{
  "module": "lens",
  "report_type": "map_audit",
  "blocking_count": 0,
  "advisory_count": 0,
  "projection_rebuild_ready": true,
  "lens_context_present": false,
  "drafts_included": false
}
```

## Safety Rules

This workflow is read-only. Never edit feature archives, ledgers, generated projections, or config files. If the audit reveals an obvious fix, describe the patch in the report instead of applying it.

Never write Lens constitution or lifecycle authority state. Feature metadata and lifecycle transitions belong to the owning local workflows, not Lens map audit.

