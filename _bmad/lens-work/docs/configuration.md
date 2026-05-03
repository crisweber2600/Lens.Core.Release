# Lens Workbench Configuration

The committed module defaults live in `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`. Local user values may be supplied in `{project-root}/lens.core/_bmad/lens-work/config.user.yaml`; that file is personal workspace state and must not be committed.

## Required Module Fields

| Field | Purpose |
| --- | --- |
| `governance_repo_path` | Absolute or placeholder-based path to the Lens governance repo. |
| `control_topology` | Fixed Lens control-repo topology. The target module uses `3-branch`. |
| `target_projects_path` | Absolute or placeholder-based path to the shared `TargetProjects` root. |
| `default_git_remote` | Default remote name for git operations. |
| `lifecycle_contract` | Path to the lifecycle contract used by module validation. |

## User Config Contract

`config.user.yaml` is authoritative for local, user-specific overrides. Supported fields are:

| Field | Purpose |
| --- | --- |
| `github_username` | GitHub username used for user-scoped branches and identity. |
| `default_branch` | Target repo base branch when a command does not receive an explicit branch. |
| `target_branch_strategy` | Target repo branch naming strategy, such as `feature/{featureStub}` or `feature/{featureStub}-{github_username}`. |
| `governance_repo_path` | Local governance checkout path when it differs from the committed default. |
| `target_projects_path` | Local `TargetProjects` root when it differs from the committed default. |
| `default_git_remote` | Local git remote name when it differs from `origin`. |

Example:

```yaml
github_username: crisweber2600
default_branch: develop
target_branch_strategy: "feature/{featureStub}-{github_username}"
```

Path values may use `{project-root}` for the target repo root and `{module-root}` for `{project-root}/lens.core/_bmad/lens-work`. Loaders normalize paths to absolute OS-native paths before writes or publish operations.