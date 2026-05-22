# LENS Workbench — Configuration Examples

Sample `bmadconfig.yaml` configurations for different team sizes, git providers, and use cases.

> New initiative metadata is governance-first. `governance_repo_path` is the canonical destination for `/new-domain`, `/new-service`, and `/new-feature`. `initiative_output_folder` remains a legacy compatibility path for older workflows and migrations.

---

## Solo Developer (GitHub)

The simplest setup — one developer, one repo, express track by default.

```yaml
# lens.core/_bmad/lens-work/bmadconfig.yaml
user_name: "Alice"
communication_language: "english"
output_folder: "docs"
target_projects_path: "../TargetProjects"
default_git_remote: "github"
lifecycle_contract: "lens.core/_bmad/lens-work/lifecycle.yaml"
governance_repo_path: "../TargetProjects/lens/lens-governance"
initiative_output_folder: "docs/lens-work/initiatives"
personal_output_folder: ".lens/personal"
```

**Recommended constitution settings:**
```yaml
# constitutions/org.yaml
permitted_tracks: [express, feature, hotfix, quickdev, spike]
branching_strategy: trunk-based
stakeholder_gate: informational
collapse_gates:
  enabled: true
```

---

## Small Team (GitHub, 2-5 developers)

Standard setup with feature tracks and PR-based review gates.

```yaml
# lens.core/_bmad/lens-work/bmadconfig.yaml
user_name: "Bob"
communication_language: "english"
output_folder: "docs"
target_projects_path: "../TargetProjects"
default_git_remote: "github"
lifecycle_contract: "lens.core/_bmad/lens-work/lifecycle.yaml"
governance_repo_path: "../TargetProjects/lens/lens-governance"
initiative_output_folder: "docs/lens-work/initiatives"
personal_output_folder: ".lens/personal"
```

**Recommended constitution settings:**
```yaml
# constitutions/org.yaml
permitted_tracks: [express, feature, full, tech-change, hotfix, quickdev, spike]
branching_strategy: pr-per-milestone
stakeholder_gate: informational
collapse_gates:
  enabled: true
  rules:
    - name: small-feature
      max_stories: 3
```

---

## Enterprise Team (GitHub, regulated)

Full governance with mandatory stakeholder approval and all gates enforced.

```yaml
# lens.core/_bmad/lens-work/bmadconfig.yaml
user_name: "Carol"
communication_language: "english"
output_folder: "docs"
target_projects_path: "../TargetProjects"
default_git_remote: "github"
lifecycle_contract: "lens.core/_bmad/lens-work/lifecycle.yaml"
governance_repo_path: "../TargetProjects/lens/lens-governance"
initiative_output_folder: "docs/lens-work/initiatives"
personal_output_folder: ".lens/personal"
```

**Recommended constitution settings:**
```yaml
# constitutions/org.yaml
permitted_tracks: [full, feature, tech-change, hotfix]
branching_strategy: pr-per-milestone
stakeholder_gate: hard
collapse_gates:
  enabled: false
content_sensing_mode: hard-gate
enable_parallel_phases: false
```

---

## Azure DevOps Setup

Same module — different git provider target.

```yaml
# lens.core/_bmad/lens-work/bmadconfig.yaml
user_name: "Dave"
communication_language: "english"
output_folder: "docs"
target_projects_path: "../TargetProjects"
default_git_remote: "azure-devops"
lifecycle_contract: "lens.core/_bmad/lens-work/lifecycle.yaml"
governance_repo_path: "../TargetProjects/lens/lens-governance"
initiative_output_folder: "docs/lens-work/initiatives"
personal_output_folder: ".lens/personal"
```

> **Note:** Azure DevOps uses the same REST API PR creation scripts. PAT scope requires `Code (Read & Write)` and `Pull Request Threads (Read & Write)`.

---

## GitLab Setup

```yaml
# lens.core/_bmad/lens-work/bmadconfig.yaml
user_name: "Eve"
communication_language: "english"
output_folder: "docs"
target_projects_path: "../TargetProjects"
default_git_remote: "gitlab"
lifecycle_contract: "lens.core/_bmad/lens-work/lifecycle.yaml"
governance_repo_path: "../TargetProjects/lens/lens-governance"
initiative_output_folder: "docs/lens-work/initiatives"
personal_output_folder: ".lens/personal"
```

> **Note:** GitLab PAT requires `api` scope. The provider adapter detects GitLab URLs and uses the GitLab REST API for merge request creation.

---

## Multi-IDE Setup

If your team uses multiple editors, install adapters for all of them:

```bash
uv run lens.core/_bmad/lens-work/scripts/install.py --all-ides
```

This generates adapter files for:
- **GitHub Copilot** (VS Code) — `.github/lens-work-instructions.md`
- **Cursor** — `.cursor/commands/`
- **Claude Code** — `.claude/`
- **Codex CLI** — `.codex/`
- **OpenCode** — `.opencode/commands/`

All adapters reference the same module and lifecycle contract — no configuration drift.

---

## Non-English Communication

LENS supports any language for agent communication:

```yaml
user_name: "Franz"
communication_language: "german"
```

All agent responses, menu items, and workflow guidance will be in German. Artifact structure and git operations remain in English (branch names, commit messages, YAML keys).

---

## Branching Strategy Reference

The `branching_strategy` constitution setting controls how promotion PRs are created:

| Strategy | PR Behavior | Best For |
|----------|-------------|----------|
| `trunk-based` | All promotion PRs merge to the trunk branch (main/master). No milestone branches. | Solo developers, express track |
| `pr-per-milestone` | Each milestone gets its own long-lived branch. Promotion PRs merge the current milestone into the next. | Small-to-medium teams with structured review |
| `pr-per-epic` | Like `pr-per-milestone` but scoped to epics rather than milestones. | Enterprise teams with epic-level governance |

These strategies interact with `collapse_gates` — when gate collapsing is enabled with `trunk-based`, intermediate milestone PRs are skipped entirely (the initiative advances directly to the target milestone).
