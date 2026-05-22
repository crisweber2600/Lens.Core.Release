# Contract Test: Branch Name Parsing

**Skill Under Test:** git-state
**Purpose:** Verify branch name parsing correctly extracts initiative root, audience, and phase.

---

## Test Cases — 2-Branch Topology

### Parse Initiative Root

| Input Branch | Expected Root | Expected Plan Branch |
|-------------|---------------|---------------------|
| `foo-bar-auth` | `foo-bar-auth` | `foo-bar-auth-plan` |
| `foo-bar-auth-plan` | `foo-bar-auth` | (this is the plan branch) |
| `a-b-c-d` | `a-b-c-d` | `a-b-c-d-plan` |
| `a-b-c-d-plan` | `a-b-c-d` | (this is the plan branch) |
| `payments` | `payments` | `payments-plan` |
| `payments-plan` | `payments` | (this is the plan branch) |

### Non-Initiative Branches

| Input Branch | Expected Behavior |
|-------------|-------------------|
| `main` | Return null initiative |
| `develop` | Return null initiative |
| `feature/epic-1` | Return null initiative |

### Edge Cases

| Input Branch | Expected Root | Notes |
|-------------|---------------|-------|
| `a` | `a` | Single-char root |
| `a-plan` | `a` | Single-char root plan branch |
| `a-b-c-d` | `a-b-c-d` | Multi-segment root |
| `a-b-c-d-plan` | `a-b-c-d` | Multi-segment root plan branch |

---

## Test Cases — Legacy Topology

> ⚠️ Legacy audience-based topology. For new initiatives, use 2-branch topology above.

### Parse Initiative Root

| Input Branch | Expected Root | Expected Audience | Expected Phase |
|-------------|---------------|-------------------|----------------|
| `foo-bar-auth` | `foo-bar-auth` | null | null |
| `foo-bar-auth-small` | `foo-bar-auth` | `small` | null |
| `foo-bar-auth-small-preplan` | `foo-bar-auth` | `small` | `preplan` |
| `foo-bar-auth-medium-devproposal` | `foo-bar-auth` | `medium` | `devproposal` |
| `foo-bar-auth-large-sprintplan` | `foo-bar-auth` | `large` | `sprintplan` |
| `foo-bar-auth-base` | `foo-bar-auth` | `base` | null |

### Edge Cases

| Input Branch | Expected Root | Notes |
|-------------|---------------|-------|
| `a-small` | `a` | Single-char root |
| `a-b-c-d-small-techplan` | `a-b-c-d` | Multi-segment root |
| `payments-small-businessplan` | `payments` | Single-segment root (feature only — domains and services never have audiences) |
| `test-worker-small` | `test-worker` | Feature-level initiative (only features have audience branches) |
| `test-worker-small-techplan` | `test-worker` | Feature-level with phase |

### Slug-Safe Validation

| Input Name | Valid | Reason |
|-----------|-------|--------|
| `thenextone` | ✅ | Lowercase alphanumeric only |
| `foo-bar` | ❌ | Hyphens are not allowed in a single name component |
| `FooBar` | ❌ | Uppercase characters |
| `foo bar` | ❌ | Spaces |
| `foo_bar` | ❌ | Underscores (not slug-safe) |
| `foo--bar` | ❌ | Non-alphanumeric separators are stripped during normalization |
| `-foobar` | ❌ | Non-alphanumeric prefix is invalid input for direct slug-safe validation |

## Verification Method

For each test case, invoke `git-state` → `current-initiative` and `current-phase` with the input branch, and compare parsed output against expected values.
