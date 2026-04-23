# Lens Core — Initial Core Rules

_This file is the seed content for `rules-core.md` in the agent sanctum. It is used once during `init-sanctum.py` to bootstrap the rules. After initialization, `rules-core.md` is the live document — this file is read-only reference._

_Version: 1.0 — expand during First Breath based on workspace inspection._

---

## Rule Schema

Each rule follows this structure when stored in `rules-core.md`:

```
### {rule-id}: {rule-name}
- **Applies to:** {workspace constructs in scope}
- **Requires:** {what must be true for the rule to pass}
- **Protects:** {what problem or confusion this rule prevents}
- **Verify:** {how to check compliance}
- **Severity:** {blocker | warning}
```

---

## R001: Control Repo Root Structure

- **Applies to:** Control repo root directory
- **Requires:** The following top-level directories must exist: `_bmad/`, `src/`, `.github/`
- **Protects:** Prevents constructs from being placed in arbitrary locations; ensures all agents and tools can find standard artifacts by convention
- **Verify:** `ls {project-root}/` — confirm `_bmad/`, `src/`, `.github/` are present
- **Severity:** blocker

---

## R002: BMad Config Directory

- **Applies to:** `_bmad/` directory
- **Requires:** `_bmad/` must contain `config.yaml` and optionally `config.user.yaml`. The `_config/` subdirectory must contain `manifest.yaml`.
- **Protects:** Ensures agent configuration is discoverable and consistent across agent activations
- **Verify:** `ls {project-root}/_bmad/` — confirm `config.yaml` present; `ls {project-root}/_bmad/_config/` — confirm `manifest.yaml` present
- **Severity:** blocker

---

## R003: Source Submodule Convention

- **Applies to:** `src/` directory
- **Requires:** `src/` must contain at minimum one subdirectory following the naming convention `{project-name}.src/`. Each `*.src/` entry must be a git submodule.
- **Protects:** Ensures source dependencies are tracked as submodules (not raw copies), enabling clean version management and downstream workspace derivation
- **Verify:** Check `src/` for `*.src/` directories; verify `.gitmodules` contains corresponding entries
- **Severity:** blocker

---

## R004: GitHub Redirect Stub Convention

- **Applies to:** `.github/workflows/` and `.github/prompts/`
- **Requires:** Files in `.github/workflows/` and `.github/prompts/` must be redirect stubs pointing to canonical equivalents under `lens.core/` (or the appropriate canonical source). Direct implementation files must not live in `.github/` — they belong in the canonical source.
- **Protects:** Prevents duplication of governance-critical workflow files; ensures the canonical source in `lens.core/` is the single point of truth
- **Verify:** Inspect `.github/workflows/*.yml` and `.github/prompts/*.md` — each must reference a canonical path rather than containing implementation logic
- **Severity:** blocker

---

## R005: Agent Memory Sanctum Location

- **Applies to:** All `lc-agent-*` memory agents
- **Requires:** Each agent's sanctum must live at `{project-root}/_bmad/memory/{skill-name}/`
- **Protects:** Prevents scattered sanctum files; ensures the governance engine can audit agent memory locations consistently
- **Verify:** For each installed memory agent, confirm `_bmad/memory/{skill-name}/` exists and contains `INDEX.md`
- **Severity:** warning

---

## R006: TargetProjects Layout

- **Applies to:** TargetProjects directories if present
- **Requires:** Any `TargetProjects/` directory must follow the pattern `TargetProjects/{project-line}/{stage}/{project-name}/` (e.g., `TargetProjects/lens-dev/release/lens.core.release/`)
- **Protects:** Enforces the standard workspace derivation hierarchy; prevents ad-hoc project location patterns that break cross-workspace tooling
- **Verify:** Inspect any `TargetProjects/` directories and verify the three-level nesting pattern
- **Severity:** warning

---

## R007: Naming Convention — Skill Directories

- **Applies to:** `skills/` directory (if present)
- **Requires:** Skill directories must follow naming convention `{module-code}-{type}-{name}` (e.g., `lc-agent-core-repo`, `bmad-agent-analyst`). No spaces, all lowercase, hyphens as separators.
- **Protects:** Ensures skills are discoverable by module code prefix; allows module-scoped tooling to find all relevant skills
- **Verify:** `ls skills/` — confirm each directory name matches `[a-z]+-[a-z]+-[a-z-]+`
- **Severity:** warning

---

## R008: Agents.md Publication

- **Applies to:** `{project-root}/Agents.md`
- **Requires:** `Agents.md` must exist at the workspace root and must be generated (or confirmed current) by the Governance Enforcement Engine. It is the human-readable public contract for all governance rules.
- **Protects:** Ensures engineers and agents always have a single authoritative document explaining what rules govern the workspace
- **Verify:** `ls {project-root}/Agents.md` — confirm exists and has been updated within the current governance cycle
- **Severity:** warning
