---
name: bmad-lens-document-project
description: 'Document the active feature or target project for AI context, scoped to domain/service/feature paths in both the control repo and governance repo. Use when the user says "document this project" or "generate project docs".'
---

# LENS Document Project Skill

**Goal:** Run `bmad-document-project` with feature-aware output paths. Documentation lands in `docs/{domain}/{service}/{feature}/docs/` in the control repo and `features/{domain}/{service}/{feature}/docs/` in the governance repo.

---

## INITIALIZATION

Load config from `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`. Resolve:

- `{governance_repo_path}` — local path to the governance repo
- `{output_folder}` — base output path (default: `docs`)
- `{communication_language}`, `{document_output_language}`

---

## EXECUTION

### Step 1: Resolve Feature Context

Check for an active feature context by looking for `feature.yaml` on the current branch:

```
feature_yaml_candidates:
  - {governance_repo_path}/features/<domain>/<service>/<featureId>/feature.yaml  (on current branch)
  - docs/<domain>/<service>/<featureId>/feature.yaml                             (fallback local)
```

**If feature.yaml is found:**
- Read `docs.path` → set as `resolved_docs_path`
- Read `docs.governance_docs_path` → set as `resolved_governance_docs_path`
- Display: "📂 Scoped to feature `{featureId}` → Control: `{resolved_docs_path}/docs` | Governance: `{governance_repo_path}/{resolved_governance_docs_path}`"

**If no feature.yaml is found:**
- Ask the user:

  > No active feature context found. How should I scope the documentation output?
  >
  > 1. **Enter domain/service/feature manually** — I'll construct the paths
  > 2. **Use flat output** (`docs/` and no governance repo write) — standard bmad-document-project behavior
  > 3. **Cancel**

  - If option 1: collect `domain`, `service`, `featureId` from the user; derive paths as:
    - `resolved_docs_path = docs/{domain}/{service}/{featureId}`
    - `resolved_governance_docs_path = features/{domain}/{service}/{featureId}/docs`
  - If option 2: set `resolved_docs_path = null` (use skill default), `resolved_governance_docs_path = null`
  - If option 3: exit

### Step 2: Prepare Output Directories

If `resolved_docs_path` is set:
- Ensure `{project-root}/{resolved_docs_path}/docs` exists (create if needed)
- Ensure `{governance_repo_path}/{resolved_governance_docs_path}` exists (create if needed)

### Step 3: Delegate to bmad-document-project

Pass the following context overrides to the skill at `{project-root}/.github/skills/bmad-document-project/SKILL.md`:

```yaml
docs_override_path: "{project-root}/{resolved_docs_path}/docs"          # null if option 2
governance_docs_path: "{governance_repo_path}/{resolved_governance_docs_path}"  # null if option 2
```

Load and follow: `{project-root}/.github/skills/bmad-document-project/SKILL.md`

> **Context note for bmad-document-project:** When `docs_override_path` is provided, use it as `project_knowledge` instead of the default from bmadconfig.yaml. When `governance_docs_path` is provided, after generating documentation, copy the `index.md` and `project-overview.md` outputs to that path as well.

### Step 4: Post-Delegation Summary

After `bmad-document-project` completes:

- Display output locations:
  - Control repo docs: `{project-root}/{resolved_docs_path}/docs/`
  - Governance repo docs: `{governance_repo_path}/{resolved_governance_docs_path}/`
- If governance docs were written, remind user to commit and push the governance repo:
  ```
  git -C {governance_repo_path} add {resolved_governance_docs_path}
  git -C {governance_repo_path} commit -m "docs({domain}/{service}): update project documentation for {featureId}"
  git -C {governance_repo_path} push
  ```
