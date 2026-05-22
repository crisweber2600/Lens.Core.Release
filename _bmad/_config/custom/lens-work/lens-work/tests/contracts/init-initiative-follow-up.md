# Contract Test: Init Initiative Service Follow-Up

**Workflow Under Test:** init-initiative
**Purpose:** Verify that `/new-service` seeds a one-shot service context for the next `/new-feature` call and that explicit feature arguments override both recent-chat context and branch-derived context.

---

## Test Cases — One-Shot Recent Service Context

| Sequence | Existing Branch Context | Expected Domain | Expected Service | Expected Behavior |
|----------|-------------------------|-----------------|------------------|-------------------|
| `/new-service processing` → `/new-feature billing-pipeline` | `newversion-scraper-*` | `newversion` | `processing` | Create feature `billingpipeline` under `newversion/processing` |
| `/new-service processing` → `/new-feature processing` | `newversion-scraper-*` | `newversion` | `processing` | Reuse `newversion/processing`, then ask for the real feature name instead of treating `processing` as the feature id |
| `/new-service processing` → `/new-feature` | any | `newversion` | `processing` | Ask only for the feature name |

## Test Cases — Explicit Override Forms

| Command | Available Context | Expected Interpretation |
|---------|-------------------|-------------------------|
| `/new-feature billing-pipeline` | no recent-service context, branch `newversion-scraper-*` | Use branch-derived `newversion/scraper`, feature `billingpipeline` |
| `/new-feature processing billing-pipeline` | recent service `processing`, branch service `scraper` | Use service `processing`, feature `billingpipeline` |
| `/new-feature newversion processing billing-pipeline` | any recent-service or branch context | Use explicit domain `newversion`, explicit service `processing`, feature `billingpipeline` |

## Test Cases — One-Shot Consumption

| Sequence | Expected Result |
|----------|-----------------|
| `/new-service processing` → `/new-feature billing-pipeline` → `/new-feature auth-refresh` on branch `newversion-scraper-*` | The second feature falls back to the current branch service `scraper` unless another `/new-service` runs first |
| `/new-service processing` → `/new-feature newversion scraper auth-refresh` | Explicit override wins and the pending service context is cleared after feature creation |

## Verification Method

Run each sequence in the same chat session. Confirm that the collected domain, service, and feature values shown by Step 2 match the expected interpretation before the workflow advances into validation and creation.