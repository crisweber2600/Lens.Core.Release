#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0"]
# ///

from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
SKILL_DIR = TEST_DIR.parents[1]
MODULE_ROOT = TEST_DIR.parents[3]
REPO_ROOT = TEST_DIR.parents[5]

SKILL = SKILL_DIR / "SKILL.md"
RELEASE_PROMPT = MODULE_ROOT / "prompts" / "lens-preplan.prompt.md"
STUB_PROMPT = REPO_ROOT / ".github" / "prompts" / "lens-preplan.prompt.md"
MODULE_HELP = MODULE_ROOT / "module-help.csv"
AGENT = MODULE_ROOT / "agents" / "lens.agent.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_order(text: str, *tokens: str) -> None:
    positions = [text.index(token) for token in tokens]
    assert positions == sorted(positions)


def assert_no_drive_absolute_path(text: str) -> None:
    assert not any(f"{letter}:/" in text for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def section(text: str, heading: str) -> str:
    start = text.index(heading)
    next_heading = text.find("\n## ", start + len(heading))
    if next_heading == -1:
        return text[start:]
    return text[start:next_heading]


def test_stub_preflight_then_release_prompt():
    text = read_text(STUB_PROMPT)
    preflight = "uv run _bmad/lens-work/skills/bmad-lens-preflight/scripts/light-preflight.py"
    release_prompt = "_bmad/lens-work/prompts/lens-preplan.prompt.md"

    assert preflight in text
    assert release_prompt in text
    assert "If that command exits non-zero, stop" in text
    assert_order(text, preflight, release_prompt)
    assert_no_drive_absolute_path(text)


def test_release_prompt_is_thin_skill_redirect():
    text = read_text(RELEASE_PROMPT)

    assert "_bmad/lens-work/skills/bmad-lens-preplan/SKILL.md" in text
    assert "follow it exactly" in text
    assert "prompt-local business logic" in text
    assert "validate-phase-artifacts.py" not in text
    assert "bmad-lens-batch" not in text


def test_analyst_activation_precedes_brainstorm_mode_selection():
    text = read_text(SKILL)

    assert "Activate `bmad-agent-analyst` before brainstorm mode selection" in text
    assert_order(text, "bmad-agent-analyst", "brainstorm mode selection")

    authoring = section(text, "## Authoring Flow")
    assert_order(authoring, "bmad-agent-analyst", "brainstorm mode selection", "bmad-brainstorming")


def test_both_brainstorm_routes_and_brainstorm_first_gate():
    text = read_text(SKILL)
    authoring = section(text, "## Authoring Flow")

    assert "`bmad-brainstorming`" in authoring
    assert "`bmad-cis`" in authoring
    assert "`bmad-lens-bmad-skill`" in authoring
    assert "`brainstorm.md` must exist" in text
    assert_order(authoring, "brainstorm.md", "bmad-domain-research")
    assert_order(authoring, "brainstorm.md", "bmad-product-brief")


def test_batch_pass_one_and_pass_two_contract():
    text = read_text(SKILL)

    assert "bmad-lens-batch --target preplan" in text
    assert "Pass 1 writes the batch intake and stops" in text
    assert "no lifecycle artifacts are written" in text
    assert "Pass 2 resumes with `batch_resume_context`" in text
    assert "do not recreate the two-pass contract inline" in text


def test_review_ready_delegates_to_shared_validator():
    text = read_text(SKILL)

    assert "validate-phase-artifacts.py --phase preplan --contract review-ready" in text
    assert "--lifecycle-path {lifecycle_contract}" in text
    assert "--docs-root {docs_path}" in text
    assert "uv run _bmad/lens-work/skills/bmad-lens-validate-phase-artifacts/scripts/validate-phase-artifacts.py" in text
    assert "--phase preplan" in text
    assert "--contract review-ready" in text
    assert "--lifecycle-path" in text
    assert "--docs-root" in text
    assert "--json" in text
    assert "do not perform inline artifact checks" in text
    assert "no inline artifact checks" in text


def test_phase_gate_fail_and_pass_contract():
    text = read_text(SKILL)
    completion = section(text, "## Phase Completion")

    assert "bmad-lens-adversarial-review --phase preplan --source phase-complete" in completion
    assert "party-mode adversarial gate" in completion
    assert "verdict is `fail`" in completion
    assert "keep `feature.yaml` unchanged" in completion
    assert "verdict is `pass` or `pass-with-warnings`" in completion
    assert "bmad-lens-feature-yaml" in completion
    assert_order(completion, "bmad-lens-adversarial-review", "bmad-lens-feature-yaml")


def test_no_governance_write_invariant():
    text = read_text(SKILL)

    assert "Never invoke `publish-to-governance`" in text
    assert "never write governance artifacts directly" in text
    assert "no direct governance file writes" in text
    assert "no `publish-to-governance` call" in text


def test_next_handoff_and_fetch_context_contracts():
    text = read_text(SKILL)

    assert "When invoked by `/next`" in text
    assert "pre-confirmed" in text
    assert "no launch confirmation prompt" in text
    assert "bmad-lens-init-feature fetch-context" in text
    assert_order(text, "bmad-lens-init-feature fetch-context", "bmad-lens-constitution")


def test_integration_table_contains_required_delegations():
    text = read_text(SKILL)
    table = section(text, "## Integration Points")

    assert "| Integration | Delegation | Contract |" in table
    for token in (
        "bmad-lens-feature-yaml",
        "bmad-lens-init-feature fetch-context",
        "bmad-lens-constitution",
        "bmad-lens-batch --target preplan",
        "validate-phase-artifacts.py --phase preplan --contract review-ready --lifecycle-path {lifecycle_contract} --docs-root {docs_path} --json",
        "bmad-agent-analyst",
        "bmad-brainstorming",
        "bmad-cis",
        "bmad-domain-research",
        "bmad-market-research",
        "bmad-technical-research",
        "bmad-product-brief",
        "bmad-lens-adversarial-review --phase preplan --source phase-complete",
        "bmad-lens-git-orchestration",
    ):
        assert token in table


def test_module_help_and_shell_discovery_are_aligned_without_duplicates():
    module_help = read_text(MODULE_HELP)
    agent = read_text(AGENT)

    assert module_help.count("bmad-lens-preplan,preplan") == 1
    assert "module-help.csv" in agent
    assert "/lens-help" in agent
    assert "including preplan" in agent
    assert "Display only the compact menu" in agent


def test_no_owned_implementation_layer_reference_in_skill():
    text = read_text(SKILL)

    assert "This skill owns no implementation script" in text
    assert "Only `scripts/tests/` may exist" in text
    assert "ops.py" not in text
    assert_no_drive_absolute_path(text)