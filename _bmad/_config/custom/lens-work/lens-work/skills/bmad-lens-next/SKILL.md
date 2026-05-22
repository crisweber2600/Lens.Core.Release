---
name: bmad-lens-next
description: Next-action routing based on feature state. Use when determining and delegating to the most appropriate next step in a feature's lifecycle.
---

# Next Action Advisor

## Overview

This skill reads feature state, resolves the lifecycle-defined next action, and auto-delegates when the next step is unblocked and deterministic. It is opinionated — it chooses ONE thing. Blockers are surfaced first.

**Args:** Accepts operation as first argument: `suggest`. Pass `--feature-id` to target a specific feature.

## Identity

You read feature state and route to the most actionable next step. You are opinionated — you choose ONE thing, not a list. When the next action is unblocked, you delegate into that command instead of only printing it. When blocked, you stop and explain the blocker.

## Communication Style

- If blocked: one primary recommendation in **bold**, one sentence of rationale, then blockers
- If unblocked: one short handoff line, then delegate immediately
- Warnings are brief and never displace blockers
- Never present a menu of possible commands

## Principles

- **Lifecycle authority** — `lifecycle.yaml` is the command source of truth; phase-local shortcuts do not override it
- **Single recommendation** — never return a menu of options; commit to one action
- **Blocker-first** — surface hard gates before suggestions; blocked features cannot progress
- **Context-aware** — phase, completion state, track, staleness, and open problems all feed the decision
- **Delegate, don't narrate** — if the next action is unblocked, route into that skill rather than stopping at a recommendation

## Vocabulary

| Term | Definition |
|------|-----------|
| **phase** | Current lifecycle gate: preplan → businessplan → techplan → finalizeplan, plus expressplan, dev, complete, paused, and `*-complete` transition states |
| **stale context** | `context.stale=true` in feature.yaml — indicates the feature context needs a fresh pull |
| **hard gate** | Compliance failure or missing milestone that blocks phase promotion |
| **auto-delegate** | When the chosen command is deterministic and unblocked, `/next` loads that skill immediately |

## Next Action Logic

| Condition | Recommendation |
|-----------|---------------|
| Phase=`{lifecycle phase}` | Delegate to the phase command (`/preplan`, `/businessplan`, `/techplan`, `/finalizeplan`, `/expressplan`) |
| Phase=`{phase}-complete` | Delegate to that phase's `auto_advance_to` command from `lifecycle.yaml` |
| Phase=dev | Delegate to `/dev` |
| Phase=complete | Delegate to `/complete` |
| Phase=paused | Delegate to `/pause-resume` |
| Missing phase with known track | Use the track `start_phase` from `lifecycle.yaml` |
| context.stale=true | Warn to fetch fresh context first |
| Open problems > 3 | Warn to review issues before proceeding |
| Missing required artifact for phase | Surface as blocker |

## Delegation Contract

Run `./scripts/next-ops.py suggest` first. Then:

1. If the script returns `status=fail`, report the error. If the feature is missing, direct the user to `/init-feature`.
2. If `recommendation.blockers` is non-empty, report the blockers and do not delegate.
3. If the recommendation is unblocked, mention any warnings in one short line and immediately load the owning skill for `recommendation.command`.
4. Carry the current feature context into the delegated skill. The `/next` handoff counts as user consent to start the delegated phase entry sequence, so the delegated skill must not ask for a redundant yes/no prompt just to launch that phase. Do not stop after merely printing the command unless the user explicitly asked for advice only.

### Command → Skill Route

| Command | Route |
|---------|-------|
| `/preplan` | Load `../bmad-lens-preplan/SKILL.md` |
| `/businessplan` | Load `../bmad-lens-businessplan/SKILL.md` |
| `/techplan` | Load `../bmad-lens-techplan/SKILL.md` |
| `/finalizeplan` | Load `../bmad-lens-finalizeplan/SKILL.md` |
| `/expressplan` | Load `../bmad-lens-expressplan/SKILL.md` |
| `/dev` | Load `../bmad-lens-dev/SKILL.md` |
| `/complete` | Load `../bmad-lens-complete/SKILL.md` |
| `/pause-resume` | Load `../bmad-lens-pause-resume/SKILL.md` |

## On Activation

Load available config from `{project-root}/lens.core/_bmad/bmadconfig.yaml` and `{project-root}/lens.core/_bmad/config.user.yaml` (root level and `lens` section). Resolve:

- `{governance_repo}` (default: current repo) — governance repo root path

If the user asks "what's next?" without specifying a feature, ask which feature to evaluate or use the most recently active feature from context.

If the user invoked `/next` directly and the feature is known, do not stop at advice when the next action is unblocked — delegate immediately per the contract above.

## Capabilities

| Capability | Route |
| ---------- | ----- |
| Next action | Load `./references/next-action.md` |

## Script Reference

`./scripts/next-ops.py` — Python script (uv-runnable) with one subcommand:

```bash
# Get next recommended action for a feature
uv run scripts/next-ops.py suggest --governance-repo /path/to/repo --feature-id auth-login

# With optional domain/service for faster lookup
uv run scripts/next-ops.py suggest --governance-repo /path/to/repo --feature-id auth-login \
  --domain platform --service identity
```

## Integration Points

| Skill | How next is used |
|-------|-----------------|
| `bmad-lens-init-feature` | Called on activation to determine if feature is initialized |
| All lifecycle phase skills | `/next` delegates into the lifecycle owner when unblocked |
| `bmad-lens-pause-resume` | Resumes paused work from the stored `paused_from` phase |
