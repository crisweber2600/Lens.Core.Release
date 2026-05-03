from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def feature_yaml_fixture(tmp_path: Path) -> Path:
    """Create a minimal governance feature.yaml fixture and return its path."""
    feature_dir = tmp_path / "features" / "lens-dev" / "new-codebase" / "lens-dev-new-codebase-complete"
    feature_dir.mkdir(parents=True)
    feature_yaml = feature_dir / "feature.yaml"
    feature_yaml.write_text(
        "featureId: lens-dev-new-codebase-complete\n"
        "domain: lens-dev\n"
        "service: new-codebase\n"
        "phase: dev\n",
        encoding="utf-8",
    )
    return feature_yaml


@pytest.fixture
def governance_repo_fixture(feature_yaml_fixture: Path) -> Path:
    """Return the temporary governance repo root containing the feature fixture."""
    return feature_yaml_fixture.parents[4]
