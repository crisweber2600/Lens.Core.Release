# Shared Preflight

**Include with:** Reference this file from any prompt that needs preflight.

**Purpose:** Ensures all authority repos are synchronized and constitutional governance is resolved before workflow execution.

---

## Preflight Steps

### 1. Check Release Branch

Read the `bmad.lens.release` branch:
```bash
git -C bmad.lens.release branch --show-current
```

### 2. Determine Pull Strategy

Read `_bmad-output/lens-work/personal/.preflight-timestamp` as the last successful full preflight time (ISO 8601 UTC datetime).

Use branch-aware freshness windows:
- **If branch is `alpha`:** run full preflight when timestamp is missing or older than **1 hour**.
- **If branch is `beta`:** run full preflight when timestamp is missing or older than **3 hours**.
- **Otherwise:** run full preflight when timestamp is missing or older than **today** (daily cadence).

If full preflight is required, pull ALL authority repos:

```bash
git -C bmad.lens.release pull origin
git -C {governance-repo-path} pull origin   # path from governance-setup.yaml
```

If full preflight is not required, skip pulls and run presence + `.github` sync checks only.

### 3. Sync .github from Release Repo

On every preflight run, verify `.github/` completeness against `bmad.lens.release/.github/` and sync if files are missing. Also sync if release `.github/` changed during pull.

This check runs even when pull is skipped by timestamp.

If `bmad.lens.release/.github/` is missing, stop with an error.

If `.github/` is missing, create it and copy from release.

If any files are missing in local `.github/`, copy from release.

If pull detected changes under release `.github/`, copy from release.

After sync, keep prompt hygiene: `.github/prompts/` must only contain `lens-work*.prompt.md` files.

**PowerShell:**
```powershell
if (-not (Test-Path "bmad.lens.release/.github")) {
        throw "Missing authority folder: bmad.lens.release/.github"
}

if (-not (Test-Path ".github")) {
        New-Item -ItemType Directory -Path ".github" -Force | Out-Null
        Copy-Item -Recurse -Force "bmad.lens.release/.github/*" ".github/"
}

$missing = Get-ChildItem "bmad.lens.release/.github" -Recurse -File |
        Where-Object {
                $relative = $_.FullName.Substring((Resolve-Path "bmad.lens.release/.github").Path.Length).TrimStart('\\','/')
                -not (Test-Path (Join-Path ".github" $relative))
        }

$changed = git -C bmad.lens.release diff --name-only HEAD@{1} HEAD -- .github/ 2>$null

if ($missing.Count -gt 0 -or $changed) {
        Copy-Item -Recurse -Force "bmad.lens.release/.github/*" ".github/"
}

if (Test-Path ".github/prompts") {
        Get-ChildItem ".github/prompts" -File -Filter "*.prompt.md" |
                Where-Object { $_.Name -notlike "lens-work*.prompt.md" } |
                Remove-Item -Force
}
```

**Bash:**
```bash
if [ ! -d "bmad.lens.release/.github" ]; then
    echo "ERROR: Missing authority folder bmad.lens.release/.github"
    exit 1
fi

if [ ! -d ".github" ]; then
    mkdir -p .github
    cp -rf bmad.lens.release/.github/* .github/
fi

missing="$(cd bmad.lens.release && find .github -type f | while read -r f; do [ -f "../$f" ] || echo "$f"; done)"
changed="$(git -C bmad.lens.release diff --name-only HEAD@{1} HEAD -- .github/ 2>/dev/null || true)"

if [ -n "$missing" ] || [ -n "$changed" ]; then
    cp -rf bmad.lens.release/.github/* .github/
fi

if [ -d ".github/prompts" ]; then
    find .github/prompts -type f -name '*.prompt.md' ! -name 'lens-work*.prompt.md' -delete
fi
```

### Step 3b: Sync Agent Entry Points

On every preflight run, sync agent entry point files from the release repo to the workspace root. Copy each entry point file if it is missing or if the release version changed during pull.

This check runs even when the pull is skipped by timestamp.

