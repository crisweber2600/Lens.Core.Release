#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""LENS Workbench — Module Installer.

Sets up IDE adapters (GitHub Copilot, Cursor, Claude, Codex, OpenCode) and output directories.
Safe to re-run: skips existing files unless --update is passed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SUPPORTED_IDES = ["github-copilot", "cursor", "claude", "codex", "opencode"]

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_created = 0
_skipped = 0
_errors = 0
_removed = 0
_dry_run = False
_update = False
_project_root: Path = Path(".")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_adapter_file(file_path: Path, content: str) -> None:
    global _created, _skipped, _errors, _dry_run, _update
    rel = file_path.relative_to(_project_root)
    existed = file_path.exists()
    if existed and not _update:
        print(f"[SKIP] {rel} (exists, use --update to overwrite)")
        _skipped += 1
        return
    if _dry_run:
        verb = "Would overwrite" if existed else "Would create"
        print(f"[INFO] {verb}: {rel}")
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    verb = "Updated" if _update and existed else "Created"
    print(f"[OK]   {verb}: {rel}")
    _created += 1


def ensure_dir(path: Path) -> None:
    if not path.is_dir():
        if _dry_run:
            print(f"[INFO] Would create directory: {path.relative_to(_project_root)}")
        else:
            path.mkdir(parents=True, exist_ok=True)
            print(f"[OK]   Created directory: {path.relative_to(_project_root)}")


def remove_stale_adapter_files(dir_path: Path, predicate, label: str) -> None:
    global _removed, _dry_run
    if not dir_path.exists():
        return

    for child in sorted(dir_path.iterdir()):
        if not child.is_file() or not predicate(child.name):
            continue

        rel = child.relative_to(_project_root)
        if _dry_run:
            print(f"[INFO] Would remove stale {label}: {rel}")
        else:
            child.unlink()
            print(f"[OK]   Removed stale {label}: {rel}")
        _removed += 1


# ---------------------------------------------------------------------------
# Stub generators
# ---------------------------------------------------------------------------

LIGHT_PREFLIGHT_COMMAND = "uv run ./lens.core/_bmad/lens-work/scripts/light-preflight.py"


def gh_stub_prompt(name: str, description: str, target_prompt: str, extra: str = "") -> str:
    extra_block = f"\n{extra}" if extra else ""
    return f"""---
model: Claude Sonnet 4.6 (copilot)
description: '{description}'
---

# {name} (Stub)

> **This is a stub.** Load and execute the full prompt from the release module.
> When appropriate, use `vscode_askQuestions` to get feedback from users if the tool is available.
> All `lens.core/_bmad/` paths in the full prompt are relative to `lens.core/` — do NOT resolve paths against the user's main project repo.

You MUST execute these steps in order:
1. FIRST, run `{LIGHT_PREFLIGHT_COMMAND}` from the workspace root.
2. If that command exits non-zero, stop and surface the failure.
3. ONLY AFTER a successful prompt-start sync, read and follow all instructions in: `lens.core/_bmad/lens-work/prompts/{target_prompt}`

```bash
{LIGHT_PREFLIGHT_COMMAND}
```
{extra_block}"""


def ide_command(name: str, description: str, workflow_path: str) -> str:
    return f"""---
name: '{name}'
description: '{description}'
---

IT IS CRITICAL THAT YOU FOLLOW THIS COMMAND: FIRST, run `{LIGHT_PREFLIGHT_COMMAND}` from the workspace root. If it fails, stop and surface the error. THEN LOAD the FULL @lens.core/_bmad/lens-work/{workflow_path}, READ its entire contents and follow its directions exactly!
"""


# ---------------------------------------------------------------------------
# Common command list for Cursor / Claude / Codex
# ---------------------------------------------------------------------------

