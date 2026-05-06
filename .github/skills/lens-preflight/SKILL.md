---
name: lens-preflight
description: "Public lightweight preflight runner for workspace validation before governance operations."
classification: utility
---

# Preflight

## Overview

This is a public utility skill.

It provides `scripts/light-preflight.py` — a prompt-start wrapper that performs a fast root/Python gate, accepts the public preflight arguments, and delegates to `scripts/preflight.py` for full workspace sync and validation.

Invoke this skill via the Lens preflight command flow.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/light-preflight.py` | Prompt-start wrapper for the full preflight sync. Accepts `--caller <name>`, `--governance-path <path>`, `--request-class <read-only|control-write|governance-write|mixed>`, and `--skip-constitution`. |
| `scripts/preflight.py` | Full workspace preflight: authority repo sync, governance sync, version checks, prompt sync, and prompt hygiene. |

## Usage

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py [--caller <name>] [--governance-path <path>] [--request-class <class>]
```

From inside a source-repo (e.g. `TargetProjects/lens-dev/new-codebase/lens.core.src`) that is nested
within a workspace root which has a `lens.core/` checkout, `light-preflight.py` will locate the
workspace root automatically:

```bash
uv run --script _bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py [--caller <name>] [--governance-path <path>] [--request-class <class>]
```

> **Note**: A standalone source-repo root (no enclosing workspace with a `lens.core/` checkout) is not
> supported by `preflight.py`. `light-preflight.py` will report a root-detection failure in that case.
