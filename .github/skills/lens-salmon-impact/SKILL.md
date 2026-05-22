---
name: lens-salmon-impact
description: Reviews upstream Salmon impacts. Use when the user requests 'lens salmon impact', 'review upstream impact', or 'trace recursive consistency'.
---

# Lens Salmon Impact

## Overview

Use `vscode_askQuestions` for all follow-up questions that require user input. If the tool is unavailable, stop and present the exact question instead of guessing.

This skill reviews Salmon upstream-impact signals: changes discovered downstream that need to swim back through service, domain, and program knowledge. Act as a recursive consistency reviewer. Your output is an impact report that separates advisory refreshes from blocking contradictions before teams promote or publish updated truth.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, `{project-root}/_bmad/config.toml`, and `{project-root}/_bmad/config.user.toml`, checking both root values and the `lens` or `modules.lens` section. If config is missing, let the user know `lens-setup` can configure Lens at any time. Use these defaults:

- `feature_archive_path`: `{project-root}/docs/features`
- `landscape_root`: `{project-root}/docs`
- `reporting_output_path`: `{project-root}/_bmad-output/lens`
- `freshness_threshold_hours`: `24`
- `lens_mode`: `auto`

Support interactive and headless use. In headless mode, inspect explicit paths or configured defaults, write the impact report, and return JSON with `status`, `report_path`, `blocking_count`, and `advisory_count`.

## Salmon Signals

Treat any of these as an upstream-impact signal: `salmon_upstream: true`, `impact: upstream`, `upstream_impact`, `UPSTREAM IMPACT`, an explicit user request, or a feature/ledger note saying a downstream finding changes parent assumptions.

The review follows `belongs_to` from the originating artifact toward parent service, domain, and program ledgers, then walks back down through inverse references and named dependents. Inspect siblings or downstream artifacts when they are connected by `links`, `related_to`, `extends`, `replaces`, `source_feature`, shared contracts, dependencies, or reused decisions.

When Lens context fields are present, include `lens_feature_id`, `lens_track`, `lens_phase`, `lens_docs_path`, and Lens preflight or constitution status in the evidence chain. These fields help classify risk but do not authorize Lens to change Lens lifecycle or governance metadata.

## Classification

Classify findings as:

- **Blocking:** downstream evidence contradicts a published parent decision, breaks a contract or dependency statement, changes security/compliance/program commitments, invalidates a stable ID relationship, is blocked by Lens constitution or preflight status, or requires a topology change before promotion.
- **Advisory:** parent docs need refresh, examples are stale, report freshness is beyond threshold, related ledgers should add breadcrumbs, or the impact is plausible but not proven.

Be explicit about confidence. Label inferences as inferred, and keep speculative impacts out of blocking status unless the contradiction is evidence-backed.

## Workflow

Identify the origin of the Salmon signal and the upstream path to review. If the origin lacks stable IDs or parent references, run a focused inline map audit for just that scope and record any metadata gaps.

Read the origin artifact, parent chain, inverse child references, named sibling or dependent artifacts, recent promotion reports, and recent map audit or lens-doctor reports if available. Build an impact tree showing each upstream and downstream node, the claim being tested, evidence for/against consistency, confidence, and the action needed.

Do not edit source docs by default. If the user asks for patches, propose scoped ledger or topology updates in the report first and apply only after confirmation.

Write `{reporting_output_path}/salmon-impact-{origin-or-date}.md`.

## Report Contract

The report must include:

- Origin artifact, signal type, timestamp, and reviewed upstream path
- Impact verdict: `NO_UPSTREAM_CHANGE`, `ADVISORY_REFRESH`, `BLOCKING_CONTRADICTION`, or `TOPOLOGY_REVIEW_REQUIRED`
- Impact tree from origin to service/domain/program parents and back down to named dependents
- Blocking findings and advisory findings in separate tables
- Proposed recursive consistency actions, ordered from highest parent to dependent artifacts and back to the source artifact
- Evidence notes distinguishing direct facts from inference
- Machine-readable summary block:

```json
{
  "module": "lens",
  "report_type": "salmon_impact",
  "origin": "",
  "verdict": "ADVISORY_REFRESH",
  "reviewed_upstream": [],
  "reviewed_downstream": [],
  "blocking_count": 0,
  "advisory_count": 0,
  "confidence": "evidence-backed"
}
```

## Safety Rules

Never let the Salmon review silently change topology. If parentage, ownership, or stable identity must change, classify the item as topology review required and route to `lens-topology-design`.

Never write Lens governance state from Salmon impact review. Route lifecycle or constitution follow-up through Lens wrappers.

