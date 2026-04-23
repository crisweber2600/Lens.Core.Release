# Define Core Rules

## What Success Looks Like

The Lens Core ruleset is documented, authoritative, and accessible. `rules-core.md` in the sanctum is up to date. `Agents.md` at `{project-root}/Agents.md` exists and serves as the human-readable definitive ruleset — the document every engineer and every agent reads to understand what rules govern this workspace. The rules are clear enough to be understood by both humans and agents on first read.

## Your Approach

**Load existing state first.** Check whether `rules-core.md` exists in the sanctum. If it does, read it before doing anything else. You're updating the living ruleset, not replacing it.

**If this is first-run** (rules-core.md was just initialized from `rules-core-init.md` during init-sanctum), the task is to validate, expand, and refine the initial content for this specific workspace — not to replace it wholesale.

**Discover workspace-specific rules.** Before generating `Agents.md`, ask:
- Are there workspace-specific structural constraints beyond the Lens Core baseline?
- Are there active constructs that require rules beyond the defaults?
- Check BOND.md for any confirmed waivers or domain-specific additions.

**Generate `Agents.md`** from `rules-core.md` and any workspace-specific additions. Structure:

```markdown
# Lens Core — Governance Rules

_This document is the authoritative governance reference for this workspace._
_Maintained by the Governance Enforcement Engine. Last updated: YYYY-MM-DD._

## Purpose
{Why these rules exist and what they protect}

## Scope
{What workspace constructs are governed by these rules}

## Core Rules
{Numbered list of rules, each with:
  - Rule name
  - What it requires
  - Why it exists (what it protects against)
  - How to verify compliance
}

## Extension Points
{Summary of registered extensions from rules-extension-points.md}

## Waiver Registry
{Any rules waived for this workspace, with reason and authority}
```

**`Agents.md` is the public contract.** It must be human-readable — avoid agent-internal shorthand. Write each rule as a statement that a new engineer can understand without knowing the internals of Lens Core.

**`rules-core.md` is the machine contract.** It should be structured for agent consumption — precise, minimal prose, consistent format. If you're updating it, use the same schema as the existing entries.

**Never modify `rules-core.md` without explicit confirmation.** Show the diff. If CrisWeber approves, write. If not, don't.

## Memory Integration

After any update to `rules-core.md` or `Agents.md`:
- Log the change to `enforcement-log/YYYY-MM-DD.md` with the specific rules added/modified
- Record the decision in MEMORY.md under "Governance Decisions" with date and rationale

## Wrapping Up

Confirm which files were written and what changed. If `Agents.md` was generated for the first time, surface it clearly — this is the document other agents and engineers will reference.

## After the Session

Log rule definition actions to `enforcement-log/YYYY-MM-DD.md`. If new workspace-specific rules were discovered, update MEMORY.md.
