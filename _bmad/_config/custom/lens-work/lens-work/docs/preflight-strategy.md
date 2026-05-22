# Preflight Pull Strategy

## Branch-Aware Freshness Windows

The preflight pull strategy uses different freshness windows depending on the current branch to balance synchronization frequency against developer flow:

| Branch | Window | Rationale |
|--------|--------|-----------|
| `alpha` | 1 hour | Pre-release branch with frequent changes from multiple contributors. Short window ensures governance, workflows, and adapter files stay current during rapid iteration. |
| `beta` | 3 hours | Stabilization branch with fewer changes. Moderate window avoids disrupting focused testing/validation sessions while keeping authority repos reasonably fresh. |
| All others | Daily | Development and feature branches change infrequently in authority repos. Daily cadence prevents unnecessary network calls while guaranteeing daily sync. |

## Full vs. Partial Preflight

- **Full preflight:** Pulls all authority repos, syncs `.github/`, prunes stale managed `.github/` files recorded in the local hash manifest, verifies IDE adapters, and updates the preflight timestamp.
- **Partial preflight (cache hit):** Skips pulls but still reconciles `.github/` against the current local `lens.core` snapshot to catch local deletions or manual modifications. Upstream deletions are only observed after the next full preflight refreshes `lens.core`.

## Managed `.github/` Reconciliation

- `.lens/.github-hashes` tracks the `.github/` files last synchronized from `lens.core/.github/`.
- Preflight removes only files that were previously synced and are no longer present in `lens.core/.github/`.
- Untracked local `.github/` files are preserved, except for `.github/prompts/*.prompt.md` files that fall outside the published `lens-*.prompt.md` contract.

## Timestamp Mechanism

The timestamp file (`.lens/.preflight-timestamp`) stores the last successful full preflight time as an ISO 8601 UTC datetime. This file is local-only (not committed) and lives in the universal Lens settings directory so it can stay separate from personal profile state.
