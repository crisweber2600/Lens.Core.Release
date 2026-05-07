---
applyTo: "**"
---

# LENS Workbench — Control Repo and Governance Repo Git Rules

## Repo Topology

LENS Workbench uses three distinct repositories. Every agent and skill must understand which repo it is operating in before performing any git or file operation.

```
source repo  (the installed module payload — read-only at runtime)
  └── {module_path}/_bmad/lens-work/   ← skills, prompts, scripts, lifecycle contract
      └── module.yaml                  ← authoritative module identity and version

control repo  (the operational workspace for active feature work)
  ├── {featureId}                 ← base branch: approved planning state
  ├── {featureId}-plan            ← planning branch: drafts accumulate here
  └── {featureId}-dev-{username}  ← optional dev tracking branch

governance repo  (always on main — canonical feature registry and approved artifact mirror)
  ├── feature-index.yaml          ← global feature registry
  ├── features/{domain}/{service}/{featureId}/
  │   ├── feature.yaml            ← canonical feature state (phase, track, gates)
  │   ├── summary.md
  │   └── docs/                   ← approved artifact mirror (published by CLI only)
  └── constitutions/              ← 4-level constitutional hierarchy
```

Resolve `{control_repo}` and `{governance_repo}` from `_bmad/config.yaml` (or `_bmad/config.user.yaml`) in the installed module payload before any operation. Do not hard-code paths.

**Key distinction:**
- The **control repo** holds live feature work in named branches. It is an operational workspace — not a code repo.
- The **governance repo** holds canonical feature state and approved artifact mirrors, always on `main`. Never create branches in the governance repo.
- The **source repo** (module payload) holds the skills, prompts, and lifecycle contract. It is read-only at runtime — never duplicate its contents into `.github/`.

---

## Mandatory Git Discipline

### ALWAYS pull before reading state

Before any operation that reads feature state, branch state, or governance artifacts — run a pull in the relevant repo. This applies to both the control repo and the governance repo.

```bash
# Before reading feature.yaml or any governance artifact
cd {governance_repo} && git pull

# Before reading control repo branch state
cd {control_repo} && git pull

# Before reading the module payload (skills, lifecycle contract)
cd {module_path} && git pull
```

**Do not skip the pull** even if you believe the local copy is current. Remote state may have been updated by another agent session, a CI pipeline, or a collaborator.

### ALWAYS push after committing

After any `git commit` in the control repo or governance repo, immediately push to remote. Do not allow local commits to accumulate without pushing.

```bash
# After committing artifacts to the control repo
git push [--set-upstream origin {branch}]

# After the publish-to-governance CLI writes and commits governance artifacts
cd {governance_repo} && git push
```

**Unsynced commits are invisible to other agents and collaborators.** The Lens lifecycle relies on git as the sole source of truth — local-only commits break that contract.

### Pull-then-push sequence for every write operation

Every write operation follows this exact sequence — no exceptions:

1. `git pull` in the target repo (fail fast on merge conflicts — do not auto-resolve)
2. Perform the write (create/update files, run the publish CLI)
3. `git add` the changed files
4. `git commit -m "[{PHASE}] {featureId} — {description}"`
5. `git push` (with `--set-upstream` if tracking ref is not yet set)
6. Report the pushed commit SHA and remote ref to the user

---

## Authority Domain Rules

Every file belongs to exactly one authority domain. Cross-authority writes are hard errors — not warnings.

| Domain | Repo | Path | Who May Write |
|--------|------|------|--------------|
| Control repo artifacts | control repo | `docs/{domain}/{service}/{featureId}/` | `@lens` agent via Lens skills |
| Module source | source repo | `{module_path}/_bmad/lens-work/` | Module maintainer only — read-only at runtime |
| Copilot adapter | control repo | `.github/` | Human user only — not modified during feature work |
| Governance artifacts | governance repo | `features/...`, `constitutions/` | Publish CLI only — never direct file writes |

**Governance write rule:** Agents must never create or edit files in the governance repo directly using file tools or patches. All governance writes go through the publish CLI:

```bash
uv run {module_path}/_bmad/lens-work/skills/bmad-lens-git-orchestration/scripts/git-orchestration-ops.py \
  publish-to-governance \
  --governance-repo {governance_repo} \
  --control-repo {control_repo} \
  --feature-id {feature_id} \
  --phase {phase}
```

After the CLI completes, commit and push the governance repo if the CLI does not do so automatically.

---

## Control Repo: 2-Branch Model

Every feature in the control repo has exactly two branches:

| Branch | Purpose | Who writes |
|--------|---------|------------|
| `{featureId}` | Approved base state — merged plan artifacts | `bmad-lens-git-orchestration` via plan PR |
| `{featureId}-plan` | Planning drafts — all artifact commits during active phases | `@lens` agent during phase work |

**Rules:**
- Planning artifact commits always go to `{featureId}-plan`, never directly to `{featureId}`.
- `{featureId}` is updated only via a reviewed PR from `{featureId}-plan` (the plan PR gate).
- Feature-only naming (e.g. `auth` instead of `domain-service-auth`) is permitted when the `features.yaml` registry maps the short name to its full domain/service path.

---

## Governance Repo: Main-Only

The governance repo has no feature branches. All feature state lives on `main` in committed `feature.yaml` files. The governance repo is updated through:

1. The `publish-to-governance` CLI (copies approved artifacts from the control repo docs path into the governance mirror path)
2. `bmad-lens-feature-yaml` (creates and updates `feature.yaml` entries)

After either operation, commit and push to `main` in the governance repo immediately.

---

## Pre-Operation Checklist

Before starting any Lens skill or phase operation, verify:

- [ ] `git pull` completed in the control repo — no conflicts
- [ ] `git pull` completed in the governance repo — no conflicts  
- [ ] Current branch in the control repo matches the expected feature branch (`{featureId}` or `{featureId}-plan`)
- [ ] `feature.yaml` for the current feature exists in the governance repo
- [ ] Working directory is clean (no uncommitted changes from a prior interrupted session)

If any check fails, surface it to the user and stop. Do not proceed with an ambiguous git state.

---

## Skill Reference

| Need | Skill | Path |
|------|-------|------|
| Read branch and PR state | `bmad-lens-git-state` | `{module_path}/_bmad/lens-work/skills/bmad-lens-git-state/SKILL.md` |
| Create branches, commit, push, publish | `bmad-lens-git-orchestration` | `{module_path}/_bmad/lens-work/skills/bmad-lens-git-orchestration/SKILL.md` |
| Read/write `feature.yaml` | `bmad-lens-feature-yaml` | `{module_path}/_bmad/lens-work/skills/bmad-lens-feature-yaml/SKILL.md` |
| Resolve governance constitutions | `bmad-lens-constitution` | `{module_path}/_bmad/lens-work/skills/bmad-lens-constitution/SKILL.md` |

Load the relevant skill file before performing any operation in its domain.
