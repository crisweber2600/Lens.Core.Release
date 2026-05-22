#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Tests for NextLens design-context and target-root resolution."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from lens_config import (  # noqa: E402
    ConfigError,
    _load_topdown_constraints,
    ensure_within_root,
    find_module_config,
    resolve_nextlens_design_context,
)


TEST_FILE = Path(__file__).resolve()
SKILL_SOURCE_ROOT = TEST_FILE.parents[4]
CONTROL_REPO_ROOT = SKILL_SOURCE_ROOT.parents[3]
GOVERNANCE_REPO_ROOT = CONTROL_REPO_ROOT / "TargetProjects" / "lens" / "Lens.Core.governance"
FEATURE_ID = "nextlens-src-dogfoodnext"


def _mixed_case_text(path: Path) -> str:
    text = str(path)
    swapped = []
    for index, char in enumerate(text):
        if char.isalpha():
            swapped.append(char.upper() if index % 2 else char.lower())
        else:
            swapped.append(char)
    return "".join(swapped)


def _create_escape_link(link_path: Path, target_path: Path) -> bool:
    if os.name == "nt":
        try:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except (OSError, subprocess.CalledProcessError):
            try:
                os.symlink(target_path, link_path, target_is_directory=True)
                return True
            except OSError:
                return False

    try:
        os.symlink(target_path, link_path, target_is_directory=True)
        return True
    except OSError:
        return False


def test_find_module_config_from_workspace_root_and_non_root_control_paths():
    workspace_config = find_module_config(CONTROL_REPO_ROOT)
    nested_config = find_module_config(CONTROL_REPO_ROOT / "docs" / "nextlens" / "src" / FEATURE_ID / "stories")

    expected = SKILL_SOURCE_ROOT / "_bmad" / "lens-work" / "bmadconfig.yaml"
    assert workspace_config == expected.resolve()
    assert nested_config == expected.resolve()


def test_resolve_nextlens_design_context_from_workspace_root():
    context = resolve_nextlens_design_context(
        FEATURE_ID,
        start=CONTROL_REPO_ROOT,
        governance_repo=GOVERNANCE_REPO_ROOT,
    )

    assert context.control_repo_root == CONTROL_REPO_ROOT.resolve()
    assert context.docs_context_root == (CONTROL_REPO_ROOT / "docs" / "nextlens" / "src").resolve()
    assert context.feature_docs_root == (context.docs_context_root / FEATURE_ID).resolve()
    assert context.skill_source_root == SKILL_SOURCE_ROOT.resolve()
    assert context.runtime_target_root == (
        CONTROL_REPO_ROOT / "TargetProjects" / "nextlens" / "src" / "NextLens"
    ).resolve()
    assert [constraint.title for constraint in context.constraints] == [
        "TopDownLens bugfix guide",
        "TopDownLens bugfix example",
    ]
    assert any("approved target surfaces" in excerpt for excerpt in context.constraints[0].excerpts)


def test_resolve_nextlens_design_context_from_non_root_cwd():
    start = CONTROL_REPO_ROOT / "docs" / "nextlens" / "src" / FEATURE_ID / "stories"
    context = resolve_nextlens_design_context(
        FEATURE_ID,
        start=start,
        governance_repo=GOVERNANCE_REPO_ROOT,
    )

    assert context.control_repo_root == CONTROL_REPO_ROOT.resolve()
    assert context.docs_context_root == (CONTROL_REPO_ROOT / "docs" / "nextlens" / "src").resolve()
    assert context.skill_source_root == SKILL_SOURCE_ROOT.resolve()
    assert context.runtime_target_root == (
        CONTROL_REPO_ROOT / "TargetProjects" / "nextlens" / "src" / "NextLens"
    ).resolve()