COMMANDS = [
    ("bmad-lens-onboard.md", "onboard", "Run shared preflight and show role-aware next steps", "skills/bmad-lens-onboard/SKILL.md"),
    ("bmad-lens-preflight.md", "preflight", "Run shared workspace preflight sync and validation", "prompts/lens-preflight.prompt.md"),
    ("bmad-lens-init-feature.md", "init-feature", "Create new feature with 2-branch topology", "skills/bmad-lens-init-feature/SKILL.md"),
    ("bmad-lens-target-repo.md", "target-repo", "Provision or register a feature target repo and persist governance metadata", "skills/bmad-lens-target-repo/SKILL.md"),
    ("bmad-lens-preplan.md", "preplan", "Launch PrePlan phase (brainstorm/research/product brief)", "skills/bmad-lens-preplan/SKILL.md"),
    ("bmad-lens-businessplan.md", "businessplan", "Launch BusinessPlan phase (PRD/UX design)", "skills/bmad-lens-businessplan/SKILL.md"),
    ("bmad-lens-techplan.md", "techplan", "Launch TechPlan phase (architecture/technical design)", "skills/bmad-lens-techplan/SKILL.md"),
    ("bmad-lens-adversarial-review.md", "adversarial-review", "Run lifecycle adversarial review with a party-mode blind-spot challenge", "skills/bmad-lens-adversarial-review/SKILL.md"),
    ("bmad-lens-finalizeplan.md", "finalizeplan", "Launch FinalizePlan phase (review, planning bundle, PR handoff)", "skills/bmad-lens-finalizeplan/SKILL.md"),
    ("bmad-lens-dev.md", "dev", "Launch Dev phase — epic-level implementation loop", "skills/bmad-lens-dev/SKILL.md"),
    ("bmad-lens-next.md", "next", "Recommend next action based on lifecycle state", "skills/bmad-lens-next/SKILL.md"),
    ("bmad-lens-batch.md", "batch", "Generate or resume a two-pass batch intake for planning targets", "skills/bmad-lens-batch/SKILL.md"),
    ("bmad-lens-switch.md", "switch", "Switch to different feature branch", "skills/bmad-lens-switch/SKILL.md"),
    ("bmad-lens-help.md", "help", "Show available commands and usage reference", "skills/bmad-lens-help/SKILL.md"),
    ("bmad-lens-constitution.md", "constitution", "Resolve and display constitutional governance", "skills/bmad-lens-constitution/SKILL.md"),
    ("bmad-lens-audit.md", "audit", "Run cross-initiative compliance audit dashboard", "skills/bmad-lens-audit/SKILL.md"),
    ("bmad-lens-sensing.md", "sensing", "Cross-initiative overlap detection on demand", "skills/bmad-lens-sensing/SKILL.md"),
    ("bmad-lens-module-management.md", "module-management", "Check module version and clarify legacy branch migration status", "skills/bmad-lens-module-management/SKILL.md"),
    ("bmad-lens-discover.md", "discover", "Sync TargetProjects with governance repo inventory", "skills/bmad-lens-discover/SKILL.md"),
]

COMMAND_FILE_NAMES = {file_name for file_name, _, _, _ in COMMANDS}


# ---------------------------------------------------------------------------
# Phase 1: Output directories
# ---------------------------------------------------------------------------

def install_output_dirs() -> None:
    print("[INFO] Creating output directory structure...")
    for rel in [
        "docs",
        "docs/planning-artifacts",
        "docs/implementation-artifacts",
        "docs/lens-work",
        "docs/lens-work/initiatives",
        ".lens",
        ".lens/personal",
        "docs/reports/lens-work/quality-scan",
    ]:
        ensure_dir(_project_root / rel)


# ---------------------------------------------------------------------------
# Phase 2: GitHub Copilot adapter
# ---------------------------------------------------------------------------

