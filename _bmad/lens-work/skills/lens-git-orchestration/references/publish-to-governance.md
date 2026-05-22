# publish-to-governance

## Outcome

Reviewed planning artifacts that already exist in the control repo docs path are copied into the feature's governance docs mirror by the publish CLI. The operation reports which feature metadata source was used, exactly what was published, and what was missing.

## Preconditions

- `feature.yaml` exists for the feature in the governance repo, or in the control repo feature archive under `docs/features/{featureId}/feature.yaml` or `features/{featureId}/feature.yaml`
- The control repo has staged planning docs under `feature.yaml.docs.path` or the fallback docs path
- The caller provides a valid phase (`preplan`, `businessplan`, `techplan`, `finalizeplan`, or `expressplan`)

## Process

1. Resolve feature metadata from governance first, then from the control repo feature archive, unless `--feature-path` is provided
2. Resolve `control_docs_path` from `feature.yaml.docs.path`, top-level `docs_path`, or fallback to `docs/{domain}/{service}/{featureId}` for domain/service features and `docs/features/{featureId}` for local feature archives
3. Resolve `governance_docs_path` from `feature.yaml.docs.governance_docs_path`, top-level `governance_docs_path`, or fallback to `features/{domain}/{service}/{featureId}/docs` for domain/service features and `features/{featureId}/docs` for local feature archives
4. Expand the phase into the expected artifact filenames unless explicit `--artifact` values were provided
5. Invoke `uv run {project-root}/lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py publish-to-governance --governance-repo {governance_repo} --control-repo {control_repo} --feature-id {feature_id} --phase {phase}` or the equivalent wrapper entrypoint
6. Let the CLI copy all existing non-empty files for those artifacts into `governance_docs_path`
7. Do not create governance files or directories directly with tool calls or patches; the publish CLI performs that copy
8. Return `feature_yaml_source`, `published_files`, `copied_from`, and `missing_artifacts`

## Command Shape

```bash
uv run {project-root}/lens.core/_bmad/lens-work/skills/lens-git-orchestration/scripts/git-orchestration-ops.py publish-to-governance \
  --governance-repo {governance_repo} \
  --control-repo {control_repo} \
  --feature-id {feature_id} \
  [--feature-path docs/features/{feature_id}/feature.yaml] \
  --phase {phase}
```

The phase conductor may read the returned JSON and decide how to continue, but it must not replace this CLI step with manual governance file creation.

## Output

```json
{
  "feature_id": "auth-login",
  "feature_yaml_source": "governance",
  "phase": "preplan",
  "requested_artifacts": ["product-brief", "research", "brainstorm"],
  "control_docs_path": "/repo/docs/platform/identity/auth-login",
  "governance_docs_path": "/governance/features/platform/identity/auth-login/docs",
  "copied_from": [
    "/repo/docs/platform/identity/auth-login/product-brief.md"
  ],
  "published_files": [
    "/governance/features/platform/identity/auth-login/docs/product-brief.md"
  ],
  "missing_artifacts": ["research", "brainstorm"],
  "dry_run": false
}
```

Missing artifacts are reported explicitly so the phase conductor can decide whether to continue, pause, or ask the human for clarification.