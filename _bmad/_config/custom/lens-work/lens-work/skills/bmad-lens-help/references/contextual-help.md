# Contextual Help

Renders a phase-filtered, track-filtered view of the help topic registry. Called when the user types `/help` with no arguments, or when another skill surfaces suggestions for the current state.

## When to Use

- When the user invokes `/help` without a query
- When a skill wants to surface "what can I do next" suggestions
- At the end of a status output to hint at available actions

## Filtering Logic

1. Load topics from `assets/help-topics.yaml`
2. Filter by phase: include topic if `phases` contains the current phase OR `phases` contains `"all"`
3. Filter by track: include topic if `tracks` contains the current track OR `tracks` contains `"all"`
4. Sort: phase-specific topics first (those without `"all"` in phases), then universal topics
5. Apply limit (default: 5)

## Output

```json
{
  "status": "pass",
  "phase": "dev",
  "track": "full",
  "topics": [
    {"id": "complete", "command": "/complete", "description": "Finalize a feature — retrospective, documentation, archive", "category": "lifecycle"},
    {"id": "retrospective", "command": "/retrospective", "description": "Run root cause analysis on feature problems", "category": "lifecycle"},
    {"id": "log-problem", "command": "/log-problem", "description": "Log a problem with phase and category tags", "category": "tracking"},
    {"id": "dashboard", "command": "/dashboard", "description": "Review portfolio health and cross-feature blockers", "category": "reporting"},
    {"id": "next", "command": "/next", "description": "Get contextual suggestion for what to do next", "category": "navigation"}
  ],
  "total_available": 10
}
```

`total_available` reflects how many topics match the phase/track filter in total, before the limit is applied.

## Display Format

Present as a compact markdown table:

```
**Available commands** (dev phase · full track):

| Command | Description |
|---------|-------------|
| `/complete` | Finalize a feature — retrospective, documentation, archive |
| `/retrospective` | Run root cause analysis on feature problems |
| `/log-problem` | Log a problem with phase and category tags |
| `/dashboard` | Review portfolio health and cross-feature blockers |
| `/next` | Get contextual suggestion for what to do next |

_Showing 5 of 10 available. Search with `/help <query>` or ask to show all._
```

## Script Usage

```bash
uv run scripts/help-ops.py contextual \
  --topics-file assets/help-topics.yaml \
  --phase dev \
  --track full \
  --limit 5
```

## Errors

| Error key | Detail | Exit code | Cause |
|-----------|--------|-----------|-------|
| `topics_file_not_found` | path | 1 | `--topics-file` path does not exist |
| `invalid_topics_file` | message | 1 | YAML parse error in topics file |
