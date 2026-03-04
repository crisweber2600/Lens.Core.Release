---
name: onboarding
description: Create profile + run bootstrap
agent: "@lens/discovery"
trigger: '@lens onboard or @lens-work onboard'
category: utility
first_run: true
---

# Onboarding Workflow

**Purpose:** Create user profile and bootstrap TargetProjects for new team members.

---

## Security Guardrails — MANDATORY

These rules are **non-negotiable**. Violating any of them leaks secrets or
personal data into the LLM context window.

### NEVER DO

| Prohibited action | Why | What to do instead |
|---|---|---|
| `Get-Content` / `cat` / `read_file` on any file under `personal/` | Exposes PATs, profile PII | Use `Test-Path` / `file_exists()` to check existence only |
| `Select-String` / `grep` for `token`, `pat`, `ghp_` in any file | Exposes secrets | Just check env var existence |
| `Get-Content` / `cat` / `read_file` on PAT storage scripts | Pulls script source into context needlessly | The scripts are self-documenting; tell the user to run them |
| Direct `git clone` of target repos | May fail without auth; exposes enterprise URLs | Always delegate to `discovery.repo-reconcile` (Step 5) |
| Reading env var **values** (e.g. `$env:GITHUB_PAT`, `echo $GH_TOKEN`) | Prints the token | Use `env_exists()` or `Test-Path Env:\GITHUB_PAT` (boolean only) |
| Printing or logging any credential value | Puts secrets in chat | Report only "configured" / "not configured" |

### ALWAYS DO

- Use **existence checks only**: `file_exists()`, `Test-Path`, `dir_exists()`
- Use **`env_exists()`** (not `env()`) for environment variable detection
- Delegate repo cloning to `discovery.repo-reconcile` — never run `git clone` directly
- When verifying the PAT script ran, check only: `env_exists("GITHUB_PAT")` or `env_exists("GH_ENTERPRISE_TOKEN")`
- If a step needs file contents (e.g. repo-inventory.yaml), it is explicitly
  marked with `load_yaml()` in the pseudocode. If a file is NOT loaded in
  the pseudocode, do NOT read it.

---

## Execution Sequence

### 1. Welcome

```
🔭 Welcome to LENS Workbench!

I'm LENS, your setup guide. I'll help you:
1. Create your profile
2. Set up your TargetProjects

This takes about 3-5 minutes. Let's get started!
```

### 2. Create Profile

