# Generate Enforcement Workflows

## What Success Looks Like

CrisWeber has working GitHub Actions workflow files that run Lens Core rule validation on PRs or pushes. The workflows are correct, runnable, and target the right rules. The generated files follow the canonical `lens.core/` structure. Running the generation twice produces the same output.

## Your Approach

**Read the workflow template first.** Load `github-templates/workflows.md` from the sanctum. This is your canonical base — don't invent workflow structure from scratch.

**Gather configuration inputs.** Before generating, confirm:
- Which rules should the workflow enforce? (default: all rules in `rules-core.md`)
- What GitHub event triggers it? (default: `pull_request` + `push` to main/release branches)
- What's the target directory for the generated workflow file?
- Should the workflow block merges on failure (strict) or only warn (advisory)? Check BOND.md governance mode.

**Check for existing workflows.** List `.github/workflows/` before writing. If a Lens Core enforcement workflow already exists:
- If it matches the template → report already compliant, skip
- If it exists but is outdated → show diff, ask before overwriting
- If it doesn't exist → generate it

**Substitute into template.** Fill in:
- `{trigger-events}` — the GitHub events that activate the workflow
- `{rules-list}` — formatted list of rules to enforce
- `{fail-behavior}` — `exit 1` (strict) or `echo warning` (advisory)
- `{workflow-name}` — descriptive name for the workflow run

**Validate the generated YAML.** Before presenting it, verify:
- Valid YAML structure (correct indentation, no duplicate keys)
- The `on:` block is valid GitHub Actions syntax
- No references to non-existent scripts or paths

**Show before writing.** Display the complete generated file and confirm before writing to disk.

## Output Format

```yaml
# Generated: YYYY-MM-DD
# Rule target: [rule set name]
# Trigger: [events]
# Mode: [strict | advisory]

name: Lens Core Enforcement

on:
  pull_request:
    branches: [main, release/**]
  push:
    branches: [main]

jobs:
  validate-workspace:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # ... enforcement steps
```

## Memory Integration

Log to `enforcement-log/YYYY-MM-DD.md`. If the workflow template was modified or extended during this session, update `github-templates/workflows.md` in the sanctum.

## Wrapping Up

After generating, note that the workflow must be committed to take effect. Offer to validate the `.github/` structure after the workflow is committed.

## After the Session

Log generated workflow paths to `enforcement-log/YYYY-MM-DD.md`. Update MEMORY.md if this surfaced any workspace-specific constraints on workflow structure.
