# Audit Enforcement

## What Success Looks Like

CrisWeber has a clear, readable compliance trail covering the requested date range. They can see what was validated, what was generated, what failed, and how each issue was resolved — or that it remains unresolved. The audit output is useful both as a accountability record and as a signal for where governance needs attention.

## Your Approach

**Scope the audit.** Ask or confirm:
- Date range (default: last 30 days, or "all" for the full history)
- Focus area (full audit, validation-only, generation-only, or unresolved failures only)
- Output format (summary for a human, or full log for agent ingestion)

**Load the enforcement logs.** Read all `enforcement-log/YYYY-MM-DD.md` files within scope from the sanctum. If MEMORY.md has already-curated summaries relevant to the scope, load those too.

**Analyze before summarizing.** Before generating output:
- Count validations, generations, and other actions by type
- Identify violations that were reported but not resolved
- Flag recurring violations (same rule, multiple dates)
- Note gaps in the log (days with workspace activity but no enforcement log entry)

**Generate the audit report:**

```markdown
## Enforcement Audit Report
**Generated:** YYYY-MM-DD
**Period:** YYYY-MM-DD to YYYY-MM-DD
**Scope:** {what was audited}

### Summary

| Metric | Count |
|--------|-------|
| Validation runs | {n} |
| Rules evaluated | {n} |
| Pass | {n} |
| Fail | {n} |
| Auto-resolved | {n} |
| Unresolved | {n} |
| Files generated | {n} |
| Extensions registered | {n} |

### Unresolved Violations

{Table of violations still open — rule name, date first reported, last seen}

### Recurring Issues

{Rules that failed more than once — names and frequency}

### Recent Governance Activity

{Chronological summary of key enforcement actions}

### Coverage Gaps

{Days or periods where workspace changes occurred without enforcement coverage}
```

**Surface what matters.** An audit that lists everything is an audit that communicates nothing. Lead with unresolved violations and recurring patterns — those are the signals that need attention.

**Governance mode context.** If BOND.md shows advisory mode, note that unresolved violations are recommendations, not blockers. If strict, they are debt.

## Memory Integration

Log the audit run itself to `enforcement-log/YYYY-MM-DD.md`. If the audit surfaced new patterns, update MEMORY.md under "Patterns Observed".

## Wrapping Up

After presenting the report, offer:
1. To remediate any specific unresolved violation (pivot to validate-workspace)
2. To archive old enforcement logs if they're accumulating (compress entries older than 90 days into a summary)

## After the Session

Log the audit to `enforcement-log/YYYY-MM-DD.md`. If recurring patterns were confirmed, update MEMORY.md.
