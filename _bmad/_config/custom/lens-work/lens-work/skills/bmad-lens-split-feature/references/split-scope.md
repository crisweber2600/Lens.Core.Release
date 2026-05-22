# Split Scope

Carve a feature's planning documents (business plan, tech plan) into two separate features.

## Outcome

Two feature directories exist with their own planning artifacts. The new feature has a complete feature.yaml, feature-index entry, and summary stub on main. The original feature's documents are updated to reflect the narrowed scope.

## When to Use

When a feature's scope has grown too large and needs to be divided at the planning level — before or during story creation.

## Pre-conditions

- Original feature exists in governance repo
- Split boundary is defined (what scope goes to the new feature)
- No in-progress stories in the scope being split (validate first)

## Process

### Step 1: Validate

If there are stories in the split scope, validate first:

```bash
python3 ./scripts/split-feature-ops.py validate-split \
  --sprint-plan-file {sprint_plan_path} \
  --story-ids "{story_ids_in_new_scope}"
```

If validation fails, hard-stop and surface blocked story IDs.

### Step 2: Confirm with user

Present the split plan:
- **Original feature ({featureId}):** retains [describe remaining scope]
- **New feature ({new_feature_id}):** receives [describe split scope]

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

Dry-run first to verify:

```bash
python3 ./scripts/split-feature-ops.py create-split-feature ... --dry-run
```

### Step 4: Move stories (if any)

If stories exist in the split scope:

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

### Step 5: Update planning documents

Guide the user to:
1. Update the original feature's business-plan.md and tech-plan.md to reflect the narrowed scope
2. Populate the new feature's planning documents with the split scope content
3. Update cross-references between the two features in their respective feature.yaml files

## Output Confirmation

After completion, confirm:
- New feature path: `{governance_repo}/features/{target_domain}/{target_service}/{new_feature_id}/`
- New feature.yaml: created at `preplan` phase
- feature-index.yaml: updated with new entry
- summary.md stub: written to new feature directory
- Stories moved: list any moved story files
