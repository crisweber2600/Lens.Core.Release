#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Direct unit tests for next-ops.py.

This file intentionally follows the BMB script scanner's expected naming pattern
for scripts/next-ops.py. Broader routing and no-write coverage lives in
test_next_no_writes.py.
"""

import importlib.util
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "next-ops.py"
LIFECYCLE = Path(__file__).resolve().parents[4] / "lifecycle.yaml"


def load_next_ops():
    spec = importlib.util.spec_from_file_location("next_ops_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_empty_result_schema():
    next_ops = load_next_ops()

    result = next_ops._empty_result("preplan", "full")

    assert result == {
        "status": "",
        "recommendation": "",
        "blockers": [],
        "warnings": [],
        "phase": "preplan",
        "track": "full",
        "error": "",
    }


def test_find_feature_yaml_returns_none_for_missing_feature(tmp_path):
    next_ops = load_next_ops()
    governance_repo = tmp_path / "governance"
    (governance_repo / "features").mkdir(parents=True)

    feature_yaml = next_ops._find_feature_yaml("missing-feature", governance_repo)

    assert feature_yaml is None


def test_suggest_fails_with_alternate_governance_hint(tmp_path):
    next_ops = load_next_ops()
    feature_id = "nextlens-src-implement"

    governance_root = tmp_path / "TargetProjects" / "lens"
    primary_repo = governance_root / "Lens.Core.Governance"
    alternate_repo = governance_root / "lens-governance"
    (primary_repo / "features").mkdir(parents=True)
    alternate_feature_dir = alternate_repo / "features" / "nextlens" / "src" / feature_id
    alternate_feature_dir.mkdir(parents=True)
    (alternate_feature_dir / "feature.yaml").write_text(
        yaml.safe_dump({"track": "full", "phase": "techplan-complete"}, sort_keys=False),
        encoding="utf-8",
    )

    next_ops._FEATURE_YAML_INDEX_CACHE.clear()
    result = next_ops.suggest(feature_id, str(primary_repo), None, str(LIFECYCLE))

    assert result["status"] == "fail"
    assert "alternate governance clone" in result["error"]
    assert str(alternate_feature_dir) in result["error"]


def test_suggest_fails_on_governance_phase_conflict(tmp_path):
    next_ops = load_next_ops()
    feature_id = "nextlens-src-implement"

    governance_root = tmp_path / "TargetProjects" / "lens"
    primary_repo = governance_root / "lens-governance"
    alternate_repo = governance_root / "Lens.Core.Governance"
    primary_feature_dir = primary_repo / "features" / "nextlens" / "src" / feature_id
    alternate_feature_dir = alternate_repo / "features" / "nextlens" / "src" / feature_id
    primary_feature_dir.mkdir(parents=True)
    alternate_feature_dir.mkdir(parents=True)

    (primary_feature_dir / "feature.yaml").write_text(
        yaml.safe_dump({"track": "full", "phase": "techplan-complete"}, sort_keys=False),
        encoding="utf-8",
    )
    (alternate_feature_dir / "feature.yaml").write_text(
        yaml.safe_dump({"track": "full", "phase": "businessplan-complete"}, sort_keys=False),
        encoding="utf-8",
    )

    next_ops._FEATURE_YAML_INDEX_CACHE.clear()
    result = next_ops.suggest(feature_id, str(primary_repo), None, str(LIFECYCLE))

    assert result["status"] == "fail"
    assert "governance_phase_conflict" in result["error"]
    assert "businessplan-complete" in result["error"]