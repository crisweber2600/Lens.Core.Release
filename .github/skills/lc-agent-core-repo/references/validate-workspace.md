# Validate Workspace Structure

## What Success Looks Like

CrisWeber has a complete, structured compliance report. They know exactly which rules pass, which fail, and what to do about each failure. The report is actionable, not just informational — every violation comes with a clear remediation path. No violation is reported without context for why the rule exists.

## Your Approach

**Before you begin**, load `rules-core.md` and `rules-extension-points.md` from the sanctum. You cannot validate what you don't know.

**Gather workspace state** first. Walk the workspace from `{project-root}/` and build a mental model of what exists before applying any rules. This prevents the mistake of reporting a violation before checking whether the artifact exists elsewhere.

**Evaluate rule by rule.** For each rule in `rules-core.md` and registered extensions in `rules-extension-points.md`:
1. State the rule
2. Check workspace against it
3. Mark pass / fail / not-applicable (with reason)
4. For failures: provide a remediation step

**Structure the report** as:

```
## Workspace Compliance Report
**Date:** YYYY-MM-DD
**Scope:** [what was evaluated — full workspace or targeted paths]
**Governance Mode:** [strict / advisory / audit-only from BOND.md]

### Structure Diagram
[ascii or inline representation of current workspace layout]

### Rule Results

| Rule | Status | Notes |
|------|--------|-------|
| {rule-name} | ✅ PASS | {optional context} |
| {rule-name} | ❌ FAIL | {what's wrong + how to fix} |
| {rule-name} | ⚪ N/A | {why not applicable} |

### Remediation Steps
[Numbered list of actions to bring workspace into compliance, in priority order]

### Rule Gaps Noticed
[Any structural concerns observed that aren't yet covered by a rule — these are gifts to future governance]
```

**Governance mode matters.** Check BOND.md:
- `strict` — present failures as blockers requiring remediation
- `advisory` — present failures as recommended changes
- `audit-only` — validate and report but explicitly note no action is being taken

**Explain before you enumerate.** If CrisWeber is still learning the rules, open each failed rule with a one-line explanation of why it exists before describing the violation.

## Memory Integration

After validation:
- Append a summary entry to `enforcement-log/YYYY-MM-DD.md`
- If new rule gaps were found, note them in MEMORY.md under "Patterns Observed"
- If any rules were waived (N/A), confirm with BOND.md and document the waiver if it was deliberate

## Wrapping Up

Offer CrisWeber the option to immediately act on any remediations — you can generate the missing files or stubs if they confirm. Don't auto-generate; ask first.

## After the Session

Log the validation to `enforcement-log/YYYY-MM-DD.md` before session close. Update MEMORY.md if any recurring pattern was confirmed.
