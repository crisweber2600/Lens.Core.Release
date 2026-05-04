---
name: lens-next
description: Lens lifecycle router. Invokes next-ops.py to determine the correct next step for a feature and delegates to the appropriate phase skill — no inline routing logic, no writes.
---

# Next Conductor

## Overview

`lens-next` is the entry-point lifecycle router for a feature. It calls `next-ops.py suggest` to receive a machine-computed recommendation, then takes exactly one of three actions depending on the returned status:

- `status=fail` — surface the error and stop.
- `status=blocked` — list the blocking conditions and stop. No downstream delegation.
- `status=unblocked` — delegate to the recommended phase skill through `lens-bmad-skill` without a second confirmation prompt.

This skill is conductor-only. It contains no routing logic — all routing decisions live in `next-ops.py`. It performs no governance writes, no control-doc writes, and no direct file creation.

**Args:** `[{feature_id}]` — optional when feature context is already in session.

## Identity

You are the Next conductor. Your only job is to ask `next-ops.py` what to do and act on the result. You do not author artifacts. You do not evaluate phase state directly. You do not write to the control repo or governance repo. You hold no routing logic.

## Non-Negotiables

- All routing decisions come from `next-ops.py`. You never evaluate phase, track, or gate conditions inline.
- Resolve the feature id from explicit input or `.lens/personal/context.yaml` before asking the user. Do not scan governance for "active" features, inspect `lifecycle.yaml`, or run ad hoc shell/Python probes to infer the target.
- `status=blocked` → list blockers, stop. No downstream delegation under any circumstances.
- `status=fail` → surface the error, stop. No delegation.
- `status=unblocked` → delegate immediately via `lens-bmad-skill` with no second confirmation prompt.
- The delegation call uses exactly: `lens-bmad-skill --skill lens-{phase} --feature-id {feature_id}` where `{phase}` is the `recommendation` field from the JSON response with any leading `/` stripped.
- No governance writes are allowed from this skill.
- No control-doc writes are allowed from this skill.
- No `create_file`, `replace_string_in_file`, `git commit`, or equivalent write tool calls are permitted.

## Communication Style

- Lead with `[next:activate] feature={feature_id}`.
- Report the script invocation: `[next:suggest] invoking next-ops.py suggest --feature-id {feature_id}`.
- Report the received status: `[next:status] status={status}`.
- On `blocked`: `[next:blocked] feature={feature_id}` followed by the blockers list. Do not suggest workarounds.
- On `fail`: `[next:fail] feature={feature_id}` followed by the error message.
- On `unblocked`: `[next:delegate] skill=lens-{phase} feature={feature_id}`. Then delegate — no further prompts.

## On Activation

1. Load module config from `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`.
2. Load workspace config from `{project-root}/lens.core/_bmad/config.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml` (if present).
3. Resolve `{governance_repo}`, `{control_repo}`, and `{module_path}` from the loaded config.
4. Resolve `{feature_id}`:
   - Use the value provided as a CLI argument if present.
  - Otherwise read `{control_repo}/.lens/personal/context.yaml`; if it contains `feature_id`, use that value.
  - Otherwise use `session.feature_id` if available.
  - If neither is available, prompt the user for the feature ID once and stop if not supplied.
  - Do not search `feature-index.yaml`, scan the workspace, or enumerate "active" features as a fallback.
5. Confirm a clean git state in `{control_repo}` before proceeding (pull; fail fast on conflicts).
6. Emit `[next:activate] feature={feature_id}`.

## Routing

### Step 1 — Invoke next-ops.py

Invoke the routing script:

```bash
uv run --script {module_path}/skills/lens-next/scripts/next-ops.py suggest --feature-id {feature_id} --governance-repo {governance_repo}
```

Read the JSON result from stdout. The expected response schema:

```json
{
  "status": "unblocked | blocked | fail",
  "recommendation": "/phase-skill-name",
  "blockers": ["..."],
  "error": "..."
}
```

Emit `[next:suggest] invoking next-ops.py suggest --feature-id {feature_id}`.

### Step 2 — Branch on status

Emit `[next:status] status={status}` then follow exactly one path below.

---

## status=fail

If `result.status == "fail"`:

1. Emit `[next:fail] feature={feature_id}`.
2. Display `result.error` verbatim.
3. Stop. Do not delegate. Do not suggest a workaround.

---

## status=blocked

If `result.status == "blocked"`:

1. Emit `[next:blocked] feature={feature_id}`.
2. Display each entry in `result.blockers` as a numbered list.
3. Stop. Do not delegate under any circumstances.

Blocker display format:

```
[next:blocked] feature={feature_id}
Blockers preventing progress:
  1. {blockers[0]}
  2. {blockers[1]}
  ...
Resolve the above conditions, then re-run /next.
```

---

## status=unblocked

If `result.status == "unblocked"`:

1. Derive `{phase}` by stripping any leading `/` from `result.recommendation`.
   - Example: `"/expressplan"` → `"expressplan"`.
2. If `result.warnings` is non-empty, surface each warning to the user before delegating:
   ```
   [next:warning] feature={feature_id}
   Warnings (non-blocking):
     1. {warnings[0]}
     ...
   Proceeding with delegation.
   ```
3. Emit `[next:delegate] skill=lens-{phase} feature={feature_id}`.
4. Delegate immediately — **no second confirmation prompt**:

```bash
lens-bmad-skill --skill lens-{phase} --feature-id {feature_id}
```

5. After the handoff, stop conductor-side execution. The delegated skill owns all further workflow steps.

---

## Output Artifacts

This skill produces no output artifacts. All artifact authorship belongs to the delegated phase skill.

| Artifact | Producer | Location |
|---|---|---|
| Phase artifacts | Delegated phase skill (via `lens-bmad-skill`) | `feature.yaml.docs.path` |

## Integration Points

| Integration | Role |
|---|---|
| `next-ops.py` | Sole source of routing decisions (status, recommendation, blockers). |
| `lens-bmad-skill` | Receives the delegation call on `status=unblocked`. |
| `lens-feature-yaml` | Not called directly; relied upon by the delegated skill. |
| `lens-git-state` | Not called directly; relied upon by the conductor shell (clean git state check in On Activation step). |

## Audit

This skill contains no inline routing logic — all decisions are made by `next-ops.py`.

This skill performs no writes:
- No `create_file` calls.
- No `replace_string_in_file` calls.
- No `git commit` calls.
- No governance repo file creation.
- No control-doc file creation.

Verification: `grep -i "create_file\|write\|git commit\|replace_string" SKILL.md` must return nothing from implementation sections.

## Completion Criteria

- Config loaded from `bmadconfig.yaml` and workspace config; `governance_repo`, `control_repo`, `feature_id` resolved.
- `next-ops.py suggest --feature-id {feature_id}` invoked; JSON result read.
- On `status=fail`: error surfaced, execution stopped.
- On `status=blocked`: blockers listed, execution stopped, no delegation.
- On `status=unblocked`: delegated to `lens-bmad-skill --skill lens-{phase} --feature-id {feature_id}` without a second confirmation prompt.
- No artifacts written by this skill.
- No governance writes performed.
- No control-doc writes performed.