def test_nextlens_override_accepts_mixed_case_and_mixed_separators_inside_roots():
    docs_override = _mixed_case_text(Path("docs") / "nextlens" / "src" / "nextlens-src-topdownlens").replace("\\", "/")
    runtime_override = _mixed_case_text(
        Path("TargetProjects") / "nextlens" / "src" / "NextLens"
    ).replace("/", "\\")

    context = resolve_nextlens_design_context(
        FEATURE_ID,
        start=CONTROL_REPO_ROOT,
        governance_repo=GOVERNANCE_REPO_ROOT,
        docs_path_override=docs_override,
        runtime_target_override=runtime_override,
    )

    assert context.docs_context_path == (CONTROL_REPO_ROOT / "docs" / "nextlens" / "src" / "nextlens-src-topdownlens").resolve()
    assert context.runtime_target_path == (
        CONTROL_REPO_ROOT / "TargetProjects" / "nextlens" / "src" / "NextLens"
    ).resolve()


def test_nextlens_override_rejects_relative_escape():
    with pytest.raises(ConfigError, match="runtime target override escapes approved root"):
        resolve_nextlens_design_context(
            FEATURE_ID,
            start=CONTROL_REPO_ROOT,
            governance_repo=GOVERNANCE_REPO_ROOT,
            runtime_target_override=r"TargetProjects\nextlens\src\NextLens\..\..\..\lens-dev\new-codebase\lens.core.src",
        )


def test_ensure_within_root_rejects_symlink_or_junction_escape(tmp_path: Path):
    approved = tmp_path / "approved"
    outside = tmp_path / "outside"
    approved.mkdir()
    outside.mkdir()
    link = approved / "escape"
    if not _create_escape_link(link, outside):
        pytest.skip("symlink/junction creation is not supported in this environment")

    with pytest.raises(ConfigError, match="escapes approved root"):
        ensure_within_root(link, approved_root=approved, label="override path")


def test_load_topdown_constraints_reports_missing_docs_without_guessing(tmp_path: Path):
    docs_root = tmp_path / "docs" / "nextlens" / "src"
    docs_root.mkdir(parents=True)
    guide = docs_root / "nextlens-src-topdownlens" / "guides" / "bugfix-flow.md"
    guide.parent.mkdir(parents=True)
    guide.write_text("# incomplete\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="NextLens docs context is incomplete or conflicting"):
        _load_topdown_constraints(docs_root)


def test_resolve_nextlens_design_context_rejects_conflicting_feature_docs_path(tmp_path: Path):
    control_root = tmp_path / "control"
    skill_root = control_root / "TargetProjects" / "lens-dev" / "new-codebase" / "lens.core.src"
    module_root = skill_root / "_bmad" / "lens-work"
    governance_root = tmp_path / "governance"
    feature_root = governance_root / "features" / "nextlens" / "src" / FEATURE_ID
    docs_root = control_root / "docs" / "elsewhere"
    feature_docs_root = docs_root / "feature-docs"
    nextlens_docs_root = control_root / "docs" / "nextlens" / "src"
    runtime_root = control_root / "TargetProjects" / "nextlens" / "src" / "NextLens"

    module_root.mkdir(parents=True)
    feature_root.mkdir(parents=True)
    feature_docs_root.mkdir(parents=True)
    nextlens_docs_root.mkdir(parents=True)
    runtime_root.mkdir(parents=True)

    (module_root / "lifecycle.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    (module_root / "bmadconfig.yaml").write_text(
        yaml.safe_dump(
            {
                "governance_repo_path": str(governance_root),
                "control_topology": "3-branch",
                "target_projects_path": "{project-root}/../../..",
                "default_git_remote": "origin",
                "lifecycle_contract": "{module-root}/lifecycle.yaml",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (feature_root / "feature.yaml").write_text(
        yaml.safe_dump(
            {
                "featureId": FEATURE_ID,
                "docs": {"path": "docs/elsewhere/feature-docs"},
                "target_repos": [
                    {"name": "lens.core.src", "local_path": "TargetProjects/lens-dev/new-codebase/lens.core.src"},
                    {"name": "NextLens", "local_path": "TargetProjects/nextlens/src/NextLens"},
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="conflicts with required NextLens docs root"):
        resolve_nextlens_design_context(FEATURE_ID, start=control_root)
