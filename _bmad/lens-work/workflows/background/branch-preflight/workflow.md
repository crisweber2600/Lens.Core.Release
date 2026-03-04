---
name: branch-preflight
description: Automatic branch check and switch before any BMAD process
agent: system
trigger: "pre-execution (before all BMAD processes)"
category: background
priority: 0  # Highest priority - runs first
---

# Background Workflow: branch-preflight

**Purpose:** Ensures correct branch is checked out before ANY BMAD process starts. This is a mandatory pre-flight check that runs automatically.

---

## Trigger Conditions

| Trigger | Action |
|---------|--------|
| `bmad_process_start` | Check and switch to correct branch |
| `workflow_start` | Validate branch before workflow execution |
| `command_invocation` | Check branch before any command |
| `initiative_change` | Switch branch when changing initiatives |
| `phase_transition` | Update branch for new phase |

---

## Execution Steps

### 1. Git Repository Check

```yaml
# Verify we're in a git repository
if not git_repo:
  if bmad_control_repo_expected:
    error: "Not in a BMAD control repository"
    suggest: "Navigate to your BMAD control repo"
    exit: 1
  else:
    # Non-git workflow, skip branch check
    continue: true
```

### 2. Fetch Latest

```yaml
# Always fetch to ensure we have latest remote branches
git fetch --all --quiet --prune

# Get current branch
current_branch = git rev-parse --abbrev-ref HEAD
log: "Current branch: ${current_branch}"
```

### 3. Load State & Determine Context

```yaml
state = load("_bmad-output/lens-work/state.yaml")

# Extract context
active_initiative = state.active_initiative || null
current_phase = state.current_phase || null
workflow_status = state.workflow_status || "idle"
active_track = state.active_track || null

# Log context
log_context:
  initiative: ${active_initiative}
  phase: ${current_phase}
  status: ${workflow_status}
  track: ${active_track}
```

### 4. Determine Expected Branch

```yaml
# Branch determination logic
if active_initiative == null:
  # No active initiative - use default branch
  expected_branch = get_default_branch()
  context: "no_initiative"

elif workflow_status == "running" && current_phase != null:
  # Active workflow - use phase branch
  audience = get_phase_audience(current_phase)  # From lifecycle.yaml

  if audience == "base":
    expected_branch = initiative_root
  else:
    expected_branch = "${initiative_root}-${audience}-${current_phase}"
  context: "active_workflow"

elif current_phase != null:
  # Between workflows - use audience branch
  audience = get_phase_audience(current_phase)

  if audience == "base":
    expected_branch = initiative_root
  else:
    expected_branch = "${initiative_root}-${audience}"
  context: "audience_level"

else:
  # Initiative exists but no phase - use root
  expected_branch = initiative_root
  context: "initiative_root"

log: "Expected branch: ${expected_branch} (${context})"
```

### 4a. Governance Periodic Pull

Before any workflow runs, pull the latest `main` from the governance repo if the
configured TTL has elapsed. This ensures every session sees the latest constitutions,
roster entries, and policies without requiring a manual `@lens sync`.

```yaml
# Resolve config
module = load_yaml("_bmad/lens-work/module.yaml")
governance_root = module.outputs.governance_repo_root
ttl_seconds = module.git.governance_sync_ttl  # default 900
marker_file = "${governance_root}/.last-governance-pull"

# Only run if governance repo is cloned
if dir_exists(governance_root) and is_git_repo(governance_root):

  last_pull_epoch = 0
  if file_exists(marker_file):
    last_pull_epoch = int(read_file(marker_file).strip())

  now_epoch = unix_timestamp()
  seconds_since_pull = now_epoch - last_pull_epoch

  if seconds_since_pull >= ttl_seconds:
    log: "Governance repo TTL exceeded (${seconds_since_pull}s >= ${ttl_seconds}s) — pulling origin/main"
```

```bash
    git -C "${governance_root}" fetch origin main --quiet --prune
    git -C "${governance_root}" merge --ff-only origin/main --quiet 2>&1
```

```yaml
    if pull_succeeded:
      write_file(marker_file, str(unix_timestamp()))
      log: "Governance repo updated from origin/main"
    else:
      # Non-fatal: warn and continue — local copy may still be usable
      warn: |
        ⚠️  Could not fast-forward governance repo from origin/main.
        Local copy may be stale.  Run '@lens sync' to investigate.
  else:
    log: "Governance repo pull skipped (${seconds_since_pull}s < ${ttl_seconds}s TTL)"
```

