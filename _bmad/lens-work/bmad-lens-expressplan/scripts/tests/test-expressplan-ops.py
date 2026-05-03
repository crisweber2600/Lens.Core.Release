#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Focused regression tests for bmad-lens-expressplan command surface.

Run:
    cd TargetProjects/lens-dev/new-codebase/lens.core.src
    uv run --with pytest --with pyyaml pytest _bmad/lens-work/skills/bmad-lens-expressplan/scripts/tests/test-expressplan-ops.py -q
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Path resolution - anchored to this file's location
#   test file: _bmad/lens-work/skills/bmad-lens-expressplan/scripts/tests/test-expressplan-ops.py
#   parents[0] = tests/
#   parents[1] = scripts/
#   parents[2] = bmad-lens-expressplan/  <- SKILL_ROOT
#   parents[3] = skills/
#   parents[4] = lens-work/              <- MODULE_ROOT
#   MODULE_ROOT.parents[0] = _bmad/
#   MODULE_ROOT.parents[1] = lens.core.src/  <- REPO_ROOT
# ---------------------------------------------------------------------------
TEST_FILE = Path(__file__).resolve()
SKILL_ROOT = TEST_FILE.parents[2]
MODULE_ROOT = TEST_FILE.parents[4]
REPO_ROOT = MODULE_ROOT.parents[1]

STUB_PROMPT = REPO_ROOT / ".github" / "prompts" / "lens-expressplan.prompt.md"
RELEASE_PROMPT = MODULE_ROOT / "prompts" / "lens-expressplan.prompt.md"
CONDUCTOR_SKILL = SKILL_ROOT / "SKILL.md"
MODULE_YAML = MODULE_ROOT / "module.yaml"
MODULE_HELP = MODULE_ROOT / "module-help.csv"


def read_text(path: Path) -> str:
    """Read repository text files as UTF-8 across platforms."""
    return path.read_text(encoding="utf-8")


def module_help_rows() -> list[dict[str, str]]:
    with MODULE_HELP.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# ---------------------------------------------------------------------------
# Prompt/help/module surface regressions
# ---------------------------------------------------------------------------


def test_stub_exists_and_preflights_before_release_prompt():
    """Public stub must run light preflight before loading the release prompt."""
    assert STUB_PROMPT.exists(), f"Missing public stub: {STUB_PROMPT}"
    text = read_text(STUB_PROMPT)
    preflight = "light-preflight.py"
    release = "_bmad/lens-work/prompts/lens-expressplan.prompt.md"
    assert preflight in text, f"Stub missing preflight command: {preflight!r}"
    assert release in text, f"Stub missing release prompt reference: {release!r}"
    assert text.index(preflight) < text.index(release), (
        "Stub must reference preflight before the release prompt path"
    )
    assert "If that command exits non-zero, stop" in text, (
        "Stub must include stop-on-failure instruction for preflight"
    )


def test_release_prompt_exists_and_routes_to_conductor_skill():
    """Release prompt must be a thin stub routing to the expressplan SKILL.md."""
    assert RELEASE_PROMPT.exists(), f"Missing release prompt: {RELEASE_PROMPT}"
    text = read_text(RELEASE_PROMPT)
    assert "bmad-lens-expressplan/SKILL.md" in text, (
        "Release prompt must reference bmad-lens-expressplan/SKILL.md"
    )
    forbidden = ["feature.yaml.track", "QuickPlan owns", "expressplan-adversarial-review.md"]
    for phrase in forbidden:
        assert phrase not in text, (
            f"Release prompt must remain a routing stub; found inline contract phrase {phrase!r}"
        )


def test_module_yaml_registers_expressplan_prompt():
    """lens-expressplan.prompt.md must appear in module.yaml prompts list."""
    assert MODULE_YAML.exists(), f"Missing module.yaml: {MODULE_YAML}"
    data = yaml.safe_load(read_text(MODULE_YAML))
    prompts = data.get("prompts", [])
    assert "lens-expressplan.prompt.md" in prompts, (
        f"lens-expressplan.prompt.md not found in module.yaml prompts list. Current prompts: {prompts}"
    )


def test_module_help_retains_expressplan_entry():
    """Help surface must expose expressplan."""
    rows = module_help_rows()
    expressplan_rows = [row for row in rows if row["skill"] == "bmad-lens-expressplan"]
    assert expressplan_rows, "module-help.csv must include bmad-lens-expressplan"
    assert any(row["display-name"] == "expressplan" and row["action"] == "plan" for row in expressplan_rows), (
        f"bmad-lens-expressplan row must expose display-name=expressplan/action=plan: {expressplan_rows}"
    )


