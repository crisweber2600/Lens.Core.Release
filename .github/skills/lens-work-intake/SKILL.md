---
name: lens-work-intake
description: Starts durable NextLens feature archives. Use when the user requests 'lens work intake', 'start work', or 'create related feature'.
---

# Lens Work Intake

## Overview

Use `vscode_askQuestions` for all follow-up questions that require user input. If the tool is unavailable, stop and present the exact question instead of guessing.

This skill creates a durable unit of work by turning an idea, change request, or related feature into an inspectable NextLens feature archive. Act as a work-intake steward: preserve the user's raw intent as concise file memory, connect related work without copying noise, initialize local lifecycle state, and hand the unit to `/next` or the right phase command.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, `{project-root}/_bmad/config.toml`, and `{project-root}/_bmad/config.user.toml`, checking both root values and the `lens` or `modules.lens` section. If config is missing, let the user know `lens-setup` can configure Lens at any time. Use these defaults:

- `work_intake_path`: `{project-root}/docs/features`
- `feature_archive_path`: `{project-root}/docs/features`
- `landscape_root`: `{project-root}/docs`
- `reporting_output_path`: `{project-root}/_bmad-output/lens`
- `freshness_threshold_hours`: `24`
- `lens_mode`: `auto`
- `lens_lifecycle_contract`: `{project-root}/skills/lens-lifecycle/assets/lifecycle.yaml`
- `lens_context_path`: `{project-root}/.lens/personal/context.yaml`

Support interactive and headless use. In headless mode, infer the feature ID, relationship, lifecycle track, and lifecycle handoff from the provided request and existing artifacts; write the archive; and return compact JSON with `status`, `feature_id`, `work_path`, `feature_path`, `handoff_path`, `next_skill`, and `open_questions`.

## Work Unit Contract

A unit of work is the permanent historical record for one feature, change, investigation, or related follow-up. Create or update it under `{work_intake_path}/<feature-id>/`. The feature archive is authored truth for delivery history and local lifecycle state; living service/domain/program ledgers remain current operational truth and are only changed later by `lens-ledger-promotion`.

Use the shared Lens metadata contract at `{project-root}/skills/lens-setup/assets/metadata-schema.md` and the work template at `{project-root}/skills/lens-setup/assets/templates/work.md` when available. `status` tracks lifecycle; `publication_state` controls whether the artifact participates in published projections.

Each feature archive contains:

- `feature.yaml` - stable ID, parent, lifecycle track, current phase, artifact path, target repos when known, promotion status, and Salmon signals.
- `work.md` - frontmatter, goal, scope, success criteria, status, lifecycle handoff, and completion evidence.
- `memory.md` - durable thread memory: decisions, source signals, user constraints, related-work context, open loops, and discarded options worth preserving.
- `journey.md` - end-to-end user journey and lifecycle trace for this unit.
- `handoff.md` - the next Lens/BMad workflow, inputs it needs, and the exact context to carry forward.
- `links.md` - stable IDs, related work, source artifacts, ledger targets, story files, reports, and promotion status.

Keep memory concise, inspectable, and diffable. Do not rely on hidden chat history for anything a future worker needs.

## Workflow

Start by identifying whether the request creates new work, resumes existing work, or creates related work. Generate a stable kebab-case `feature_id`; use `feature:<feature-id>` as `stable_id` unless that ID already exists, in which case surface the collision and choose a non-conflicting variant. Use `work_id` as an alias for `feature_id` when older templates expect it.

For related work, scan nearby feature archives under `work_intake_path` and `feature_archive_path` for `feature.yaml`, `work.md`, `feature.md`, `memory.md`, and `links.md`. Load only likely matches unless the user explicitly asks for a broad inventory. Record relationships using `related_to`, `extends`, `replaces`, `source_feature`, and `belongs_to` when known. Carry forward only durable decisions and constraints that matter to the new work; do not bulk-copy prior memory.

