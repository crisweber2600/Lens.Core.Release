#!/usr/bin/env python3
"""
First Breath — Deterministic sanctum scaffolding for lc-agent-core-repo.

This script runs BEFORE the conversational awakening. It creates the sanctum
folder structure, copies template files with config values substituted,
copies all capability files and their supporting references into the sanctum,
and initializes governance domain files (rules-core.md, github-templates/,
enforcement-log/).

After this script runs, the sanctum is fully self-contained — the agent does
not depend on the skill bundle location for normal operation.

Usage:
    python3 init-sanctum.py <project-root> <skill-path>

    project-root: The root of the project (where _bmad/ lives)
    skill-path:   Path to the skill directory (where SKILL.md, references/, assets/ live)
"""

import sys
import shutil
from datetime import date
from pathlib import Path

# --- Agent-specific configuration ---

SKILL_NAME = "lc-agent-core-repo"
SANCTUM_DIR = SKILL_NAME

# Files used only during First Breath — not copied into sanctum/references/
SKILL_ONLY_FILES = {"first-breath.md", "rules-core-init.md", "redirect-stub-template.md", "workflow-template.md"}

# Asset template files to copy + substitute into sanctum root (without "-template" suffix)
TEMPLATE_FILES = [
    "INDEX-template.md",
    "PERSONA-template.md",
    "CREED-template.md",
    "BOND-template.md",
    "MEMORY-template.md",
]

# Governance domain files to initialize (source in references/, dest in sanctum/)
GOVERNANCE_SEED_FILES = {
    "rules-core-init.md": "rules-core.md",
    "redirect-stub-template.md": "github-templates/redirect-stub.md",
    "workflow-template.md": "github-templates/workflows.md",
}

# Whether the owner can teach this agent new capabilities
EVOLVABLE = False

# --- End agent-specific configuration ---


