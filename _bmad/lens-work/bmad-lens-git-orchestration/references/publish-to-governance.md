# publish-to-governance

## Outcome

Reviewed planning artifacts that already exist in the control repo docs path are copied into the feature's governance docs mirror by the publish CLI. The operation reports exactly what was published and what was missing.

## Preconditions

- `feature.yaml` exists for the feature in the governance repo
- The control repo has staged planning docs under `feature.yaml.docs.path` or the fallback docs path
- The caller provides a valid phase (`preplan`, `businessplan`, `techplan`, `finalizeplan`, or `expressplan`)

## Process

1. Resolve `control_docs_path` from `feature.yaml.docs.path` or fallback to `docs/{domain}/{service}/{featureId}`
2. Resolve `governance_docs_path` from `feature.yaml.docs.governance_docs_path` or fallback to `features/{domain}/{service}/{featureId}/docs`
3. Expand the phase into the expected artifact filenames unless explicit `--artifact` values were provided
4. Invoke `uv run {project-root}/lens.core/_bmad/lens-work/skills/bmad-lens-git-orchestration/scripts/git-orchestration-ops.py publish-to-governance --governance-repo {governance_repo} --control-repo {control_repo} --feature-id {feature_id} --phase {phase}` or the equivalent wrapper entrypoint
5. Let the CLI copy all existing non-empty files for those artifacts into `governance_docs_path`
6. Do not create governance files or directories directly with tool calls or patches; the publish CLI performs that copy
7. Return `published_files`, `copied_from`, and `missing_artifacts`

## Command Shape

```bash
uv run {project-root}/lens.core/_bmad/lens-work/skills/bmad-lens-git-orchestration/scripts/git-orchestration-ops.py publish-to-governance \
  --governance-repo {governance_repo} \
  --control-repo {control_repo} \
  --feature-id {feature_id} \
  --phase {phase}
```

The phase conductor may read the returned JSON and decide how to continue, but it must not replace this CLI step with manual governance file creation.

## Output

```json
{
  "feature_id": "auth-login",
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