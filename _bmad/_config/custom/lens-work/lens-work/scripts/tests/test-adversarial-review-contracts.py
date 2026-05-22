"""Static contract tests for lifecycle adversarial review gates."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parent.parent.parent


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_lifecycle_declares_completion_review_for_preplan_businessplan_and_techplan():
    text = _read("lifecycle.yaml")

    assert "report: preplan-adversarial-review.md" in text
    assert "ready_when_artifacts: [product-brief, research, brainstorm]" in text
    assert "reviewed_artifacts: [product-brief, research, brainstorm]" in text
    assert "report: businessplan-adversarial-review.md" in text
    assert "ready_when_artifacts: [prd, ux-design]" in text
    assert "reviewed_artifacts: [prd, ux-design]" in text
    assert "report: techplan-adversarial-review.md" in text
    assert "ready_when_artifacts: [architecture]" in text
    assert "reviewed_artifacts: [architecture]" in text
    assert "report: finalizeplan-review.md" in text
    assert "ready_when_artifacts: [product-brief, research, brainstorm, prd, ux-design, architecture]" in text
    assert "reviewed_artifacts: [product-brief, research, brainstorm, prd, ux-design, architecture]" in text
    assert "report: expressplan-adversarial-review.md" in text
    assert "ready_when_artifacts: [business-plan, tech-plan, sprint-plan]" in text
    assert "reviewed_artifacts: [business-plan, tech-plan]" in text


def test_phase_conductors_block_completion_until_review_gate_passes():
    preplan = _read("skills/bmad-lens-preplan/SKILL.md")
    businessplan = _read("skills/bmad-lens-businessplan/SKILL.md")
    techplan = _read("skills/bmad-lens-techplan/SKILL.md")

    assert "Run `bmad-lens-adversarial-review --phase preplan --source phase-complete`" in preplan
    assert "If the verdict is `fail`, stop and do not update `feature.yaml`." in preplan

    assert "Run `bmad-lens-adversarial-review --phase businessplan --source phase-complete`" in businessplan
    assert "If the verdict is `fail`, stop and do not update `feature.yaml`." in businessplan

    assert "Run `bmad-lens-adversarial-review --phase techplan --source phase-complete`" in techplan
    assert "If the verdict is `fail`, stop and do not update `feature.yaml`." in techplan


def test_phase_conductors_resume_directly_into_review_when_review_is_next_step():
    preplan = _read("skills/bmad-lens-preplan/SKILL.md")
    businessplan = _read("skills/bmad-lens-businessplan/SKILL.md")
    techplan = _read("skills/bmad-lens-techplan/SKILL.md")
    expressplan = _read("skills/bmad-lens-expressplan/SKILL.md")

    assert "--phase preplan --contract review-ready" in preplan
    assert "treat adversarial review as the next deterministic step" in preplan

    assert "--phase businessplan --contract review-ready" in businessplan
    assert "Do not reopen the workflow selection menu or ask the direct-run confirmation prompt." in businessplan

    assert "--phase techplan --contract review-ready" in techplan
    assert "Do not ask a redundant yes/no prompt or relaunch the native architecture handoff." in techplan

    assert "--phase expressplan --contract review-ready" in expressplan
    assert "Do not re-run QuickPlan or re-confirm the feature and mode." in expressplan


def test_handoff_docs_publish_review_artifacts_with_predecessor_phase_outputs():
    businessplan = _read("skills/bmad-lens-businessplan/SKILL.md")
    techplan = _read("skills/bmad-lens-techplan/SKILL.md")
    finalizeplan = _read("skills/bmad-lens-finalizeplan/SKILL.md")

    assert "including the preplan review report when present" in businessplan
    assert "including the businessplan review report when present" in techplan
    assert "including the techplan review report when present" in finalizeplan


def test_adversarial_review_skill_requires_party_mode_challenge_and_no_state_updates():
    text = _read("skills/bmad-lens-adversarial-review/SKILL.md")
    contract = _read("skills/bmad-lens-adversarial-review/references/review-contract.md")

    assert "party-mode challenge" in text
    assert "You do not update `feature.yaml` phase state yourself." in text
    assert "## Party-Mode Challenge" in contract
    assert "## Gaps You May Not Have Considered" in contract


def test_module_registration_surfaces_include_adversarial_review():
    module_yaml = _read("module.yaml")
    module_help = _read("module-help.csv")
    help_topics = _read("skills/bmad-lens-help/assets/help-topics.yaml")
    installer = _read("_module-installer/installer.js")
    prompt = _read("prompts/lens-adversarial-review.prompt.md")

    assert "- id: bmad-lens-adversarial-review" in module_yaml
    assert "- lens-adversarial-review.prompt.md" in module_yaml
    assert "Lens,bmad-lens-adversarial-review,adversarial-review,RV" in module_help
    assert "command: /lens-adversarial-review" in help_topics
    assert "file: 'lens-adversarial-review.prompt.md'" in installer
    assert "file: 'bmad-lens-adversarial-review.md'" in installer
    assert "lens.core/_bmad/lens-work/skills/bmad-lens-adversarial-review/SKILL.md" in prompt