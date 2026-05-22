# Getting Started with LENS Workbench

## What is LENS?

LENS is an AI-powered planning assistant that turns ideas into implementation-ready stories using git as the workflow engine. It guides you through structured planning phases — from brainstorming through architecture to sprint-ready stories — with configurable governance and automated quality gates.

**No runtime code, no database, no external services** — everything lives in git branches, PRs, and committed artifacts.

---

## 3-Step Quick Start

### Step 1: Set Up Your Control Repo

```bash
# Clone or create your control repo, then run:
uv run setup-control-repo.py

# Windows:
powershell uv run setup-control-repo.py
```

This clones the governance repo and sets up the `TargetProjects/` folder where your code repos will live.

If terms like control repo, governance repo, `TargetProjects/`, or `lens.core/` are new to you, read [Understanding Your LENS Workspace](./understanding-your-workspace.md) before moving on.

### Step 2: Onboard

Open your AI chat and run:

```
/onboard
```

This detects your git provider, validates authentication (PAT), creates your user profile, and auto-clones any missing target repos from the governance inventory.

### Step 3: Start Your First Project

```
/new-project
```

LENS will walk you through reusing or creating the domain and service, naming the first feature, selecting a lifecycle track, and provisioning the target repo in the same flow. Then run the command it recommends (usually `/preplan` or `/expressplan`) to begin planning. If you want the workbench to route for you, use `/next` and it will load the one unblocked phase command automatically.

Use `/new-feature`, `/new-domain`, `/new-service`, or `/target-repo` directly when you only need one part of the bootstrap flow.

---

## Which Track Should I Use?

| Track | When to Use | Phases | Start Command |
|-------|------------|--------|---------------|
| **express** | Small features, solo dev, quick turnaround | expressplan -> finalizeplan | `/expressplan` |
| **feature** | Known business context, skip research | businessplan -> techplan -> finalizeplan | `/businessplan` |
| **full** | Greenfield, complex, or multi-team | preplan -> businessplan -> techplan -> finalizeplan | `/preplan` |
| **tech-change** | Infra/tooling, no business case needed | techplan -> finalizeplan | `/techplan` |
| **hotfix** | Urgent fix, minimal planning | techplan | `/techplan` |
| **quickdev** | Jump directly to implementation packaging | finalizeplan | `/finalizeplan` |
| **spike** | Research only, no implementation | preplan | `/preplan` |

> **Not sure?** Start with `express` for small work or `feature` for anything substantial.

---

## Key Commands

| Command | What It Does |
|---------|-------------|
| `/next` | Resolve the one unblocked next step and load it immediately |
| `/batch` | Generate or resume a two-pass batch intake for the current planning target |
| `/help` | List all available commands |
| `/switch` | Switch to a different initiative |
| `/dashboard` | See all active initiatives across domains |
| `/expressplan` | Run the express planning workflow (single-phase, no PRs) |
| `/retrospective` | Run a retrospective on a completed initiative |
| `/log-problem` | Record an issue or friction point for the active initiative |
| `/move-feature` | Reclassify a feature to a different domain/service |
| `/split-feature` | Split a feature initiative into multiple child initiatives |
| `/complete` | Finalize and archive a completed feature |

`/next` does not show a menu when the next step is deterministic. It surfaces blockers when it cannot proceed; otherwise it routes straight into the owning phase command.

`/batch` defaults to the current planning target. On the first pass it writes a context-derived `{target}-batch-input.md` file and stops; once the required answer blocks are filled, re-running `/batch` resumes the owning planning command automatically.

---

## How LENS Uses Git

LENS uses git as its **only source of truth**:

- **Branches** = initiative state (what exists tells you what's been started)
- **PRs** = review gates (approval at milestone boundaries)
- **Committed files** = planning artifacts (what's been produced)

There are no hidden state files, no databases, no runtime processes. If you can read git, you can read LENS state.

### Branch Model

```text
main
└── {featureId}         ← approved feature branch
    └── {featureId}-plan    ← planning drafts and review reports
```

The plan PR merges `{featureId}-plan` into `{featureId}`. The final implementation PR merges `{featureId}` into `main`.

### Feature-Only Branch Naming (v3.2)

Initiatives can use short feature-only branch names (e.g., `auth` instead of `foo-bar-auth`) when the feature name is unique. LENS maps short names to their full domain/service path via `features.yaml` at the control repo root.

### FinalizePlan Handoff

`/finalizeplan` is the planning handoff phase. It runs the final review, prepares the plan PR, packages downstream implementation artifacts, and marks the feature `dev-ready` once the constitution gate passes.

---

## Configuration

LENS reads defaults from `{release_repo_root}/lens.core/_bmad/lens-work/bmadconfig.yaml`:

```yaml
user_name: "Your Name"
communication_language: "english"
output_folder: "docs"
target_projects_path: "../TargetProjects"
default_git_remote: "github"
governance_repo_path: "../TargetProjects/lens/lens-governance"
```

See [Configuration Examples](./configuration-examples.md) for sample configs for different team sizes and git providers.

---

## Next Steps

- [Understanding Your LENS Workspace](./understanding-your-workspace.md) — what lives where and how the main folders work together
- [Onboarding Checklist](./onboarding-checklist.md) — detailed step-by-step with troubleshooting
- [Lifecycle Reference](./lifecycle-reference.md) — deep dive into phases, milestones, and tracks
- [Lifecycle Visual Guide](./lifecycle-visual-guide.md) — Mermaid diagrams of the full lifecycle
- [Configuration Examples](./configuration-examples.md) — sample configs for solo dev, teams, enterprise