---

### 4b. Governance Write Guard

Before executing any command that will write to the governance repo local path,
verify the governance repo is cloned and on a valid branch.

```yaml
# Resolve governance root from module.yaml
module = load_yaml("_bmad/lens-work/module.yaml")
governance_root = module.outputs.governance_repo_root  # TargetProjects/lens/lens-governance

if pending_write_targets_path(governance_root):

  # Governance repo must exist
  if not dir_exists(governance_root) or not is_git_repo(governance_root):
    error: |
      ❌ Governance repo not cloned at ${governance_root}.
      Run '@lens check-repos' first to clone bmad.lens.governance.
    exit: 1

  # Governance repo must be on a universal/* branch or main
  governance_branch = git_current_branch(governance_root)

  if not (governance_branch == "main" or governance_branch.startswith("universal/")):
    error: |
      ❌ Governance write blocked.

      You are attempting to write governance data (constitutions, roster, or
      policies) but the governance repo is on branch: ${governance_branch}

      Governance writes must happen on a 'universal/{slug}' branch in
      ${governance_root}.

      Steps to fix:
        cd ${governance_root}
        git checkout -b universal/{your-change-slug}
      Then retry your command.
    exit: 1

  log: "Governance repo on valid branch: ${governance_branch}"
```

### 4c. Module Source Freshness Check

Before any workflow runs, check whether the `bmad.lens.release` and `.github`
(bmad.lens.copilot) clones are up to date with their tracked remote branches.
This uses a TTL-based marker file (same pattern as step 4a) so the check only
runs periodically, not on every single invocation.

```yaml
# Load source repo config from governance-setup.yaml (may not exist on fresh installs)
if not file_exists("_bmad-output/lens-work/governance-setup.yaml"):
  log: "governance-setup.yaml not found — skipping freshness check"
  continue: true

gov_setup = load_yaml("_bmad-output/lens-work/governance-setup.yaml")
source_repos = gov_setup.source_repos || null
source_ttl = (gov_setup.source_sync || {}).ttl
if source_ttl == null:
  source_ttl = 3600  # default 1 hour

# Skip entirely if source_repos not configured (pre-upgrade control repos)
if source_repos == null:
  log: "source_repos not configured in governance-setup.yaml — skipping freshness check"
  continue: true
```

```yaml
# TTL gate — store marker in gitignored personal folder to avoid dirty working tree
marker_file = "_bmad-output/lens-work/personal/.last-source-check"
last_check_epoch = 0

if file_exists(marker_file):
  last_check_epoch = int(read_file(marker_file).strip())

now_epoch = unix_timestamp()
seconds_since_check = now_epoch - last_check_epoch

# Also skip if suppressed for this session (user chose [I] earlier)
if session_var("source_check_suppressed") == true:
  log: "Source freshness check suppressed for this session"
  continue: true

if seconds_since_check < source_ttl and source_ttl > 0:
  log: "Source freshness check skipped (${seconds_since_check}s < ${source_ttl}s TTL)"
  continue: true

log: "Source freshness TTL exceeded (${seconds_since_check}s >= ${source_ttl}s) — checking clones"
```

```yaml
# Fetch and compare each source repo
behind_repos = []

for repo_key, repo_config in source_repos.items():
  local_path = repo_config.local_path
  branch = repo_config.branch
  role = repo_config.role

  # Skip if clone doesn't exist (not yet set up)
  if not dir_exists(local_path) or not is_git_repo(local_path):
    log: "Source repo ${repo_key} not found at ${local_path} — skipping"
    continue
```

```bash
  # Fetch the tracked branch
  git -C "${local_path}" fetch origin "${branch}" --quiet 2>&1
```

```yaml
  if fetch_failed:
    # Non-fatal: network may be unavailable
    warn: "⚠️  Could not fetch ${repo_key} from origin/${branch}. Network may be unavailable."
    continue
```

```yaml
  # Count commits behind (YAML helper keeps value in workflow context)
  behind_count = git_commits_behind(local_path, "origin/" + branch)
```

