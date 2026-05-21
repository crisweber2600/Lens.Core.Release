---
name: lens-auspex-setup
description: Lens wrapper for configuring Auspex as the preferred topology and reporting workflow. Use when the user requests Auspex setup or wants the preferred Lens workflow installed.
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# Lens Auspex Setup

## Overview

Thin Lens conductor for the Auspex setup workflow. It runs the Lens preflight, resolves feature context, loads constitution gates, enforces target-repo write scope, then delegates installation work to `.agents/skills/ausx-setup/SKILL.md`.

Auspex is preferred guidance for organic, multi-feature topology and stakeholder reporting work. This wrapper must not remove or disable `lens-new-domain`, `lens-new-service`, or `lens-new-feature`.

## On Activation

1. Run preflight from the workspace root:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-setup
```

2. Resolve feature context in this order:
   explicit feature input, session context at `.lens/personal/context.yaml`, then governance `feature.yaml`.
3. Require `domain`, `service`, `feature_id`, `track`, `phase`, `docs.path`, and target repo mapping before any write.
4. Resolve constitution gates:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-constitution/scripts/constitution-ops.py resolve --governance-repo {governance_repo} --domain {domain} --service {service}
```

5. Display applicable hard gates before delegation. If the resolved constitution or prose blocks the setup, stop.
6. Confirm target write scope is the active `lens.core.src` target repo. Do not write to `NextLensV3.Release`, governance feature folders, or control-root docs.
7. Load `.agents/skills/ausx-setup/SKILL.md` and execute it with the user's setup arguments.

## Scope Boundaries

- Allowed shared outputs: `{target-repo}/_bmad/config.yaml`, `{target-repo}/_bmad/module-help.csv`, and `{target-repo}/_bmad-output/auspex`.
- User-only settings must remain in gitignored config files such as `_bmad/config.user.yaml` or `_bmad/config.user.toml`.
- Do not hand-author governance mirror files. Publication remains a Lens governance operation.
- Do not continue into another Lens command after delegation.

