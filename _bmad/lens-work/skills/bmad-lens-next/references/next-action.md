# Next Action Reference

## Recommendation Rules

The `suggest` subcommand derives one recommendation from feature state. It resolves
commands from `lifecycle.yaml`, not from hard-coded phase shortcuts. Rules apply in
priority order — the first matching rule wins.

### Priority Order

1. **Hard gates (blockers)** — missing required milestones for the current phase block promotion
2. **Stale context** — a warning (not a blocker) to fetch fresh context before proceeding
3. **Open issues** — a warning when more than 3 issues are open
4. **Phase-based recommendation** — the canonical action for the current phase or completed phase transition

### Phase → Action Map

| Phase | Action | Command | Rationale |
|-------|--------|---------|-----------|
| preplan | preplan | `/preplan` | Feature is in PrePlan — continue the PrePlan workflow |
| businessplan | businessplan | `/businessplan` | Feature is in BusinessPlan — continue the BusinessPlan workflow |
| techplan | techplan | `/techplan` | Feature is in TechPlan — continue the TechPlan workflow |
| finalizeplan | finalizeplan | `/finalizeplan` | Feature is in FinalizePlan — continue the FinalizePlan workflow |
| expressplan | expressplan | `/expressplan` | Feature is in ExpressPlan — continue the ExpressPlan workflow |
| preplan-complete | businessplan | `/businessplan` | PrePlan is complete — continue with `/businessplan` |
| businessplan-complete | techplan | `/techplan` | BusinessPlan is complete — continue with `/techplan` |
| techplan-complete | finalizeplan | `/finalizeplan` | TechPlan is complete — continue with `/finalizeplan` |
| finalizeplan-complete | dev | `/dev` | FinalizePlan is complete — continue with `/dev` |
| expressplan-complete | finalizeplan | `/finalizeplan` | ExpressPlan is complete — continue with `/finalizeplan` |
| dev-complete | complete | `/complete` | Dev execution is complete — run closeout workflow (retrospective, documentation, archival) |
| dev | dev | `/dev` | Feature is in dev execution — continue implementation and story flow |
| complete | complete | `/complete` | Feature is at lifecycle closeout — finalize retrospective, documentation, and archival |
| paused | pause-resume | `/pause-resume` | Feature is paused — resume when ready |

### Blockers (Hard Gates)

A blocker surfaces when a required milestone for the current or auto-advanced phase was not completed:

| Phase | Required Milestone | Blocker Message |
|-------|--------------------|-----------------|
| techplan | `milestones.businessplan` | Business plan milestone not completed |
| finalizeplan | `milestones.techplan` | Tech plan milestone not completed |
| dev | `milestones.finalizeplan` | Finalize plan milestone not completed |
| complete | `milestones.dev-complete` | Dev-complete milestone not set |

Track-aware exception: if the feature track starts at `techplan` (for example `hotfix` or `tech-change`), `/next` does not require a businessplan milestone before delegating to `/techplan`.

### Warnings

- `context.stale=true` → `"context.stale — consider fetching fresh context first"`
- `len(links.issues) > 3` → `"{N} open issues — consider reviewing before proceeding"`

## Delegation Behavior

- If `recommendation.blockers` is empty, `/next` should auto-delegate to `recommendation.command`.
- If warnings exist, surface them briefly and continue delegating.
- If blockers exist, do not delegate; show blockers first.

## Output Format

```json
{
  "status": "pass",
  "featureId": "auth-login",
  "phase": "preplan",
  "track": "full",
  "path": "/path/to/feature.yaml",
  "recommendation": {
    "action": "preplan",
    "rationale": "Feature is in PrePlan — continue the PrePlan workflow",
    "command": "/preplan",
    "blockers": [],
    "warnings": []
  }
}
```

## Error Cases

| Condition | Status | Exit Code |
|-----------|--------|-----------|
| Feature not found | fail | 1 |
| Invalid feature-id (unsafe characters) | fail | 1 |
| Feature YAML unreadable | fail | 1 |
