---
model: "Claude Sonnet 4.6 (copilot)"
---

# LENS Workbench Slash Commands

This file registers the LENS Workbench command palette with GitHub Copilot Chat.

## Commands

### Feature Initialization & Status

- `/init-feature` — Create a new feature with 2-branch topology and governance entries
- `/feature-status` — Show current phase, branch state, and activity for a feature  
- `/switch-feature` — Switch active feature context
- `/list-features` — List all features with status and staleness info

### Planning & Execution

- `/plan` — Run full planning pipeline (business → tech → finalize) with adversarial review
- `/validate-plan` — Validate frontmatter and plan state for a feature
- `/next-action` — Resolve the one unblocked next command for current feature
- `/batch` — Generate or resume a two-pass batch intake for planning target

### Git & Branch Operations

- `/read-git-state` — Read branch commit and working tree state  
- `/orchestrate-git` — Execute multi-step git workflows atomically
- `/feature-yaml` — Read/write feature.yaml files atomically

### Governance & Constitution

- `/load-constitution` — Load governance rules and workflow defaults
- `/apply-theme` — Apply visual theme to LENS output

### Problem & Risk Management

- `/log-problem` — Capture a problem or blocker in the feature's problem log
- `/resolve-problem` — Mark a logged problem as resolved
- `/list-problems` — List logged problems for a feature with status filter
- `/analyze-problems` — Analyze problem log patterns and frequencies

### Pause, Resume & Archives

- `/pause` — Pause the current feature preserving state
- `/resume` — Resume a paused feature restoring context  
- `/pause-status` — Check pause state and reason for a feature

### Retrospective & Completion

- `/generate-report` — Generate a narrative retrospective report
- `/update-insights` — Append lessons learned to the governance insights store
- `/document-project` — Run wrapped project documentation workflow before archival
- `/finalize-feature` — Confirm gate and archive a completed feature
- `/archive-status` — Check whether a feature has been archived

### Feature Structuring

- `/move-feature` — Relocate a feature to a new domain/service with reference patching
- `/list-references` — List all cross-references to a feature across governance repo
- `/split-feature` — Create a new feature from a subset of stories
- `/validate-split` — Validate story IDs for splitting
- `/move-stories` — Move story files from source to split feature

### Dashboard & Reporting

- `/generate-dashboard` — Generate self-contained HTML dashboard for all features
- `/dependency-graph` — Build dependency graph data for all features
- `/domain-status` — Show all features in a domain with status
- `/portfolio-status` — Show all active features across portfolio

### Migration (Legacy v3→v4)

- `/scan-legacy` — Scan for legacy LENS v3 branches and build migration plan
- `/migrate-feature` — Migrate a single legacy feature to new 2-branch topology
- `/check-conflicts` — Check for naming conflicts before migration

### Setup & Administration

- `/preflight` — Check prerequisites before governance repo setup
- `/onboard` — Scaffold governance repo and write initial config
- `/write-config` — Write user preferences to user-profile.md and config.user.yaml
- `/setup-lens` — Install or update LENS module configuration
- `/contextual-help` — Show phase-filtered help for current lifecycle state
- `/search-help` — Search help topics by keyword
- `/all-help` — Show all available help topics grouped by category

## Usage Examples

```
/init-feature my-awesome-feature --domain payment --service checkout
/plan my-awesome-feature --track agile
/feature-status my-awesome-feature
/next-action
/log-problem my-awesome-feature "Database connection string not configured"
/analyze-problems my-awesome-feature
/finalize-feature my-awesome-feature
```
