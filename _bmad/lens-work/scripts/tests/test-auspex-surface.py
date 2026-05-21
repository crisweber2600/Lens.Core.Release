#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Regression tests for the Lens Auspex preferred workflow surface.

Run:
    cd TargetProjects/lens-dev/new-codebase/lens.core.src
    uv run --with pytest --with pyyaml pytest _bmad/lens-work/scripts/tests/test-auspex-surface.py -q
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml


TEST_FILE = Path(__file__).resolve()
MODULE_ROOT = TEST_FILE.parents[2]
REPO_ROOT = MODULE_ROOT.parents[1]
PROMPTS_DIR = MODULE_ROOT / "prompts"
PUBLIC_PROMPTS_DIR = REPO_ROOT / ".github" / "prompts"
SKILLS_DIR = MODULE_ROOT / "skills"
MODULE_YAML = MODULE_ROOT / "module.yaml"
MODULE_HELP = MODULE_ROOT / "module-help.csv"
SETUP_MODULE_HELP = MODULE_ROOT / "lens-work-setup" / "assets" / "module-help.csv"
ROOT_CONFIG = REPO_ROOT / "_bmad" / "config.yaml"
ROOT_MODULE_HELP = REPO_ROOT / "_bmad" / "module-help.csv"
AGENT_FILE = MODULE_ROOT / "agents" / "lens.agent.md"
README = MODULE_ROOT / "README.md"
GITIGNORE = REPO_ROOT / ".gitignore"
ARCH_DOC = REPO_ROOT / "docs" / "auspex-architecture.md"
UI_CONTRACT_DOC = REPO_ROOT / "docs" / "auspex-reporting-ui-contract.md"
USER_GUIDE = REPO_ROOT / "docs" / "auspex-user-guide.md"
INTEGRATION_FLOW = REPO_ROOT / "docs" / "auspex-lens-integration-flow.md"


AUSPEX_WRAPPERS = {
    "lens-auspex-start": "lens-init-feature",
    "lens-auspex-setup": "ausx-setup",
    "lens-auspex-map-audit": "ausx-map-audit",
    "lens-auspex-ledger-promotion": "ausx-ledger-promotion",
    "lens-auspex-salmon-impact": "ausx-salmon-impact",
    "lens-auspex-topology-design": "ausx-topology-design",
    "lens-auspex-reporting-snapshot": "ausx-reporting-snapshot",
    "lens-auspex-reporting-ui": "ausx-reporting-snapshot",
}