```yaml
output: |
  📝 Creating your profile from git config...

name = git_config("user.name")
email = git_config("user.email")

output: |
  Using: ${name} <${email}>

# Load domains from repo inventory
inventory = load_yaml("_bmad-output/lens-work/repo-inventory.yaml")
domains = []
for repo in inventory.repos.matched:
  domain = repo.domain
  if domain not in domains:
    domains.append(domain)

# ── Detect GitHub domains from repo inventory ──────────────────────────
github_domains = set()
for repo in inventory.repos.matched:
  if repo.remote:
    if "github.com/" in repo.remote:
      github_domains.add("github.com")
    elif "github" in repo.remote:
      match = re.match(r"https?://([^/]+)/", repo.remote)
      if match:
        github_domains.add(match.group(1))

github_domains = sorted(list(github_domains))

# ── PAT detection: existence-only checks ────────────────────────────────
# SECURITY: Only test whether env vars EXIST.
# NEVER read, print, or store PAT values — that would expose secrets
# in the LLM context window.
#
# Lookup order (matches promote-branch scripts):
#   github.com:  GITHUB_PAT -> GH_TOKEN
#   enterprise:  GH_ENTERPRISE_TOKEN -> GH_TOKEN

covered_domains = []
uncovered_domains = []

for domain in github_domains:
  if domain == "github.com":
    if env_exists("GITHUB_PAT") or env_exists("GH_TOKEN"):
      covered_domains.append(domain)
      continue
  else:
    if env_exists("GH_ENTERPRISE_TOKEN") or env_exists("GH_TOKEN"):
      covered_domains.append(domain)
      continue
  uncovered_domains.append(domain)

# Report what was found
if covered_domains.length > 0:
  output: |
    
    GitHub PAT Status
    
    Already configured (environment variable):
  for domain in covered_domains:
    output: "  [OK] ${domain}"

all_pats_covered = (uncovered_domains.length == 0)

if all_pats_covered:
  output: |
    
    All ${len(github_domains)} GitHub domain(s) have PATs configured.
    Skipping PAT setup.
  pat_choice = "N"

# ── Profile prompt ──────────────────────────────────────────────────────
output: |
  
  **Profile Setup**
  
  What's your role?
  [1] Developer
  [2] Tech Lead
  [3] Architect
  [4] Product Owner
  [5] Scrum Master
  
  What domain/team do you work on?
for i, domain in enumerate(domains):
  output: "[${i+6}] ${domain}"
output: "[${len(domains)+6}] all (full access to all domains)"

if not all_pats_covered:
  output: |
    
    Set up GitHub PAT now?
    [Y]es - I'll run the secure script in my terminal
    [N]o  - Skip for now (you can run it anytime later)
    
    Enter three values separated by space (role domain pat):
    Example: "3 ${len(domains)+6} Y" = Architect + all domains + set up PAT
else:
  output: |
    
    Enter two values separated by space (role domain):
    Example: "3 ${len(domains)+6}" = Architect + all domains

user_input = prompt_user()
parts = user_input.split()
role = parts[0]
scope_choice = parts[1]
if not all_pats_covered:
  pat_choice = parts[2] if len(parts) > 2 else "N"

if scope_choice == str(len(domains)+6):
  scope = "all"
else:
  scope = domains[int(scope_choice) - 6]

if not all_pats_covered and uncovered_domains.length > 0:
  output: |
    
    GitHub Personal Access Tokens Setup
    
    SECURITY WARNING:
    PATs should NEVER be entered into Copilot, Claude, or any LLM chat.
    
    Missing PATs for ${len(uncovered_domains)} domain(s):
  for domain in uncovered_domains:
    output: "  [!!] ${domain}"

  output: |
    
    You can provide PATs via environment variables:
      github.com  -> set GITHUB_PAT or GH_TOKEN
      enterprise  -> set GH_ENTERPRISE_TOKEN or GH_TOKEN
    
    Or run the secure storage script (sets environment variables automatically).

if not all_pats_covered and pat_choice.lower() in ["y", "yes"] and uncovered_domains.length > 0:
  output: |
    
    Perfect! Please copy and run this command in a NEW TERMINAL WINDOW:
    
    Copy this entire command:
    
    cd "${PROJECT_ROOT}" && bash _bmad/lens-work/scripts/store-github-pat.sh
    
    On Windows with PowerShell:
    cd "${PROJECT_ROOT}"; .\\_bmad\\lens-work\\scripts\\store-github-pat.ps1
    
    The script will:
    - Run outside of LLM context for security
    - Prompt for PAT for each domain
    - Set environment variables (GITHUB_PAT / GH_ENTERPRISE_TOKEN)
    - Verify the env vars were stored correctly
    
    **Send "Continue" when ready...**
  
  wait_for_user = prompt_user()
  
  # Check if env vars were set by the script
  # SECURITY: existence check ONLY — do NOT read or print values
  env_ok = False
  for domain in uncovered_domains:
    if domain == "github.com":
      if env_exists("GITHUB_PAT") or env_exists("GH_TOKEN"):
        env_ok = True
    else:
      if env_exists("GH_ENTERPRISE_TOKEN") or env_exists("GH_TOKEN"):
        env_ok = True
  if env_ok:
    output: "PAT environment variables detected! Continuing with onboarding..."
  else:
    output: "No PAT env vars detected. You can set them later by running the script."
    output: "(Do NOT attempt to read or search for credential values — security risk.)" 
elif not all_pats_covered and pat_choice.lower() not in ["y", "yes"] and uncovered_domains.length > 0:
  output: |
    
    Skipping PAT setup. You can configure PATs anytime:
    
    Option 1 — environment variables (recommended for CI):
      export GITHUB_PAT=ghp_...          # github.com
      export GH_ENTERPRISE_TOKEN=ghp_... # enterprise
    
    Option 2 — secure storage script (sets env vars for you):
      bash _bmad/lens-work/scripts/store-github-pat.sh
    
    (from project root directory)

# REQ-2: Question mode preference prompt
output: |
  
  **Question Mode**
  
  How would you like to answer phase questions?
  [1] Interactive (guided chat — recommended)
  [2] Batch MD (single markdown file per phase)

qm_input = prompt_user()
if qm_input.strip() == "2":
  question_mode = "batch"
else:
  question_mode = "interactive"

# REQ-3: Tracker preference prompt
output: |
  
  **Work Item Tracker**
  
  What work item tracker do you use?
  [1] Jira
  [2] Azure DevOps
  [3] None

tracker_input = prompt_user()
if tracker_input.strip() == "1":
  tracker = "jira"
  output: |
    Jira base URL (optional):
    Example: https://mycompany.atlassian.net
    Press Enter to skip.
  jira_url_input = prompt_user()
  jira_base_url = jira_url_input.strip() if jira_url_input.strip() else null
elif tracker_input.strip() == "2":
  tracker = "azure-devops"
  jira_base_url = null
  output: |
    Azure DevOps organization name (required for MCP sync):
    Example: my-org
  ado_org_input = prompt_user()
  ado_organization = ado_org_input.strip() if ado_org_input.strip() else null
  output: |
    Azure DevOps project name (required for MCP sync):
    Example: my-project
  ado_proj_input = prompt_user()
  ado_project = ado_proj_input.strip() if ado_proj_input.strip() else null
else:
  tracker = "none"
  jira_base_url = null
  ado_organization = null
  ado_project = null

# REQ-SOURCE: Source repo branch configuration
# Populate source_repos in governance-setup.yaml so the background
# freshness preflight (step 4c) knows which branches to track.
gov_setup_path = "_bmad-output/lens-work/governance-setup.yaml"
if file_exists(gov_setup_path):
  gov_setup = load_yaml(gov_setup_path)

  # Only prompt if source_repos section is missing (first-time or pre-upgrade)
  if not gov_setup.get("source_repos"):
    output: |

      **Source Repository Branches**

      The BMAD system checks whether your local clones of bmad.lens.release
      and bmad.lens.copilot (.github) are up to date.  Confirm the branches
      you want to track for updates:

    # Detect current branch from clone if it exists
    default_release_branch = "release/4.5"
    if dir_exists("bmad.lens.release") and is_git_repo("bmad.lens.release"):
      detected = git_current_branch("bmad.lens.release")
      if detected:
        default_release_branch = detected

    release_branch_input = prompt_user("bmad.lens.release branch [${default_release_branch}]: ")
    release_branch = release_branch_input.strip() if release_branch_input.strip() else default_release_branch

    copilot_branch_input = prompt_user(".github (bmad.lens.copilot) branch [main]: ")
    copilot_branch = copilot_branch_input.strip() if copilot_branch_input.strip() else "main"

    # Detect remote URLs from existing clones
    release_url = "https://github.com/crisweber2600/bmad.lens.release"
    copilot_url = "https://github.com/crisweber2600/bmad.lens.copilot"
    if dir_exists("bmad.lens.release") and is_git_repo("bmad.lens.release"):
      detected_url = git_remote_url("bmad.lens.release", "origin")
      if detected_url:
        release_url = detected_url
    if dir_exists(".github") and is_git_repo(".github"):
      detected_url = git_remote_url(".github", "origin")
      if detected_url:
        copilot_url = detected_url

    # Write source_repos and source_sync to governance-setup.yaml
    gov_setup.source_repos = {
      lens_release: {
        local_path: "bmad.lens.release",
        remote_url: release_url,
        branch: release_branch,
        role: "module-source"
      },
      lens_copilot: {
        local_path: ".github",
        remote_url: copilot_url,
        branch: copilot_branch,
        role: "ide-integration"
      }
    }
    gov_setup.source_sync = { ttl: 3600 }
    save(gov_setup, gov_setup_path)

    output: |
      ✅ Source repo tracking configured:
        bmad.lens.release → origin/${release_branch}
        .github (copilot)  → origin/${copilot_branch}

profile = {
  name: name,
  email: email,
  role: roles[role],
  scope: scope,
  created_at: now(),
  preferences: {
    communication_style: "professional",
    auto_fetch: true,
    question_mode: question_mode,  # REQ-2
    tracker: tracker,  # REQ-3
    jira_base_url: jira_base_url if tracker == "jira" and jira_base_url else null,  # REQ-3
    ado_organization: ado_organization if tracker == "azure-devops" and ado_organization else null,  # ADO MCP
    ado_project: ado_project if tracker == "azure-devops" and ado_project else null  # ADO MCP
  }
}

# REQ-4
# ANTI-PATTERN: Do NOT create profiles/*.yaml files.
# User preferences go ONLY in: personal/profile.yaml
# Team roster info goes in the GOVERNANCE REPO: roster/{name}.yaml
# The profiles/ directory must NOT exist.
# The roster/ directory must NOT exist inside _bmad-output/lens-work/.

# Save personal profile (local/gitignored)
save(profile, "_bmad-output/lens-work/personal/profile.yaml")

# Resolve governance repo root from module.yaml
module = load_yaml("_bmad/lens-work/module.yaml")
governance_root = module.outputs.governance_repo_root  # TargetProjects/lens/lens-governance

# Verify governance repo is cloned
if not dir_exists(governance_root) or not is_git_repo(governance_root):
  output: |
    ⚠️  Governance repo not cloned at ${governance_root}.
    Running check-repos to clone it before saving roster entry...
  run_workflow("check-repos", repo="bmad.lens.governance")

# Create roster entry in the GOVERNANCE REPO (committed directly to default branch, no PR required)
# Per governance rules: roster updates bypass PR and commit directly to the default branch
roster_entry = {
  name: name,
  email: email,
  role: roles[role],
  onboarded_at: now(),
  repos_initiated: [],  # Populated when user runs new-* commands
  stats: {
    initiatives_started: 0,
    initiatives_completed: 0,
    last_active: now()
  }
}
roster_path = "${governance_root}/roster/${sanitize(name)}.yaml"
save(roster_entry, roster_path)

# Commit directly to default branch (no PR for roster updates)
# Resolve the default branch dynamically from the governance repo
shell: |
  cd "${governance_root}"
  default_branch=$(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@')
  git config user.name "${name}"
  git config user.email "${email}"
  git add roster/${sanitize(name)}.yaml
  git commit -m "onboard: add ${name} to roster"
  git push origin HEAD:${default_branch}
output: "✅ Roster entry committed to governance repo"
```

