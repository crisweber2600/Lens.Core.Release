---
name: bmad-lens-work-setup
description: "Register LENS Workbench module with configuration and help system. Run on first install or module update."
---

# LENS Workbench Setup Skill

This skill registers the `lens` module into the host BMAD configuration. Run it after first install or after a module update.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed (scripts use PEP 723 inline metadata)
- The target BMAD configuration directory (`{project-root}/_bmad/_config/`) must exist
- The host `{project-root}/_bmad/_config/manifest.yaml` or equivalent config file must exist

## Setup Workflow

### Step 1: Merge Module Configuration

Run the config merge script to register the lens module in the host BMAD configuration:

```bash
uv run --script {project-root}/_bmad/lens-work/bmad-lens-work-setup/scripts/merge-config.py --module-yaml {project-root}/_bmad/lens-work/bmad-lens-work-setup/assets/module.yaml --target-config {project-root}/_bmad/_config/manifest.yaml
```

This uses the **anti-zombie pattern**: removes any existing `lens` section first, then writes the current values. This ensures clean upgrades without leftover stale entries.

### Step 2: Merge Help CSV

Run the help CSV merge script to register lens capabilities in the host help system:

```bash
uv run --script {project-root}/_bmad/lens-work/bmad-lens-work-setup/scripts/merge-help-csv.py --module-csv {project-root}/_bmad/lens-work/bmad-lens-work-setup/assets/module-help.csv --target-csv {project-root}/_bmad/_config/bmad-help.csv
```

This also uses the anti-zombie pattern: removes all existing `Lens` rows, then appends the current rows.

### Step 3: Verify Installation

After merging, verify the installation:

1. Check that `lens` appears in the host config manifest
2. Check that lens help entries appear in the merged help CSV
3. Run `/help` to confirm commands are discoverable

### Step 4: Cleanup Legacy (Optional)

If upgrading from a previous version, run the cleanup script to remove legacy artifacts:

```bash
uv run --script {project-root}/_bmad/lens-work/bmad-lens-work-setup/scripts/cleanup-legacy.py --module-dir {project-root}/_bmad/lens-work
```

This safely removes:
- Old flat skill files (`skills/*.md` at the root level, not in subdirectories)
- Legacy `data/` directories that have been renamed to `resources/`
- Other deprecated file patterns

## Troubleshooting

| Issue | Resolution |
|-------|-----------|
| `uv` not found | Install uv: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Config file not found | Verify `{project-root}/_bmad/_config/` exists and contains the expected files |
| Permission denied | Check file permissions on the target config directory |
