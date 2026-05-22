# Update Feature State

Modify specific fields in a feature.yaml file while preserving all other state.

## Outcome

The target field(s) are updated, the `updated` timestamp is refreshed, and if the phase changed, a new entry is appended to `phase_transitions`. Dependency modifications are bidirectionally synced.

## Process

Run the update operation:

```bash
python3 ./scripts/feature-yaml-ops.py update \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --set "phase=techplan" \
  --set "milestones.businessplan=2026-04-05T22:55:00Z" \
  --username {username}
```

The `--set` flag accepts dot-notation paths for nested fields. Multiple `--set` flags can be passed for atomic multi-field updates.

**Phase transition handling:** When `phase` is updated, the script automatically:
- Appends to `phase_transitions` with the new phase, timestamp, and username
- Updates the `updated` timestamp
- Validates the transition is legal per the feature's track (see transition table below)

**Dependency updates:** When modifying `dependencies.depends_on`, the script also updates the `depended_by` list on the referenced feature (bidirectional sync). Adding feature B to A's `depends_on` also adds A to B's `depended_by`.

## Phase Transition Rules

Transitions are track-aware. Each track defines which phases can follow which:

| From \ Track | full | quickplan | hotfix | express | spike | feature | hotfix-express | tech-change |
|---|---|---|---|---|---|---|---|---|
| preplan | businessplan | businessplan, techplan, finalizeplan, dev | dev | expressplan, dev | dev | businessplan | dev | techplan, dev |
| businessplan | techplan | techplan, finalizeplan, dev | — | — | — | techplan | — | — |
| techplan | finalizeplan | finalizeplan, dev | — | — | — | finalizeplan | expressplan | dev |
| finalizeplan | dev | dev | — | — | — | dev | — | dev |
| dev | complete | complete | complete | complete | complete | complete | complete | complete |
| paused | any | any | any | any | any | any | any | any |

All transitions also allow `paused` as a target. `complete` allows no further transitions.