```yaml
  if int(behind_count) > 0:
    behind_repos.append({
      key: repo_key,
      local_path: local_path,
      branch: branch,
      role: role,
      behind: int(behind_count)
    })
    log: "${repo_key}: ${behind_count} commits behind origin/${branch}"
  else:
    log: "${repo_key}: up to date with origin/${branch}"
```

```yaml
# If everything is current, record the check and move on
if len(behind_repos) == 0:
  write_file(marker_file, str(unix_timestamp()))
  log: "All source repos up to date"
  continue: true

# Build notification message
update_lines = []
for repo in behind_repos:
  label = repo.local_path
  if repo.role == "ide-integration":
    label = "${repo.local_path} (copilot)"
  update_lines.append("  ${label}: ${repo.behind} commits behind origin/${repo.branch}")

notify: |
  ⚠️  Module source update available

  ${join(update_lines, "\n")}

  [U] Update now  [S] Skip (re-check after TTL)  [I] Ignore for this session

choice = prompt_user("[U/S/I]", default="S")

if choice == "U":
  # Fall through to step 4d
  pass

elif choice == "I":
  set_session_var("source_check_suppressed", true)
  log: "Source freshness check suppressed for this session"
  continue: true

else:
  # [S] or default — write marker, skip update
  write_file(marker_file, str(unix_timestamp()))
  log: "Source update skipped — will re-check after TTL"
  continue: true
```

---

### 4d. Module Source Update

Triggered when the user selects **[U]** in step 4c. Pulls the latest changes
for each behind repo via fast-forward merge, then re-runs the module installer
to refresh deployed files (stubs, instructions, prompts).

```yaml
update_results = []

for repo in behind_repos:
  local_path = repo.local_path
  branch = repo.branch
  repo_key = repo.key

  log: "Updating ${repo_key} — merging origin/${branch}..."
```

```bash
  # Fast-forward only — diverged clones need manual intervention
  git -C "${local_path}" merge --ff-only origin/"${branch}" --quiet 2>&1
```

```yaml
  if merge_succeeded:
```

```bash
    new_sha=$(git -C "${local_path}" rev-parse --short HEAD)
```

```yaml
    log: "✓ ${repo_key} updated to ${new_sha}"
    update_results.append({ key: repo_key, status: "updated", sha: new_sha })

  else:
    warn: |
      ⚠️  Could not fast-forward ${repo_key} from origin/${branch}.
      The local clone may have diverged.

      To resolve manually:
        cd ${local_path}
        git status
        git log --oneline HEAD..origin/${branch}

      The update for this repo was skipped.  Other repos will still be updated.
    update_results.append({ key: repo_key, status: "failed" })
```

```yaml
# Re-run installer if bmad.lens.release was updated
lens_release_updated = any(r.key == "lens_release" and r.status == "updated" for r in update_results)

if lens_release_updated:
  log: "Re-running module installer to refresh deployed files..."

  installer_path = "bmad.lens.release/_bmad/lens-work/_module-installer/installer.js"

  if file_exists(installer_path):
```

```bash
    # Run installer in update mode — refreshes prompts and instructions
    # even if they already exist (unlike initial install which skips existing)
    node -e "
      (async () => {
        try {
          const { install } = require('./${installer_path}');
          const installSucceeded = await install({
            projectRoot: process.cwd(),
            config: {},
            installedIDEs: ['github-copilot'],
            updateMode: true,
            logger: { log: console.log, warn: console.warn, error: console.error }
          });
          if (!installSucceeded) {
            process.exit(1);
          }
        } catch (err) {
          console.error(err);
          process.exit(1);
        }
      })();
    "
```

```yaml
    if install_succeeded:
      log: "✓ Module installer completed — deployed files refreshed"
    else:
      warn: "⚠️  Module installer encountered errors. Deployed files may be stale."
  else:
    warn: "⚠️  Installer not found at ${installer_path}. Deployed files were not refreshed."
```

```yaml
# Write marker file after update attempt
write_file(marker_file, str(unix_timestamp()))

# Summary
successful = [r for r in update_results if r.status == "updated"]
failed = [r for r in update_results if r.status == "failed"]

if len(successful) > 0:
  log: "✓ Updated: ${', '.join(r.key for r in successful)}"
if len(failed) > 0:
  warn: "⚠️  Failed: ${', '.join(r.key for r in failed)} — see warnings above"
```

