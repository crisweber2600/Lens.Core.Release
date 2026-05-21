---
name: lens-auspex-topology-design
description: Lens wrapper for designing or updating Auspex Two-Tree program, domain, and service topology.
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# Lens Auspex Topology Design

## Overview

Thin Lens conductor for topology design. It resolves Lens governance context and constitution gates before delegating to `.agents/skills/ausx-topology-design/SKILL.md`.

Topology design is preferred over forcing every organic project through a fixed domain/service/feature mental model. Existing domain, service, and feature commands remain available.

## On Activation

1. Run:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-topology-design
```

2. Resolve feature context from explicit input, `.lens/personal/context.yaml`, then governance `feature.yaml`.
3. Require `domain`, `service`, `feature_id`, `track`, `phase`, `docs.path`, and target repo mapping before applying design output.
4. Resolve and display constitution gates with `lens-constitution` for the active domain and service. Stop on violations.
5. Enforce write scope:
   - design reports may be written under `_bmad-output/auspex`
   - `--apply` is required before writing landscape scaffold files
   - landscape writes must stay under the configured `landscape_root`
   - IDs are stable; landscape paths are mutable addresses
   - `NextLensV3.Release` is read-only source material and must not be written
6. Load `.agents/skills/ausx-topology-design/SKILL.md` and delegate the design request.

## Design Contract

Preserve the Two-Tree model: permanent feature archives under `docs/features/`, reorganizable service/domain/program landscape ledgers, and derived map data rebuilt from frontmatter rather than hand-authored.