def install_github_copilot() -> None:
    print("[INFO] Installing GitHub Copilot adapter...")

    gh_dir = _project_root / ".github"
    agents_dir = gh_dir / "agents"
    prompts_dir = gh_dir / "prompts"

    if (gh_dir / ".git").is_dir():
        print("[SKIP] GitHub Copilot adapter already installed via cloned copilot repo at .github/; skipping generation")
        return

    ensure_dir(agents_dir)
    ensure_dir(prompts_dir)
    remove_stale_adapter_files(
        prompts_dir,
        lambda name: name.startswith("lens-work") and name.endswith(".prompt.md"),
        "prompt alias",
    )

    # Agent stub
    agent_content = """\
```chatagent
---
description: '@lens — LENS Workbench thin shell for help and next-action routing'
tools: ['read', 'edit', 'search', 'execute']
---

You must fully embody this agent's persona and follow all activation instructions exactly as specified.

<agent-activation CRITICAL="TRUE">
1. LOAD the module config from lens.core/_bmad/lens-work/module.yaml
2. LOAD the FULL agent definition from lens.core/_bmad/lens-work/agents/lens.agent.md
3. READ its entire contents - this contains the complete thin-shell agent persona and menu
4. LOAD the lifecycle contract from lens.core/_bmad/lens-work/lifecycle.yaml
5. LOAD the module help index from lens.core/_bmad/lens-work/module-help.csv
6. FOLLOW every activation step in the agent definition precisely
7. DISPLAY the shell greeting and compact menu from the agent definition
8. WAIT for user input before proceeding
</agent-activation>

```
"""
    write_adapter_file(agents_dir / "bmad-agent-lens-work-lens.agent.md", agent_content)

    # Stub prompts
    prompts = [
        ("lens-onboard.prompt.md", "lens-onboard", "Run shared preflight and show role-aware next steps", "lens-onboard.prompt.md"),
        ("lens-preflight.prompt.md", "lens-preflight", "Run shared workspace preflight sync and validation", "lens-preflight.prompt.md"),
        ("lens-init-feature.prompt.md", "lens-init-feature", "Create a new feature with 2-branch topology", "lens-init-feature.prompt.md"),
        ("lens-new-domain.prompt.md", "lens-new-domain", "Create new domain-level constitution scaffolding", "lens-new-domain.prompt.md"),
        ("lens-new-service.prompt.md", "lens-new-service", "Create new service-level constitution scaffolding within a domain", "lens-new-service.prompt.md"),
        ("lens-new-feature.prompt.md", "lens-new-feature", "Initialize a new feature with 2-branch topology, feature YAML, and PR", "lens-new-feature.prompt.md"),
        ("lens-new-project.prompt.md", "lens-new-project", "Bootstrap a new project by creating or reusing domain/service containers, initializing a feature, and provisioning a target repo", "lens-new-project.prompt.md"),
        ("lens-target-repo.prompt.md", "lens-target-repo", "Provision or register a feature target repo in GitHub, TargetProjects, and governance metadata", "lens-target-repo.prompt.md"),
        ("lens-preplan.prompt.md", "lens-preplan", "Run PrePlan phase (brainstorm, research, product brief)", "lens-preplan.prompt.md"),
        ("lens-businessplan.prompt.md", "lens-businessplan", "Run BusinessPlan phase (PRD, UX design)", "lens-businessplan.prompt.md"),
        ("lens-techplan.prompt.md", "lens-techplan", "Run TechPlan phase (architecture, technical design)", "lens-techplan.prompt.md"),
        ("lens-adversarial-review.prompt.md", "lens-adversarial-review", "Run lifecycle adversarial review with a party-mode blind-spot challenge", "lens-adversarial-review.prompt.md"),
        ("lens-finalizeplan.prompt.md", "lens-finalizeplan", "Run FinalizePlan phase (review, planning bundle, PR handoff)", "lens-finalizeplan.prompt.md"),
        ("lens-expressplan.prompt.md", "lens-expressplan", "Run ExpressPlan phase (all artifacts in one session)", "lens-expressplan.prompt.md"),
        ("lens-dev.prompt.md", "lens-dev", "Launch Dev phase — epic-level implementation loop with story management", "lens-dev.prompt.md"),
        ("lens-complete.prompt.md", "lens-complete", "Complete feature lifecycle — retrospective, archive, close", "lens-complete.prompt.md"),
        ("lens-retrospective.prompt.md", "lens-retrospective", "Post-feature retrospective and lessons learned", "lens-retrospective.prompt.md"),
        ("lens-next.prompt.md", "lens-next", "Recommend next action based on lifecycle state", "lens-next.prompt.md"),
        ("lens-batch.prompt.md", "lens-batch", "Generate or resume a two-pass batch intake for planning targets", "lens-batch.prompt.md"),
        ("lens-switch.prompt.md", "lens-switch", "Switch to a different feature via git checkout", "lens-switch.prompt.md"),
        ("lens-constitution.prompt.md", "lens-constitution", "Resolve and display constitutional governance", "lens-constitution.prompt.md"),
        ("lens-sensing.prompt.md", "lens-sensing", "Run cross-initiative overlap detection", "lens-sensing.prompt.md"),
        ("lens-audit.prompt.md", "lens-audit", "Run cross-initiative compliance audit dashboard", "lens-audit.prompt.md"),
        ("lens-approval-status.prompt.md", "lens-approval-status", "Show promotion PR approval status", "lens-approval-status.prompt.md"),
        ("lens-help.prompt.md", "lens-help", "Show available commands and usage", "lens-help.prompt.md"),
        ("lens-log-problem.prompt.md", "lens-log-problem", "Record issues and friction points for active feature", "lens-log-problem.prompt.md"),
        ("lens-move-feature.prompt.md", "lens-move-feature", "Reclassify feature to different domain/service", "lens-move-feature.prompt.md"),
        ("lens-split-feature.prompt.md", "lens-split-feature", "Split feature into multiple initiatives", "lens-split-feature.prompt.md"),
        ("lens-pause-resume.prompt.md", "lens-pause-resume", "Pause or resume feature with state preservation", "lens-pause-resume.prompt.md"),
        ("lens-rollback.prompt.md", "lens-rollback", "Safely roll back to a previous lifecycle phase", "lens-rollback.prompt.md"),
        ("lens-profile.prompt.md", "lens-profile", "View and edit onboarding profile", "lens-profile.prompt.md"),
        ("lens-bmad-brainstorming.prompt.md", "lens-bmad-brainstorming", "Run BMAD brainstorming with Lens context", "lens-bmad-brainstorming.prompt.md"),
        ("lens-bmad-product-brief.prompt.md", "lens-bmad-product-brief", "Run BMAD product brief with Lens context", "lens-bmad-product-brief.prompt.md"),
        ("lens-bmad-domain-research.prompt.md", "lens-bmad-domain-research", "Run BMAD domain research with Lens context", "lens-bmad-domain-research.prompt.md"),
        ("lens-bmad-market-research.prompt.md", "lens-bmad-market-research", "Run BMAD market research with Lens context", "lens-bmad-market-research.prompt.md"),
        ("lens-bmad-technical-research.prompt.md", "lens-bmad-technical-research", "Run BMAD technical research with Lens context", "lens-bmad-technical-research.prompt.md"),
        ("lens-bmad-create-prd.prompt.md", "lens-bmad-create-prd", "Run BMAD create PRD with Lens context", "lens-bmad-create-prd.prompt.md"),
        ("lens-bmad-create-ux-design.prompt.md", "lens-bmad-create-ux-design", "Run BMAD create UX design with Lens context", "lens-bmad-create-ux-design.prompt.md"),
        ("lens-bmad-create-architecture.prompt.md", "lens-bmad-create-architecture", "Run BMAD create architecture with Lens context", "lens-bmad-create-architecture.prompt.md"),
        ("lens-bmad-create-epics-and-stories.prompt.md", "lens-bmad-create-epics-and-stories", "Run BMAD create epics and stories with Lens context", "lens-bmad-create-epics-and-stories.prompt.md"),
        ("lens-bmad-check-implementation-readiness.prompt.md", "lens-bmad-check-implementation-readiness", "Run BMAD implementation readiness with Lens context", "lens-bmad-check-implementation-readiness.prompt.md"),
        ("lens-bmad-sprint-planning.prompt.md", "lens-bmad-sprint-planning", "Run BMAD sprint planning with Lens context", "lens-bmad-sprint-planning.prompt.md"),
        ("lens-bmad-create-story.prompt.md", "lens-bmad-create-story", "Run BMAD create story with Lens context", "lens-bmad-create-story.prompt.md"),
        ("lens-bmad-quick-dev.prompt.md", "lens-bmad-quick-dev", "Run BMAD quick dev with Lens context", "lens-bmad-quick-dev.prompt.md"),
        ("lens-bmad-code-review.prompt.md", "lens-bmad-code-review", "Run BMAD code review with Lens context", "lens-bmad-code-review.prompt.md"),
        ("lens-bmad-document-project.prompt.md", "lens-bmad-document-project", "Run BMAD document-project with Lens-aware feature docs scope", "lens-bmad-document-project.prompt.md"),
        ("lens-module-management.prompt.md", "lens-module-management", "Check module version and clarify legacy branch migration status", "lens-module-management.prompt.md"),
        ("lens-upgrade.prompt.md", "lens-upgrade", "Migrate control repo schema to current version or route legacy branches to lens-migrate", "lens-upgrade.prompt.md"),
        ("lens-dashboard.prompt.md", "lens-dashboard", "Cross-feature dashboard with dependency graphs", "lens-dashboard.prompt.md"),
        ("lens-discover.prompt.md", "lens-discover", "Sync TargetProjects with governance repo inventory", "lens-discover.prompt.md"),
        ("lens-feature-yaml.prompt.md", "lens-feature-yaml", "Feature YAML lifecycle operations", "lens-feature-yaml.prompt.md"),
        ("lens-git-orchestration.prompt.md", "lens-git-orchestration", "Git write operations for Lens features", "lens-git-orchestration.prompt.md"),
        ("lens-git-state.prompt.md", "lens-git-state", "Read-only git queries for Lens features", "lens-git-state.prompt.md"),
        ("lens-migrate.prompt.md", "lens-migrate", "Migration bridge between LENS v3 and Lens Next", "lens-migrate.prompt.md"),
        ("lens-theme.prompt.md", "lens-theme", "Theme loading and persona overlay system", "lens-theme.prompt.md"),
        ("lens-quickplan.prompt.md", "lens-quickplan", "End-to-end QuickPlan pipeline", "lens-quickplan.prompt.md"),
    ]

    for file_name, name, desc, target in prompts:
        write_adapter_file(prompts_dir / file_name, gh_stub_prompt(name, desc, target))

    # Instructions file
    instructions = """\
<!-- LENS-WORK ADAPTER -->
# LENS Workbench — Copilot Instructions

## Module Reference

This control repo uses the LENS Workbench module from the release payload:

- **Module path:** `lens.core/_bmad/lens-work/`
- **Lifecycle contract:** `lens.core/_bmad/lens-work/lifecycle.yaml`
- **Module version:** See `lens.core/_bmad/lens-work/module.yaml`

## Agent

The `@lens` agent is defined at `.github/agents/bmad-agent-lens-work-lens.agent.md` and references
the module agent at `lens.core/_bmad/lens-work/agents/lens.agent.md`.

## Skills (by path reference)

| Skill | Path |
|-------|------|
| bmad-lens-git-state | `lens.core/_bmad/lens-work/skills/bmad-lens-git-state/SKILL.md` |
| bmad-lens-git-orchestration | `lens.core/_bmad/lens-work/skills/bmad-lens-git-orchestration/SKILL.md` |
| bmad-lens-constitution | `lens.core/_bmad/lens-work/skills/bmad-lens-constitution/SKILL.md` |
| bmad-lens-sensing | `lens.core/_bmad/lens-work/skills/bmad-lens-sensing/SKILL.md` |
| bmad-lens-checklist | `lens.core/_bmad/lens-work/skills/bmad-lens-checklist/SKILL.md` |

## Important

- This adapter references module content by path — it NEVER duplicates it
- Do not copy skills, workflows, or lifecycle definitions into `.github/`
- Module updates propagate automatically through path references
<!-- /LENS-WORK ADAPTER -->
"""
    write_adapter_file(gh_dir / "lens-work-instructions.md", instructions)
    print("[OK]   GitHub Copilot adapter complete")


