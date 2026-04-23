# Register Rule Extensions

## What Success Looks Like

A custom rule from another agent is correctly registered in `rules-extension-points.md`. The extension doesn't conflict with existing core rules. The registration is documented with enough context that a future session can understand why it was added. The extension registry remains clean and navigable as it grows.

## Your Approach

**Load before touching.** Read `rules-core.md` and `rules-extension-points.md` before doing anything. You cannot check for conflicts without knowing what already exists.

**Gather the extension spec.** Request or confirm:
- Extension name (unique identifier, kebab-case)
- Registering agent (which `lc-agent-*` is adding this rule)
- Rule description (what the rule requires)
- Rule rationale (why it exists — what does it protect against?)
- Scope (which workspace constructs does it apply to?)
- Enforcement severity (blocker / warning / info)
- Any constraints (conditions under which the rule doesn't apply)

**Conflict check — required before registration.** For each existing rule in `rules-core.md` and `rules-extension-points.md`:
- Does the new rule contradict any existing rule?
- Does the new rule duplicate any existing rule (same intent, different wording)?
- Does the new rule overlap with another extension from a different agent?

If conflicts are found, surface them clearly with the conflicting rule and proposed resolution before proceeding.

**Format the extension entry** using the schema from `rules-extension-points.md`:

```markdown
## {extension-name}

- **Agent:** {registering-agent-code}
- **Added:** YYYY-MM-DD
- **Severity:** {blocker | warning | info}
- **Scope:** {workspace constructs this rule governs}

### Rule
{Clear statement of what the rule requires}

### Rationale
{Why this rule exists — what problem it prevents or what structure it protects}

### Constraints
{Conditions under which this rule doesn't apply, or is automatically waived}
```

**Show before writing.** Display the formatted entry and any conflict check results. Confirm before appending to `rules-extension-points.md`.

**Update `Agents.md` if it exists.** If `{project-root}/Agents.md` is present, append the new extension to the "Extension Points" section. Confirm before writing.

## Memory Integration

Log registration to `enforcement-log/YYYY-MM-DD.md`:
```
[YYYY-MM-DD] Registered extension: {extension-name} (from {agent})
```

Update MEMORY.md under "Extension History" in BOND.md after the session.

## Wrapping Up

Confirm the extension is registered and note any conflict resolutions made. If conflicts were found and resolved by waiving or modifying the extension, make sure the resolution is explicit in the log.

## After the Session

Log to `enforcement-log/YYYY-MM-DD.md`. Update BOND.md "Extension History" with the new registration.
