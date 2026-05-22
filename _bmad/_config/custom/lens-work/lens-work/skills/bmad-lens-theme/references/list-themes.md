# List Themes

Scans the themes directory and returns all available themes with metadata. Used for presenting theme options to the user.

## When to Use

- When the user asks "what themes are available?"
- During onboarding when collecting theme preferences
- Before a theme switch to confirm the requested theme exists

## Output — normal

```json
{
  "themes": [
    {
      "name": "default",
      "description": "Standard Lens persona — direct, professional, and technically precise.",
      "version": "1.0.0",
      "author": "Lens",
      "persona_count": 13,
      "easter_egg_count": 0,
      "file": "default.yaml"
    },
    {
      "name": "wh40k",
      "description": "In the grim darkness of the far future, there is only shipping.",
      "version": "1.0.0",
      "author": "Cris Weber",
      "persona_count": 13,
      "easter_egg_count": 4,
      "file": "wh40k.yaml"
    }
  ],
  "count": 2
}
```

## Output — with warnings and unknown keys

When corrupt files or unknown YAML keys are found:

```json
{
  "themes": [
    {
      "name": "custom",
      "description": "My theme",
      "version": "1.0.0",
      "author": "Alice",
      "persona_count": 13,
      "easter_egg_count": 0,
      "file": "custom.yaml",
      "unknown_keys": ["custom_field"]
    }
  ],
  "count": 1,
  "warnings": [
    { "file": "broken.yaml", "warning": "Could not parse: YAML parse error: ..." }
  ]
}
```

`unknown_keys` appears on a theme entry when it has unrecognized top-level YAML keys. `warnings` appears at the root when files could not be parsed at all.

An empty themes directory returns `{"themes": [], "count": 0}` with exit 0 — this is distinct from the `themes_dir_not_found` error.

## Script Usage

```bash
uv run scripts/theme-ops.py list \
  --themes-dir /path/to/governance-repo/themes/
```

## Presenting to User

```
Available themes (2):

  default    Standard Lens persona — direct, professional, and technically precise.
             Personas: 13 | Easter eggs: 0 | Author: Lens

  wh40k      In the grim darkness of the far future, there is only shipping.
             Personas: 13 | Easter eggs: 4 | Author: Cris Weber

→ Current theme: default
→ To switch: "use wh40k theme"
```

## Theme Directory

Theme files are discovered from `{governance-repo}/themes/`. Any `.yaml` file in that directory is treated as a potential theme. Corrupt or unparseable files are reported as warnings and skipped — they do not block the listing of valid themes.

## Theme Name Constraints

Theme names must contain only alphanumeric characters, hyphens, and underscores. The name in the output is taken from the `name` field in the YAML, falling back to the file stem.

## Adding a Custom Theme

Drop a `.yaml` file into the themes directory. It will be discovered automatically on the next `list` or `load` call. See the Theme Schema below.

## Theme Schema

Required top-level keys:

| Key | Type | Description |
|-----|------|-------------|
| `name` | string | Theme slug (must match the filename stem) |
| `description` | string | One-line description shown in list view |
| `version` | string | Semantic version, e.g. `"1.0.0"` |
| `author` | string | Attribution |
| `personas` | mapping | Per-role persona definitions (see below) |

Optional:

| Key | Type | Description |
|-----|------|-------------|
| `easter_eggs` | list | Easter egg definitions (see easter-eggs.md) |

**Persona roles** (the 13 known roles): `lens`, `analyst`, `architect`, `dev`, `pm`, `qa`, `quick_dev`, `sm`, `tech_writer`, `ux_designer`, `brainstorming_coach`, `creative_problem_solver`, `design_thinking_coach`.

Per-persona fields:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Display name for this role |
| `title` | yes | Short title/rank |
| `communication_style` | yes | Style description (max ~500 chars) |
| `flavor_phrases` | no | List of flavor strings surfaced occasionally |

## Errors

| Error key | Detail | Exit code | Cause |
|-----------|--------|-----------|-------|
| `themes_dir_not_found` | path | 1 | `--themes-dir` path is not a directory |

