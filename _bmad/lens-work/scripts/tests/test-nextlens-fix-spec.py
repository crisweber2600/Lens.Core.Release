#!/usr/bin/env python3
"""Tests for nextlens_fix_spec.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


TEST_FILE = Path(__file__).resolve()
SCRIPTS_DIR = TEST_FILE.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
SCRIPT = SCRIPTS_DIR / "nextlens_fix_spec.py"

FEATURE_ID = "nextlens-src-dogfoodnext"
SKILL_SOURCE_ROOT = TEST_FILE.parents[4]
CONTROL_REPO_ROOT = SKILL_SOURCE_ROOT.parents[3]
GOVERNANCE_REPO_ROOT = CONTROL_REPO_ROOT / "TargetProjects" / "lens" / "Lens.Core.governance"


def _normalize_path_text(value: str) -> str:
    return value.replace("\\", "/")


def load_module():
    spec = importlib.util.spec_from_file_location("nextlens_fix_spec", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def base_intake(**overrides):
    data = {
        "what_happened": "Applying a Lens patch from NextLens crashes after selecting the target tree.",
        "what_should_have_happened": "NextLens should open the patch preview and keep the session alive.",
        "chat_history": (
            "User: I selected the patch target and the panel disappeared.\n"
            "Assistant: I saw the command restart.\n"
            "User: It happens every time on the dogfood build."
        ),
        "evidence_refs": ["artifact://nextlens/session-17"],
    }
    data.update(overrides)
    return data


def test_fix_spec_contains_required_fields_in_deterministic_order():
    ops = load_module()
    spec = ops.generate_nextlens_fix_spec(
        FEATURE_ID,
        base_intake(
            suspected_target_surface=r"TargetProjects\nextlens\src\NextLens\Runtime",
            validation_request="Run the NextLens patch preview regression and capture Doctor output.",
        ),
        bug_state={
            "status": "QuickDev",
            "namespace": "nextlens",
            "governance_repo_root": str(GOVERNANCE_REPO_ROOT),
        },
        start=str(CONTROL_REPO_ROOT),
        governance_repo=str(GOVERNANCE_REPO_ROOT),
    )

    assert list(spec) == [
        "status",
        "feature_id",
        "bugfix_feature_id",
        "bugfix_feature_slug",
        "bugfix_working_branch",
        "bug_slug",
        "bug_status",
        "bug_artifact_path",
        "bug_reporter_fields",
        "actual_behavior",
        "expected_behavior",
        "evidence_summary",
        "design_context_references",
        "skill_source_root",
        "allowed_write_root",
        "allowed_write_root_display",
        "prohibited_write_roots",
        "suspected_target_surfaces",
        "validation_expectations",
        "salmon_linkage",
        "delegation_blocked",
        "delegation_blockers",
        "handoff_storage",
    ]
    assert spec["status"] == "ready"
    assert spec["feature_id"] == FEATURE_ID
    assert spec["bugfix_feature_id"] == f"nextlens-bugfix-{spec['bug_slug']}"
    assert spec["bugfix_feature_slug"] == spec["bugfix_feature_id"]
    assert spec["bugfix_working_branch"] == f"feature/{spec['bugfix_feature_id']}"
    assert spec["bug_status"] == "QuickDev"
    assert _normalize_path_text(spec["bug_artifact_path"]).endswith(
        f"bugs/nextlens/QuickDev/{spec['bug_slug']}.md"
    )
    assert spec["bug_reporter_fields"]["title"].startswith("NextLens bug:")
    assert spec["bug_reporter_fields"]["queue"] == "QuickDev"
    assert spec["bug_reporter_fields"]["source"] == "nextlens-bugfix"
    assert spec["bug_reporter_fields"]["namespace"] == "nextlens"
    assert "Actual Behavior:" in spec["bug_reporter_fields"]["description"]
    assert "Transcript digest:" in spec["bug_reporter_fields"]["chat_log"]
    assert spec["actual_behavior"] == base_intake()["what_happened"]
    assert spec["expected_behavior"] == base_intake()["what_should_have_happened"]
    assert spec["allowed_write_root_display"] == r"TargetProjects\nextlens\src\NextLens"
    assert [reference["title"] for reference in spec["design_context_references"]] == [
        "TopDownLens bugfix guide",
        "TopDownLens bugfix example",
    ]
    assert [entry["label"] for entry in spec["prohibited_write_roots"]] == [
        "governance_repo",
        "release_clone_paths",
        "unrelated_control_paths",
    ]
    assert [_normalize_path_text(path) for path in spec["suspected_target_surfaces"]] == [
        (CONTROL_REPO_ROOT / "TargetProjects" / "nextlens" / "src" / "NextLens" / "Runtime").resolve().as_posix()
    ]
    assert spec["validation_expectations"][0] == "Run the NextLens patch preview regression and capture Doctor output."
    assert spec["delegation_blocked"] is False
    assert spec["handoff_storage"] == "in-memory"


def test_fix_spec_preserves_salmon_linkage_when_signal_exists():
    ops = load_module()
    spec = ops.generate_nextlens_fix_spec(
        FEATURE_ID,
        base_intake(severity="high", salmon_signal_id="salmon.20260514T045700Z.high_correct_course"),
        bug_state={
            "status": "QuickDev",
            "namespace": "nextlens",
            "governance_repo_root": str(GOVERNANCE_REPO_ROOT),
        },
        start=str(CONTROL_REPO_ROOT),
        governance_repo=str(GOVERNANCE_REPO_ROOT),
    )

    assert spec["salmon_linkage"] == {
        "signal_id": "salmon.20260514T045700Z.high_correct_course",
        "severity": "high",
        "recommended_action": "bmad_correct_course",
        "evidence_refs": ["artifact://nextlens/session-17"],
        "closure_expectations": [
            "Treat the signal as an immediate bugfix path before more dependent work or promotion proceeds.",
            "Record validation evidence and any PR linkage before marking the originating signal resolved.",
            "If a newer signal replaces this bug, mark the originating signal superseded with a pointer to the replacement.",
        ],
    }


def test_fix_spec_without_salmon_keeps_evidence_fields_and_fallback_surface():
    ops = load_module()
    spec = ops.generate_nextlens_fix_spec(
        FEATURE_ID,
        base_intake(),
        bug_state={
            "status": "QuickDev",
            "namespace": "nextlens",
            "governance_repo_root": str(GOVERNANCE_REPO_ROOT),
        },
        start=str(CONTROL_REPO_ROOT),
        governance_repo=str(GOVERNANCE_REPO_ROOT),
    )

    assert spec["salmon_linkage"] is None
    assert "Transcript digest:" in spec["evidence_summary"]
    assert [_normalize_path_text(path) for path in spec["suspected_target_surfaces"]] == [
        (CONTROL_REPO_ROOT / "TargetProjects" / "nextlens" / "src" / "NextLens").resolve().as_posix()
    ]


def test_fix_spec_blocks_delegation_when_nextlens_target_root_is_missing_or_ambiguous(tmp_path: Path):
    ops = load_module()

    for mode in ("missing", "ambiguous"):
        control_root = tmp_path / mode / "control"
        skill_root = control_root / "TargetProjects" / "lens-dev" / "new-codebase" / "lens.core.src"
        module_root = skill_root / "_bmad" / "lens-work"
        governance_root = tmp_path / mode / "governance"
        feature_root = governance_root / "features" / "nextlens" / "src" / FEATURE_ID
        docs_root = control_root / "docs" / "nextlens" / "src" / FEATURE_ID
        guide = control_root / "docs" / "nextlens" / "src" / "nextlens-src-topdownlens" / "guides" / "bugfix-flow.md"
        example = control_root / "docs" / "nextlens" / "src" / "nextlens-src-topdownlens" / "examples" / "bugfix-example.md"
        runtime_root = control_root / "TargetProjects" / "nextlens" / "src" / "NextLens"

        module_root.mkdir(parents=True)
        feature_root.mkdir(parents=True)
        docs_root.mkdir(parents=True)
        guide.parent.mkdir(parents=True)
        example.parent.mkdir(parents=True)
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
        guide.write_text(
            "\n".join(
                [
                    "implement only in approved target surfaces",
                    "Governance repo: stay on `main`; no feature-branch governance topology.",
                    "They must not hand-copy changes into governance or release as a fallback.",
                ]
            ),
            encoding="utf-8",
        )
        example.write_text(
            "\n".join(
                [
                    "Target branch: prepared by `lens-git-orchestration` for the resolved target repo.",
                    "It does not write directly to governance feature folders or release paths.",
                ]
            ),
            encoding="utf-8",
        )

        target_repos = [
            {"name": "lens.core.src", "local_path": "TargetProjects/lens-dev/new-codebase/lens.core.src"},
        ]
        if mode == "ambiguous":
            target_repos.extend(
                [
                    {"name": "NextLens", "local_path": "TargetProjects/nextlens/src/NextLens"},
                    {"name": "NextLens", "local_path": "TargetProjects/nextlens/src/NextLens"},
                ]
            )

        (feature_root / "feature.yaml").write_text(
            yaml.safe_dump(
                {
                    "featureId": FEATURE_ID,
                    "docs": {"path": f"docs/nextlens/src/{FEATURE_ID}"},
                    "target_repos": target_repos,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        spec = ops.generate_nextlens_fix_spec(
            FEATURE_ID,
            base_intake(),
            bug_state={
                "status": "QuickDev",
                "namespace": "nextlens",
                "governance_repo_root": str(governance_root),
            },
            start=str(control_root),
            config_path=str(module_root / "bmadconfig.yaml"),
            governance_repo=str(governance_root),
        )

        assert spec["status"] == "blocked"
        assert spec["delegation_blocked"] is True
        assert spec["allowed_write_root"] is None
        assert spec["design_context_references"] == []
        assert spec["delegation_blockers"]
        if mode == "missing":
            assert "does not include 'NextLens'" in spec["delegation_blockers"][0]
        else:
            assert "includes multiple 'NextLens' entries" in spec["delegation_blockers"][0]


def test_fix_spec_cli_emits_same_branch_identity_and_boundary_fields():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--feature-id",
            FEATURE_ID,
            "--intake-json",
            json.dumps(base_intake()),
            "--bug-state-json",
            json.dumps(
                {
                    "status": "QuickDev",
                    "namespace": "nextlens",
                    "governance_repo_root": str(GOVERNANCE_REPO_ROOT),
                }
            ),
            "--start",
            str(CONTROL_REPO_ROOT),
            "--governance-repo",
            str(GOVERNANCE_REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["bugfix_feature_id"] == f"nextlens-bugfix-{payload['bug_slug']}"
    assert payload["bugfix_working_branch"] == f"feature/{payload['bugfix_feature_id']}"
    assert payload["allowed_write_root_display"] == r"TargetProjects\nextlens\src\NextLens"


def test_fix_spec_requires_nextlens_namespace_for_bug_state():
    ops = load_module()

    with pytest.raises(
        ValueError,
        match="NextLens fix specs require a namespaced bug state with namespace 'nextlens'",
    ):
        ops.generate_nextlens_fix_spec(
            FEATURE_ID,
            base_intake(),
            bug_state={
                "status": "QuickDev",
                "namespace": "lens-core",
                "governance_repo_root": str(GOVERNANCE_REPO_ROOT),
            },
            start=str(CONTROL_REPO_ROOT),
            governance_repo=str(GOVERNANCE_REPO_ROOT),
        )
