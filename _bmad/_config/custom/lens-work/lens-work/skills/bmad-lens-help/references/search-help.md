# Search Help

Searches the full help topic registry for entries matching a text query. Called when the user types `/help <query>` or when another skill needs to find specific commands programmatically.

## When to Use

- When the user types `/help retrospective` or `/help <any keyword>`
- When a skill needs to surface commands matching a concept
- When contextual help doesn't surface what the user is looking for

## Search Logic

1. Load topics from `assets/help-topics.yaml`
2. Normalize query to lowercase
3. For each topic, check if the query string appears (case-insensitive) in:
   - `id`
   - `command`
   - `description`
4. Return all matching topics; no truncation (search is exhaustive)
5. Order: exact command match first, then id match, then description match

## Output

```json
{
  "status": "pass",
  "query": "retrospective",
  "matches": [
    {"id": "retrospective", "command": "/retrospective", "description": "Run root cause analysis on feature problems", "category": "lifecycle"}
  ],
  "total": 1
}
```

On zero matches, `matches` is an empty list and `total` is 0 — this is not an error:

```json
{
  "status": "pass",
  "query": "nonexistent",
  "matches": [],
  "total": 0
}
```

## Display Format

**Matches found:**

```
**Search results for "retrospective":**

| Command | Description |
|---------|-------------|
| `/retrospective` | Run root cause analysis on feature problems |

_1 result found._
```

**No matches:**

```
No help topics found for "nonexistent". Try `/help` to browse by current phase, or ask about a specific command.
```

## Script Usage

```bash
uv run scripts/help-ops.py search \
  --topics-file assets/help-topics.yaml \
  --query "retrospective"
```

## Errors

| Error key | Detail | Exit code | Cause |
|-----------|--------|-----------|-------|
| `topics_file_not_found` | path | 1 | `--topics-file` path does not exist |
| `invalid_topics_file` | message | 1 | YAML parse error in topics file |
| `missing_query` | message | 1 | `--query` argument not provided |
