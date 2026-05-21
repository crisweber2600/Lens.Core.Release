#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "auspex_start_memory.py"


def load_script():
    spec = importlib.util.spec_from_file_location("auspex_start_memory", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def args(tmp_path: Path, **overrides):
    values = {
        "project_root": str(tmp_path),
        "feature_id": "lens-dev-new-codebase-reporting-snapshot-contract",
        "title": "Reporting Snapshot Contract",
        "domain": "lens-dev",
        "service": "new-codebase",
        "track": "express",
        "docs_path": "docs/lens-dev/new-codebase/lens-dev-new-codebase-reporting-snapshot-contract",
        "related": [],
        "intent": "Create a stable snapshot contract.",
        "memory_note": "Remember the reporting contract is read-only.",
        "timestamp": "2026-05-21T12:00:00Z",
        "dry_run": True,
    }
    values.update(overrides)
    return Namespace(**values)


def frontmatter_from(content: str) -> dict:
    assert content.startswith("---\n")
    _, frontmatter, _ = content.split("---\n", 2)
    return yaml.safe_load(frontmatter)


def test_dry_run_reports_feature_archive_memory_path(tmp_path: Path):
    module = load_script()
    result = module.write_memory(args(tmp_path))
    assert result["status"] == "dry-run"
    assert result["relative_memory_path"] == (
        "docs/features/lens-dev-new-codebase-reporting-snapshot-contract/memory.md"
    )
    assert not (tmp_path / result["relative_memory_path"]).exists()


def test_memory_frontmatter_contains_required_fields(tmp_path: Path):
    module = load_script()
    result = module.write_memory(args(tmp_path))
    frontmatter = frontmatter_from(result["content"])
    assert frontmatter["featureId"] == "lens-dev-new-codebase-reporting-snapshot-contract"
    assert frontmatter["kind"] == "auspex_unit_memory"
    assert frontmatter["status"] == "active"
    assert frontmatter["belongs_to"] == {"service": "new-codebase", "domain": "lens-dev", "program": None}
    assert frontmatter["docs_path"] == (
        "docs/lens-dev/new-codebase/lens-dev-new-codebase-reporting-snapshot-contract"
    )
    assert frontmatter["promotion_status"] == "pending"
    assert frontmatter["created_at"] == "2026-05-21T12:00:00Z"
    assert frontmatter["updated_at"] == "2026-05-21T12:00:00Z"


def test_related_feature_ids_are_recorded(tmp_path: Path):
    module = load_script()
    result = module.write_memory(
        args(
            tmp_path,
            related=[
                "lens-dev-new-codebase-reporting-snapshot-contract",
                "lens-dev-new-codebase-reporting-snapshot-contract",
                "lens-dev-new-codebase-reporting-filtering",
            ],
        )
    )
    frontmatter = frontmatter_from(result["content"])
    assert frontmatter["related_units"] == [
        "lens-dev-new-codebase-reporting-snapshot-contract",
        "lens-dev-new-codebase-reporting-filtering",
    ]


def test_write_is_confined_to_feature_archive(tmp_path: Path):
    module = load_script()
    result = module.write_memory(args(tmp_path, dry_run=False))
    target = tmp_path / result["relative_memory_path"]
    assert target.exists()
    assert target.parent == tmp_path / "docs" / "features" / result["feature_id"]
    assert not (tmp_path / "_bmad-output").exists()
    assert not (tmp_path / "NextLensV3.Release").exists()


def test_rejects_feature_id_path_escape(tmp_path: Path):
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(tmp_path),
            "--feature-id",
            "..\\escape",
            "--title",
            "Escape",
            "--domain",
            "lens-dev",
            "--service",
            "new-codebase",
            "--track",
            "express",
            "--docs-path",
            "docs/lens-dev/new-codebase/escape",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stderr)
    assert payload["status"] == "fail"
    assert "path separators" in payload["error"]

