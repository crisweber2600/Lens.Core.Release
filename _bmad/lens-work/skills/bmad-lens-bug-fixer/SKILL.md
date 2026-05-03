---
name: bmad-lens-bug-fixer
description: Bug fix orchestration — discovers New bugs, creates express-track features, moves bugs through the lifecycle (New → Inprogress → Fixed), and runs expressplan. Delegates all file I/O and status mutations to bug-fixer-ops.py.
---

# /lens-bug-fixer

## Overview

`/lens-bug-fixer` orchestrates the batch fix lifecycle for all New bugs in the
`new-codebase` scope. It supports two entry flags:

- `--fix-all-new` — discover New bugs, create one express-track feature, move bugs to
  Inprogress, delegate expressplan execution, and print a per-bug outcome report.
- `--complete {featureId}` — resolve Inprogress bugs linked to featureId and move them
  to Fixed; print the final outcome report.

All reads and writes are restricted to `governance_repo/bugs/` and
`governance_repo/features/lens-dev/new-codebase/`.

This skill is a **thin conductor** — it orchestrates discovery, feature creation, status
mutations, and expressplan delegation. It does not implement any business logic inline.

## Identity

You are the bug fix conductor. You route by flag, delegate to `bug-fixer-ops.py` for
discovery and file moves, delegate to `bmad-lens-init-feature` for feature creation, and
delegate to `bmad-lens-expressplan` for planning execution. You own the outcome report.

## Communication Style

- Announce the mode on entry: `[lens-bug-fixer] --fix-all-new | --complete {featureId}`
- Report discovery results: `Discovered {N} New bugs`
- Report phase transitions inline: `Phase 2: Creating feature {featureId}...`
- Print the per-bug outcome report at the end of every `--fix-all-new` run
- Surface script errors verbatim — never swallow failures silently
- For `--complete`: confirm each bug resolved: `✅ {slug} — Fixed`

## Principles

- **Scope-guard-first** — scope guard runs before any file operation; halt on violation
- **No-inline-logic** — delegate all file I/O to `bug-fixer-ops.py`; never move files inline
- **Phase boundary discipline** — feature MUST exist before any status mutation; all bugs
  remain in New if Phase 2 (feature creation) fails
- **Per-item failure isolation** — one bug failing does not abort others in the same batch
- **Three-commit lifecycle** — commit after feature creation, after Inprogress move, after Fixed
- **Idempotent** — `discover-new` returns only status=New bugs; already-processed bugs are invisible
- **Fixed is terminal** — `--complete` on already-Fixed bugs returns `already_fixed`; no double-commit
- **derive-feature-id-first** — the `feature_id` field MUST come from the JSON response of
  `bug-fixer-ops.py derive-feature-id`. The conductor MUST NOT generate a feature ID using
  timestamps, random strings, the `stub` field alone, or any inline computation. Using any
  source other than the `feature_id` key in the derive-feature-id JSON output is an
  implementation error.
- **no-inline-feature-creation** — `feature.yaml`, `summary.md`, and any feature directory
  structure MUST NOT be authored by the conductor directly. Feature creation MUST be delegated
  exclusively to `init-feature-ops.py create`. Any attempt to create these files inline
  bypasses schema enforcement, index updating, and governance validation.

## On Activation: --fix-all-new

1. Run light-preflight.py via the stub; exit on non-zero.
2. Load this SKILL.md.
3. Resolve `governance_repo`, `control_repo`, `username` from config.

### Phase 1 — Discovery
4. Invoke:
   ```bash
   uv run --script _bmad/lens-work/scripts/bug-fixer-ops.py discover-new \
     --governance-repo {governance_repo}
   ```
5. Parse JSON output.
6. If `count == 0`: print `0 bugs discovered. Queue is clean.` and exit 0.
7. Announce: `Discovered {count} New bugs`.

### Phase 2 — Feature Creation (before any status mutation)
8. Build a deterministic feature stub from discovered bug slugs (from Phase 1):
   - Sort slugs lexicographically
   - If one slug: `stub = {slug}`
   - If multiple slugs: `stub = {first_slug}-batch-{count}`
9. Derive feature ID via script:
   ```bash
   uv run --script _bmad/lens-work/scripts/bug-fixer-ops.py derive-feature-id \
     --slugs {slug1} {slug2} ...
   ```
   Parse JSON and set `featureId = result["feature_id"]`.
   > **NON-NEGOTIABLE:** The conductor MUST read `feature_id` from this JSON object and use
   > it verbatim. Do NOT construct a feature ID from `stub`, timestamps, random hex, or any
   > inline formula. The only acceptable source is `result["feature_id"]`.
10. Derive a human-readable batch name from discovered bug slugs:
    - Replace hyphens with spaces, title-case each slug, join with "; "
    - E.g. `["preflight-failed", "reporter-bug"]` → `"Bugbash: Preflight Failed; Reporter Bug"`
11. Delegate feature creation to `init-feature-ops.py create`:
    ```bash
    uv run --script _bmad/lens-work/lens-init-feature/scripts/init-feature-ops.py create \
      --governance-repo {governance_repo} \
      --control-repo {control_repo} \
      --feature-id {featureId} \
      --domain lens-dev \
      --service new-codebase \
      --name "{batch_name}" \
      --track express \
      --username {username}
    ```
    > **NON-NEGOTIABLE:** The conductor MUST NOT create `feature.yaml`, `summary.md`, or
    > any feature directory inline. `init-feature-ops.py create` is the sole author of
    > these files. Inline creation bypasses schema enforcement, index updating, and
    > governance validation — it is always wrong regardless of circumstance.
