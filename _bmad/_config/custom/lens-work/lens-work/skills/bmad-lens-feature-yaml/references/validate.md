# Validate Feature YAML

Check feature.yaml consistency against its schema and governance state.

## Outcome

A validation report identifying any inconsistencies in schema compliance, directory structure, dependency integrity, phase coherence, and team composition.

## Process

Run the validate operation:

```bash
python3 ./scripts/feature-yaml-ops.py validate \
  --governance-repo {governance_repo} \
  --feature-id {featureId}
```

**Validation checks:**
- **Schema compliance** — All required fields present, values match allowed enums
- **Directory consistency** — Feature directory exists at the expected path for its domain/service
- **Dependency integrity** — All referenced featureIds in `depends_on`/`depended_by` exist and have reciprocal references
- **Phase/milestone coherence** — Milestone timestamps are consistent with current phase (no future milestones completed before current phase)
- **Team validity** — At least one team member with `lead` role

Returns JSON with pass/warning/fail status and detailed findings for any issues. Present results to the user with severity levels: critical (blocks work), warning (should fix), info (observation).
