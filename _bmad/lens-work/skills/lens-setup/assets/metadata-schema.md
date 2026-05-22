# Lens Metadata Contract

This contract defines the frontmatter Lens workflows read from authored project artifacts. Authored artifacts live in the work/feature archive or the living landscape. Generated projections are derived views and must not become source truth.

## Entity Types

| Type | Stable ID Prefix | Authored Location | Parent Rule |
| ---- | ---------------- | ----------------- | ----------- |
| `program` | `program:` | `{landscape_root}/<program>/ledger/program.md` | no parent required |
| `domain` | `domain:` | `{landscape_root}/<program>/<domain>/ledger/domain.md` | `belongs_to` should reference a `program:` ID |
| `service` | `service:` | `{landscape_root}/<program>/<domain>/<service>/ledger/service.md` | `belongs_to` should reference a `domain:` ID |
| `feature` | `feature:` | `{work_intake_path}/<feature-id>/feature.yaml`, `{work_intake_path}/<work-id>/work.md`, or `{feature_archive_path}/<feature-id>/feature.md` | `belongs_to` should reference a `service:`, `domain:`, or `program:` ID when known |
| `projection` | `projection:` | `{reporting_output_path}/governance-map.*` | derived; no authored parent |

## Core Fields

| Field | Required | Applies To | Meaning |
| ----- | -------- | ---------- | ------- |
| `stable_id` | yes | all governed authored entities | Stable identity that survives file moves. Prefix must match `entity_type`. |
| `entity_type` | yes | all governed authored entities | One of `program`, `domain`, `service`, `feature`, or `projection`. |
| `title` | yes | all governed authored entities | Human-readable name. |
| `belongs_to` | conditional | domain, service, feature | Parent stable ID. Use `unknown` only for intake or draft work that is not projection-ready. |
| `status` | yes | authored entities | Delivery or knowledge lifecycle, such as `intake`, `in_progress`, `completed`, `promoted`, `active`, `retired`. |
| `publication_state` | yes | authored entities | Projection participation state: `draft`, `published`, or `retired`. |
| `updated_at` | yes | authored entities | ISO date or timestamp used for freshness checks. |

## Work And Feature Fields

| Field | Required | Meaning |
| ----- | -------- | ------- |
| `work_id` | yes for work archives | Kebab-case work archive folder name. |
| `feature_id` | yes for feature lifecycle records | Kebab-case local feature folder name under `docs/features`. |
| `track` | yes for feature lifecycle records | `full` or `express`. Full uses `preplan -> businessplan -> techplan -> finalizeplan -> dev`; express uses `expressplan -> finalizeplan -> dev`. |
| `phase` | yes for feature lifecycle records | Current local phase, optionally suffixed with `-complete` after validation. |
| `docs_path` | recommended | Local feature archive path that owns lifecycle artifacts. Defaults to the `feature.yaml` parent directory. |
| `target_repos` | required before `dev` | Local implementation repository paths where Dev may write code. |
| `lifecycle_stage` | yes for work archives | Current local lifecycle stage, usually matching `phase` for feature records. |
| `source_feature` | optional | Stable ID or path that this work came from. |
| `related_to` | optional | Stable IDs for related work or features. |
| `extends` | optional | Stable IDs this work extends. |
| `replaces` | optional | Stable IDs this work supersedes. |
| `depends_on` | optional | Stable IDs, story IDs, or local artifact paths that must be complete first. |
| `blockers` | optional | Human-readable blocking issues that prevent phase advancement. |
| `artifact_state` | optional | Per-phase artifact readiness summary for local lifecycle commands. |
| `promotion_status` | optional | `not_started`, `planned`, `promoted`, or `blocked`. |
| `salmon_upstream` | optional | Boolean signal that downstream evidence may affect upstream truth. |
| `salmon_status` | optional | `none`, `pending`, `reviewed`, or `blocked`. |
| `links` | optional | Local paths or stable IDs this artifact depends on or references. |

## Local Lifecycle Artifacts

All clean-room lifecycle artifacts for a feature live beside `feature.yaml` unless `docs_path` points elsewhere.

| Phase | Required Artifacts |
| ----- | ------------------ |
| `preplan` | `brainstorm.md`, `research.md`, `product-brief.md`, `preplan-adversarial-review.md` |
| `businessplan` | `prd.md`, `ux-design.md`, `businessplan-adversarial-review.md` |
| `techplan` | `architecture.md`, `techplan-adversarial-review.md` |
| `expressplan` | `business-plan.md`, `tech-plan.md`, `sprint-plan.md`, `expressplan-adversarial-review.md` |
| `finalizeplan` | `finalizeplan-review.md`, `epics.md`, `stories.md`, `implementation-readiness.md`, `sprint-status.yaml`, and `stories/*.md` |
| `dev` | `sprint-status.yaml`, `stories/*.md`, `dev-session.yaml` when execution has begun |

## Optional External Context Fields

These legacy fields let NextLens record observed external context without making it authoritative. They are optional provenance fields only. Local NextLens lifecycle state lives in `docs/features/<feature-id>/feature.yaml`.

| Field | Required | Meaning |
| ----- | -------- | ------- |
| `lens_feature_id` | optional | Lens governance feature identifier associated with this Lens artifact. |
| `lens_track` | optional | Lens lifecycle track, such as `full`, `express`, `quickdev`, `hotfix-express`, or `spike`. |
| `lens_phase` | optional | Current Lens phase observed from context or governance metadata. |
| `lens_docs_path` | optional | Lens planning documents path associated with the feature. |
| `lens_constitution_root` | optional | Local path to the Lens constitution root when known. |
| `lens_feature_yaml_path` | optional | Local path or repo-relative path to an external Lens feature record. |
| `lens_constitution_status` | optional | Summary status supplied by Lens or clean-room NextLens constitution checks, such as `pass`, `advisory`, `blocked`, or `unknown`. |
| `lens_preflight_status` | optional | Summary status supplied by Lens or Lens preflight, such as `pass`, `blocked`, or `unknown`. |

## Publication Semantics

`status` tracks lifecycle. `publication_state` controls whether the artifact participates in published projections.

- `draft`: inspectable during doctor runs but excluded from published projections unless `--include-drafts` is explicit.
- `published`: included in doctor checks, projection rebuilds, reporting snapshots, and promotion decisions.
- `retired`: retained for history and traceability; excluded from current projections unless the user explicitly requests retired entities.

Do not use branches as the source of planning isolation. Planning state belongs in `publication_state`, with all decisions visible in files.

## Blocking Conditions

Lens doctor, map audit, and projection rebuild treat these as blocking for published projections:

- Missing `stable_id`, `entity_type`, `title`, `status`, `publication_state`, or `updated_at`.
- `stable_id` prefix does not match `entity_type`.
- Duplicate published `stable_id` values.
- `belongs_to` is missing, `unknown`, broken, cyclic, or points to an invalid parent type.
- Broken local Markdown links.
- Published feature completion has no resolvable ledger target when promotion is required.

Draft artifacts may carry incomplete parentage, but doctor reports must surface those gaps as draft advisories.