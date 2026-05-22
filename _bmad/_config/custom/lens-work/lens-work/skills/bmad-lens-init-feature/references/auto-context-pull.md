# Auto-Context Pull

Load relevant domain context for a feature — related summaries and full docs for dependencies.

## Outcome

After this process, the agent has loaded:

- Domain constitution rules (if present at `{governance-repo}/domains/{domain}/constitution.md`)
- Summaries for all other features in the same domain (from `feature-index.yaml` → `summary.md` files on `main`)
- Full feature docs for all `depends_on` and `blocks` entries (full `feature.yaml` plus any available mirrored governance docs)
- Optional governance context for services that emerge during the current conversation
- Retrospective insights from `{governance-repo}/retrospectives/{domain}/` if present

## Process

### Step 1: Fetch Feature Index Context

```bash
python3 ./scripts/init-feature-ops.py fetch-context \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --depth summaries
```

The output includes:

- `related` — list of featureIds in the same domain
- `depends_on` — list of featureIds in the feature's `depends_on` list
- `blocks` — list of featureIds in the feature's `blocks` list
- `context_paths` — filesystem paths to `summary.md` for same-domain context plus `feature.yaml` and mirrored governance docs for dependency features

### Step 2: Load Related Summaries

For each path in `context_paths` that points to a `summary.md`, read and incorporate the content into your working context. These summaries describe what adjacent features are doing, enabling coherent scoping and avoiding duplication.

### Step 3: Load Depends-On Full Docs

For features listed in `depends_on`, run with `--depth full` to get full feature.yaml paths:

```bash
python3 ./scripts/init-feature-ops.py fetch-context \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --depth full
```

Read and incorporate the full `feature.yaml` content and any mirrored governance docs for each `depends_on` or `blocks` feature. This ensures the new feature's planning respects the constraints and interfaces of its dependencies.

### Step 3b: Load Named Service Context As The Session Unfolds

If the user names other services in the request, brainstorm answers, or follow-up discussion, load that governance context as part of the working session instead of asking a dedicated upfront service-selection question. Pass recent user text when service names need to be detected implicitly:

```bash
python3 ./scripts/init-feature-ops.py fetch-context \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --service-ref-text "{recent_user_text}"
```

When the service name is already clear, pass it directly:

```bash
python3 ./scripts/init-feature-ops.py fetch-context \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --service-ref {service_name}
```

Use the result fields as follows:

- `detected_service_refs` — services inferred from the recent conversation text
- `service_context_paths` — matching governance service files, service docs, and child feature summaries
- `missing_service_refs` — services that were requested or detected but have no governance context available

If `missing_service_refs` is non-empty, tell the user those governance docs are missing and continue without falling back to source-code inspection.

### Step 4: Load Domain Constitution

Check for domain-level governance rules:

```
{governance-repo}/domains/{domain}/constitution.md
```

If present, load and apply its constraints to all planning and scoping decisions for this feature.

### Step 5: Load Retrospective Insights

Check for retrospective artifacts:

```
{governance-repo}/retrospectives/{domain}/
```

If present, load the most recent retrospective (sort by filename date). Surface any recurring issues, anti-patterns, or lessons learned that apply to the current domain or service.

### Context Summary

After loading all context, present a brief summary:

- N related features in domain (list featureIds)
- N depends-on / blocks features (list featureIds)
- N named-service governance contexts loaded (list service names)
- Missing governance service contexts: list service names, if any
- Constitution loaded: yes/no
- Retrospective insights: yes/no (date of most recent)

This context remains active for the duration of the feature planning session.