**Bash:**
```bash
for entry_point in CLAUDE.md; do
    if [ -f "bmad.lens.release/$entry_point" ]; then
        changed="$(git -C bmad.lens.release diff --name-only HEAD@{1} HEAD -- "$entry_point" 2>/dev/null || true)"
        if [ ! -f "./$entry_point" ] || [ -n "$changed" ]; then
            cp "bmad.lens.release/$entry_point" "./$entry_point"
        fi
    fi
done
```

**PowerShell:**
```powershell
foreach ($entryPoint in @("CLAUDE.md")) {
    $src = "bmad.lens.release/$entryPoint"
    $dst = "./$entryPoint"
    if (Test-Path $src) {
        $changed = git -C bmad.lens.release diff --name-only HEAD@{1} HEAD -- $entryPoint 2>$null
        if (-not (Test-Path $dst) -or $changed) {
            Copy-Item -Force $src $dst
        }
    }
}
```

If any authority repo directory is missing, stop and report the failure.

**Exception for /onboard:** If missing repos are reported during onboarding, continue so the workflow can bootstrap/repair those repos.

### Step 4: Verify IDE Adapters

On every preflight run, check that IDE command adapters are installed. For Claude Code, the required adapter is `.claude/commands/`. If the directory is missing, run the installer in idempotent mode before proceeding.

This check runs even when pull is skipped by timestamp.

**Bash:**
```bash
if [ ! -d ".claude/commands" ]; then
    echo "[preflight] .claude/commands missing — running installer..."
    bash bmad.lens.release/_bmad/lens-work/scripts/install.sh --ide claude
fi
```

**PowerShell:**
```powershell
if (-not (Test-Path ".claude/commands")) {
    Write-Host "[preflight] .claude/commands missing — running installer..."
    bash bmad.lens.release/_bmad/lens-work/scripts/install.sh --ide claude
}
```

Note: If additional IDEs are active (Cursor, Codex), add equivalent checks as those adapters are introduced to the workspace.

### 5. Resolve and Enforce Constitution

Resolve constitutional governance before any workflow-specific logic runs.

```yaml
# Resolve constitutional context (initiative-aware when available, global fallback otherwise)
constitutional_context = invoke("constitution.resolve-context")

if constitutional_context.status == "parse_error":
        # Bootstrap workflows (for example /onboard, /new-domain) may not have
        # initiative-level context yet. Downgrade to advisory in that case.
        if constitutional_context.context_available == false:
                warning: "⚠️ Constitutional context unavailable during bootstrap. Continuing in advisory mode."
                constitutional_context.gate_mode = "advisory"
        else:
                FAIL("❌ Constitutional context parse error. Fix governance files before continuing.")

session.constitutional_context = constitutional_context

# Enforce hard-gate mode immediately when constitution requires it
if constitutional_context.gate_mode == "hard" and constitutional_context.preflight_status == "FAIL":
        FAIL("❌ Constitution hard gate failed during preflight. Resolve compliance issues before running this workflow.")

# Advisory mode never blocks, but must be surfaced to the user
if constitutional_context.gate_mode == "advisory" and constitutional_context.preflight_status == "WARN":
        warning: "⚠️ Constitution advisory warnings detected. Continue with care and address warnings in phase outputs."
```

All downstream workflow decisions MUST follow `session.constitutional_context`.

### 6. Update Timestamp

After a successful full preflight, write the current UTC timestamp (ISO 8601 datetime) to `_bmad-output/lens-work/personal/.preflight-timestamp`.

---

## Authority Repos

| Repo | Purpose |
|------|---------|
| `bmad.lens.release` | Release module with workflows, agents, prompts |
| `{governance-repo-path}` | Governance settings (from `_bmad-output/lens-work/governance-setup.yaml`) |

## Synced Content

| Source | Destination | Content |
|--------|-------------|---------|
| `bmad.lens.release/.github/` | `.github/` | Copilot agents, prompts, instructions |
| `bmad.lens.release/CLAUDE.md` | `./CLAUDE.md` | Claude Code agent entry point |
