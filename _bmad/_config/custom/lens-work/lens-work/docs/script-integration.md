# lens-work Script Integration Reference

**Module:** lens-work v4.0  
**Policy:** All git operations use direct GitHub/Azure DevOps REST API calls with PAT authentication. The `gh` CLI is never required.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/create-pr.py` | Create a PR between any two branches via REST API |
| `scripts/store-github-pat.py` | Secure PAT setup into environment (run outside AI chat) |

## PAT Resolution Order

`create-pr.py` resolves authentication in this order:

1. `GITHUB_PAT` environment variable
2. `GH_TOKEN` environment variable
3. `profile.yaml` (in `.lens/personal/`)
4. URL-only fallback (manual PR creation instructions provided)

## PR Creation

`create-pr.py` creates PRs between any two branches:

```bash
# Bash
uv run lens.core/_bmad/lens-work/scripts/create-pr.py \
  --source-branch "${phase_branch}" \
  --target-branch "${audience_branch}" \
  --title "[PHASE] ${initiative_id} — Phase Complete" \
  --body "Phase complete with artifacts committed to ${phase_branch}."
```

```powershell
**Features:**
- Uses GitHub (or Azure DevOps) REST API directly
- Supports provider-specific URL patterns
- Returns structured output for downstream workflow steps
- Falls back to manual instructions with the PR URL if no PAT is available

## Branch Promotion

## Workflow Integration Pattern

Phase-completing workflows invoke `create-pr` directly:

```yaml
# Workflow step pattern (in steps/*.md)
invoke: script
script: "${PROJECT_ROOT}/lens.core/_bmad/lens-work/scripts/create-pr.py"
params:
  source_branch: ${phase_branch}
  target_branch: ${audience_branch}
  title: "[PHASE] ${initiative.id} — Phase Complete"
  body: "Phase complete. Artifacts committed."
```

## Policy: Never Use gh CLI

- PR creation → `create-pr.py`
- PAT management → `store-github-pat.py` (setup only, run by user outside AI chat)
- All API access → GitHub/Azure DevOps REST API directly
- No `gh`, `az`, or other external CLIs required at runtime

## Next Steps

1. Complete `businessplan`, `techplan`, and `finalizeplan` PR script integration.
2. Run end-to-end workflow testing from `preplan` through `finalizeplan` and the `/dev` handoff.
3. Verify PAT configuration in `profile.yaml` or environment.
4. Keep user-facing documentation aligned with the script-based PR policy.