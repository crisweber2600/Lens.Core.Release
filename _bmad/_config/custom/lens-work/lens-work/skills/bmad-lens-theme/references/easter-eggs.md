# Easter Eggs

Checks whether a phrase or date triggers a hidden behavior in the active theme. Easter eggs are purely cosmetic — they produce a response string but alter no state.

## When to Use

- After receiving user input: run easter egg check against the active theme
- This is a lightweight, side-effect-free check — safe to run on every message
- Only themes with `easter_eggs` entries can trigger; the default theme has none
- **Ownership:** Lens (the top-level coordinating skill) runs the check once per user message. Orchestrated BMM sub-agents do not check independently — Lens injects the response before delegating if an egg fires.

## Trigger Types

| Type | Format | Matching |
|------|--------|---------|
| Phrase | String in `phrases` list | Case-insensitive, word-boundary match — `\bphrase\b` |
| Date | `MM-DD` in theme, ISO date `YYYY-MM-DD` in call | Exact month+day match |

**Note on phrase matching:** Matching uses word boundaries (`\b`), so short triggers like "go" will not match "golang" or "cargo". Keep trigger phrases reasonably specific (2+ words) for best results. Both `--phrase` and `--date` can be provided in a single call; phrase is evaluated before date.

## Output — triggered

```json
{
  "triggered": true,
  "egg_id": "praise-the-omnissiah",
  "response": "⚙️ **01001000 01100101...**\n\nThe machine spirits stir..."
}
```

`egg_id` defaults to `"unknown"` if the egg definition omits the `id` field.

## Output — not triggered

```json
{ "triggered": false }
```

When the theme has no easter eggs at all:

```json
{ "triggered": false, "reason": "no_easter_eggs_in_theme" }
```

## Suppressing Already-Fired Eggs

Pass `--already-fired` as a JSON array of egg IDs to suppress eggs that have already fired this session:

```bash
uv run scripts/theme-ops.py easter-egg \
  --themes-dir /path/to/themes/ \
  --theme wh40k \
  --phrase "praise the omnissiah" \
  --already-fired '["praise-the-omnissiah"]'
```

The calling skill is responsible for maintaining the list of fired egg IDs for the session duration.

## Script Usage

```bash
# Phrase-based check
uv run scripts/theme-ops.py easter-egg \
  --themes-dir /path/to/themes/ \
  --theme wh40k \
  --phrase "praise the omnissiah"

# Date-based check
uv run scripts/theme-ops.py easter-egg \
  --themes-dir /path/to/themes/ \
  --theme wh40k \
  --date "2026-04-06"

# Both triggers in one call (phrase evaluated first)
uv run scripts/theme-ops.py easter-egg \
  --themes-dir /path/to/themes/ \
  --theme wh40k \
  --phrase "praise the omnissiah" \
  --date "2026-04-06"
```

## WH40K Easter Eggs

| ID | Trigger phrases | Notes |
|----|----------------|-------|
| `praise-the-omnissiah` | "praise the omnissiah", "blessed is the omnissiah" | AdMech devotion |
| `for-the-emperor` | "for the emperor", "the emperor protects" | Space Marine rally |
| `heresy` | "this is fine", "technical debt is fine", "we'll fix it later" | Inquisition arrives |
| `machine-spirit-angry` | "the build is broken", "nothing works", "everything is broken" | Debug ritual |

## Adding Easter Eggs to a Theme

In your theme's `.yaml` file, add an `easter_eggs` list. Each entry needs:

```yaml
easter_eggs:
  - id: my-egg           # unique ID string
    triggers:
      phrases:           # word-boundary matching, case-insensitive
        - "trigger phrase one"
        - "trigger phrase two"
      date: "12-25"      # optional MM-DD — activates on that calendar date
    response: >
      The response text shown to the user.
      Can be multi-line markdown.
```

- Phrase triggers and date triggers are independent — either can activate the egg
- At most one easter egg fires per check (first match in the list wins)
- Egg IDs must be unique within a theme to avoid suppression collisions

## Errors

| Error key | Detail | Exit code | Cause |
|-----------|--------|-----------|-------|
| `missing_trigger` | message | 1 | Neither `--phrase` nor `--date` provided |
| `invalid_date_format` | message | 1 | Date is not exactly `YYYY-MM-DD` |
| `invalid_theme_name` | message | 1 | Theme name contains invalid characters |
| `invalid_already_fired` | message | 1 | `--already-fired` is not a valid JSON array |
| `theme_load_failed` | message | 1 | Theme not found and default fallback also unavailable |
| `themes_dir_not_found` | path | 1 | `--themes-dir` path is not a directory |

