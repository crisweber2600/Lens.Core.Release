---
name: lens-preflight
description: "Public lightweight preflight runner for workspace validation before governance operations."
classification: utility
---

# Preflight

## Overview

This is a public utility skill.

It provides `scripts/light-preflight.py` — a lightweight preflight check script used to validate workspace state before governance repo setup.

Invoke this skill via the Lens preflight command flow.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/light-preflight.py` | Check prerequisites (uv, git, config files) before governance setup. Accepts `--caller <name>` and `--governance-path <path>`. |

## Usage

```bash
uv run --script ./_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py [--caller <name>] [--governance-path <path>]
```
