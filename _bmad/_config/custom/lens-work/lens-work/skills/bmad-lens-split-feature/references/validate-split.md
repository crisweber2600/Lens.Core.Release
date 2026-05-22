# Validate Split

Check that a set of stories is eligible to be split — none may be in-progress.

## Outcome

A pass/fail result with the list of eligible stories and any blocked stories with their reasons.

## When to Use

Before executing any split operation (scope or stories). This must pass before `create-split-feature` or `move-stories` is called.

## Pre-conditions

- `sprint-plan.md` (or equivalent sprint plan file) is accessible
- Story IDs are known

## Process

Run the validate-split operation:

```bash
python3 ./scripts/split-feature-ops.py validate-split \
  --sprint-plan-file {sprint_plan_path} \
  --story-ids "{comma_separated_story_ids}"
```

Or with a JSON array:

```bash
python3 ./scripts/split-feature-ops.py validate-split \
  --sprint-plan-file {sprint_plan_path} \
  --story-ids '["story-1","story-2","story-3"]'
```

## Output

```json
{
  "status": "pass",
  "eligible": ["story-1", "story-2"],
  "blocked": [],
  "blockers": []
}
```

When blocked:

```json
{
  "status": "fail",
  "eligible": ["story-1"],
  "blocked": [
    {"id": "story-2", "reason": "in-progress"}
  ],
  "blockers": ["story-2"]
}
```

## Handling Failures

If `status` is `fail`:
- Hard-stop. Do not proceed with any split operation.
- Display the blocked story IDs to the user.
- Explain: these stories have active dev work in progress and cannot be moved.
- Offer options: wait until in-progress stories are complete, or revise the split boundary to exclude them.

If a story ID is not found in the sprint plan:
- Treat as `eligible` (status unknown = not in-progress).
- The `blockers` list shows only confirmed in-progress stories.

## Sprint Plan Format

The script reads the sprint plan file and looks for story status entries. Supported formats:

```yaml
# Pure YAML with development_status section
development_status:
  story-1: pending
  story-2: in-progress
  story-3: done
```

Or embedded in markdown as a YAML code block:

````markdown
```yaml
development_status:
  story-1: pending
  story-2: done
```
````

Or simple story entries:

```yaml
stories:
  story-1:
    status: pending
  story-2:
    status: in-progress
```
