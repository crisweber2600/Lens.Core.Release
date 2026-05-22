---
name: lens-ledger-promotion
description: Promotes feature knowledge into ledgers. Use when the user requests 'lens ledger promotion', 'promote feature to ledger', or 'update living ledgers'.
---

# Lens Ledger Promotion

## Overview

Use `vscode_askQuestions` for all follow-up questions that require user input. If the tool is unavailable, stop and present the exact question instead of guessing.

This skill promotes completed LENS/BMAD feature knowledge into living service, domain, or program ledgers without erasing the permanent feature archive. Act as a knowledge steward: preserve provenance, surface conflicts before edits, and produce a promotion report that explains what moved, what stayed, and what still blocks promotion.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, `{project-root}/_bmad/config.toml`, and `{project-root}/_bmad/config.user.toml`, checking both root values and the `lens` or `modules.lens` section. If config is missing, let the user know `lens-setup` can configure Lens at any time. Use these defaults:

- `work_intake_path`: `{project-root}/docs/features`
- `feature_archive_path`: `{project-root}/docs/features`
- `landscape_root`: `{project-root}/docs`
- `reporting_output_path`: `{project-root}/_bmad-output/lens`
- `freshness_threshold_hours`: `24`
- `lens_mode`: `auto`

Support interactive and headless use. In headless mode, produce a promotion plan and report only unless the user explicitly passed an apply instruction such as `--apply`.

## Promotion Contract

The feature archive remains the immutable record of delivery history. The living ledger is the current operational truth for service/domain/program knowledge. Promotion copies or synthesizes durable knowledge from completed published features into the right ledger while preserving `source_feature` references and stable IDs.

Promotion candidates usually have `status: completed`, `status: done`, an accepted story closeout, or a completion note in `{work_intake_path}/<work-id>/` or `{feature_archive_path}/<feature-id>/`, plus `publication_state: published`. When a work archive includes `memory.md`, promote only durable decisions and completion evidence; leave open loops, discarded options, and working notes in the archive. Skip drafts, in-progress work, retired work, and already-promoted records unless the user explicitly asks for a re-promotion review.

When external Lens context fields are present, use `lens_feature_id`, `lens_track`, `lens_phase`, and `lens_docs_path` as provenance and readiness signals only. Do not update external governance records; promotion writes only to approved living ledgers under `landscape_root` when apply is explicitly approved.

## Classification

Classify findings as:

- **Blocking:** feature has no stable ID, no resolvable ledger target, conflicting parent reference, duplicate entity identity, contradiction with a newer ledger entry, unclear source of truth, blocked Lens preflight or constitution status, or missing user approval for write-back.
- **Advisory:** ledger target is clear but metadata is incomplete, promotion is overdue, source breadcrumbs are weak, or the ledger update is non-controversial but would benefit from cleanup.

When a completed feature has clear durable knowledge but no matching ledger, recommend a new ledger path using the Two-Tree topology instead of writing to an arbitrary location.

## Workflow

Start by identifying the scope: one work archive, one feature folder, all completed unpromoted work, or a specific service/domain/program ledger. If there is no recent map audit, recommend running `lens-map-audit` first; continue only when the user accepts the risk or the scope is narrow enough to verify inline.

If Lens mode is required or Lens context fields are present, require a clean `lens-preflight` result or Lens wrapper context before applying ledger edits. Missing Lens context can remain advisory for report-only promotion plans, but blocked Lens preflight or constitution status blocks apply.

Read the feature archive and target ledger before proposing edits. Compare stable IDs, parent references, current ledger content, and source feature breadcrumbs. Build a promotion plan that separates direct ledger updates, new ledger entries, deferred items, and blocked items.

For interactive runs, show the promotion plan before editing source files. For headless runs without `--apply`, do not edit source files. When applying changes, keep edits tightly scoped to ledger files under `landscape_root`; never rewrite feature archives except to add a user-approved promotion marker.

Write `{reporting_output_path}/ledger-promotion-{feature-id-or-scope}-{date}.md`.

## Report Contract

The report must include:

- Scope, selected feature archives, target ledger paths, and timestamp
- Promotion verdict: `APPLIED`, `PLANNED`, `PARTIAL`, or `BLOCKED`
- Ledger updates applied or proposed, with stable IDs and source features
- Blocking findings and advisory findings in separate tables
- Deferred items with owner/action recommendations
- Source files read and files modified, if any
- Machine-readable summary block:

```json
{
  "module": "lens",
  "report_type": "ledger_promotion",
  "scope": "",
  "applied": false,
  "blocking_count": 0,
  "advisory_count": 0,
  "files_modified": []
}
```

## Safety Rules

Do not flatten feature history into the ledger. Preserve traceability by adding `source_feature` or equivalent provenance on every promoted entry. If a ledger update would change published topology, stop and route the user to `lens-topology-design` or `lens-salmon-impact` as appropriate.

Never write directly to the Lens governance repo. If promotion requires lifecycle or governance metadata changes, route back to the appropriate Lens wrapper.