# ---------------------------------------------------------------------------
# Phase 3: Cursor
# ---------------------------------------------------------------------------

def install_cursor() -> None:
    print("[INFO] Installing Cursor adapter...")
    cursor_dir = _project_root / ".cursor/commands"
    ensure_dir(cursor_dir)
    remove_stale_adapter_files(
        cursor_dir,
        lambda name: name in COMMAND_FILE_NAMES,
        "command alias",
    )
    for fname, name, desc, wf in COMMANDS:
        write_adapter_file(cursor_dir / fname, ide_command(name, desc, wf))
    print("[OK]   Cursor adapter complete")


# ---------------------------------------------------------------------------
# Phase 4: Claude
# ---------------------------------------------------------------------------

def install_claude() -> None:
    print("[INFO] Installing Claude Code adapter...")
    claude_dir = _project_root / ".claude/commands"
    ensure_dir(claude_dir)
    remove_stale_adapter_files(
        claude_dir,
        lambda name: name in COMMAND_FILE_NAMES,
        "command alias",
    )
    for fname, name, desc, wf in COMMANDS:
        write_adapter_file(claude_dir / fname, ide_command(name, desc, wf))
    print("[OK]   Claude Code adapter complete")


# ---------------------------------------------------------------------------
# Phase 5: Codex
# ---------------------------------------------------------------------------