### 3. Determine Bootstrap Scope

```yaml
if scope == "all":
  bootstrap_scope = "full"
  output: "Will bootstrap all repos from service map"
else:
  bootstrap_scope = scope
  output: "Will bootstrap repos for ${scope}"
```

### 3a. Ensure TargetProjects Directory <!-- REQ-5 -->

```yaml
# REQ-5: Auto-create TargetProjects directory before discovery
# Derives the target-projects parent path from governance-setup.yaml
# (or falls back to repo-inventory.yaml).
# Idempotent — no error if directory already exists.

gov_setup_path = "_bmad-output/lens-work/governance-setup.yaml"
if file_exists(gov_setup_path):
  gov_setup = load_yaml(gov_setup_path)
  # e.g. "TargetProjects/lens/lens-governance" → "TargetProjects/lens"
  target_path = dirname(gov_setup.repo.local_path)
else:
  # Fallback: derive from repo-inventory if available
  inventory_path = "_bmad-output/lens-work/repo-inventory.yaml"
  if file_exists(inventory_path):
    inv = load_yaml(inventory_path)
    target_path = inv.target_projects_root or "TargetProjects"
  else:
    target_path = "TargetProjects"

shell: mkdir -p "${target_path}"

output: |
  📂 TargetProjects directory ensured: ${target_path}
```

