# Collect and Write Config

## Purpose

Gather user preferences and write them to `user-profile.md` and `lens.core/_bmad/config.user.yaml` inside the governance repo. This step runs after scaffold and before the first feature is created.

## Config Fields

| Field | Required | Default | Description |
|---|---|---|---|
| `username` | Yes | — | GitHub username (used for feature ownership) |
| `github_pat` | Yes | — | Personal access token with repo scope |
| `default_ide` | Yes | `cursor` | IDE for adapter setup (`cursor`, `vscode`, `windsurf`) |
| `target_repos` | Yes | — | Comma-separated list of control repo URLs |
| `default_track` | No | `full` | Default planning track (`full`, `quickplan`, `hotfix`, `express`) |
| `theme` | No | `default` | Lens theme name |

## Progressive Disclosure

Ask essential questions as a single grouped prompt:
1. GitHub username
2. GitHub PAT (masked in display)
3. Default IDE
4. Target repo URL(s)

Then confirm defaults and offer to change:
- Default track: `full` — "Change? (y/N)"
- Theme: `default` — "Change? (y/N)"

## Files Written

### `users/{username}.md`

```markdown
# {username}

username: {username}
default_ide: {default_ide}
default_track: {default_track}
theme: {theme}
target_repos:
  - {repo1}
  - {repo2}
```

### `lens.core/_bmad/config.user.yaml`

```yaml
github_pat: "{pat}"
username: "{username}"
default_ide: "{default_ide}"
target_repos:
  - {repo1}
default_track: "{default_track}"
theme: "{theme}"
```

The `lens.core/_bmad/` directory is created if it does not exist. All writes are atomic (temp file + rename).

## Post-Write Git Sync

After the script confirms `status: ok`, commit and push the written files to the governance remote:

```bash
git -C {governance_dir} add users/{username}.md lens.core/_bmad/config.user.yaml
git -C {governance_dir} commit -m "chore: write user config for {username}"
git -C {governance_dir} push origin main
```

Skip this section when `--dry-run` is active. If there is no remote configured yet (first onboard before remote is added), report `⚠ Remote not set — push skipped. Add a remote and run: git -C {governance_dir} push origin main` and continue.

## Output Contract

```json
{
  "status": "ok" | "error",
  "files_written": [
    "users/{username}.md",
    "lens.core/_bmad/config.user.yaml"
  ],
  "message": "optional error message"
}
```

## Dry-Run Behavior

When `--dry-run` is passed:
- No files are written
- `files_written` shows what **would** be written
- File content previews are included as `preview` key in output

## Error Cases

| Condition | Status | Message |
|---|---|---|
| `--username` missing | `"error"` | "--username is required" |
| `--governance-dir` missing | `"error"` | "--governance-dir is required" |
| Path traversal in `--governance-dir` | `"error"` | "Path traversal not allowed in governance-dir" |
| Write failure (permissions) | `"error"` | "Failed to write {path}: {reason}" |
