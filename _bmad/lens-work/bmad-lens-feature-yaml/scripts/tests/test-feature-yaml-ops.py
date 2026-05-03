#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Focused tests for feature-yaml-ops.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path(__file__).parent.parent / "feature-yaml-ops.py"


def load_ops_module():
    spec = importlib.util.spec_from_file_location("feature_yaml_ops", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def run_feature_yaml(args: list[str]) -> tuple[dict, int]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - diagnostic path
        raise AssertionError(f"Non-JSON output\nstdout={result.stdout}\nstderr={result.stderr}") from exc
    return payload, result.returncode


def write_feature(repo: Path, feature_id: str, data: dict) -> Path:
    feature_dir = repo / "features" / data["domain"] / data["service"] / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    feature_path = feature_dir / "feature.yaml"
    feature_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return feature_path


def write_feature_index(repo: Path, features: list[dict]) -> Path:
    index = repo / "feature-index.yaml"
    index.write_text(yaml.safe_dump({"features": features}, sort_keys=False), encoding="utf-8")
    return index


def base_feature(**overrides: object) -> dict:
    data = {
        "name": "Authentication",
        "featureId": "auth-login",
        "featureSlug": "login",
        "domain": "platform",
        "service": "identity",
        "phase": "finalizeplan-complete",
        "track": "express",
        "milestones": {"finalizeplan": "2026-05-01T00:00:00Z", "dev-ready": None},
        "dependencies": {"depends_on": ["oauth-provider"], "blocks": ["audit-log"]},
        "target_repos": [
            {
                "name": "lens.core.src",
                "local_path": "TargetProjects/lens-dev/new-codebase/lens.core.src",
                "default_branch": "develop",
            }
        ],
        "phase_transitions": [
            {"phase": "expressplan", "timestamp": "2026-04-30T00:00:00Z", "user": "alice"},
            {"phase": "finalizeplan-complete", "timestamp": "2026-05-01T00:00:00Z", "user": "alice"},
        ],
        "docs": {
            "path": "docs/platform/identity/auth-login",
            "governance_docs_path": "features/platform/identity/auth-login/docs",
        },
        "unknown_field": {"preserve": True},
    }
    data.update(overrides)
    return data


def test_read_returns_feature_state_contract_fields(tmp_path: Path):
    feature_path = write_feature(tmp_path, "auth-login", base_feature())

    payload, code = run_feature_yaml(["read", "--feature-path", str(feature_path)])

    assert code == 0
    assert payload["status"] == "pass"
    assert payload["identity"]["featureId"] == "auth-login"
    assert payload["identity"]["featureSlug"] == "login"
    assert payload["phase"] == "finalizeplan-complete"
    assert payload["track"] == "express"
    assert payload["docs_path"] == "docs/platform/identity/auth-login"
    assert payload["governance_docs_path"] == "features/platform/identity/auth-login/docs"
    assert payload["target_repos"][0]["name"] == "lens.core.src"
    assert payload["dependencies"]["depends_on"] == ["oauth-provider"]
    assert payload["transition_history"] == payload["phase_transitions"]


def test_validate_rejects_invalid_phase_transition(tmp_path: Path):
    feature_path = write_feature(tmp_path, "auth-login", base_feature(phase="expressplan"))

    payload, code = run_feature_yaml(["validate", "--feature-path", str(feature_path), "--to-phase", "dev"])

    assert code == 1
    assert payload["status"] == "fail"
    assert payload["error"] == "invalid_phase_transition"
    assert payload["current_phase"] == "expressplan"
    assert "expressplan-complete" in payload["allowed_next_phases"]


def test_validate_warns_when_implementation_feature_has_no_target_repos(tmp_path: Path):
    feature_path = write_feature(tmp_path, "auth-login", base_feature(target_repos=[]))

    payload, code = run_feature_yaml(["validate", "--feature-path", str(feature_path), "--to-phase", "dev"])

    assert code == 0
    assert payload["status"] == "warning"
    assert payload["warnings"] == [
        {
            "code": "missing_target_repos",
            "message": "Implementation-impacting feature has no target_repos entries.",
        }
    ]


def test_update_surgically_changes_requested_fields_and_preserves_unknowns(tmp_path: Path):
    feature_path = write_feature(tmp_path, "auth-login", base_feature())
    target_repos = [
        {
            "name": "new.repo",
            "local_path": "TargetProjects/example/new.repo",
            "default_branch": "main",
        }
    ]
    milestones = {"finalizeplan": "2026-05-01T00:00:00Z", "dev-ready": "2026-05-02T00:00:00Z"}

    payload, code = run_feature_yaml(
        [
            "update",
            "--feature-path",
            str(feature_path),
            "--phase",
            "dev",
            "--docs-path",
            "docs/new/path",
            "--governance-docs-path",
            "features/new/path/docs",
            "--target-repos",
            json.dumps(target_repos),
            "--milestones",
            json.dumps(milestones),
        ]
    )

    assert code == 0
    assert payload["status"] == "pass"
    assert payload["changed_fields"] == [
        "phase",
        "docs.path",
        "docs.governance_docs_path",
        "target_repos",
        "milestones",
    ]

    updated = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    assert updated["phase"] == "dev"
    assert updated["docs"]["path"] == "docs/new/path"
    assert updated["docs"]["governance_docs_path"] == "features/new/path/docs"
    assert updated["target_repos"] == target_repos
    assert updated["milestones"] == milestones
    assert updated["unknown_field"] == {"preserve": True}
    assert updated["dependencies"] == base_feature()["dependencies"]
    assert updated["phase_transitions"] == base_feature()["phase_transitions"]


def test_sync_feature_index_updates_stale_entry(tmp_path: Path):
    feature_path = write_feature(tmp_path, "auth-login", base_feature(phase="expressplan-complete", status="active"))
    write_feature_index(
        tmp_path,
        [
            {
                "id": "auth-login",
                "domain": "platform",
                "service": "identity",
                "phase": "expressplan",
                "status": "active",
                "track": "express",
            }
        ],
    )

    payload, code = run_feature_yaml(
        [
            "sync-feature-index",
            "--feature-path",
            str(feature_path),
            "--governance-repo",
            str(tmp_path),
        ]
    )

    assert code == 0
    assert payload["status"] == "pass"
    assert payload["updated_existing_entry"] is True

    index_data = yaml.safe_load((tmp_path / "feature-index.yaml").read_text(encoding="utf-8"))
    entry = index_data["features"][0]
    assert entry["phase"] == "expressplan-complete"


def test_update_phase_auto_syncs_feature_index(tmp_path: Path):
    feature_path = write_feature(tmp_path, "auth-login", base_feature(phase="finalizeplan-complete", status="active"))
    write_feature_index(
        tmp_path,
        [
            {
                "id": "auth-login",
                "domain": "platform",
                "service": "identity",
                "phase": "finalizeplan-complete",
                "status": "active",
                "track": "express",
            }
        ],
    )

    payload, code = run_feature_yaml(
        [
            "update",
            "--feature-path",
            str(feature_path),
            "--governance-repo",
            str(tmp_path),
            "--phase",
            "dev-ready",
        ]
    )

    assert code == 0
    assert payload["status"] == "pass"
    assert payload["feature_index_sync"] is not None

    index_data = yaml.safe_load((tmp_path / "feature-index.yaml").read_text(encoding="utf-8"))
    entry = index_data["features"][0]
    assert entry["phase"] == "dev-ready"


def test_dirty_state_handler_pulls_stages_commits_pushes_and_reports_sha(tmp_path: Path):
    ops = load_ops_module()
    commands: list[list[str]] = []
    sha = "abc123def456"

    def fake_runner(command, capture_output=True, text=True):
        commands.append(command)
        git_args = command[3:]
        if git_args[:2] == ["status", "--porcelain"]:
            return subprocess.CompletedProcess(command, 0, stdout=" M features/x/feature.yaml\n", stderr="")
        if git_args == ["diff", "--cached", "--quiet"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
        if git_args == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, stdout=f"{sha}\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    payload = ops.handle_dirty_state(
        tmp_path,
        ["features/x/feature.yaml"],
        "[STATE] auth-login - persist feature yaml state",
        runner=fake_runner,
    )

    assert payload["status"] == "pass"
    assert payload["dirty"] is True
    assert payload["committed"] is True
    assert payload["sha"] == sha
    assert [command[3:] for command in commands] == [
        ["status", "--porcelain", "--", "features/x/feature.yaml"],
        ["pull", "--rebase", "--autostash"],
        ["add", "--", "features/x/feature.yaml"],
        ["diff", "--cached", "--quiet"],
        ["commit", "-m", "[STATE] auth-login - persist feature yaml state"],
        ["rev-parse", "HEAD"],
        ["push"],
    ]