### 4. Run Discovery

```yaml
invoke: discovery.repo-discover
params:
  scope: bootstrap_scope

# Creates:
#   - _bmad-output/lens-work/repo-inventory.yaml (canonical repo metadata)
#   - _bmad-output/lens-work/personal/personal-repo-inventory.yaml (local machine state)

output: |
  🔍 Discovery complete
  ├── Found: ${matched} repos
  ├── Missing: ${missing} repos
  └── Extra: ${extra} repos
```

### 5. Run Reconcile (Clone Missing)

```yaml
# SECURITY: NEVER run `git clone` directly from the chat context.
# Always delegate to the reconcile workflow, which handles auth,
# path resolution, and error recovery outside the LLM context.

if missing > 0:
  output: |
    Cloning ${missing} missing repos...
    This may take a few minutes.
  
  invoke: discovery.repo-reconcile
  
  # If reconcile fails (e.g. no PAT), report the count and suggest:
  # "Run the PAT storage script, then re-run @lens onboard."
  # Do NOT fall back to running git clone directly.
```

### 6. Completion

```
🎉 Onboarding Complete!

Profile: ${profile.name} (${profile.role})
Scope: ${profile.scope}

What's ready:
├── ✅ Profile created
├── ✅ ${cloned_count} repos cloned
└── ✅ PATs configured

Next steps:
├── Run #new-feature "your-feature" to start an initiative
├── Run @lens ST to see status anytime
└── Run @lens H for help

Welcome to the team! 🚀
```

