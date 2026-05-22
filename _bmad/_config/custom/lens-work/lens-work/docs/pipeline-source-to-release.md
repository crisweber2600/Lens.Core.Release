# Source-to-Release Promotion Pipeline

**Purpose:** Build a full BMAD release with the lens-work custom module embedded, then promote to `lens.core` (alpha → beta PR).

## Workflow Location

```
bmad.lens.bmad/.github/workflows/promote-to-release.yml
```

## Pipeline Flow

```
push to master (bmad.lens.src/lens.core/_bmad/lens-work/**)
  │
  ├─ 1.  Validate declarative-only constraint
  ├─ 2.  Validate required files exist
  ├─ 3.  Read module version from module.yaml
  │
  ├─ 4.  Prepare release repo (checkout or recreate alpha from beta)
  ├─ 5.  Prepare clean build-output workspace
  │
  ├─ 6.  Fetch BMB module source (from bmad-builder npm package)
  ├─ 7.  Install full BMAD framework via npx bmad-method:
  │       modules: core, bmm, cis, gds, tea + custom BMB
  │       IDEs:    github-copilot, cursor, claude-code
  │
  ├─ 8.  Overlay lens-work custom module into build-output/lens.core/_bmad/lens-work/
  │       (also registered in build-output/lens.core/_bmad/_config/custom/lens-work/)
  │
  ├─ 9.  Run lens-work _module-installer to generate IDE adapters
  │       (.github/agents/, .github/prompts/, .github/skills/)
  │
  ├─ 10. Sync source .github/agents/*.md into release payload
  ├─ 10.5 Overlay source .github/skills/*/SKILL.md into generated BMAD skill stubs
  ├─ 10.6 Prune .github/prompts to lens-work stubs only
  │
  ├─ 11. Post-process: rename .yaml→.yaml, bmadconfig.yaml→bmadconfig.yaml
  ├─ 12. Patch copilot-instructions.md project name
  │
  ├─ 13. Validate embedded .github payload (required agents, prompts, skills)
  ├─ 14. Update BMAD manifest.yaml with lens-work entry
  │
  ├─ Commit build-output to alpha (preserve history)
  └─ Create PR: alpha → beta (via GitHub REST API, no gh CLI)
```

## Triggers

| Trigger | Action |
|---------|--------|
| Push to `master` changing `bmad.lens.src/lens.core/_bmad/lens-work/**` | Validate + full build + promote to alpha + open PR to beta |
| Push to `master` changing `.github/workflows/promote-to-release.yml` | Same |
| Manual `workflow_dispatch` | Same as above |

## Validation Steps

1. **Declarative-only scan** — Fail if executable files found outside `scripts/` or `_module-installer/`
2. **Required files check** — Verify `lifecycle.yaml`, `module.yaml`, `module-help.csv`, `README.md`, `_module-installer/installer.js` exist
3. **Version read** — Extract version from `module.yaml` for commit message and PR title
4. **Release payload validation** — Verify required agent, prompt, and skill files exist in build output; enforce no non-lens prompts and no non-stub skill payloads

## BMAD Framework Build

The pipeline installs a complete BMAD framework (not just lens-work) into a clean `build-output/` workspace:

| Component | Source |
|-----------|--------|
| Core + standard modules | `npx bmad-method@6.2.0` (npm) |
| BMB module | `bmad-builder@latest` npm package (`/src/`) |
| lens-work module | `bmad.lens.src/lens.core/_bmad/lens-work/` in this repo |

The lens-work module is overlaid on top of the installed framework, then its `_module-installer/installer.js` generates IDE-specific adapter files.

## Release Repo Structure

| Build output | Release (`alpha` branch) |
|-------------|--------------------------|
| `build-output/lens.core/_bmad/` | `lens.core/_bmad/` |
| `build-output/.github/` | `.github/` |
| `build-output/.github/agents/` | `.github/agents/` |
| `build-output/.github/skills/` | `.github/skills/` (BMAD + lens-work redirect stubs) |
| `build-output/.github/prompts/` | `.github/prompts/` (lens-work stubs only) |

### Included in promotion:
All output from the BMAD installer + lens-work overlay, including:
- `lens.core/_bmad/lens-work/` — full module source
- `lens.core/_bmad/_config/` — manifest, agent configs
- `lens.core/_bmad/core/`, `lens.core/_bmad/bmm/`, `lens.core/_bmad/cis/`, `lens.core/_bmad/gds/`, `lens.core/_bmad/tea/` — standard modules
- `.github/agents/`, `.github/skills/`, `.github/prompts/` — IDE-ready adapter stubs

### Excluded from promotion:
- CI/CD workflow files (not written to build-output)
- Any disallowed executable files outside `scripts/` or `_module-installer/` (hard failure)

## Alpha Branch Strategy

- If `alpha` exists and shares history with `beta`: commits directly to `alpha`
- If `alpha` history is unrelated to `beta`: recreates `alpha` from `beta` (history repair)
- If `alpha` does not exist: creates `alpha` from `beta` (first publish)

## PR Creation

- Uses **GitHub REST API** directly (no `gh` CLI dependency)
- If an open PR from `alpha → beta` already exists, the push updates it automatically
- PR title includes module version; body includes source commit SHA and actor

## Idempotency

The pipeline is idempotent — re-running produces the same result. The clean `build-output/` workspace, combined with overlay + copy operations, ensures:
- New files in source appear in release
- Deleted files in source are removed from release
- Modified files in source update in release

## Security

- Release repo push requires `RELEASE_REPO_TOKEN` secret (PAT with `repo` scope on `lens.core`)
- Pipeline runs as `github-actions[bot]` — no human credentials in git history
- Executable file scan enforces the declarative-only constraint at CI level
- Token is never logged; used only in `git remote` auth and GitHub REST API calls

## Required Secrets

| Secret | Purpose |
|--------|---------|
| `RELEASE_REPO_TOKEN` | PAT with `repo` scope on `lens.core` — enables clone, push, and PR creation |
