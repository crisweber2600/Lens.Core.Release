# LENS Workbench TODO

## Agent Build Checklist

- [x] Primary LENS agent defined for runtime activation in `agents/lens.agent.md`
- [x] Validator-compatible structured companion added in `agents/lens.agent.yaml`
- [x] Run deep agent validation against `agents/lens.agent.yaml`

## Workflow Build Checklist

- [x] Core, router, utility, and governance workflows implemented
- [x] Step-file scaffolding added for single-file workflows so packaging is consistent
- [x] Run deep workflow validation on representative workflows, starting with `router/dev` and `router/sprintplan` — **Done: all 36 workflows validated, all step chains intact**
- [x] Decide whether to fully migrate legacy single-file workflows to step-driven execution — **Decision: only `utility/dashboard` remains single-file (intentional thin wrapper)**

## Testing

- [x] Re-run BMAD module validation after each structural change — **Done: full audit + dry-run of all 125 prompts, 160 path references validated**
- [x] Smoke test installer output for GitHub Copilot, Cursor, Claude, and Codex stubs — **Done: 76 GitHub Copilot stubs synced, all validated**
- [x] Verify `module-help.csv` command ordering remains aligned with the LENS agent menu — **Done: all 16 menu code collisions resolved, zero remaining**

## Next Steps

- [ ] Confirm whether install-question naming remains intentionally snake_case because of installer compatibility
- [ ] Document the dual agent representation (`.md` runtime source and `.yaml` structured companion) in release-facing docs if this pattern is retained

---

## v4.0 Module Audit (completed)

- Fixed `module.yaml` schema_version 3.2 → 3.4
- Created 21 missing Lens Next prompt files
- Created 44 missing GitHub Copilot adapter stubs
- Fixed 16 menu code collisions in `module-help.csv`
- Created missing `utility/profile/SKILL.md`
- Standardized 5 SKILL.md name prefixes to `lens-work-*`
- Removed deprecated `includes/size-topology.md`
- Fixed `promote-to-release.yml`: version extraction bug, IDE list mismatch, prompt overlay deletion bug, Output Folder sed bug, `.yaml` word-boundary fix, PR body wds omission
- Dry-run validated all 125 prompts (0 broken references)
- Added 3 missing prompts to `module.yaml` prompts section
- Added 18 missing `stub_prompts` to `module.yaml` GitHub Copilot adapter

---

## Deferred Items (Quality Scan 2026-04-01)

Items identified during quality scan remediation that are out of scope for the fix pass.

### New Workflows — ✅ COMPLETED

All workflow directories created with SKILL.md, workflow.md, step files, and prompt files:

| Workflow | Purpose | Menu Code |
|----------|---------|-----------|
| `/approval-status` | Show pending promotion PR approval state | AS |
| `/rollback-phase` | Revert a phase to restart artifact production | RB |
| `/pause-epic` | Suspend an in-flight epic without losing state | PE |
| `/resume-epic` | Resume a paused epic | RE |
| `/audit-all-initiatives` | Cross-initiative compliance dashboard | AA |

### Script Extraction — ✅ COMPLETED

All scripts extracted to `scripts/` as cross-platform Python (`.py`) files:

**High (done):** `derive-initiative-status`, `scan-active-initiatives`, `load-command-registry`, `validate-phase-artifacts`, `plan-lifecycle-renames`

**Medium (done):** `validate-feature-move`, `bootstrap-target-projects`, `derive-next-action`, `run-preflight-cached`

### Enhancement Roadmap

**UX — ✅ COMPLETED:**
- First-run scope guidance (pre-init explainer in init-initiative)
- `/next` preview mode (confirmation before auto-execution)
- `/profile` command (view/edit onboarding profile)
- Status health indicators (stuck detection, completeness badges)

**Governance — ✅ COMPLETED:**
- Soft gates for sensing (high-severity overlaps pause with proceed/rename/abort)
- Constitution-aware track filtering (blocked tracks marked ⛔)
- Sensing advisory guidance (per-overlap recommendations)

**Lifecycle — PARTIAL:**
- ✅ Pre-sprintplan readiness summary (epic/story completeness scan)
- [ ] Story-state tracking in initiative-state.yaml
- [ ] Story chaining rollback (`/reset-story-branch`) — complex, warrants own workflow

**Diagnostics — ✅ COMPLETED:**
- Config load failure diagnosis (required fields list + /onboard link)
- LENS_VERSION mismatch upgrade guidance (version display + /lens-upgrade link)
- Move-feature in-flight work safeguards (branch/PR orphan detection)

**Safety — ✅ COMPLETED:**
- Branch-state validation before constitution load in preflight
- Governance repo requirements documented in architecture.md §12

**Architecture — ✅ COMPLETED:**
- Batch PR status queries (status/step-03 collects all PR tuples, single batch call)
- Parallel sensing + constitution (init-initiative/step-03 uses invoke_async for concurrent execution)
- Context propagation pattern (preflight OUTPUT CONTRACT with `session.preflight_result`)

### Architecture Notes

- 28/29 workflows use step-driven architecture; only `utility/dashboard` is single-file (intentional — thin delegation wrapper)
- All shell scripts pass SC2086 quoting checks; flagged `$2` refs are awk/jq field variables inside single quotes (false positives)
- Relative paths (`./`, `../`) in YAML frontmatter are an intentional architectural pattern for intra-workflow step references