---

## Storage Locations

### Personal Profile (Gitignored)
Your personal profile is stored locally in `_bmad-output/lens-work/personal/profile.yaml`:

```yaml
# _bmad-output/lens-work/personal/profile.yaml
name: Jane Smith
email: jane.smith@example.com
role: Developer
scope: payment-service
created_at: 2026-02-03T10:00:00Z
preferences:
  communication_style: professional
  auto_fetch: true
  question_mode: interactive  # REQ-2
  tracker: jira  # REQ-3
  jira_base_url: https://mycompany.atlassian.net  # REQ-3 (only if tracker is jira)
  # — OR for Azure DevOps —
  # tracker: azure-devops
  # ado_organization: my-org      # ADO MCP (only if tracker is azure-devops)
  # ado_project: my-project       # ADO MCP (only if tracker is azure-devops)
```

### GitHub PAT Environment Variables
Your GitHub Personal Access Tokens are stored in environment variables.

**Environment Variables:**

| Variable | Purpose |
|---|---|
| `GITHUB_PAT` | PAT for github.com |
| `GH_ENTERPRISE_TOKEN` | PAT for GitHub Enterprise |
| `GH_TOKEN` | Fallback for either (used by GitHub REST API) |

**Security Notes:**
- NEVER read or print env var values — existence checks only
- Used for GitHub API access (PRs, issues, CI status)
- Separate env vars for each GitHub domain type (SaaS and Enterprise)
- Can be regenerated anytime from GitHub settings
- The PAT setup script sets these automatically

**Generate Tokens:**
- GitHub.com (SaaS): https://github.com/settings/tokens
- GitHub Enterprise: https://{your-domain}/settings/tokens
- Required scopes: `repo`, `read:org`

### Roster Entry (Team Stats)
Your roster entry is stored in `_bmad-output/lens-work/roster/jane-smith.yaml`:

```yaml
# _bmad-output/lens-work/roster/jane-smith.yaml
name: Jane Smith
email: jane.smith@example.com
role: Developer
onboarded_at: 2026-02-03T10:00:00Z
repos_initiated: ["payment-service", "auth-service"]
stats:
  initiatives_started: 5
  initiatives_completed: 3
  last_active: 2026-02-10T15:30:00Z
```

### Personal Repo Inventory
Your machine-specific repo state is tracked in `_bmad-output/lens-work/personal/personal-repo-inventory.yaml`:

```yaml
# _bmad-output/lens-work/personal/personal-repo-inventory.yaml
scanned_at: "2026-02-10T15:00:00Z"
workstation: "DESKTOP-ABC123"

repos:
  - name: payment-service
    local_path: "D:/Projects/payment-service"
    current_branch: "feature/new-payment-api"
    has_uncommitted: true
    last_pull: "2026-02-10T09:00:00Z"
    
  - name: auth-service
    local_path: "D:/Projects/auth-service"
    current_branch: "main"
    has_uncommitted: false
    last_pull: "2026-02-09T16:30:00Z"
```
