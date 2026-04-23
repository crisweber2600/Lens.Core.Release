# Memory Guidance

_This document defines the memory discipline for the Governance Enforcement Engine. Load it during Session Close and follow it before ending any session._

---

## Why Memory Matters More Here

This agent is the governance bedrock. Other agents read `rules-core.md` and `rules-extension-points.md` from this agent's sanctum. If your memory is incomplete or stale, the entire governance chain degrades silently. Your memory isn't just for you — it's the foundation others build on.

Every session that doesn't update the sanctum is a session where the next agent (and the next engineer) inherits a less accurate picture of the workspace.

---

## Session Log — Do This Every Session

Write a session log to `sessions/YYYY-MM-DD.md` before ending. Include:

```markdown
# Session Log — {YYYY-MM-DD}

## Summary
{One sentence: what happened in this session?}

## Actions Taken
{List every governance action: validations run, files generated, rules modified, extensions registered}

## Violations Found
{Rule violations surfaced — include rule ID and whether resolved or left open}

## Decisions Made
{Any explicit decisions with rationale — governance mode changes, waivers granted, rules added/modified}

## Open Items
{Anything unresolved or flagged for a future session}

## What I Learned
{Patterns observed, workspace nuances discovered, gaps in rules noticed}
```

Keep session logs as the raw record. They are not curated — they are the evidence.

---

## Enforcement Log — Required After Any Governance Action

Every time you validate, generate, register, or audit — append an entry to `enforcement-log/YYYY-MM-DD.md`:

```markdown
[{HH:MM}] {ACTION-TYPE}: {brief description}
  Result: {outcome — PASS / FAIL / GENERATED / REGISTERED}
  Files affected: {list if applicable}
  Notes: {anything the record needs to be useful in 6 months}
```

Action types: `VALIDATE`, `GENERATE-STUBS`, `GENERATE-WORKFLOW`, `DEFINE-RULES`, `REGISTER-EXTENSION`, `AUDIT`

The enforcement log is the audit trail. If it isn't there, governance didn't happen.

---

## MEMORY.md — Curated Intelligence

MEMORY.md is distilled from session logs. It should contain only what recurs or matters across sessions — not raw notes.

Update MEMORY.md when:
- A recurring violation pattern has been confirmed (more than once, same rule)
- A new workspace nuance was discovered that will affect future sessions
- A governance decision was made that should be context for all future reasoning
- A rule gap was found that isn't yet covered by any rule

**Prune MEMORY.md** when:
- A workspace condition no longer exists (don't keep notes about things that were fixed)
- An insight was superseded by a better understanding
- The file exceeds 200 lines — distill further or archive old sections

Do not fill MEMORY.md with things that can be re-derived from reading the workspace. MEMORY.md holds things you can't re-derive.

---

## sanctum Files to Check Each Session

Before closing, review:

| File | When to update |
|------|---------------|
| `BOND.md` | New workspace topology info, new preferences, new extensions |
| `CREED.md` | Mission drift (if what CrisWeber needs has evolved), new standing orders |
| `MEMORY.md` | Recurring patterns, governance decisions, rule gaps found |
| `rules-core.md` | Only with explicit confirmation — never silently |
| `rules-extension-points.md` | When a new extension was registered or an old one deactivated |
| `PERSONA.md` | Evolution log — if something changed about how you work |

---

## Log Maintenance

Enforcement logs accumulate. Don't let them become noise.

- Logs older than 90 days: compress into a monthly summary entry, then archive the daily files to `enforcement-log/archive/`
- Session logs older than 30 days: archive to `sessions/archive/` after curating insights to MEMORY.md
- Monthly: verify MEMORY.md remains under 200 lines

---

## Headless Mode Memory Discipline

When activated with `--headless`:
- No session log is written (no interactive session to record)
- Enforcement log entries ARE required — silent headless governance is no governance
- If the headless run surfaced something unexpected, write a brief session log anyway

---

## The Memory Test

Before closing, ask yourself:

1. If I were activated tomorrow with no memory of this session — would my sanctum give me enough context to understand what happened today and why?
2. Is the enforcement log complete enough that CrisWeber could audit what I did without asking me?
3. Did I notice anything about the workspace that isn't yet in my rules, MEMORY.md, or BOND.md?

If any answer is no — add what's missing before closing.
