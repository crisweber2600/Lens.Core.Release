---
feature: lens-dev-new-codebase-finalizeplan
doc_type: test-coverage-gaps
status: draft
updated_at: 2026-04-30T00:00:00Z
---

# FinalizePlan Test Coverage Gaps

| Gap | Severity | Current Coverage | Next Step |
|---|---|---|---|
| FinalizePlan step-2 PR creation path | High | Structural tests verify the conductor routes through `merge-plan --strategy pr`, but do not exercise `gh pr` behavior. | Add an integration test with a temporary git remote or mocked `gh` CLI. |
| FinalizePlan step-3 bundle plus final PR path | High | Structural tests verify delegation order and phase-update placement, but do not execute downstream BMAD skills or create a final PR. | Add an end-to-end fixture that mocks `lens-bmad-skill` outputs and `lens-git-orchestration create-pr`. |
| ExpressPlan constitution mock test | Medium | Story notes confirm the real governance constitution permits express tracks, and structural tests verify the gate exists. | Add a mock constitution fixture covering permitted and blocked express tracks. |
| End-to-end command activation | Medium | Prompt-chain tests verify public stubs and thin redirects, but do not activate `/lens-finalizeplan` or `/lens-expressplan` in a real IDE session. | Add behavior-level command activation tests once the prompt runner has a stable harness. |

These gaps are tracked as hardening work. They do not block the current clean-room conductor implementation because the current scope is structural skill delivery and regression coverage.