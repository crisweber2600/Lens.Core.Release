"""Focused contract tests for the Lens Dev conductor instructions."""

from __future__ import annotations

from pathlib import Path


SKILL_MD = Path(__file__).resolve().parents[1] / "SKILL.md"


def _skill_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def test_governance_resolution_prefers_setup_file_before_phase_validation():
    content = _skill_text()
    resolution = content.split("## Governance Repo Resolution", 1)[1].split(
        "## Control Dev Branch Activation", 1
    )[0]

    assert ".lens/governance-setup.yaml" in resolution
    assert "governance_repo_path" in resolution
    assert "bmadconfig.yaml" in resolution
    assert "config_missing" in resolution
    assert "before reading `feature.yaml`" in resolution


def test_governance_resolution_forbids_sibling_clone_fallbacks():
    content = _skill_text()
    resolution = content.split("## Governance Repo Resolution", 1)[1].split(
        "## Control Dev Branch Activation", 1
    )[0]

    assert "MUST NOT probe sibling governance clone candidates" in resolution
    assert "TargetProjects/lens/lens-governance" in resolution
    assert "hardcoded default" in resolution


def test_phase_validation_uses_resolved_governance_repo():
    content = _skill_text()

    assert (
        "All `feature-yaml`, `lens-constitution`, `lens-git-orchestration`, and `lens-complete` calls"
        in content
    )
    assert "MUST use the resolved `governance_repo`" in content