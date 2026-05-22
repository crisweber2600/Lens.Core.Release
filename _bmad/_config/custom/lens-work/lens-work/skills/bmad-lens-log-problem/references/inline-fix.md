# Inline Fix

Log a problem and its resolution atomically — the entry is written with `Status: resolved` in a single operation.

## Outcome

A resolved problem entry is appended to `problems.md`. The fix is captured alongside the problem so the log is never half-complete. The entry is visible to retrospective analysis as a resolved item with a known resolution path.

## When to Use

Use inline fix when you have both the problem and the resolution available at the same moment — for example, when a dev story surfaces a bug that was fixed in the same session, or when another skill detects and auto-resolves an issue.

Do not use inline fix to paper over problems that are not actually resolved. Log them as open instead.

## Process

1. Collect all fields for the problem (same as log-problem).
2. Additionally collect the resolution description.
3. Run the log operation to create an open entry:

```bash
python3 ./scripts/log-problem-ops.py log \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --domain {domain} \
  --service {service} \
  --phase {phase} \
  --category {category} \
  --title "{short title}" \
  --description "{full description}"
```

4. Capture the `entry_id` from the output.
5. Immediately run the resolve operation:

```bash
python3 ./scripts/log-problem-ops.py resolve \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --domain {domain} \
  --service {service} \
  --entry-id {entry_id} \
  --resolution "{resolution description}"
```

## Output

After both commands succeed, confirm in one line:

```
Logged + resolved: {entry_id} [{phase}/{category}] — {resolution summary}
```

In headless mode, emit only the final JSON from the resolve command.

## Error Handling

If the log step succeeds but the resolve step fails, the entry remains open. Surface the entry_id to the caller so the resolution can be applied later via the resolve subcommand directly.
