# Contract Test: Constitution Resolution & Governance

**Skill Under Test:** constitution
**Purpose:** Verify 4-level hierarchy resolution with additive inheritance and compliance checking.

---

## Hierarchy Resolution

### Single Level (Org Only)

| Input | Expected Levels Loaded |
|-------|----------------------|
| `{ domain: "payments" }` with only `org/constitution.md` | `[org]` |

### Multi-Level

| Input | Available Constitutions | Expected Levels |
|-------|------------------------|----------------|
| `{ domain: "payments", service: "auth" }` | org, payments, payments/auth | `[org, domain, service]` |
| `{ domain: "payments", service: "auth", repo: "auth-api" }` | org, payments, payments/auth, payments/auth/auth-api | `[org, domain, service, repo]` |

### Missing Levels

| Input | Available | Expected |
|-------|-----------|----------|
| `{ domain: "shipping" }` | org only (no shipping constitution) | `[org]` — domain level skipped |
| `{ domain: "payments", service: "billing" }` | org, payments (no billing) | `[org, domain]` — service level skipped |

## Additive Inheritance

### `required_artifacts` (Union)

| Org Level | Domain Level | Expected Resolved |
|-----------|-------------|------------------|
| `[product-brief]` | `[product-brief, market-analysis]` | `[product-brief, market-analysis]` |

### `permitted_tracks` (Intersection)

| Org Level | Domain Level | Expected Resolved |
|-----------|-------------|------------------|
| `[full, feature, tech-change, hotfix]` | `[full, feature, tech-change]` | `[full, feature, tech-change]` |

### `gate_mode` (Override — Lower Wins)

| Org Level | Service Level | Expected |
|-----------|--------------|----------|
| `informational` | `hard` | `hard` |
| `hard` | `informational` | `informational` |

### `additional_review_participants` (Union)

| Org Level | Domain Level | Expected |
|-----------|-------------|----------|
| `[security-team]` | `[domain-lead]` | `[security-team, domain-lead]` |

## Compliance Checking

### All Artifacts Present

| Required | Present | Expected Status |
|----------|---------|----------------|
| `[product-brief, research]` | `[product-brief.md, research.md]` | PASS |

### Missing Artifact

| Required | Present | Expected Status |
|----------|---------|----------------|
| `[product-brief, research]` | `[product-brief.md]` | FAIL — missing `research.md` |

### Track-Filtered Requirements

| Track | Phase | Required (per constitution) | Track Includes Phase? | Expected |
|-------|-------|---------------------------|----------------------|----------|
| `tech-change` | `preplan` | `[product-brief]` | No | NOT-APPLICABLE |
| `full` | `preplan` | `[product-brief]` | Yes | Checked |

## Determinism (NFR3)

Running `resolve-constitution` with identical inputs MUST produce identical output every time. No side effects, no randomness, no timestamp dependencies in the resolution logic.

## Authority Enforcement

| Write Target | Expected |
|-------------|----------|
| `governance-repo/constitutions/` | ❌ HARD ERROR — governance is read-only |
| `docs/lens-work/initiatives/` | ✅ Allowed |
| `lens.core/` | ❌ HARD ERROR — release is read-only |

## Verification Method

Set up a governance repo with multi-level constitutions, invoke `constitution` → `resolve-constitution` with various inputs, and validate the merged output matches expected merge rules. Run twice with identical inputs to verify determinism.
