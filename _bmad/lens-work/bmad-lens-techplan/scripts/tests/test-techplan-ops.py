#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Focused regression tests for bmad-lens-techplan command surface.

Run:
    cd TargetProjects/lens-dev/new-codebase/lens.core.src
    uv run --with pytest pytest _bmad/lens-work/skills/bmad-lens-techplan/scripts/tests/test-techplan-ops.py -q
"""

from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Path resolution — anchored to this file's location
#   test file: _bmad/lens-work/skills/bmad-lens-techplan/scripts/tests/test-techplan-ops.py
#   parents[0] = tests/
#   parents[1] = scripts/
#   parents[2] = bmad-lens-techplan/  ← SKILL_ROOT
#   parents[3] = skills/
#   parents[4] = lens-work/           ← MODULE_ROOT (via SKILL_ROOT.parents[1])
#   parents[5] = _bmad/
#   parents[6] = lens.core.src/       ← REPO_ROOT (via MODULE_ROOT.parents[1])
# ---------------------------------------------------------------------------
SKILL_ROOT = Path(__file__).resolve().parents[2]       # bmad-lens-techplan/
MODULE_ROOT = SKILL_ROOT.parents[1]                     # lens-work/
REPO_ROOT = MODULE_ROOT.parents[1]                      # lens.core.src/

STUB_PROMPT = REPO_ROOT / ".github" / "prompts" / "lens-techplan.prompt.md"
RELEASE_PROMPT = MODULE_ROOT / "prompts" / "lens-techplan.prompt.md"
CONDUCTOR_SKILL = SKILL_ROOT / "SKILL.md"
MODULE_YAML = MODULE_ROOT / "module.yaml"


def read_text(path: Path) -> str:
    """Read repository text files as UTF-8 across platforms."""
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Prompt-start regressions (TK-2.5)
# ---------------------------------------------------------------------------


def test_stub_exists():
    """Public stub must exist under .github/prompts/."""
    assert STUB_PROMPT.exists(), (
        f"Missing public stub: {STUB_PROMPT}\n"
        "Create .github/prompts/lens-techplan.prompt.md (TK-2.2)"
    )


def test_stub_preflight_then_release_prompt():
    """Stub must run preflight before loading the release prompt, and must stop on failure."""
    text = read_text(STUB_PROMPT)
    preflight = "uv run _bmad/lens-work/skills/bmad-lens-preflight/scripts/light-preflight.py"
    release = "_bmad/lens-work/prompts/lens-techplan.prompt.md"
    assert preflight in text, f"Stub missing preflight command: {preflight!r}"
    assert release in text, f"Stub missing release prompt reference: {release!r}"
    assert text.index(preflight) < text.index(release), (
        "Stub must reference preflight BEFORE the release prompt path"
    )
    assert "If that command exits non-zero, stop" in text, (
        "Stub must include stop-on-failure instruction for preflight"
    )


def test_release_prompt_exists():
    """Release prompt must exist under _bmad/lens-work/prompts/."""
    assert RELEASE_PROMPT.exists(), (
        f"Missing release prompt: {RELEASE_PROMPT}\n"
        "Create _bmad/lens-work/prompts/lens-techplan.prompt.md (TK-2.3)"
    )


# ---------------------------------------------------------------------------
# Wrapper-equivalence regressions (TK-2.5)
# ---------------------------------------------------------------------------


def test_release_prompt_routes_to_conductor_skill():
    """Release prompt must be a thin stub routing to SKILL.md with no inline logic branches."""
    text = read_text(RELEASE_PROMPT)
    assert "bmad-lens-techplan/SKILL.md" in text, (
        "Release prompt must reference _bmad/lens-work/skills/bmad-lens-techplan/SKILL.md"
    )
    # The release prompt must not contain inline architecture prose or branching logic.
    # It delegates entirely — no 'if ... then' decision trees should appear.
    forbidden = ["if featureId", "if feature_id", "architecture.md", "if phase"]
    for f in forbidden:
        assert f not in text, (
            f"Release prompt must not contain inline logic: found {f!r}. "
            "It should be a thin stub that delegates to the conductor skill."
        )


def test_conductor_skill_exists():
    """Conductor SKILL.md must exist under skills/bmad-lens-techplan/."""
    assert CONDUCTOR_SKILL.exists(), (
        f"Missing conductor skill: {CONDUCTOR_SKILL}\n"
        "Create _bmad/lens-work/skills/bmad-lens-techplan/SKILL.md (TK-2.3)"
    )


def test_conductor_skill_is_conductor_only():
    """Conductor skill must identify itself as conductor-only and delegate to BMAD wrapper."""
    text = read_text(CONDUCTOR_SKILL)
    assert "conductor" in text.lower(), (
        "Conductor skill must self-identify as a conductor"
    )
    assert "bmad-lens-bmad-skill" in text, (
        "Conductor skill must reference bmad-lens-bmad-skill for BMAD wrapper delegation"
    )
    assert "bmad-create-architecture" in text, (
        "Conductor skill must reference bmad-create-architecture as the delegated authoring skill"
    )
    # Conductor must not author architecture inline.
    forbidden_phrases = ["## Architecture Design", "## System Architecture", "## Components\n"]
    for phrase in forbidden_phrases:
        assert phrase not in text, (
            f"Conductor skill must not contain inline architecture authoring: found {phrase!r}"
        )


def test_lens_techplan_registered_in_module_yaml():
    """lens-techplan.prompt.md must appear in module.yaml prompts list."""
    assert MODULE_YAML.exists(), f"Missing module.yaml: {MODULE_YAML}"
    data = yaml.safe_load(read_text(MODULE_YAML))
    prompts = data.get("prompts", [])
    assert "lens-techplan.prompt.md" in prompts, (
        f"lens-techplan.prompt.md not found in module.yaml prompts list.\n"
        f"Current prompts: {prompts}"
    )


# ---------------------------------------------------------------------------
# TK-3.1 pending — shared utility dependency stubs
# These tests will activate once TK-3.1 delivers the shared utility surfaces.
# ---------------------------------------------------------------------------


def test_publish_gate_runs_before_architecture_authoring():
    """Conductor must invoke publish hook before architecture authoring begins."""
    text = read_text(CONDUCTOR_SKILL)
    assert "publish-to-governance" in text, (
        "Conductor skill must invoke publish-to-governance hook (bmad-lens-git-orchestration)"
    )
    assert "bmad-lens-git-orchestration" in text
    # No [TK-3.1] pending markers should remain
    assert "[TK-3.1]" not in text, "All TK-3.1 pending markers must be removed"
    # Publish step must appear before architecture delegation step
    publish_idx = text.index("publish-to-governance")
    delegate_idx = text.index("bmad-lens-bmad-skill --skill bmad-create-architecture")
    assert publish_idx < delegate_idx, (
        "publish-to-governance must appear before BMAD wrapper delegation in the conductor"
    )


def test_adversarial_review_gate_enforced():
    """Conductor must gate on businessplan adversarial review artifact being present."""
    text = read_text(CONDUCTOR_SKILL)
    assert "bmad-lens-adversarial-review" in text, (
        "Conductor skill must reference bmad-lens-adversarial-review gate"
    )
    assert "responses-recorded" in text, (
        "Conductor skill must check for status: responses-recorded"
    )
    assert "[TK-3.1]" not in text


def test_constitution_loader_activated():
    """Conductor must load domain constitution via bmad-lens-constitution."""
    text = read_text(CONDUCTOR_SKILL)
    assert "bmad-lens-constitution" in text, (
        "Conductor skill must invoke bmad-lens-constitution loader"
    )
    assert "[TK-3.1]" not in text


def test_bmad_wrapper_routing_activated():
    """Conductor must route architecture authoring through BMAD wrapper without stub markers."""
    text = read_text(CONDUCTOR_SKILL)
    assert "bmad-lens-bmad-skill" in text
    assert "[TK-3.1 pending]" not in text
    assert "[TK-3.1]" not in text


# ---------------------------------------------------------------------------
# Parity regressions (TK-3.2) — behavioral contract verification
# ---------------------------------------------------------------------------


def test_pr1_publish_gate_stops_before_authoring():
    """PR-1: Publish gate stops execution before architecture authoring if governance is out-of-date.

    Verifies the conductor SKILL.md enforces publish-before-author as a hard prerequisite:
    the publish hook must be invoked and its failure must stop the skill before any
    BMAD wrapper delegation occurs.
    """
    text = read_text(CONDUCTOR_SKILL)
    # Must call the publish hook
    assert "publish-to-governance" in text
    # Failure must stop the skill — stop-on-error language required
    assert "non-zero" in text or "stop" in text.lower(), (
        "Conductor must stop if the publish hook exits non-zero"
    )
    # Publish must precede delegation
    assert text.index("publish-to-governance") < text.index("bmad-lens-bmad-skill --skill"), (
        "Publish hook must precede BMAD delegation — publish-before-author is a hard gate"
    )


def test_pr2_prd_reference_stops_if_missing():
    """PR-2: Missing PRD causes the conductor to stop and report the missing reference."""
    text = read_text(CONDUCTOR_SKILL)
    # PRD hard gate language must be present
    assert "PRD not found" in text or "prd" in text.lower(), (
        "Conductor skill must include PRD reference gate"
    )
    assert "stop" in text.lower() or "cannot begin" in text.lower(), (
        "Conductor skill must stop if PRD is not found"
    )


def test_pr3_adversarial_review_gate_blocks_if_absent():
    """PR-3: Missing or incomplete adversarial review blocks phase advancement."""
    text = read_text(CONDUCTOR_SKILL)
    # Gate must reference the adversarial review skill
    assert "bmad-lens-adversarial-review" in text
    # Must check for responses-recorded status
    assert "responses-recorded" in text
    # Must be before the architecture delegation (not after)
    review_idx = text.index("bmad-lens-adversarial-review")
    delegate_idx = text.index("bmad-lens-bmad-skill --skill bmad-create-architecture")
    assert review_idx < delegate_idx, (
        "Adversarial review gate must appear before BMAD delegation"
    )


def test_pr4_constitution_loaded_for_domain_context():
    """PR-4: Constitution loader resolves the domain/service constitution before authoring."""
    text = read_text(CONDUCTOR_SKILL)
    assert "bmad-lens-constitution" in text
    # Must pass governance-dir context to the loader
    assert "governance_repo" in text or "governance-dir" in text, (
        "Constitution loader must receive governance repo context"
    )


def test_pr5_conductor_delegates_only_no_inline_authoring():
    """PR-5: Conductor delegates to BMAD wrapper — no inline architecture authoring."""
    text = read_text(CONDUCTOR_SKILL)
    # Must delegate to wrapper
    assert "bmad-lens-bmad-skill --skill bmad-create-architecture" in text
    # Must not contain inline architecture prose
    forbidden = [
        "## System Components",
        "## Service Boundaries",
        "## Data Flow",
        "## API Contracts",
        "## Deployment Architecture",
    ]
    for phrase in forbidden:
        assert phrase not in text, (
            f"Conductor skill must not contain inline architecture authoring: found {phrase!r}"
        )


def test_pr6_clean_room_no_old_codebase_prose():
    """PR-6: Implementation is clean-room — no old-codebase prose reproduced verbatim.

    If no old-codebase techplan skill exists, the test documents this and passes.
    """
    old_codebase_skill = (
        REPO_ROOT.parents[1]  # TargetProjects/lens-dev/
        / "old-codebase"
        / "lens.core.src"
        / "_bmad"
        / "lens-work"
        / "skills"
        / "bmad-lens-techplan"
        / "SKILL.md"
    )
    if not old_codebase_skill.exists():
        # No old-codebase skill to compare against — clean-room AC is N/A
        return

    old_text = read_text(old_codebase_skill)
    new_text = read_text(CONDUCTOR_SKILL)

    # Extract paragraphs of 20+ words from old codebase for verbatim-copy check
    import re
    old_paragraphs = [p.strip() for p in re.split(r"\n{2,}", old_text) if len(p.split()) >= 20]
    for para in old_paragraphs:
        assert para not in new_text, (
            f"Clean-room violation: old-codebase paragraph reproduced verbatim in new skill:\n{para[:120]}..."
        )