def install_codex() -> None:
    print("[INFO] Installing Codex CLI adapter...")

    agents_md = """\
# LENS Workbench — Codex Agent

This project uses the LENS Workbench module for lifecycle routing and git orchestration.

## Module Reference

- **Module path:** `lens.core/_bmad/lens-work/`
- **Agent definition:** `lens.core/_bmad/lens-work/agents/lens.agent.md`
- **Lifecycle contract:** `lens.core/_bmad/lens-work/lifecycle.yaml`
- **Module config:** `lens.core/_bmad/lens-work/module.yaml`

## Activation

1. LOAD the module config from `lens.core/_bmad/lens-work/module.yaml`
2. LOAD the FULL agent definition from `lens.core/_bmad/lens-work/agents/lens.agent.md`
3. READ its entire contents — this contains the complete agent persona, skills, lifecycle routing, and phase-to-agent mapping
4. LOAD the lifecycle contract from `lens.core/_bmad/lens-work/lifecycle.yaml`
5. FOLLOW every activation step in the agent definition precisely

## Available Commands

See `lens.core/_bmad/lens-work/module-help.csv` for the complete command list.

## Skills (path references)

| Skill | Path |
|-------|------|
| bmad-lens-git-state | `lens.core/_bmad/lens-work/skills/bmad-lens-git-state/SKILL.md` |
| bmad-lens-git-orchestration | `lens.core/_bmad/lens-work/skills/bmad-lens-git-orchestration/SKILL.md` |
| bmad-lens-constitution | `lens.core/_bmad/lens-work/skills/bmad-lens-constitution/SKILL.md` |
| bmad-lens-sensing | `lens.core/_bmad/lens-work/skills/bmad-lens-sensing/SKILL.md` |
| bmad-lens-checklist | `lens.core/_bmad/lens-work/skills/bmad-lens-checklist/SKILL.md` |
"""
    write_adapter_file(_project_root / "AGENTS.md", agents_md)

    codex_dir = _project_root / ".codex/commands"
    ensure_dir(codex_dir)
    remove_stale_adapter_files(
        codex_dir,
        lambda name: name in COMMAND_FILE_NAMES,
        "command alias",
    )
    for fname, name, desc, wf in COMMANDS:
        write_adapter_file(codex_dir / fname, ide_command(name, desc, wf))

    print("[OK]   Codex CLI adapter complete")