Create the archive if absent. If it already exists, read `feature.yaml`, `work.md`, `memory.md`, and `links.md`, append a dated update section, and preserve previous content unless the user explicitly asks for a rewrite.

Write `feature.yaml` with at least `stable_id`, `entity_type: feature`, `title`, `belongs_to`, `status: intake`, `publication_state: draft`, `updated_at`, `feature_id`, `track`, `phase`, `docs_path`, `related_to`, `depends_on`, `target_repos` when known, `promotion_status: not_started`, `salmon_upstream`, and `salmon_status`. Default `track` to `full` unless the user explicitly asks for an express path or the scope is clearly small and implementation-ready, in which case ask or record why `express` was chosen. Default `phase` to `preplan` for full-track features and `expressplan` for express-track features.

Write `work.md` with frontmatter that includes `stable_id`, `entity_type: feature`, `title`, `status: intake`, `publication_state: draft`, `work_id`, `feature_id`, `created_at` or `updated_at`, relationship fields when present, and `lifecycle_stage`. The body must capture the goal, non-goals, success criteria, current understanding, risks or open questions, and completion evidence placeholders.

When external Lens context is detected or supplied, also record `lens_feature_id`, `lens_track`, `lens_phase`, `lens_docs_path`, `lens_constitution_root`, `lens_feature_yaml_path`, `lens_constitution_status`, and `lens_preflight_status` as provenance fields only. Do not treat external branch or constitution-root state as local lifecycle authority.

Write `memory.md` as the work's durable notebook. Capture the user's raw intent, decisions with reasons, assumptions, open loops, source artifacts, and related-work learnings. Treat this as the explicit file memory inspired by long-running agent threads: useful knowledge survives compaction because it is serialized into project artifacts.

Write `journey.md` with the end-to-end path from intake to completion. Include the current work unit's path through discovery, PRD/architecture if needed, epics/stories, sprint status, story creation, development, review, completion, audit, ledger promotion, Salmon impact if triggered, and reporting snapshot.

Write `handoff.md` with the next recommended local lifecycle command:

- Full track start: `/preplan`, which may use `bmad-product-brief`, research, and adversarial review skills.
- Full track continuation: `/businessplan`, `/techplan`, `/finalizePlan`, then `/dev`.
- Express track start: `/expressplan`, then `/finalizePlan`, then `/dev`.
- Unknown or mixed state: `/next`, which runs the local lifecycle router.

Write `links.md` with all known artifact paths and relationship metadata. If the work is ready for implementation, include a story-template note instructing `bmad-create-story` to cite this feature archive under the story's Lens work-unit section.

## Completion Routing

When a NextLens/BMAD story, design delivery, or quick-dev change completes, update the feature archive with story path, review status, changed files, validation evidence, and completion notes. Then route governance in this order:

1. `lens-preflight` to verify local Lens readiness and optional Lens context.
2. `lens-map-audit` to verify IDs, parentage, links, and projection readiness.
3. `lens-ledger-promotion` to move durable completed knowledge into living ledgers.
4. `lens-salmon-impact` when the work has `salmon_upstream`, `impact: upstream`, or evidence that parent assumptions changed.
5. `lens-reporting-snapshot` for stakeholder visibility.

## Output Contract

End every run with the work path, files created or updated, relationship summary, selected next workflow, and open questions. Include a fenced JSON summary:

```json
{
  "module": "lens",
  "report_type": "work_intake",
  "feature_id": "",
  "work_path": "",
  "feature_path": "",
  "next_skill": "",
  "related_work": [],
  "open_questions": []
}
```

## Safety Rules

Never edit living ledgers, generated projections, sprint status, story files, or implementation code during intake. Intake may create or update only the feature archive and optional index artifacts under the configured work path. Do not fabricate relationships to make the topology look complete; use `unknown` and carry the question into `handoff.md`.

Never write external governance mirrors directly. Intake records observed external context only; local NextLens lifecycle commands remain the authority for feature creation and phase movement.