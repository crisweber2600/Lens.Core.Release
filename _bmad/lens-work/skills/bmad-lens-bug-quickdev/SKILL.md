---
name: bmad-lens-bug-quickdev
description: Bug quick-dev conductor. Takes one bug report, records bug intake, then runs quick-dev implementation in target project with required git and PR flow.
---

# /lens-bug-quickdev

## Overview

`/lens-bug-quickdev` is a single-bug execution flow for direct implementation.
It captures one bug report, records a governance bug artifact, and then delegates
implementation to quick-dev in the target project.

This skill is a thin conductor. It orchestrates inputs and delegation only.

## Required Inputs

Collect these fields before execution:

- `title`
- `description`
- `repro_steps`
- `expected`
- `actual`

If any field is missing, ask only for missing fields and stop until complete.

## On Activation

1. Ensure prompt-start preflight already succeeded.
2. Resolve:
   - `governance_repo = {project-root}/TargetProjects/lens/lens-governance`
   - `target_project = {project-root}/TargetProjects/lens-dev/new-codebase/lens.core.src`
   - `legacy_project = {project-root}/TargetProjects/lens-dev/old-codebase/lens.core.src`
3. Create bug intake artifact:

```bash
uv run --script lens.core/_bmad/lens-work/scripts/bug-reporter-ops.py create-bug \
  --title "{title}" \
  --description "{description}\n\nRepro Steps:\n{repro_steps}\n\nExpected:\n{expected}\n\nActual:\n{actual}" \
  --chat-log "Bug report submitted via /lens-bug-quickdev." \
  --governance-repo {governance_repo}
```

4. Parse script JSON:
   - `status: created` or `status: duplicate` are both valid; continue.
   - On non-zero exit, stop and surface error.
5. Load and run `d:/lensTrees/Lens.Core.control copy/.github/skills/bmad-quick-dev/SKILL.md`.
6. Use this implementation intent exactly:

"Fix this bug report in `TargetProjects/lens-dev/new-codebase/lens.core.src`.
Title: {title}
Description: {description}
Repro Steps: {repro_steps}
Expected: {expected}
Actual: {actual}

Required workflow in target project:
1) `git checkout develop`
2) `git pull`
3) `git checkout -b feature/bugfix-{bug-title-slug}`
4) Before implementing, identify the primary affected Lens command and inspect the same command in `TargetProjects/lens-dev/old-codebase/lens.core.src` to understand legacy behavior and identify gaps. Use the same command name and closest matching prompt/skill/script entrypoint when available. If no legacy match exists, record that as a gap.
5) If the legacy comparison reveals large gaps that materially change expected behavior, workflow, or outputs, stop and use `vscode_askQuestions` to confirm user intent before implementing.
6) Implement the fix and run relevant validation
7) `git add` and `git commit` with conventional commit message
8) `git push -u origin <branch>`
9) Open a PR to `develop` with bug context, legacy-gap notes, and validation notes"

## Output Contract

Return:

- bug artifact path
- branch name
- commit hash
- PR URL
- concise change summary
- validation summary
