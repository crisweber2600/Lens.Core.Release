# Split Stories

Move selected story files from one feature to a new feature.

## Outcome

A new feature exists with the moved stories in its `stories/` directory. The original feature's `stories/` directory no longer contains those story files. Both features have complete governance artifacts.

## When to Use

When a feature has too many stories and some should be deferred or tracked separately, or when stories naturally belong to a different scope.

## Pre-conditions

- Original feature exists in governance repo
- Story IDs to move are known
- None of the stories to move are `in-progress`

## Process

### Step 1: Validate story eligibility

```bash
python3 ./scripts/split-feature-ops.py validate-split \
  --sprint-plan-file {sprint_plan_path} \
  --story-ids "{story_ids_to_move}"
```

If any story is `in-progress`, hard-stop. Those stories cannot be moved until they reach `done`.

### Step 2: Confirm with user

Present the split plan:
- **Stories staying in {featureId}:** [list remaining story IDs]
- **Stories moving to {new_feature_id}:** [list story IDs being moved]

Do not proceed until the user confirms.

### Step 3: Create the new feature

```bash
python3 ./scripts/split-feature-ops.py create-split-feature \
  --governance-repo {governance_repo} \
  --source-feature-id {featureId} \
  --source-domain {domain} \
  --source-service {service} \
  --new-feature-id {new_feature_id} \
  --new-name "{new_feature_name}" \
  --track {track} \
  --username {username}
```

### Step 4: Move stories

Dry-run first:

```bash
python3 ./scripts/split-feature-ops.py move-stories \
  --governance-repo {governance_repo} \
  --source-feature-id {featureId} \
  --source-domain {domain} \
  --source-service {service} \
  --target-feature-id {new_feature_id} \
  --target-domain {target_domain} \
  --target-service {target_service} \
  --story-ids "{story_ids}" \
  --dry-run
```

Then execute:

```bash
python3 ./scripts/split-feature-ops.py move-stories \
  --governance-repo {governance_repo} \
  --source-feature-id {featureId} \
  --source-domain {domain} \
  --source-service {service} \
  --target-feature-id {new_feature_id} \
  --target-domain {target_domain} \
  --target-service {target_service} \
  --story-ids "{story_ids}"
```

## Output Confirmation

After completion, confirm:
- New feature: `{governance_repo}/features/{target_domain}/{target_service}/{new_feature_id}/`
- Stories moved: list exact filenames
- Original feature stories/ remaining: list remaining story files
- feature-index.yaml: updated with new entry

## Story File Format

Story files live at:
```
{governance_repo}/features/{domain}/{service}/{featureId}/stories/{story-id}.md
```
or
```
{governance_repo}/features/{domain}/{service}/{featureId}/stories/{story-id}.yaml
```

The script moves the file as-is. If a story has `status: in-progress` in its content (YAML front matter or body), the move will be blocked at the validation step.