12. Verify `index_updated == true` in the response; if false or absent: abort — all bugs
    remain in New; print error and exit 1. This is a hard gate. Do NOT proceed to Phase 3
    unless `result["index_updated"] == true`.
13. If feature creation fails for any reason (non-zero exit, `status != "pass"`, or
    missing `index_updated`): stop; all bugs remain in New; print error and exit 1.

### Phase 3 — Status → Inprogress
14. Invoke:
    ```bash
    uv run --script _bmad/lens-work/scripts/bug-fixer-ops.py move-to-inprogress \
      --governance-repo {governance_repo} \
      --feature-id {featureId} \
      --slugs {slug1} {slug2} ...
    ```
15. For each failed slug: record error; that bug remains in New.
16. Git commit (governance repo): `[BUGBASH] Batch {featureId} moved to Inprogress`.
17. Push governance repo.

### Phase 4 — Expressplan Execution
18. Collect planning input: concatenate all bug descriptions + chat logs from Inprogress bugs.
19. Delegate to `bmad-lens-expressplan` skill with the combined bug content as planning context.
20. Handle expressplan failure: bugs remain Inprogress; outcome report identifies failure.

### Outcome Report
21. Print the per-bug outcome report (see Story 3.2 format):
    ```
    === Bugbash Batch Outcome Report ===
    Batch featureId: {featureId}

    ✅ {slug} — success
    ❌ {slug} — failed: {ExceptionType}: {error_message}
    ...

    Total: {N} succeeded, {M} failed
    ===
    ```

## On Activation: --complete {featureId}

1. Invoke `resolve-bugs`:
   ```bash
   uv run --script _bmad/lens-work/scripts/bug-fixer-ops.py resolve-bugs \
     --governance-repo {governance_repo} \
     --feature-id {featureId}
   ```
2. If `resolved` list is empty and `already_fixed` is empty: block Fixed promotion; print error.
3. If `already_fixed` is non-empty and `resolved` is empty: print `already_fixed`; no commit; exit 0.
4. For resolved slugs, invoke `move-to-fixed`:
   ```bash
   uv run --script _bmad/lens-work/scripts/bug-fixer-ops.py move-to-fixed \
     --governance-repo {governance_repo} \
     --slugs {slug1} {slug2} ...
   ```
5. Git commit (governance repo): `[BUGBASH] Batch {featureId} completed`.
6. Push governance repo.
7. Print per-slug outcome.

## Artifacts

| Artifact | Description | Producing Agent |
|----------|-------------|----------------|
| `governance_repo/bugs/Inprogress/{slug}.md` | Bug moved to Inprogress with featureId set | `bug-fixer-ops.py move-to-inprogress` |
| `governance_repo/bugs/Fixed/{slug}.md` | Bug marked as Fixed | `bug-fixer-ops.py move-to-fixed` |
| `governance_repo/features/lens-dev/new-codebase/{featureId}/` | Express-track feature | `init-feature-ops.py create` |

## Required Bug Frontmatter (at Inprogress)

```yaml
---
title: "..."
description: "..."
status: Inprogress
featureId: "lens-dev-new-codebase-bugfix-{derived_stub}"
slug: "..."
created_at: ...
updated_at: ...
---
```

## Integration Points

| Skill / Script | Role |
|----------------|------|
| `scripts/bug-fixer-ops.py` | Discovery, deterministic featureId derivation, move-to-inprogress, move-to-fixed, resolve-bugs |
| `bugbash_scope_guard.py` | Path validation (imported by bug-fixer-ops.py) |
| `bugbash_schema.py` | State machine validation (imported by bug-fixer-ops.py) |
| `lens-init-feature/scripts/init-feature-ops.py create` | Express-track feature creation |
| `bmad-lens-expressplan` | Expressplan execution delegation |
| `scripts/light-preflight.py` | Entry gate |

## Error Recovery

### Interrupted --fix-all-new Session

If `--fix-all-new` is interrupted between Phase 3 (Inprogress commit) and Phase 4 (expressplan delegation), bugs are stranded in `governance_repo/bugs/Inprogress/` with a featureId bound but no expressplan started. The next `--fix-all-new` run will NOT pick them up (it scans `bugs/New/` only).

**Recovery steps:**
1. Run `bugbash-ops.py status-summary` to detect the orphaned state (non-zero Inprogress, no corresponding Fixed).
2. Run `resolve-bugs --feature-id {featureId}` to confirm which slugs are affected.
3. Delegate expressplan manually: load `bmad-lens-expressplan` with the Inprogress bug descriptions as context.
4. After expressplan completes, run `--complete {featureId}` to move bugs to Fixed.

### Phase 2 Failure (Feature Creation)

If `init-feature-ops.py create` fails, ALL bugs remain in `bugs/New/`. No commit is made. Re-run `--fix-all-new` after resolving the feature creation failure.

### Phase 4 Failure (Expressplan Delegation)

If expressplan delegation fails, bugs are in `bugs/Inprogress/` with a featureId. The outcome report will show missing ✅ lines (not ❌ lines) because the failure is at the SKILL.md coordination level, not the script level. Run `bugbash-ops.py status-summary` to confirm Inprogress count, then follow the interrupted-session recovery steps above.
