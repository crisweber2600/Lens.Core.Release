# LENS Workbench — Onboarding Checklist

A step-by-step guide from zero to your first running initiative. Each section builds on the previous one.

If you need a quick mental model for the control repo, `TargetProjects/`, governance, and `lens.core/`, start with [Understanding Your LENS Workspace](./understanding-your-workspace.md).

---

## Prerequisites

- [ ] **Git** installed and configured (`git config user.name` and `git config user.email` set)
- [ ] **VS Code** (or Cursor/Claude Code) with GitHub Copilot extension
- [ ] **GitHub account** with access to your organization's governance and target repos
- [ ] **Personal Access Token (PAT)** with `repo` scope — [Create one here](https://github.com/settings/tokens)

> **Troubleshooting:** If you don't have access to the governance repo, ask your team lead. LENS won't work without governance access for constitutional governance checks.

---

## Phase 1: PAT Setup

- [ ] Run the PAT storage script (do this **outside** of AI chat — terminal only):

```bash
# macOS/Linux:
uv run {release_repo_root}/lens.core/_bmad/lens-work/scripts/store-github-pat.py

# Windows:
powershell uv run {release_repo_root}/lens.core/_bmad/lens-work/scripts/store-github-pat.py
```

- [ ] Verify PAT is stored: the script will confirm `GITHUB_PAT` or `GH_TOKEN` is set

> **Troubleshooting:**
> - "Permission denied" → Make the script executable: `chmod +x scripts/store-github-pat.py`
> - PAT not persisting across terminals → Add `export GITHUB_PAT=...` to your shell profile (`.bashrc`, `.zshrc`, or PowerShell `$PROFILE`)
> - PAT resolution order: `GITHUB_PAT` env var → `GH_TOKEN` env var → `profile.yaml` → URL-only fallback

---

## Phase 2: Control Repo Bootstrap

- [ ] Clone or create your control repo
- [ ] Run the setup script:

```bash
uv run setup-control-repo.py

# Windows:
powershell uv run setup-control-repo.py
```

- [ ] Verify the output:
  - `TargetProjects/` folder exists with your code repos cloned
  - `{release_repo_root}/lens.core/_bmad/lens-work/` folder contains the module files
  - No error messages in the script output

> **Troubleshooting:**
> - "Governance repo not found" → Check that the governance repo URL is correct in the setup config
> - "Authentication failed" → Verify your PAT has `repo` scope and is not expired
> - Clone failures → Try cloning the target repo manually first to rule out network/permission issues

---

## Phase 3: Onboard in AI Chat

- [ ] Open VS Code and start a GitHub Copilot chat session
- [ ] Run:

```
/onboard
```

- [ ] The onboard workflow will:
  - Run the shared workspace preflight
  - Stop on real preflight failures before you start work
  - Read `.lens/personal/profile.yaml` and tailor the next-step guidance to your `primary_role`
  - Tell all users about `/next` for the recommended next command
- [ ] Follow the guidance shown after preflight:
  - If `primary_role: dev`, use `/switch` and then `/dev`
  - Otherwise, use `/switch` for existing work or `/new-*` to create new work
- [ ] Verify: preflight completed successfully and the next-step guidance matches your role

> **Troubleshooting:**
> - "No governance repo found" → Run `setup-control-repo.py` first (Phase 2)
> - "Preflight failed" → Resolve the reported workspace issue, then run `/onboard` again
> - "Next-step guidance does not match your role" → Check `.lens/personal/profile.yaml` and update `primary_role`

---

## Phase 4: Your First Project

- [ ] Create a new project stack:

```
/new-project
```

- [ ] LENS will ask you:
  - **Feature name** — short, descriptive (e.g., `user-auth`, `dark-mode`)
  - **Domain** — reuse an existing business area or create a new one (e.g., `payments`, `frontend`)
  - **Service** — reuse an existing service or create a new one within the domain (e.g., `api`, `web`)
  - **Track** — lifecycle profile (pick `express` for your first time)
  - **Target repo** — clone an existing remote or create one now so implementation has a canonical `TargetProjects/{domain}/{service}/{repo}` home
- [ ] Verify: The feature exists in governance metadata, the initiative branch exists in git, and the target repo is cloned if you chose repo provisioning

> **Advanced use:** Run `/new-feature`, `/new-domain`, `/new-service`, or `/target-repo` directly when you only need a single step from the combined bootstrap flow.

---

## Phase 5: Run Your First Planning Workflow

- [ ] For **express** track, run:

```
/expressplan
```

- [ ] For **feature** or **full** track, run:

```
/preplan
```

- [ ] The workflow will guide you through producing planning artifacts (product brief, PRD, architecture, etc.)
- [ ] Check your progress anytime with `/next` or `/dashboard`

---

## Normal Day Workflow

Once onboarded, your daily flow is:

```mermaid
flowchart TD
    A[Open VS Code + Copilot Chat] --> B{Have active initiative?}
  B -->|Yes| C[/dashboard — review current state]
    B -->|No| D[/new-feature — start something new]
    C --> E[/next — get recommended action]
    E --> F[Run the recommended phase command]
    F --> G{Phase complete?}
    G -->|Yes| H[/next — continue lifecycle]
    G -->|No| F
    H --> I{All phases done?}
    I -->|Yes| J[/dev — delegate to implementation]
    I -->|No| E
    J --> K[/retrospective — review what happened]
    K --> L[/complete — formally archive initiative]
```

### Quick Reference

| Situation | Command |
|-----------|---------|
| Start of day | `/dashboard` |
| Don't know what's next | `/next` |
| Switch to different work | `/switch` |
| Something broke | `/log-problem` |
| Feature is done | `/complete` |
| Feature was cancelled | mark the feature abandoned via the completion flow or governance process |
| Need help | `/help` |

---

## Glossary

| Term | Meaning |
|------|---------|
| **Control repo** | Your operational LENS workspace where you run commands and keep planning artifacts |
| **`TargetProjects/`** | The folder that contains the repos LENS works across, including target repos and governance |
| **Target repo** | A code repo under `TargetProjects/` where implementation happens |
| **Governance repo** | The shared repo that holds constitutions, repo inventory, and feature metadata |
| **`lens.core/`** | The read-only LENS release payload inside the control repo |
| **LENS** | The workbench that coordinates planning, governance, and target-repo implementation |
| **Initiative** | A unit of work tracked by LENS (feature, tech change, spike, etc.) |
| **Track** | A lifecycle profile that determines which phases to run |
| **Phase** | A planning stage (preplan, businessplan, techplan, finalizeplan, or expressplan) |
| **Milestone** | A promotion boundary between phases (approved via PR) |
| **Constitution** | Governance rules that apply at org, domain, service, or repo level |
| **Sensing** | Automatic detection of overlap between initiatives |
