# Auto-Context Pull

Auto-Context Pull loads the minimum useful feature context before a planning or implementation workflow begins. It helps the agent understand nearby work without flooding the session with every governance artifact.

## Outcome

After this flow completes, the caller has a structured context payload for the target feature:

```json
{
  "status": "pass",
  "feature_id": "lens-dev-new-codebase-example",
  "summaries": ["/governance/features/lens-dev/new-codebase/related/summary.md"],
  "full_docs": ["/governance/features/lens-dev/new-codebase/dependency/docs/architecture.md"],
  "context_paths": {
    "related": [],
    "depends_on": [],
    "blocks": []
  }
}
```

`summaries` and `full_docs` are the compatibility fields consumed by older prompt flows. `context_paths` is the richer Lens Next shape that preserves relationship type and existence checks.

## Inputs

- `--governance-repo <path>`: governance repo root.
- `--feature-id <id>`: feature to load context for.
- `--depth summary|full`: optional context depth. Default is `summary`.

## Flow

1. Pull governance `main` before reading state.
2. Read `feature-index.yaml` and locate the requested feature.
3. Read the feature's `feature.yaml`.
4. Collect relationship fields from `related_features`:
   - `related` loads `summary.md` only.
   - `depends_on` loads full docs when available.
   - `blocks` loads full docs when available.
5. Return existing paths only in `summaries` and `full_docs`.
6. Preserve missing paths in `context_paths` with `exists: false` so callers can report gaps without crashing.

## Invocation

> **not_yet_implemented**: The `fetch-context` and `read-context` subcommands documented below are not yet available in `init-feature-ops.py`. The current implementation only exposes `create-domain` and `create-service`. These commands will be added during the lens-dev-new-codebase-new-feature dev phase. Do not attempt to run them until that phase is complete.

```bash
uv run --script {project-root}/lens.core/_bmad/lens-work/skills/bmad-lens-init-feature/scripts/init-feature-ops.py \
  fetch-context \
  --governance-repo {governance_repo} \
  --feature-id {feature_id}
```

For full-depth context:

```bash
uv run --script {project-root}/lens.core/_bmad/lens-work/skills/bmad-lens-init-feature/scripts/init-feature-ops.py \
  fetch-context \
  --governance-repo {governance_repo} \
  --feature-id {feature_id} \
  --depth full
```

## Read Context

When no active feature branch is available, callers can read the local domain/service pointer from the personal context file:

```bash
uv run --script {project-root}/lens.core/_bmad/lens-work/skills/bmad-lens-init-feature/scripts/init-feature-ops.py \
  read-context \
  --personal-folder {personal_output_folder}
```

Expected return shape:

```json
{
  "status": "pass",
  "domain": "lens-dev",
  "service": "new-codebase",
  "updated_at": "2026-04-30T00:00:00Z",
  "updated_by": "new-service"
}
```

If the context file is absent, return `status: fail` with `error: context_missing`; do not infer a domain or service from branches.

## Clean-Room Notes

This document defines the expected command contract for the new-codebase source. It is derived from Lens planning artifacts and the public behavior of the feature initializer, not by copying old-codebase implementation code.
