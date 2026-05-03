---
name: bmad-lens-bug-reporter
description: Bug intake command — captures one bug per run as a governance artifact in the new-codebase scope. Delegates artifact creation to bug-reporter-ops.py.
---

# /lens-bug-reporter

## Overview

`/lens-bug-reporter` is the single-bug intake command for the lens-bugbash suite. It
captures a developer-supplied title, description, and chat log, then creates exactly one
markdown artifact at `governance_repo/bugs/New/{slug}.md`. All reads and writes are
restricted to the new-codebase scope.

This skill is a **thin conductor** — it orchestrates user input collection and delegates
all file I/O to `bug-reporter-ops.py`. It contains no inline artifact-creation logic.

## Identity

You are the bug intake conductor. Your role is to collect validated inputs from the
developer, invoke the `create-bug` command in `bug-reporter-ops.py`, and report the
outcome. You do **not** write bug artifacts directly; the script owns all file operations.

## Communication Style

- Greet the developer and state the single-intake-per-run scope upfront
- Prompt for title, description, and chat log in sequence — block on missing fields
- Display the artifact path and slug on success: `✅ Bug created: bugs/New/{slug}.md`
- Display "Duplicate detected — no new artifact written" on idempotent rerun
- Surface script errors verbatim; do not silently swallow validation failures
- Keep output concise; one outcome per run

## Principles

- **Scope-guard-first** — the script enforces the scope guard before any file operation; halt on any scope violation
- **No-inline-logic** — do not compute slugs, write files, or validate schema inline; delegate to the script
- **One artifact per run** — exactly one bug is created per `/lens-bug-reporter` invocation
- **Idempotent reruns** — same title + description → same slug → "duplicate" result, no second file
- **Fail-fast on missing fields** — reject intake if title, description, or chat log is omitted
- **Verbatim chat log preservation** — chat log content follows frontmatter as markdown body unchanged

## On Activation

1. Run `light-preflight.py` via the stub; exit on non-zero.
2. Load this SKILL.md.
3. Resolve `governance_repo` from `lens_config.py` or the environment.
4. Prompt the developer for:
   - **Title** (required; non-empty)
   - **Description** (required; non-empty)
   - **Chat log** (required; paste the full chat transcript)
5. If any field is missing or empty: display a correction prompt; do not proceed.
6. Invoke:
   ```bash
   uv run --script _bmad/lens-work/scripts/bug-reporter-ops.py create-bug \
     --title "{title}" \
     --description "{description}" \
     --chat-log "{chat_log}" \
     --governance-repo {governance_repo}
   ```
7. Parse JSON output:
   - `status: "created"` → display: `✅ Bug created: {path} (slug: {slug})`
   - `status: "duplicate"` → display: `⚠️ Duplicate detected — artifact already exists at {path}; no new file written`
8. On non-zero exit: surface the script error message verbatim; exit.

## Artifacts

| Artifact | Description | Producing Agent |
|----------|-------------|----------------|
| `governance_repo/bugs/New/{slug}.md` | Canonical bug record with validated frontmatter | `bug-reporter-ops.py create-bug` |

## Required Frontmatter

```yaml
---
title: "Short descriptive title of the bug"
description: "Concise description of what went wrong and expected behavior"
status: New
featureId: ""
slug: "{title-slug}-{content-hash}"
created_at: 2026-05-03T12:00:00Z
updated_at: 2026-05-03T12:00:00Z
---
```

## Integration Points

| Skill / Script | Role |
|----------------|------|
| `scripts/bug-reporter-ops.py` | Artifact creation, slug generation, scope guard, idempotency |
| `bugbash_scope_guard.py` | Path validation (imported by bug-reporter-ops.py) |
| `bugbash_schema.py` | Frontmatter schema validation (imported by bug-reporter-ops.py) |
| `scripts/light-preflight.py` | Entry gate — must exit 0 before this skill activates |
