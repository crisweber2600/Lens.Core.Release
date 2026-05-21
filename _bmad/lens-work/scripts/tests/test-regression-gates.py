#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest==9.0.3", "pyyaml==6.0.3"]
# ///
"""Cross-cutting regression gates for high-churn Lens workflow contracts."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import yaml


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
REPO_ROOT = MODULE_ROOT.parents[1]
GITHUB_PROMPTS = REPO_ROOT / ".github" / "prompts"
CORE_PROMPTS = MODULE_ROOT / "prompts"
SKILLS_ROOT = MODULE_ROOT / "skills"
LIFECYCLE = MODULE_ROOT / "lifecycle.yaml"
PREFLIGHT = MODULE_ROOT / "skills" / "lens-preflight" / "scripts" / "preflight.py"
NEXT_OPS = MODULE_ROOT / "skills" / "lens-next" / "scripts" / "next-ops.py"
GIT_ORCHESTRATION = MODULE_ROOT / "skills" / "lens-git-orchestration" / "scripts" / "git-orchestration-ops.py"
EXPRESSPLAN_SKILL = MODULE_ROOT / "skills" / "lens-expressplan" / "SKILL.md"
FINALIZEPLAN_SKILL = MODULE_ROOT / "skills" / "lens-finalizeplan" / "SKILL.md"
CORE_BUGFIX_SKILL = MODULE_ROOT / "skills" / "bmad-lens-core-bugfix" / "SKILL.md"

LIGHT_PREFLIGHT_SCRIPT_PATH = "lens.core/_bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py"
STANDARD_PREFLIGHT = f"uv run --script {LIGHT_PREFLIGHT_SCRIPT_PATH}"
LEGACY_PREFLIGHT_SCRIPT_PATTERN = r"_bmad/lens-work/skills/lens-preflight/scripts/light-preflight\.py"
LEGACY_PREFLIGHT_PATTERNS = (
    rf"(^|\s)uv\s+run\s+{LEGACY_PREFLIGHT_SCRIPT_PATTERN}(\s|$)",
    rf"(^|\s)uv\s+run\s+--script\s+{LEGACY_PREFLIGHT_SCRIPT_PATTERN}(\s|$)",
    rf"(^|\s){LEGACY_PREFLIGHT_SCRIPT_PATTERN}(\s|$)",
)
NO_PREFLIGHT_PROMPTS = {"lens-core-bugfix.prompt.md"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"Unable to load module spec for {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prompt_caller(prompt: Path) -> str:
    return prompt.name.removesuffix(".prompt.md")


def _explicit_callers_by_class(preflight) -> dict[str, set[str]]:
    return {
        "read-only": preflight.READ_ONLY_CALLERS,
        "control-write": preflight.CONTROL_WRITE_CALLERS,
        "governance-write": preflight.GOVERNANCE_WRITE_CALLERS,
        "mixed": preflight.MIXED_CALLERS,
    }


def test_public_prompt_wrappers_match_installed_workspace_contract():
    """Prevent recurring drift between installed prompt wrappers and release prompt paths."""
    prompts = sorted(GITHUB_PROMPTS.glob("lens-*.prompt.md"))
    assert prompts, "Expected public Lens prompt wrappers"

    assert not (GITHUB_PROMPTS / "lens-bug-quickdev.prompt.md").exists(), (
        "Legacy lens-bug-quickdev prompt must not be republished"
    )

    for prompt in prompts:
        text = _read(prompt)
        expected_delegate = f"lens.core/_bmad/lens-work/prompts/{prompt.name}"
        assert expected_delegate in text, f"{prompt.name} must delegate to its lens.core release prompt"
        assert "vscode_askQuestions" in text, f"{prompt.name} must preserve question-tool guidance"

        if prompt.name in NO_PREFLIGHT_PROMPTS:
            assert "preflight" not in text.lower(), f"{prompt.name} is explicitly preflight-exempt"
            continue

        caller = _prompt_caller(prompt)
        expected_command = f"{STANDARD_PREFLIGHT} --caller {caller}"
        assert expected_command in text, f"{prompt.name} must use the standard preflight command"
        assert "FIRST, run" in text, f"{prompt.name} must order preflight before module loading"
        assert "ONLY AFTER a successful prompt-start sync" in text, (
            f"{prompt.name} must gate release-prompt loading on preflight success"
        )

        bash_blocks = re.findall(r"```bash\n(.*?)```", text, re.DOTALL)
        assert bash_blocks, f"{prompt.name} must include the executable preflight bash block"
        for block in bash_blocks:
            for legacy_pattern in LEGACY_PREFLIGHT_PATTERNS:
                assert not re.search(legacy_pattern, block), (
                    f"{prompt.name} preflight command still uses legacy path pattern: {legacy_pattern}"
                )
            assert "lens.core/_bmad/lens-work/prompts/" not in block
            assert LIGHT_PREFLIGHT_SCRIPT_PATH in block


def test_core_skills_and_prompts_require_question_tool_guidance():
    """Ensure all internal skills and prompts preserve ask-questions guidance."""
    for prompt in sorted(CORE_PROMPTS.glob("lens-*.prompt.md")):
        text = _read(prompt)
        assert "vscode_askQuestions" in text, f"{prompt.name} must preserve question-tool guidance"

    for skill in sorted(SKILLS_ROOT.glob("**/SKILL.md")):
        text = _read(skill)
        assert "vscode_askQuestions" in text, f"{skill} must preserve question-tool guidance"


def test_preflight_caller_classification_covers_prompt_surface():
    """Keep prompt callers mapped to the intended sync policy classes."""
    preflight = _load_module(PREFLIGHT, "lens_preflight_regression")

    expected = {
        "lens-constitution": "read-only",
        "lens-next": "read-only",
        "lens-preflight": "read-only",
        "lens-switch": "read-only",
        "lens-expressplan": "control-write",
        "lens-preplan": "control-write",
        "lens-discover": "governance-write",
        "lens-new-domain": "governance-write",
        "lens-new-service": "governance-write",
        "lens-auspex-start": "mixed",
        "lens-auspex-ledger-promotion": "mixed",
        "lens-auspex-map-audit": "mixed",
        "lens-auspex-reporting-snapshot": "mixed",
        "lens-auspex-reporting-ui": "mixed",
        "lens-auspex-salmon-impact": "mixed",
        "lens-auspex-setup": "mixed",
        "lens-auspex-topology-design": "mixed",
        "lens-businessplan": "mixed",
        "lens-complete": "mixed",
        "lens-core-bugfix": "mixed",
        "lens-dev": "mixed",
        "lens-finalizeplan": "mixed",
        "lens-new-feature": "mixed",
        "lens-nextlens-bugfix": "mixed",
        "lens-quickdev": "mixed",
        "lens-split-feature": "mixed",
        "lens-techplan": "mixed",
        "lens-upgrade": "mixed",
    }

    prompt_callers = {
        _prompt_caller(prompt)
        for prompt in GITHUB_PROMPTS.glob("lens-*.prompt.md")
        if prompt.name not in NO_PREFLIGHT_PROMPTS
    }
    expected_prompt_callers = set(expected) - {"lens-core-bugfix"}
    assert prompt_callers == expected_prompt_callers, "Every preflight prompt caller must have an explicit policy"

    explicit_callers_by_class = _explicit_callers_by_class(preflight)
    for caller, request_class in expected.items():
        assert caller in explicit_callers_by_class[request_class], (
            f"{caller} must be explicitly listed in the {request_class} preflight caller set"
        )
        assert preflight.classify_request(caller) == request_class

    assert preflight.request_requires_repo("control-write", "control") is True
    assert preflight.request_requires_repo("control-write", "governance") is False
    assert preflight.request_requires_repo("governance-write", "governance") is True
    assert preflight.request_requires_repo("governance-write", "control") is False


def test_postflight_skill_explicitly_requires_closeout_commit_push_and_clean_state():
    postflight = _read(MODULE_ROOT / "skills" / "bmad-lens-postflight" / "SKILL.md")
    for phrase in [
        "commit and push",
        "target, control, and governance repos are clean",
        "Never leave target, control, or governance repo changes uncommitted or unpushed",
        "If any repo remains dirty after commit and push",
        "Do not sweep unrelated user edits into the closeout commit",
    ]:
        assert phrase in postflight


def test_lifecycle_contract_prevents_track_and_finalizeplan_input_drift():
    """Lock current lifecycle tracks and express FinalizePlan handoff inputs."""
    data = yaml.safe_load(_read(LIFECYCLE))
    tracks = data["tracks"]

    assert set(tracks) == {"full", "express", "quickdev", "hotfix-express", "spike"}
    assert "quickplan" not in tracks, "quickplan is an internal wrapper, not a selectable lifecycle track"
    assert tracks["express"]["phases"][:2] == ["expressplan", "finalizeplan"]
    assert tracks["quickdev"]["start_phase"] == "finalizeplan"

    finalizeplan = data["phases"]["finalizeplan"]
    contracts = finalizeplan["input_contracts_by_track"]
    assert contracts["express"] == ["business-plan", "tech-plan", "sprint-plan"]
    assert contracts["quickdev"] == ["business-plan", "tech-plan", "sprint-plan"]
    assert contracts["hotfix-express"] == ["architecture"]

    generic_full_docs = {"prd", "ux-design", "architecture"}
    assert not generic_full_docs.intersection(contracts["express"]), (
        "Express FinalizePlan input gate must not regress to generic BMAD full-track docs"
    )


def test_next_routes_active_phase_to_current_command_until_complete(tmp_path):
    """Prevent /lens-next from jumping to the next phase before the active phase is complete."""
    next_ops = _load_module(NEXT_OPS, "lens_next_regression")
    governance = tmp_path / "governance"
    feature_dir = governance / "features" / "domain" / "service" / "feature"
    feature_dir.mkdir(parents=True)

    def write_feature(phase: str) -> dict:
        feature_yaml = feature_dir / "feature.yaml"
        feature_yaml.write_text(
            yaml.safe_dump({"track": "express", "phase": phase}, sort_keys=False),
            encoding="utf-8",
        )
        next_ops._FEATURE_YAML_INDEX_CACHE.clear()
        return next_ops.suggest(
            "feature",
            str(governance),
            None,
            str(LIFECYCLE),
        )

    active = write_feature("expressplan")
    assert active["status"] == "unblocked"
    assert active["recommendation"] == "/expressplan"

    complete = write_feature("expressplan-complete")
    assert complete["status"] == "unblocked"
    assert complete["recommendation"] == "/finalizeplan"


def test_expressplan_and_finalizeplan_handoff_gates_remain_track_aware():
    expressplan = _read(EXPRESSPLAN_SKILL)
    finalizeplan = _read(FINALIZEPLAN_SKILL)

    for phrase in [
        "Interactive mode is never silent",
        "do not delegate to QuickPlan until the user responds",
        "expressplan-adversarial-review.md",
        "do not use `expressplan-review.md` as a new output or fallback",
        "No FinalizePlan bundle artifact is an ExpressPlan completion artifact",
    ]:
        assert phrase in expressplan

    for phrase in [
        "lifecycle `input-ready` contract",
        "--contract input-ready",
        "--track {track}",
        "do not ask the user to provide PRD-, architecture-, or UX-named documents",
        "Ensure every story referenced by `sprint-status.yaml` has a corresponding story file",
        "Do not treat a single seeded story file as sufficient",
        "feature.yaml` is updated to `finalizeplan-complete` in Step 3 only",
    ]:
        assert phrase in finalizeplan


def test_targetprojects_git_policy_and_core_bugfix_safety_are_explicit(tmp_path):
    git_ops = _load_module(GIT_ORCHESTRATION, "lens_git_orchestration_regression")
    missing = git_ops.feature_base_branch_missing_payload(
        "/workspace/TargetProjects/domain/service/repo",
        {"name": "repo"},
    )
    assert missing["error"] == "feature_base_branch_missing"
    assert missing["action"] == "ask_user_for_feature_base_branch"

    workspace = tmp_path / "workspace"
    repo = workspace / "TargetProjects" / "domain" / "service" / "repo"
    governance = workspace / "TargetProjects" / "lens" / "lens-governance"
    repo.mkdir(parents=True)
    governance.mkdir(parents=True)
    (governance / "repo-inventory.yaml").write_text(
        yaml.safe_dump(
            {
                "repositories": [
                    {
                        "name": "repo",
                        "local_path": "TargetProjects/domain/service/repo",
                        "feature_base_branch": "develop",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    base, error, source = git_ops.resolve_target_feature_base_branch(
        repo=str(repo),
        governance_repo=str(governance),
        requested_base_branch="main",
    )
    assert base is None
    assert source is None
    assert error["error"] == "feature_base_branch_mismatch"
    assert error["feature_base_branch"] == "develop"

    core_bugfix = _read(CORE_BUGFIX_SKILL)
    for phrase in [
        "Never create, add, remove, or use a sibling git worktree",
        "Do not run `git worktree add`",
        "If `{target_project}` is dirty or `prepare-dev-branch` exits non-zero, stop",
        "Every distinct bug must use its own branch",
        "Never tell the user to commit, push, or open the PR themselves",
        "PR URL",
    ]:
        assert phrase in core_bugfix
    assert "bugs/nextlens/QuickDev" not in core_bugfix
    assert "record-quickdev-pr" in core_bugfix
    assert "close-quickdev-bug" in core_bugfix
