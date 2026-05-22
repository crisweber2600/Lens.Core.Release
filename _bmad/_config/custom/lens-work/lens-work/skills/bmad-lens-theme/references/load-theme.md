# Load Theme

Applies a persona overlay to the Lens agent and all orchestrated BMM agents. Called silently at activation or explicitly when the user changes themes.

## When to Use

- At activation: silently load the user's preferred theme from `user-profile.md`
- When the user says "switch to wh40k theme" or similar
- When initializing a new user and a theme preference was configured during onboarding

## Resolution Order

1. `--theme <name>` argument (explicit, highest priority)
2. `theme` field in `user-profile.md` (user preference)
3. `default` (fallback — always available)

If the requested theme file is missing or corrupt, the system falls back to `default` silently. The `fallback_from` field in the output signals this occurred.

**user-profile.md format:** The script reads a bare `theme: <name>` line from the profile (case-sensitive field name). The theme name must satisfy the slug constraint (alphanumeric, hyphens, underscores only).

## Output

```json
{
  "theme": "wh40k",
  "description": "In the grim darkness of the far future, there is only shipping.",
  "version": "1.0.0",
  "author": "Cris Weber",
  "personas": {
    "lens": {
      "name": "The Ordinator",
      "title": "Master of the Ordos Lifecycle",
      "communication_style": "Terse and authoritative...",
      "flavor_phrases": ["Initiating crusade protocols."]
    },
    "dev": {
      "name": "Magos Domina",
      "title": "Adeptus Mechanicus Sacred Coder",
      "communication_style": "...",
      "flavor_phrases": ["Praise the Omnissiah. The tests pass."]
    }
  },
  "fallback_from": "mytheme",
  "fallback_reason": "YAML parse error: ...",
  "warnings": [
    { "type": "missing_roles", "roles": ["qa", "sm"] },
    { "type": "extra_roles", "roles": ["rogue_trader"] },
    { "type": "unknown_theme_keys", "keys": ["custom_field"] }
  ]
}
```

`fallback_from` and `fallback_reason` are only present when fallback occurred. `warnings` is only present when issues were detected. All top-level string fields (`theme`, `description`, `version`, `author`) are always strings even if the source YAML contained a number.

## Handling `fallback_from`

When `fallback_from` is present in the output, do **not** surface the fallback to the user by default — continue with the loaded default theme silently. Only surface a note in explicit debug or diagnostic contexts. Do not retry with a different theme.

## Script Usage

```bash
# Load by theme name
uv run scripts/theme-ops.py load \
  --themes-dir /path/to/governance-repo/themes/ \
  --theme wh40k

# Load from user-profile.md
uv run scripts/theme-ops.py load \
  --themes-dir /path/to/governance-repo/themes/ \
  --user-profile /path/to/governance-repo/users/alice/user-profile.md
```

## Applying Personas — Integration Recipe

```
1. Run: uv run theme-ops.py load --themes-dir {themes_dir} --theme {theme_name}
2. Parse JSON output → theme_data
3. Apply Lens persona: use theme_data["personas"]["lens"] for @lens identity/style
4. Pass agent personas when orchestrating BMM agents:
     Mary (analyst) → theme_data["personas"]["analyst"]
     Winston (architect) → theme_data["personas"]["architect"]
     Amelia (dev) → theme_data["personas"]["dev"]
     (and so on for all 13 roles)
5. Occasionally surface a random item from the active persona's flavor_phrases
   (at most once per major status update; never on error responses)
6. Never alter capabilities — only names, titles, communication style, and flavor text
7. If fallback_from is present, continue silently with the loaded default
```

## Session State

Load the theme once at skill activation and store the result in session context. All subsequent references to persona data should read from this cached object. Re-invoke the script only when the user explicitly switches themes or when the session restarts.

## Theme Name Constraints

Theme names must contain only alphanumeric characters, hyphens, and underscores. Path traversal characters (`/`, `..`) are rejected with `invalid_theme_name` error (exit 1).

## Warnings

| Warning type | JSON shape | Meaning |
|-------------|-----------|---------|
| `missing_roles` | `{"type": "missing_roles", "roles": ["qa", "sm"]}` | Theme doesn't define some standard roles — those roles use default behavior |
| `extra_roles` | `{"type": "extra_roles", "roles": ["rogue_trader"]}` | Theme defines personas for unrecognized roles — ignored |
| `unknown_theme_keys` | `{"type": "unknown_theme_keys", "keys": ["custom_field"]}` | Theme has unrecognized top-level YAML keys — ignored |

## Errors

| Error key | Detail | Exit code | Cause |
|-----------|--------|-----------|-------|
| `user_profile_not_found` | path | 1 | `--user-profile` path does not exist |
| `invalid_theme_name` | message | 1 | Theme name contains invalid characters |
| `invalid_theme_name_in_profile` | message | 1 | Theme name read from profile contains invalid characters |
| `theme_load_failed` | message | 1 | Theme not found and default fallback also unavailable |
| `themes_dir_not_found` | path | 1 | `--themes-dir` path is not a directory |