### 5. Check for Uncommitted Changes

```yaml
# Check working tree status
if has_uncommitted_changes():
  # Determine severity
  if is_emergency_override():
    warn: "Uncommitted changes detected - emergency override active"
    stash_changes = true
  elif is_safe_command():
    # Commands like status, help don't need clean tree
    continue: true
  else:
    error: "Uncommitted changes detected"
    suggest: "Commit or stash changes before proceeding"
    show: git status --short
    exit: 1
```

### 6. Branch Switch Logic

```yaml
if current_branch != expected_branch:
  log: "Branch mismatch - need to switch"

  # Check if expected branch exists
  if branch_exists(expected_branch):
    # Stash if needed
    if stash_changes:
      stash_id = git stash push -m "Auto-stash by branch-preflight"
      log: "Changes stashed: ${stash_id}"

    # Switch branch
    git checkout ${expected_branch}

    if success:
      log: "Switched to: ${expected_branch}"

      # Pull latest
      git pull origin ${expected_branch} --quiet

      # Restore stash if needed
      if stash_id:
        git stash pop ${stash_id}
        log: "Stash restored"
    else:
      error: "Failed to switch branch"
      exit: 1

  elif auto_create_enabled():
    # Create branch from appropriate base
    base_branch = determine_base_branch(expected_branch)
    git checkout -b ${expected_branch} ${base_branch}
    git push -u origin ${expected_branch}
    log: "Created new branch: ${expected_branch}"

  else:
    error: "Expected branch does not exist: ${expected_branch}"
    suggest: "Run with --create-branch or create manually"
    exit: 1

else:
  log: "Already on correct branch: ${current_branch}"

  # Check if behind remote
  if is_behind_remote(current_branch):
    git pull origin ${current_branch} --quiet
    log: "Updated branch from remote"
```

### 7. Record Check

```yaml
# Log the preflight check
preflight_record:
  timestamp: now()
  process: ${BMAD_PROCESS_NAME}
  command: ${BMAD_COMMAND}
  branch_from: ${original_branch}
  branch_to: ${current_branch}
  status: "success"

append_to: "_bmad-output/lens-work/preflight-checks.jsonl"
```

---

## Configuration

```yaml
# In module.yaml or bmad config
branch_preflight:
  enabled: true                    # Master switch
  auto_switch: true                # Auto-switch branches
  auto_create: false               # Auto-create missing branches
  stash_uncommitted: false         # Stash changes if needed

  # Commands that don't require branch switch
  safe_commands:
    - help
    - status
    - config
    - version

  # Emergency override for critical situations
  emergency_override: false
```

---

## Integration Points

### 1. BMAD Command Wrapper

Every BMAD command should invoke this preflight check:

```bash
# bmad command wrapper
bmad() {
  # Run preflight check
  _bmad-output/lens-work/workflows/background/branch-preflight/run.sh

  # If preflight succeeds, run actual command
  if [ $? -eq 0 ]; then
    bmad-actual "$@"
  fi
}
```

### 2. Workflow Start Hook

```yaml
# In every workflow's start sequence
pre_execution:
  - branch-preflight  # Always runs first
  - state-sync
  - constitution-check
```

### 3. IDE Integration

```json
// VS Code tasks.json
{
  "tasks": [
    {
      "label": "BMAD Pre-flight",
      "type": "shell",
      "command": "${workspaceFolder}/_bmad/_config/custom/lens-work/scripts/run-preflight.ps1",
      "runOptions": {
        "runOn": "folderOpen"
      }
    }
  ]
}
```

---

## Error Handling

| Error | Action |
|-------|--------|
| Not in git repo | Block if BMAD control repo expected |
| Uncommitted changes | Block unless safe command or emergency |
| Branch doesn't exist | Offer to create or block |
| Network error on fetch | Warn but continue |
| Merge conflict on pull | Block and require manual resolution |

---

## Bypass Conditions

The preflight check can be bypassed only in these cases:

1. **Emergency Override** - Set in config by admin
2. **Safe Commands** - Read-only commands like help, status
3. **Non-Git Workflows** - Workflows that don't require git
4. **CI/CD Environment** - Detected via environment variables

---

_Background workflow integrated into BMAD core execution flow_