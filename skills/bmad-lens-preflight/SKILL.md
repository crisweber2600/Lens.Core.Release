---
name: bmad-lens-preflight
description: Validates Lens workspace and onboarding state. Use when user runs /preflight or wants to check workspace health before starting any workflow.
---

# bmad-lens-preflight

## Overview

Validates that the workspace is correctly configured and all Lens runtime dependencies are present before any workflow begins. Runs `preflight.py` against the three configured paths (`governance_repo_path`, `control_repo_path`, `target_projects_path`), presents check-by-check results, and produces a remediation report for any failures.

**Modes:**

- **Interactive** (default) — runs checks, presents results inline, pauses at failures for user acknowledgement.
- **Headless** (`--headless` / `-H`) — runs checks silently, outputs structured JSON summary, exits non-zero on any failure.

**The non-negotiable:** Zero lifecycle state mutation. Preflight must not change any feature, governance, or config state regardless of outcome. A failing preflight has the same observable footprint as a passing one — except the exit code.

**Args:** `[--headless|-H] [--json]`

## Conventions

- Bare paths resolve from the skill root.
- `{project-root}`-prefixed paths resolve from the project working directory.
- `light-preflight.py` is the frozen stub-level gate — it runs before this skill is invoked. Its exit-code interface (`exit 0` = proceed, `exit 1` = halt) must never be altered.
- `preflight.py` is the full validation engine owned by this skill.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml` and `{project-root}/_bmad/config.user.yaml` (root level and `lens` section). If config is missing, inform the user that the `lens-work` setup can configure the module at any time, and attempt to infer paths from the current workspace. Required config keys:

| Key | Default | Purpose |
|---|---|---|
| `governance_repo_path` | `{project-root}/TargetProjects/lens/lens-governance` | Path to the local governance repo root |
| `control_repo_path` | `{project-root}` | Path to the lens.core control repo root |
| `target_projects_path` | `{project-root}/TargetProjects` | Root path for target project clones |

## Validation

Run the full workspace validation:

```
python3 scripts/preflight.py \
  --governance-repo {governance_repo_path} \
  --control-repo {control_repo_path} \
  --target-projects {target_projects_path} \
  [--json]
```

If the script cannot execute (Python/uv unavailable), perform the checks directly:

1. Verify `{project-root}/_bmad/config.yaml` or `{project-root}/_bmad/config.user.yaml` exists.
2. Confirm `python3 --version` returns 3.12 or higher.
3. Confirm `uv --version` is callable.
4. Confirm `git --version` returns 2.40 or higher.
5. Confirm `gh --version` is callable.
6. Confirm `{governance_repo_path}` is a directory and contains `features/` and `constitutions/`.
7. Confirm `{project-root}/_bmad/lens-work/lifecycle.yaml` exists.
8. Confirm `{target_projects_path}` is a directory (warn if absent, do not fail — it may not be cloned yet).

## Presenting Results

Present each check as pass or fail with a concise reason. Group by category:

- **Config** — bmadconfig presence and structure
- **Runtime** — Python version, uv, Git version, gh
- **Governance repo** — path accessible, expected structure
- **Control repo** — lifecycle.yaml present, module directory intact
- **Target projects** — root path accessible (warn only)

If all checks pass: confirm readiness and return. No further action.

If any checks fail: present a remediation guide for each failed check. In interactive mode, offer to open the HTML remediation report (see below). In headless mode, output the JSON result and exit non-zero.

## Remediation Report

If failures are detected and the user is in interactive mode, generate an HTML remediation report at `{project-root}/skills/reports/preflight-report.html`. The report must include:

- One section per failed check with the check name, failure reason, and step-by-step remediation instructions.
- A summary banner (all-clear green or failure red) at the top.
- No embedded scripts or external resources — pure static HTML, safe to open from the filesystem.

Do not generate the HTML report in headless mode — JSON output is sufficient.

## Headless Output

In headless mode, output a JSON object to stdout:

```json
{
  "status": "pass" | "fail",
  "checks": [
    {"name": "...", "category": "...", "status": "pass" | "fail" | "warn", "reason": "..."}
  ],
  "summary": {"pass": N, "fail": N, "warn": N}
}
```

Exit 0 if `status` is `pass`, non-zero if `fail`.
