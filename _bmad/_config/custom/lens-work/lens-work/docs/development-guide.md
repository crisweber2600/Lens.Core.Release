# Development Guide — LENS Workbench Module (lens-work)

**Generated:** 2026-04-01 | **Scan Level:** Deep | **Module Version:** 4.0.0

---

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Git | 2.28+ | Branch operations, state derivation, commits |
| Bash / uv | 4+ / any | Script execution (install, create-pr, setup, PAT) |
| Node.js | 16+ | CI/CD installer only (`_module-installer/installer.js`) |
| curl | any | REST API calls in scripts (GitHub/Azure DevOps) |
| jq | any (optional) | JSON parsing in scripts |
| Python | 3.11+ (optional) | `uv run --script` entrypoints including `install.py` and legacy setup merge utilities |

---

## Installation

### Default Installation (GitHub Copilot)

```bash
# From control repo root
uv run lens.core/_bmad/lens-work/scripts/install.py
```

### Multi-IDE Installation

```bash
# Install for specific IDE
uv run lens.core/_bmad/lens-work/scripts/install.py --ide cursor

# Install for all supported IDEs
uv run lens.core/_bmad/lens-work/scripts/install.py --all-ides
```

### Update Existing Installation

```bash
uv run lens.core/_bmad/lens-work/scripts/install.py --update
```

### Dry Run (Preview)

```bash
uv run lens.core/_bmad/lens-work/scripts/install.py --dry-run
```

**Supported IDEs:** `github-copilot` (default), `cursor`, `claude`, `codex`, `opencode`

**What install does:**
1. Creates IDE adapter stubs in `.github/` (or IDE-specific config folder)
2. Generates agent wrapper, skill references, prompt stubs
3. Sets up output directory structure
4. Safe to re-run (skips existing files unless `--update`)

---

## Environment Setup

### 1. GitHub PAT (Required for PR Operations)

**CRITICAL:** Run PAT setup OUTSIDE any AI/LLM context.

```bash
# Unix
bash lens.core/_bmad/lens-work/scripts/store-github-pat.py

# Windows
powershell lens.core/_bmad/lens-work/scripts/store-github-pat.py
```

Sets `GITHUB_PAT`, `GH_TOKEN`, and `GH_ENTERPRISE_TOKEN` in environment + shell profile.

### 2. Control Repo Bootstrap

```bash
# Clone governance and release repos into TargetProjects
bash lens.core/_bmad/lens-work/scripts/setup-control-repo.py
```

Options: `--org`, `--release-org`, `--release-repo`, `--release-branch`, `--base-url`, `--dry-run`

### 3. Configuration

Edit `bmadconfig.yaml` at the module root:

```yaml
github_username: your-github-username    # Required: set to your GitHub username
target_projects_path: "../TargetProjects" # Where target repos live
default_git_remote: github                # git provider (github or azure-devops)
governance_repo_path: "../TargetProjects/lens/lens-governance" # Canonical governance metadata repo
```

---

## Module Structure for Development

### Key Files to Understand

| File | Purpose | When to Modify |
|------|---------|----------------|
| `lifecycle.yaml` | All lifecycle behavior definition | Adding phases, milestones, tracks, validation rules |
| `module.yaml` | Module metadata and registry | Changing version, adding skills/prompts/adapters |
| `module-help.csv` | Command index | Adding or modifying user commands |
| `agents/lens.agent.md` | Thin-shell agent persona and compact menu | Changing shell behavior or shell entry points |
| `_module-installer/installer.js` | Canonical adapter generator | Updating published agent, prompt, or command stubs |

### Adding or Updating a Skill Surface

1. Create or update the skill folder under `skills/bmad-lens-{name}/`
2. Add or update `SKILL.md` with operations, inputs/outputs, and preconditions
3. Register the skill in `module.yaml` under `skills`
4. Add or update the prompt entry point in `prompts/lens-{name}.prompt.md` when the skill should be directly invocable
5. Add an entry to `module-help.csv` when the surface should appear in command discovery
6. Update `agents/lens.agent.md` only when the thin shell itself needs a new compact entry point
7. Keep `_module-installer/installer.js` and `scripts/install.py` aligned whenever published prompts or agent stubs change
8. Add focused tests and documentation updates for the new surface

### Modifying the Lifecycle Contract

1. Edit `lifecycle.yaml`
2. Bump `schema_version` if structural changes
3. Update `docs/lifecycle-reference.md` to match
4. Update `docs/lifecycle-visual-guide.md` if flow changes
5. Run contract tests in `tests/contracts/`

---

## Scripts Reference

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `install.py` | Module installer | `--ide`, `--all-ides`, `--update`, `--dry-run` |
| `create-pr.py` | Create PR via REST API | `--source-branch`, `--target-branch`, `--title`, `--body`, `--url-only` |
| `setup-control-repo.py` | Bootstrap repos | `--org`, `--release-branch`, `--dry-run` |
| `store-github-pat.py` | PAT management | (interactive, run outside AI context) |

---

## Testing

### Contract Tests

Located in `tests/contracts/`. These are markdown-based specification files (not automated tests):

```bash
# No test runner — these are reference specifications
# Validate manually against implementations
cat tests/contracts/branch-parsing.md    # 20+ branch name parsing cases
cat tests/contracts/governance.md        # Constitutional merge rules
cat tests/contracts/provider-adapter.md  # PR creation interface
cat tests/contracts/sensing.md           # Overlap detection scenarios
```

### Validation Checklist

1. **Declarative-only scan:** Ensure no executables outside `scripts/` and `_module-installer/`
2. **Required files check:** `lifecycle.yaml`, `module.yaml`, `bmadconfig.yaml` must exist
3. **Manifest validation:** `module.yaml` references all skills, workflows correctly
4. **Help CSV alignment:** `module-help.csv` matches agent menu items
5. **Installer smoke test:** Run `install.py --dry-run` for all IDEs

### Development TODOs (from TODO.md)

- ☐ Deep validation on representative workflows (router/dev, router/finalizeplan)
- ☐ Smoke test installer output for all IDEs
- ☐ Verify module-help.csv command ordering aligned with LENS agent menu
- ☐ Confirm install-question naming consistency
- ☐ Document dual agent pattern (`.md` + `.yaml`)

---

## Build & Release Process

### Source → Release Pipeline

```
bmad.lens.src/lens.core/_bmad/lens-work/    (source)
    ↓ push to master (changes in lens.core/_bmad/lens-work/**)
CI/CD: promote-to-release.yml
    ↓ build → overlay → package
_module-installer/installer.js    (called by pipeline)
    ↓ generate IDE adapter stubs
lens.core (alpha branch)
    ↓ auto PR
lens.core (beta branch)
```

See [pipeline-source-to-release.md](./pipeline-source-to-release.md) for details.

---

## Common Development Tasks

### Onboard to LENS Workbench

```
@lens → /onboard
```

### Create a New Initiative

```
@lens → /new-feature   (or /new-domain, /new-service)
```

### Review Portfolio State

```
@lens → /dashboard
```

### Run Compliance Check

```
@lens → /constitution
```

### Express Planning (v3.2)

```
@lens → /expressplan
```

### Post-Initiative Retrospective (v3.2)

```
@lens → /retrospective
```

### Log a Problem (v3.2)

```
@lens → /log-problem
```

### Move Feature to Different Domain/Service (v3.2)

```
@lens → /move-feature
```

### Split Feature Into Multiple Initiatives (v3.2)

```
@lens → /split-feature
```
