#!/usr/bin/env python3
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


SCRIPT = Path(__file__).resolve().parents[1] / "next-ops.py"


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