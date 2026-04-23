# Generate .github Redirect Stubs

## What Success Looks Like

The `.github/` directory contains correct redirect stubs pointing to the canonical `lens.core/` paths for each workflow and prompt. Engineers who look in `.github/` are transparently redirected to the canonical source — they don't get confused about which copy is authoritative. Every generated stub is idempotent: running this capability twice produces the same output, not duplicates.

## Your Approach

**Gather inputs first.** Before generating anything, confirm:
- Which constructs need stubs? (workflows, prompts, or both)
- What is the canonical `lens.core/` root path relative to this workspace?
- What is the target stub naming convention (match canonical name exactly)?

If BOND.md has workspace topology notes, read them now.

**Check what already exists.** List `.github/workflows/` and `.github/prompts/` before generating any file. For each target stub:
- If it already exists and matches the template → report it as already compliant, skip
- If it exists but points to a wrong path → show the diff, ask for confirmation before overwriting
- If it doesn't exist → generate it

**Generate from template.** Use `github-templates/redirect-stub.md` from the sanctum. Substitute:
- `{stub-name}` — the canonical construct name
- `{canonical-path}` — relative path from stub location to the `lens.core/` canonical file
- `{stub-type}` — `workflow` or `prompt`

**Show before writing.** Unless in headless mode, show CrisWeber the generated stub and its target path before writing. One confirm covers a batch of stubs of the same type.

**Idempotency check.** The stub must reference the canonical path correctly and produce no side effects when the canonical file is executed. If the stub type is a GitHub workflow, ensure the redirect pattern won't trigger duplicate runs.

## Output Format

```
## Generated Redirect Stubs

### .github/workflows/
| Stub File | Points To | Status |
|-----------|-----------|--------|
| {stub-name}.yml | lens.core/{canonical-path} | ✅ Created |
| {stub-name}.yml | lens.core/{canonical-path} | ⚪ Already compliant |
| {stub-name}.yml | lens.core/{canonical-path} | ⚠️ Updated (see diff) |

### .github/prompts/
[same table]

### Files Written
[list of full paths created or updated]
```

## Memory Integration

Log all stub generations to `enforcement-log/YYYY-MM-DD.md`. If BOND.md doesn't yet have canonical path info, add it after this session.

## Wrapping Up

Remind CrisWeber that stubs are generated once; if the canonical path changes, stubs must be regenerated. Offer to validate the stub integrity after generation.

## After the Session

Log generated files to `enforcement-log/YYYY-MM-DD.md`. If canonical path structure was new information, record it in BOND.md under "Workspace Topology".