def parse_yaml_config(config_path: Path) -> dict:
    """Simple YAML key-value parser. Handles top-level scalar values only."""
    config = {}
    if not config_path.exists():
        return config
    with open(config_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                value = value.strip().strip("'\"")
                if value:
                    config[key.strip()] = value
    return config


def substitute_vars(content: str, variables: dict) -> str:
    """Replace {var_name} placeholders with values from the variables dict."""
    for key, value in variables.items():
        content = content.replace(f"{{{key}}}", value)
    return content


def copy_references(source_dir: Path, dest_dir: Path) -> list:
    """Copy all reference files (except skill-only files) into the sanctum."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []

    for source_file in sorted(source_dir.iterdir()):
        if source_file.name in SKILL_ONLY_FILES:
            continue
        if source_file.is_file():
            dest_file = dest_dir / source_file.name
            if dest_file.exists():
                copied.append(f"(skipped — already exists) {source_file.name}")
            else:
                shutil.copy2(source_file, dest_file)
                copied.append(source_file.name)

    return copied


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 init-sanctum.py <project-root> <skill-path>")
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    skill_path = Path(sys.argv[2]).resolve()

    # Paths
    bmad_dir = project_root / "_bmad"
    sanctum_path = bmad_dir / "memory" / SANCTUM_DIR
    assets_dir = skill_path / "assets"
    references_dir = skill_path / "references"

    sanctum_refs = sanctum_path / "references"

    created = []
    skipped = []

    # --- Idempotency check ---
    if sanctum_path.exists() and (sanctum_path / "INDEX.md").exists():
        print(f"Sanctum already exists at {sanctum_path}")
        print("This agent has already been born. Skipping First Breath scaffolding.")
        print("To re-initialize, remove the sanctum directory first.")
        sys.exit(0)

    # Load config for variable substitution
    config = {}
    for config_file in ["config.yaml", "config.user.yaml"]:
        config.update(parse_yaml_config(bmad_dir / config_file))

    today = date.today().isoformat()
    variables = {
        "user_name": config.get("user_name", "friend"),
        "communication_language": config.get("communication_language", "English"),
        "birth_date": today,
        "project_root": str(project_root),
        "sanctum_path": str(sanctum_path),
        "skill_name": SKILL_NAME,
    }

    print(f"\n=== lc-agent-core-repo — First Breath Scaffolding ===\n")
    print(f"Project root:  {project_root}")
    print(f"Skill path:    {skill_path}")
    print(f"Sanctum:       {sanctum_path}")
    print()

    # --- Create sanctum directory structure ---
    for d in [
        sanctum_path,
        sanctum_refs,
        sanctum_path / "github-templates",
        sanctum_path / "enforcement-log",
        sanctum_path / "sessions",
        sanctum_path / "sessions" / "archive",
        sanctum_path / "enforcement-log" / "archive",
    ]:
        if not d.exists():
            d.mkdir(parents=True)
            created.append(f"  📁 {d.relative_to(sanctum_path.parent.parent)}/")

    # --- Copy and substitute template files into sanctum root ---
    for template_name in TEMPLATE_FILES:
        template_path = assets_dir / template_name
        if not template_path.exists():
            print(f"  Warning: template {template_name} not found, skipping")
            continue

        # Remove "-template" suffix and uppercase → e.g. INDEX-template.md → INDEX.md
        output_name = template_name.replace("-template", "").upper()
        output_name = output_name[:-3] + ".md"  # fix .MD → .md
        output_path = sanctum_path / output_name

        if output_path.exists():
            skipped.append(f"  ⚪ {output_name} (already exists)")
        else:
            content = template_path.read_text(encoding="utf-8")
            content = substitute_vars(content, variables)
            output_path.write_text(content, encoding="utf-8")
            created.append(f"  ✅ {output_name}")

    # --- Initialize governance domain files ---
    for source_name, dest_rel in GOVERNANCE_SEED_FILES.items():
        source_path = references_dir / source_name
        dest_path = sanctum_path / dest_rel

        if not source_path.exists():
            print(f"  Warning: governance seed {source_name} not found in references/, skipping")
            continue

        if dest_path.exists():
            skipped.append(f"  ⚪ {dest_rel} (already exists)")
        else:
            content = source_path.read_text(encoding="utf-8")
            content = substitute_vars(content, variables)
            dest_path.write_text(content, encoding="utf-8")
            created.append(f"  ✅ {dest_rel}")

    # --- Initialize empty rules-extension-points.md ---
    ext_points_path = sanctum_path / "rules-extension-points.md"
    if ext_points_path.exists():
        skipped.append(f"  ⚪ rules-extension-points.md (already exists)")
    else:
        ext_content = f"""# Rules Extension Points

_Agent-registered governance rules. Managed by the Governance Enforcement Engine._
_Core rules live in `rules-core.md`. Extensions registered by other agents live here._

_Initialized: {today}_

---

<!-- Extensions are appended below by the register-extensions capability. -->
<!-- Schema: See references/register-extensions.md for the entry format. -->
"""
        ext_points_path.write_text(ext_content, encoding="utf-8")
        created.append(f"  ✅ rules-extension-points.md")

    # --- Copy capability prompt files into sanctum/references/ ---
    print("Copying capability prompts to sanctum/references/...")
    copied_refs = copy_references(references_dir, sanctum_refs)
    for ref in copied_refs:
        if ref.startswith("(skipped"):
            skipped.append(f"  ⚪ references/{ref}")
        else:
            created.append(f"  ✅ references/{ref}")

    # --- Auto-generate CAPABILITIES.md from the CAPABILITIES-template.md ---
    caps_template = assets_dir / "CAPABILITIES-template.md"
    caps_output = sanctum_path / "CAPABILITIES.md"
    if caps_output.exists():
        skipped.append(f"  ⚪ CAPABILITIES.md (already exists)")
    elif caps_template.exists():
        content = caps_template.read_text(encoding="utf-8")
        content = substitute_vars(content, variables)
        caps_output.write_text(content, encoding="utf-8")
        created.append(f"  ✅ CAPABILITIES.md")
    else:
        print("  Warning: CAPABILITIES-template.md not found, skipping CAPABILITIES.md generation")

    # --- Write initialization log entry ---
    log_path = sanctum_path / "enforcement-log" / f"{today}.md"
    if not log_path.exists():
        log_content = f"""# Enforcement Log — {today}

## Session: init-sanctum.py — First Breath Scaffolding

**Script:** `init-sanctum.py`
**Sanctum:** `{sanctum_path}`
**Project Root:** `{project_root}`

### Actions Taken
- Sanctum directory structure created
- Standard sanctum files initialized from assets/ templates
- `rules-core.md` seeded from `rules-core-init.md` (8 initial rules)
- `rules-extension-points.md` created (empty registry)
- `github-templates/redirect-stub.md` seeded from `redirect-stub-template.md`
- `github-templates/workflows.md` seeded from `workflow-template.md`
- `enforcement-log/` and `sessions/` directories created with archive subdirs
- Capability prompts copied to `references/`

### Files Created
{chr(10).join(created)}

### Open Items
- First Breath conversational awakening not yet completed
- BOND.md workspace topology not yet populated
- Governance mode not yet configured
"""
        log_path.write_text(log_content, encoding="utf-8")
        created.append(f"  ✅ enforcement-log/{today}.md")

    # --- Summary ---
    print()
    print(f"{'=' * 50}")
    print(f"Created ({len(created)} items):")
    for item in created:
        print(item)

    if skipped:
        print()
        print(f"Skipped — already existed ({len(skipped)} items):")
        for item in skipped:
            print(item)

    print()
    print("First Breath scaffolding complete.")
    print("The conversational awakening can now begin.")
    print(f"Sanctum: {sanctum_path}")
    print()
    print("Next step: activate the agent. It will run first-breath.md automatically.")


if __name__ == "__main__":
    main()