# ---------------------------------------------------------------------------
# Phase 6: OpenCode
# ---------------------------------------------------------------------------

def install_opencode() -> None:
    print("[INFO] Installing OpenCode adapter...")
    opencode_dir = _project_root / ".opencode/commands"
    ensure_dir(opencode_dir)
    remove_stale_adapter_files(
        opencode_dir,
        lambda name: name in COMMAND_FILE_NAMES,
        "command alias",
    )
    for fname, name, desc, wf in COMMANDS:
        write_adapter_file(opencode_dir / fname, ide_command(name, desc, wf))
    print("[OK]   OpenCode adapter complete")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    global _dry_run, _update, _project_root

    parser = argparse.ArgumentParser(
        description="LENS Workbench — Module Installer"
    )
    parser.add_argument("--ide", action="append", dest="ides", metavar="IDE",
                        help=f"IDE adapter to install (repeatable). Supported: {', '.join(SUPPORTED_IDES)}")
    parser.add_argument("--all-ides", action="store_true", help="Install all IDE adapters")
    parser.add_argument("--update", action="store_true", help="Overwrite existing adapter files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without creating files")
    args = parser.parse_args()

    _dry_run = args.dry_run
    _update = args.update

    script_dir = Path(__file__).resolve().parent
    # Find control repo root: the directory that contains lens.core/
    _cwd = Path.cwd()
    _project_root = (
        _cwd if (_cwd / "lens.core").exists()
        else next((p for p in script_dir.parents if (p / "lens.core").exists()), None)
    )
    if _project_root is None:
        print("[ERR]  Could not locate project root containing lens.core/", file=sys.stderr)
        return 1

    ides = args.ides or []
    if args.all_ides:
        ides = list(SUPPORTED_IDES)
    if not ides:
        ides = ["github-copilot"]

    print()
    print("LENS Workbench v2 — Module Installer")
    print(f"Target: {_project_root}")
    print()

    if _update:
        print("[WARN] Update mode: existing adapter files will be overwritten")
    if _dry_run:
        print("[WARN] Dry run: no files will be created")

    install_output_dirs()

    for ide_name in ides:
        match ide_name:
            case "github-copilot":
                install_github_copilot()
            case "cursor":
                install_cursor()
            case "claude":
                install_claude()
            case "codex":
                install_codex()
            case "opencode":
                install_opencode()
            case _:
                print(f"[ERR]  Unknown IDE: {ide_name} (supported: {', '.join(SUPPORTED_IDES)})", file=sys.stderr)
                global _errors
                _errors += 1

    print()
    print("Summary")
    print(f"  Created: {_created}")
    print(f"  Removed: {_removed}")
    print(f"  Skipped: {_skipped}")
    if _errors:
        print(f"  Errors:  {_errors}")
    print()

    return 1 if _errors else 0


if __name__ == "__main__":
    sys.exit(main())
