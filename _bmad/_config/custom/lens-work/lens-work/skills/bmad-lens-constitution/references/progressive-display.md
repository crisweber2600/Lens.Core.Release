# Progressive Display

Returns a context-filtered view of the resolved constitution — only the rules relevant to the current phase and/or track. Prevents overwhelming feature authors with irrelevant governance rules.

## When to Use

- After `init-feature`: show applicable governance rules for the chosen track
- At the start of a plan workflow: surface what artifacts are expected
- When a developer asks "what governance rules apply to me right now?"

## Required Context

- Governance repo path
- `domain` and `service` from `feature.yaml`
- Current `phase` (optional): `planning` | `dev` | `complete`
- Current `track` (optional): `quickplan` | `full` | `hotfix` | `tech-change`

## Output

Always includes:
```json
{
  "domain": "platform",
  "service": "auth",
  "levels_loaded": ["org", "domain", "service"],
  "gate_mode": "informational",
  "additional_review_participants": ["security-team"],
  "enforce_stories": true,
  "enforce_review": true,
  "full_constitution_available": true
}
```

When `--phase` is provided, adds `required_artifacts_for_phase`:
```json
{
  "required_artifacts_for_phase": ["business-plan", "tech-plan", "security-review"]
}
```

When `--track` is provided, adds `track_permitted` and `permitted_tracks`:
```json
{
  "track_permitted": true,
  "permitted_tracks": ["quickplan", "full"]
}
```

`full_constitution_available` is `true` when the org-level constitution was loaded. If the org constitution is missing, the script returns an error (org is required).

## Gate Mode Semantics

| `gate_mode` | Behavior on failure |
|-------------|---------------------|
| `informational` | Failures listed in `informational_failures`; exit 0 |
| `hard` | Failures listed in `hard_gate_failures`; exit 2 (workflow should block) |

The resolved `gate_mode` is the strongest value across all loaded levels (hard beats informational).

## enforce_* Fields

| Field | Meaning when `true` |
|-------|---------------------|
| `enforce_stories` | Compliance check verifies `stories` artifact exists in `dev` phase |
| `enforce_review` | Compliance check verifies `additional_review_participants` is non-empty |

Both default to `false` unless a constitution explicitly sets `true`. Once set `true` at any level, lower levels cannot override it to `false` (strongest wins).

## Script Usage

```bash
uv run scripts/constitution-ops.py progressive-display \
  --governance-repo /path/to/governance-repo \
  --domain platform \
  --service auth \
  [--phase planning] \
  [--track quickplan]
```

## Display Logic

| Context | What to Show |
|---------|-------------|
| Phase provided | `required_artifacts_for_phase` for that phase only |
| Track provided | `track_permitted` + `permitted_tracks` |
| Both provided | Both + gate mode |
| Neither provided | Gate mode, reviewers, full constitution available |

## Presenting to User

Frame rules as guidance, not gatekeeping:

> **Governance rules for `platform/auth` (planning phase)**
> Required artifacts: `business-plan`, `tech-plan`
> Gate mode: informational (failures won't block, but will be noted)
> Additional reviewers: security-team
>
> → Full constitution: `uv run constitution-ops.py resolve --domain platform --service auth`

Always offer the full resolution command if the user wants more detail.