SNAPSHOT_FIELDS = {
    "module",
    "report_type",
    "created_at",
    "scope",
    "overall_status",
    "blocking",
    "advisory",
    "features",
    "ledgers",
    "salmon_impacts",
    "freshness",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _module_data() -> dict:
    data = yaml.safe_load(_read_text(MODULE_YAML))
    assert isinstance(data, dict)
    return data


def _help_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _help_row_by_skill(path: Path) -> dict[str, dict[str, str]]:
    return {row["skill"]: row for row in _help_rows(path)}


def test_every_lens_auspex_prompt_is_registered_and_has_files():
    prompts = set(_module_data().get("prompts", []))
    for wrapper in AUSPEX_WRAPPERS:
        prompt_name = f"{wrapper}.prompt.md"
        assert prompt_name in prompts
        assert (PROMPTS_DIR / prompt_name).exists()
        assert (PUBLIC_PROMPTS_DIR / prompt_name).exists()


def test_every_lens_auspex_wrapper_has_help_row_and_skill_file():
    skills = set(_module_data().get("skills", []))
    module_rows = _help_row_by_skill(MODULE_HELP)
    setup_rows = _help_row_by_skill(SETUP_MODULE_HELP)
    for wrapper in AUSPEX_WRAPPERS:
        assert wrapper in skills
        assert (SKILLS_DIR / wrapper / "SKILL.md").exists()
        assert wrapper in module_rows
        assert wrapper in setup_rows
        assert module_rows[wrapper]["phase"] == "preferred"
        assert setup_rows[wrapper]["phase"] == "preferred"


def test_wrappers_delegate_to_expected_skills_and_enforce_release_read_only():
    for wrapper, delegated_skill in AUSPEX_WRAPPERS.items():
        text = _read_text(SKILLS_DIR / wrapper / "SKILL.md")
        assert "lens-preflight" in text
        if wrapper != "lens-auspex-start":
            assert "lens-constitution" in text
        assert "write scope" in text.lower()
        assert "NextLensV3.Release" in text
        assert delegated_skill in text
    start_text = _read_text(SKILLS_DIR / "lens-auspex-start" / "SKILL.md")
    assert "lens-next" in start_text
    assert "auspex_start_memory.py" in start_text
    assert "docs/features/<feature-id>/memory.md" in start_text


def test_imported_auspex_module_surface_exists():
    expected_ausx = {
        "ausx-setup",
        "ausx-map-audit",
        "ausx-ledger-promotion",
        "ausx-salmon-impact",
        "ausx-topology-design",
        "ausx-reporting-snapshot",
    }
    for skill in expected_ausx:
        assert (REPO_ROOT / ".agents" / "skills" / skill / "SKILL.md").exists()
    root_rows = {row["skill"] for row in _help_rows(ROOT_MODULE_HELP)}
    assert expected_ausx.issubset(root_rows)


def test_auspex_root_config_paths_and_personal_config_contract():
    config = yaml.safe_load(_read_text(ROOT_CONFIG))
    assert config["output_folder"] == "{project-root}/_bmad-output"
    assert config["ausx"]["feature_archive_path"] == "{project-root}/docs/features"
    assert config["ausx"]["landscape_root"] == "{project-root}/docs"
    assert config["ausx"]["reporting_output_path"] == "{project-root}/_bmad-output/auspex"
    assert config["ausx"]["freshness_threshold_hours"] == "24"
    assert "user_name" not in config
    assert "communication_language" not in config
    assert not (REPO_ROOT / "_bmad" / "config.user.yaml").exists()
    assert not (REPO_ROOT / "_bmad" / "config.user.toml").exists()


def test_personal_config_and_generated_output_are_ignored():
    text = _read_text(GITIGNORE)
    assert "_bmad/config.user.yaml" in text
    assert "_bmad/config.user.toml" in text
    assert "_bmad-output/" in text


def test_preference_docs_recommend_auspex_without_hiding_legacy_commands():
    combined = "\n".join(
        [_read_text(AGENT_FILE), _read_text(README), _read_text(USER_GUIDE), _read_text(INTEGRATION_FLOW)]
    )
    assert "Auspex" in combined
    assert "preferred" in combined.lower()
    assert "lens-auspex-start" in combined
    assert "lens-new-domain" in combined
    assert "lens-new-service" in combined
    assert "lens-new-feature" in combined
    rows = _help_row_by_skill(MODULE_HELP)
    for legacy in ["lens-new-domain", "lens-new-service", "lens-new-feature"]:
        assert legacy in rows


def test_stable_id_metadata_examples_and_reporting_snapshot_contract_are_documented():
    arch = _read_text(ARCH_DOC)
    assert "featureId: widget-1.1" in arch
    assert "belongs_to:" in arch
    assert "ledger_path:" in arch
    assert "docs/features/" in arch
    assert "derived projection" in arch.lower()
    assert "Salmon" in arch

    ui_contract = _read_text(UI_CONTRACT_DOC)
    snapshot_skill = _read_text(
        REPO_ROOT / ".agents" / "skills" / "ausx-reporting-snapshot" / "SKILL.md"
    )
    for field in SNAPSHOT_FIELDS:
        assert f'"{field}"' in ui_contract
        assert f'"{field}"' in snapshot_skill


def test_reporting_ui_wrapper_is_contract_only_not_a_deployable_ui():
    text = _read_text(SKILLS_DIR / "lens-auspex-reporting-ui" / "SKILL.md")
    assert "does not create or deploy" in text
    assert "no UI app" in text
    assert "auspex-reporting-ui-contract.md" in text


def test_auspex_start_user_journey_documents_initial_and_related_features():
    text = _read_text(INTEGRATION_FLOW)
    assert 'lens-auspex-start "Reporting Snapshot Contract"' in text
    assert 'lens-auspex-start "Reporting Snapshot Filters"' in text
    assert "--related lens-dev-new-codebase-reporting-snapshot-contract" in text
    assert "docs/features/<feature-id>/memory.md" in text
    assert "delegates to `lens-next`" in text