# ---------------------------------------------------------------------------
# ExpressPlan conductor contract regressions
# ---------------------------------------------------------------------------


def test_conductor_skill_enforces_express_only_state_gate():
    """ExpressPlan must accept only express tracks and block retained non-express tracks."""
    text = read_text(CONDUCTOR_SKILL)
    assert "track=express|expressplan" in text, (
        "State-gate block message must state the accepted express tracks directly"
    )
    assert "accept only `express` and `expressplan` tracks" in text
    for blocked_track in ["`full`", "`quickplan`", "`hotfix`, `tech-change`"]:
        assert blocked_track in text, f"State gate must explicitly block {blocked_track}"
    assert "ExpressPlan only runs for track=express|expressplan with phase=expressplan" in text


def test_conductor_delegates_quickplan_only_through_wrapper_without_track_override():
    """QuickPlan remains the authoring path, reached only through the Lens BMAD wrapper."""
    text = read_text(CONDUCTOR_SKILL)
    wrapper_command = "bmad-lens-bmad-skill --skill bmad-lens-quickplan plan {featureId}"
    assert wrapper_command in text, "ExpressPlan must delegate QuickPlan through the wrapper command"
    direct_quickplan_command = re.compile(
        r"(?m)^(?!.*bmad-lens-bmad-skill).*bmad-lens-quickplan\s+plan\b"
    )
    assert not direct_quickplan_command.search(text), (
        "ExpressPlan must not invoke bmad-lens-quickplan directly outside the wrapper"
    )
    assert "Do not pass `--track`" in text
    assert "never forward a user-supplied `--track` to QuickPlan" in text
    assert "QuickPlan prerequisite is mandatory" in text
    for prerequisite in [
        "missing `bmad-lens-bmad-skill` registration",
        "missing `bmad-lens-quickplan` registration",
        "missing entry path",
        "missing skill file",
    ]:
        assert prerequisite in text, f"Missing QuickPlan prerequisite check: {prerequisite}"


def test_review_gate_runs_only_after_quickplan_artifacts_are_verified():
    """ExpressPlan must verify the QuickPlan bundle before invoking expressplan review."""
    text = read_text(CONDUCTOR_SKILL)
    verify_phrase = "verify that all required QuickPlan artifacts exist and are readable"
    review_command = "bmad-lens-adversarial-review --phase expressplan --source phase-complete"
    assert verify_phrase in text
    assert review_command in text
    verify_idx = text.index(verify_phrase)
    review_idx = text.index(review_command, verify_idx)
    assert verify_idx < review_idx, (
        "QuickPlan artifact verification must happen before the expressplan review gate"
    )
    for artifact in ["business-plan.md", "tech-plan.md", "sprint-plan.md"]:
        assert artifact in text, f"QuickPlan artifact must be verified before review: {artifact}"


def test_canonical_review_artifact_and_fail_hard_stop_are_asserted():
    """The selected expressplan review filename must be canonical, and fail must stop handoff."""
    text = read_text(CONDUCTOR_SKILL)
    canonical = "expressplan-adversarial-review.md"
    assert canonical in text, "Canonical expressplan review artifact filename must be asserted directly"
    assert "do not use `expressplan-review.md` as a new output or fallback" in text
    assert "If the review verdict is `fail`, stop" in text
    assert "leave `feature.yaml.phase` unchanged" in text
    assert "do not advertise `/finalizeplan` as available" in text
    assert "No pre-verdict phase mutation" in text


def test_finalizeplan_owns_downstream_bundle_and_handoff_work():
    """ExpressPlan must reuse FinalizePlan for downstream planning bundle ownership."""
    text = read_text(CONDUCTOR_SKILL)
    assert "FinalizePlan owns downstream bundle" in text
    assert "bmad-lens-finalizeplan" in text, "FinalizePlan must remain the lifecycle handoff target"
    forbidden_outputs = [
        "epics.md",
        "stories.md",
        "implementation-readiness.md",
        "sprint-status.yaml",
        "story files",
        "governance publication",
        "PR topology",
    ]
    for output in forbidden_outputs:
        assert output in text, f"FinalizePlan boundary must name downstream output: {output}"
    assert "No FinalizePlan bundle artifact is an ExpressPlan completion artifact" in text
    assert "Do not generate, repair, publish, or open PRs" in text
