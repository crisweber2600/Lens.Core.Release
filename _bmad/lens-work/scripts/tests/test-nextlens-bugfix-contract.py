#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Contract tests for the canonical NextLens bugfix command surface."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import yaml


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
REPO_ROOT = MODULE_ROOT.parents[1]
PUBLIC_PROMPT = REPO_ROOT / ".github" / "prompts" / "lens-nextlens-bugfix.prompt.md"
MODULE_PROMPT = MODULE_ROOT / "prompts" / "lens-nextlens-bugfix.prompt.md"
SKILL_MD = MODULE_ROOT / "skills" / "lens-nextlens-bugfix" / "SKILL.md"
MODULE_YAML = MODULE_ROOT / "module.yaml"
MODULE_HELP = MODULE_ROOT / "module-help.csv"
SETUP_MODULE_HELP = MODULE_ROOT / "lens-work-setup" / "assets" / "module-help.csv"
PREFLIGHT = MODULE_ROOT / "skills" / "lens-preflight" / "scripts" / "preflight.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_preflight_module():
    spec = importlib.util.spec_from_file_location("lens_preflight_ops", PREFLIGHT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _module_data() -> dict:
    return yaml.safe_load(_read(MODULE_YAML))


def _help_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_public_prompt_runs_preflight_then_routes_to_module_prompt():
    text = _read(PUBLIC_PROMPT)

    preflight_index = text.index("light-preflight.py --caller lens-nextlens-bugfix")
    module_prompt_index = text.index("lens.core/_bmad/lens-work/prompts/lens-nextlens-bugfix.prompt.md")

    assert preflight_index < module_prompt_index
    assert "If that command exits non-zero, stop" in text
    assert "vscode_askQuestions" in text


def test_module_prompt_is_redirect_only():
    text = _read(MODULE_PROMPT)

    assert "lens-nextlens-bugfix/SKILL.md" in text
    assert "routing stub only" in text
    assert "prompt-local implementation logic" in text
    assert "light-preflight.py" not in text


def test_skill_contract_names_required_inputs_and_boundaries():
    text = _read(SKILL_MD)

    for phrase in (
        "`/lens-nextlens-bugfix` is the single canonical Lens-owned NextLens bugfix surface.",
        "what_happened",
        "what_should_have_happened",
        "chat_history",
        "TargetProjects/lens-dev/new-codebase/lens.core.src",
        "TargetProjects/nextlens/src/NextLens",
        "must not bypass Lens governance, story selection, validation, or review gates",
        "nextlens_fix_spec.py",
        "git-orchestration-ops.py prepare-dev-branch",
        "direct the operator to `/lens-core-bugfix`",
        "Do not treat new NextLens skill or install-surface work inside `TargetProjects/nextlens/src/NextLens` as a Lens core bug.",
    ):
        assert phrase in text


def test_module_yaml_registers_prompt_and_skill_once():
    data = _module_data()
    prompts = [str(value) for value in data.get("prompts", [])]
    skills = [str(value) for value in data.get("skills", [])]

    assert prompts.count("lens-nextlens-bugfix.prompt.md") == 1
    assert skills.count("lens-nextlens-bugfix") == 1


def test_operator_help_exposes_single_canonical_nextlens_bugfix_row():
    rows = [row for row in _help_rows(MODULE_HELP) if row.get("skill") == "lens-nextlens-bugfix"]

    assert len(rows) == 1
    row = rows[0]
    assert row["display-name"] == "nextlens-bugfix"
    assert "what happened/should/chat inputs" in row["description"]
    assert "optional Salmon metadata" in row["description"]
    assert "fresh branch delegation" in row["description"]
    assert "PR plus Doctor closeout evidence" in row["description"]
    assert "TargetProjects/nextlens/src/NextLens" in row["description"]
    assert "new skills and install-surface updates when warranted" in row["description"]
    assert "--what-should-have-happened" in row["args"]
    assert "--chat-history" in row["args"]
    assert "PR URL" in row["outputs"]
    assert "Doctor-backed closeout evidence" in row["outputs"]


def test_setup_help_metadata_includes_nextlens_bugfix_surface():
    rows = [row for row in _help_rows(SETUP_MODULE_HELP) if row.get("skill") == "lens-nextlens-bugfix"]

    assert len(rows) == 1
    assert "what happened/should/chat inputs" in rows[0]["description"]
    assert "optional Salmon metadata" in rows[0]["description"]
    assert "fresh branch delegation" in rows[0]["description"]
    assert "PR plus Doctor closeout evidence" in rows[0]["description"]
    assert "TargetProjects/nextlens/src/NextLens" in rows[0]["description"]
    assert "new skills and install-surface updates when warranted" in rows[0]["description"]
    assert "PR URL" in rows[0]["outputs"]
    assert "Doctor-backed closeout evidence" in rows[0]["outputs"]


def test_preflight_explicitly_classifies_nextlens_bugfix_as_mixed():
    ops = _load_preflight_module()

    assert ops.classify_request("lens-nextlens-bugfix") == "mixed"


def test_skill_operator_quick_reference_is_concise_and_operational():
    text = _read(SKILL_MD)

    for phrase in (
        "## Operator Quick Reference",
        "Required inputs: `what_happened`, `what_should_have_happened`, and `chat_history`.",
        "Optional metadata: `severity`, `salmon_signal_id`, `evidence_refs`, `suspected_target_surface`, `validation_request`, and `operator_notes`.",
        "Expected outputs: `bug_artifact_path`, `bug_slug`, `working_branch`, `base_branch`, `commit_hash`, `PR URL`",
        "Required closeout evidence: recorded `PR URL`, NextLens Doctor status plus evidence or rationale, and approved-route evidence for high or blocking Salmon-linked bugs.",
    ):
        assert phrase in text


def test_skill_test_hooks_cover_registration_helper_and_boundary_drift():
    text = _read(SKILL_MD)

    for phrase in (
        "`module.yaml` registers `lens-nextlens-bugfix.prompt.md` and `lens-nextlens-bugfix` exactly once.",
        "use model judgment, not keyword spotting alone",
        "`nextlens_fix_spec.py`",
        "`bug-reporter-ops.py`",
        "namespace `nextlens`",
        "`allowed_write_root` boundary enforcement",
        "`NextLens docs context is incomplete or conflicting`",
        "`does not include 'NextLens'`",
        "`includes multiple 'NextLens' entries`",
        "`target_boundary_violation`",
    ):
        assert phrase in text
