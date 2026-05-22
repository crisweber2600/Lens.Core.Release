"""Static contract tests for Lens batch intake and resume semantics."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parent.parent.parent


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_batch_command_publication_surfaces_are_aligned():
    module_yaml = _read("module.yaml")
    module_help = _read("module-help.csv")
    help_topics = _read("skills/bmad-lens-help/assets/help-topics.yaml")
    installer = _read("_module-installer/installer.js")
    getting_started = _read("docs/GETTING-STARTED.md")
    prompt = _read("prompts/lens-batch.prompt.md")

    assert "id: bmad-lens-batch" in module_yaml
    assert "- lens-batch.prompt.md" in module_yaml
    assert ".github/prompts/lens-batch.prompt.md" in module_yaml
    assert "bmad-lens-batch.md" in module_yaml
    assert "Lens,bmad-lens-batch,batch,BT" in module_help
    assert "command: /batch" in help_topics
    assert "| `/batch` | Generate or resume a two-pass batch intake for the current planning target |" in getting_started
    assert "lens.core/_bmad/lens-work/skills/bmad-lens-batch/SKILL.md" in prompt
    assert "Generate or resume a two-pass batch intake for planning targets" in installer


def test_batch_skill_uses_automatic_readiness_detection():
    text = _read("skills/bmad-lens-batch/SKILL.md")

    assert "Questions-only first pass" in text
    assert "Automatic readiness detection" in text
    assert "every required `**Your answer:**` block contains non-placeholder content" in text
    assert "pass 1 never publishes predecessor artifacts" in text
    assert "resumes the owning planning target only after it can automatically detect that the required answer blocks in that file have been filled" in text
    assert "{target}-batch-input.md" in text


def test_phase_conductors_delegate_batch_to_shared_skill():
    targets = {
        "skills/bmad-lens-preplan/SKILL.md": "bmad-lens-batch --target preplan",
        "skills/bmad-lens-businessplan/SKILL.md": "bmad-lens-batch --target businessplan",
        "skills/bmad-lens-techplan/SKILL.md": "bmad-lens-batch --target techplan",
        "skills/bmad-lens-finalizeplan/SKILL.md": "bmad-lens-batch --target finalizeplan",
        "skills/bmad-lens-expressplan/SKILL.md": "bmad-lens-batch --target expressplan",
        "skills/bmad-lens-quickplan/SKILL.md": "bmad-lens-batch --target quickplan",
    }

    for relative_path, marker in targets.items():
        text = _read(relative_path)

        assert marker in text
        assert "batch_resume_context" in text


def test_quickplan_references_describe_two_pass_batch_behavior():
    for relative_path in (
        "skills/bmad-lens-quickplan/references/business-plan.md",
        "skills/bmad-lens-quickplan/references/tech-plan.md",
        "skills/bmad-lens-quickplan/references/adversarial-review.md",
        "skills/bmad-lens-quickplan/references/sprint-planning.md",
    ):
        text = _read(relative_path)

        assert "### Pass 1" in text
        assert "### Pass 2" in text
