---
name: lens-auspex-start
description: Preferred Auspex entry point for creating a new Lens unit of work, bootstrapping durable memory, and handing off to lens-next.
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# Lens Auspex Start

## Overview

`lens-auspex-start` is the preferred entry point for organic Auspex work. It creates a normal Lens governance feature, bootstraps an Auspex memory artifact under `docs/features/<feature-id>/memory.md`, records related unit context when supplied, then delegates to `lens-next`.

The memory artifact follows the Codex-maxxing memory principle: useful work context should become a durable, inspectable, editable, diffable file instead of remaining trapped in chat history. Reference: https://jxnl.github.io/blog/writing/2026/05/10/codex-maxxing/

## Contract

This wrapper is orchestration-only:

- Run Lens preflight before any config resolution or delegation.
- Resolve domain, service, and track using Lens rules.
- Require explicit operator confirmation of domain, service, and track before feature creation.
- Resolve and display constitution gates with `lens-constitution` for the selected domain and service before feature creation.
- Delegate feature creation to `lens-init-feature`; never write governance directly.
- Execute returned branch/context follow-up through Lens orchestration and `lens-switch`.
- Bootstrap memory only through `scripts/auspex_start_memory.py`.
- Enforce write scope before memory bootstrap.
- Auto-delegate to `lens-next` after memory bootstrap succeeds.
- Run the required Lens postflight after each Lens command execution.

## On Activation

### Step 1 - Preflight

Run from the workspace root:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py --caller lens-auspex-start
```

If preflight exits non-zero, stop and surface the failure.

### Step 2 - Resolve Configuration

Resolve:

- `{governance_repo}` from `.lens/governance-setup.yaml` or Lens config
- `{control_repo}` as the workspace root
- `{module_path}` as `lens.core/_bmad/lens-work`
- `{feature_title}` from the command argument or a follow-up question
- `{domain}`, `{service}`, and `{track}` using the same rules as `lens-new-feature`
- optional `{related_feature_ids}` from repeated `--related <feature-id>` values
- optional `{initial_intent}` or `{memory_note}` from the user's prompt

If a related feature is supplied, load its governance summary and any existing `docs/features/<related-feature-id>/memory.md` as context. Use that context to recommend the same domain and service when appropriate, but require the operator to explicitly confirm or override before creation.

Resolve constitution gates before creating the feature:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-constitution/scripts/constitution-ops.py resolve --governance-repo {governance_repo} --domain {domain} --service {service}
```

Display applicable hard gates. If the resolved constitution or prose blocks the new unit of work, stop before delegation.

### Step 3 - Create The Lens Feature

Load and delegate to:

```text
lens.core/_bmad/lens-work/skills/lens-init-feature/SKILL.md
```

Use the `create` intent. The underlying write path must remain `init-feature-ops.py create`.

After creation, execute returned `remaining_commands` in order. This is expected to include control branch creation and `lens-switch` context activation when a separate control repo is configured.

### Step 4 - Bootstrap Auspex Memory

After the feature context is active, run:

```bash
uv run --script lens.core/_bmad/lens-work/skills/lens-auspex-start/scripts/auspex_start_memory.py \
  --project-root {control_repo} \
  --feature-id {feature_id} \
  --title "{feature_title}" \
  --domain {domain} \
  --service {service} \
  --track {track} \
  --docs-path {docs_path} \
  --intent "{initial_intent}" \
  --related {related_feature_id}
```

Repeat `--related` for each related feature. The script may write only:

```text
docs/features/<feature-id>/memory.md
```

It must not write governance files, release clone files, `_bmad-output`, or landscape ledgers.

### Step 5 - Hand Off To Lens Lifecycle

Load and delegate to:

```text
lens.core/_bmad/lens-work/skills/lens-next/SKILL.md
```

Pass the created `{feature_id}`. `lens-next` owns the lifecycle routing decision.

## Memory Artifact

The memory artifact must include frontmatter:

```yaml
featureId: example-domain-service-feature
kind: auspex_unit_memory
status: active
belongs_to:
  service: example-service
  domain: example-domain
  program: null
related_units: []
docs_path: docs/example-domain/example-service/example-domain-service-feature
promotion_status: pending
created_at: 2026-05-21T00:00:00Z
updated_at: 2026-05-21T00:00:00Z
```

The body must include these sections:

- Intent
- Decisions
- Open Loops
- Related Context
- Lifecycle Handoff
- Promotion Notes

## Boundaries

- Do not create, patch, or publish governance artifacts inline.
- Do not move feature archives.
- Do not write to `NextLensV3.Release`.
- Do not write to `_bmad-output/auspex`.
- Do not update landscape ledgers; use `lens-auspex-ledger-promotion` after lifecycle work produces durable knowledge.
- Do not replace `lens-new-feature`; this command wraps it as the preferred Auspex start path.
