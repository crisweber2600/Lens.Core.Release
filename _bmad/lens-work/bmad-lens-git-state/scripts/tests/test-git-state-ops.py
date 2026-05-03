#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Focused tests for git-state-ops.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


SCRIPT = Path(__file__).parent.parent / "git-state-ops.py"


def load_ops_module():
    spec = importlib.util.spec_from_file_location("git_state_ops", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


ops = load_ops_module()


def run_git_state(args: list[str]) -> tuple[dict, int]:
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


def run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    subprocess.run(["git", "-c", "init.defaultBranch=main", "init", str(repo)], check=True, capture_output=True)
    run_git(repo, ["config", "user.email", "test@example.com"])
    run_git(repo, ["config", "user.name", "Test User"])
    (repo / "README.md").write_text("# Test\n", encoding="utf-8")
    run_git(repo, ["add", "."])
    run_git(repo, ["commit", "-m", "init"])
    return repo


def make_branch(repo: Path, branch: str) -> None:
    run_git(repo, ["branch", branch])


def write_feature_index(governance_repo: Path, features: list[dict]) -> None:
    governance_repo.mkdir(parents=True, exist_ok=True)
    (governance_repo / "feature-index.yaml").write_text(
        yaml.safe_dump({"features": features}, sort_keys=False),
        encoding="utf-8",
    )


def write_feature_yaml(
    governance_repo: Path,
    feature_id: str,
    *,
    domain: str = "platform",
    service: str = "identity",
    phase: str = "preplan",
    track: str = "full",
) -> Path:
    feature_dir = governance_repo / "features" / domain / service / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    feature_path = feature_dir / "feature.yaml"
    feature_path.write_text(
        yaml.safe_dump(
            {
                "featureId": feature_id,
                "domain": domain,
                "service": service,
                "phase": phase,
                "track": track,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return feature_path


def test_branch_state_reports_feature_topology(tmp_path: Path):
    repo = init_repo(tmp_path)
    for branch in (
        "alpha",
        "alpha-plan",
        "alpha-dev",
        "beta-dev-alice",
        "gamma-plan",
        "feature/dogfood",
        "develop",
    ):
        make_branch(repo, branch)

    payload, code = run_git_state(["branch-state", "--repo", str(repo)])

    assert code == 0
    assert payload["status"] == "pass"
    state = payload["branch_state"]
    assert state["current_branch"] == "main"
    assert "alpha" in state["local_branches"]
    assert state["features_with_plan_branches"] == ["alpha", "gamma"]
    assert state["features_with_dev_branches"] == ["alpha", "beta"]

    by_feature = {item["feature_id"]: item for item in state["feature_branches"]}
    assert by_feature["alpha"]["has_base_branch"] is True
    assert by_feature["alpha"]["has_plan_branch"] is True
    assert by_feature["alpha"]["has_dev_branch"] is True
    assert by_feature["beta"]["dev_branches"] == ["beta-dev-alice"]
    assert "feature/dogfood" not in [entry["name"] for entry in state["all_feature_branches"]]


def test_active_features_reports_phase_from_feature_yaml(tmp_path: Path):
    governance_repo = tmp_path / "governance"
    write_feature_index(
        governance_repo,
        [
            {
                "id": "alpha",
                "featureId": "alpha",
                "domain": "platform",
                "service": "identity",
                "status": "preplan",
                "track": "full",
            },
            {
                "id": "archived-feature",
                "featureId": "archived-feature",
                "domain": "platform",
                "service": "identity",
                "status": "archived",
                "track": "full",
            },
        ],
    )
    write_feature_yaml(governance_repo, "alpha", phase="dev", track="express")

    payload, code = run_git_state(["active-features", "--governance-repo", str(governance_repo)])

    assert code == 0
    assert payload["status"] == "pass"
    assert [feature["feature_id"] for feature in payload["active_features"]] == ["alpha"]
    assert payload["active_features"][0]["phase"] == "dev"
    assert payload["active_features"][0]["phase_source"] == "feature.yaml"
    assert payload["active_features"][0]["track"] == "express"


def test_discrepancies_report_specific_phase_vs_branch_mismatches(tmp_path: Path):
    repo = init_repo(tmp_path)
    make_branch(repo, "alpha")
    make_branch(repo, "alpha-plan")
    make_branch(repo, "beta")

    governance_repo = tmp_path / "governance"
    write_feature_index(
        governance_repo,
        [
            {"id": "alpha", "featureId": "alpha", "domain": "platform", "service": "identity", "status": "dev"},
            {"id": "beta", "featureId": "beta", "domain": "platform", "service": "identity", "status": "preplan"},
        ],
    )
    write_feature_yaml(governance_repo, "alpha", phase="dev")
    write_feature_yaml(governance_repo, "beta", phase="preplan")

    payload, code = run_git_state(["discrepancies", "--repo", str(repo), "--governance-repo", str(governance_repo)])

    assert code == 0
    assert payload["status"] == "pass"
    mismatches = payload["discrepancies"]
    alpha_dev = next(
        item
        for item in mismatches
        if item["feature_id"] == "alpha" and item["branch_state_field"] == "branch_state.dev_branches"
    )
    assert alpha_dev["field"] == "feature.yaml.phase"
    assert alpha_dev["yaml_value"] == "dev"
    assert alpha_dev["branch_state_value"] == []
    assert "alpha-dev" in alpha_dev["expected_state"]

    alpha_plan = next(
        item
        for item in mismatches
        if item["feature_id"] == "alpha" and item["branch_state_field"] == "branch_state.plan_branches"
    )
    assert alpha_plan["branch_state_value"] == ["alpha-plan"]

    beta_plan = next(
        item
        for item in mismatches
        if item["feature_id"] == "beta" and item["branch_state_field"] == "branch_state.plan_branches"
    )
    assert beta_plan["yaml_value"] == "preplan"
    assert beta_plan["branch_state_value"] == []


def test_read_only_git_allowlist_rejects_write_operations():
    with pytest.raises(ops.GitStateError) as exc_info:
        ops.assert_git_args_read_only(["checkout", "main"])

    assert exc_info.value.error == "git_write_rejected"


def test_collect_branch_state_uses_only_allowlisted_read_queries(tmp_path: Path):
    repo = init_repo(tmp_path)
    commands: list[list[str]] = []

    def recording_runner(command, **kwargs):
        commands.append(command)
        return subprocess.run(command, **kwargs)

    state = ops.collect_branch_state(repo, runner=recording_runner)

    assert state["current_branch"] == "main"
    assert commands
    for command in commands:
        assert command[0] == "git"
        ops.assert_git_args_read_only(command[1:])
        assert command[1] not in ops.MUTATING_GIT_SUBCOMMANDS


def test_discrepancies_detect_dev_branch_without_dev_phase(tmp_path: Path):
    """Test that discrepancies are detected when dev branch exists but phase ≠ 'dev'."""
    repo = init_repo(tmp_path)
    make_branch(repo, "beta")
    make_branch(repo, "beta-dev")

    governance_repo = tmp_path / "governance"
    write_feature_index(
        governance_repo,
        [
            {"id": "beta", "featureId": "beta", "domain": "platform", "service": "identity", "status": "preplan"},
        ],
    )
    write_feature_yaml(governance_repo, "beta", phase="preplan")

    payload, code = run_git_state(["discrepancies", "--repo", str(repo), "--governance-repo", str(governance_repo)])

    assert code == 0
    assert payload["status"] == "pass"
    discrepancies = payload["discrepancies"]
    
    # Should find a discrepancy for dev branch existing but phase != dev
    inverse_mismatch = next(
        (
            item
            for item in discrepancies
            if item["feature_id"] == "beta"
            and item["branch_state_field"] == "branch_state.dev_branches"
            and item["branch_state_value"]  # non-empty dev_branches
        ),
        None,
    )
    assert inverse_mismatch is not None
    assert inverse_mismatch["field"] == "feature.yaml.phase"
    assert inverse_mismatch["yaml_value"] == "preplan"
    assert inverse_mismatch["branch_state_value"] == ["beta-dev"]
    assert "beta-dev" in inverse_mismatch["message"]


def test_run_git_read_only_timeout_handling(tmp_path: Path):
    """Test that subprocess.TimeoutExpired is caught and wrapped as GitStateError."""
    repo = init_repo(tmp_path)

    def slow_runner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 30)

    with pytest.raises(ops.GitStateError) as exc_info:
        ops.run_git_read_only(repo, ["rev-parse", "--is-inside-work-tree"], runner=slow_runner)

    assert exc_info.value.error == "git_timeout"
    assert "timed out" in exc_info.value.message


def test_run_git_read_only_sanitizes_stderr(tmp_path: Path):
    """Test that error messages do not leak raw stderr output."""
    repo = init_repo(tmp_path)

    def failing_runner(command, **kwargs):
        # Simulate a git failure with stderr output
        result = subprocess.CompletedProcess(
            command,
            returncode=1,
            stdout="",
            stderr="fatal: some internal git error message\n",
        )
        return result

    with pytest.raises(ops.GitStateError) as exc_info:
        ops.run_git_read_only(repo, ["rev-parse", "--is-inside-work-tree"], runner=failing_runner)

    assert exc_info.value.error == "git_query_failed"
    # Ensure stderr is NOT exposed in the message
    assert "fatal:" not in exc_info.value.message
    # Should contain only the generic error message
    assert "git rev-parse --is-inside-work-tree failed" in exc_info.value.message


def test_feature_state_combines_reports(tmp_path: Path):
    """Test that feature-state combines branch_state, active_features, and discrepancies."""
    repo = init_repo(tmp_path)
    make_branch(repo, "alpha")
    make_branch(repo, "alpha-plan")

    governance_repo = tmp_path / "governance"
    write_feature_index(
        governance_repo,
        [
            {"id": "alpha", "featureId": "alpha", "domain": "platform", "service": "identity", "status": "preplan"},
        ],
    )
    write_feature_yaml(governance_repo, "alpha", phase="dev")

    payload, code = run_git_state(["feature-state", "--repo", str(repo), "--governance-repo", str(governance_repo)])

    assert code == 0
    assert payload["status"] == "pass"
    assert payload["read_only"] is True
    assert "branch_state" in payload
    assert "active_features" in payload
    assert "discrepancies" in payload
    assert payload["branch_state"]["current_branch"] == "main"
    assert len(payload["active_features"]) == 1
    assert payload["active_features"][0]["feature_id"] == "alpha"
    assert len(payload["discrepancies"]) > 0  # Should have dev branch without dev phase discrepancy


def test_read_yaml_mapping_rejects_oversized_files(tmp_path: Path):
    """Test that oversized YAML files are rejected."""
    large_yaml = tmp_path / "large.yaml"
    # Create a file that exceeds 10MB
    large_content = "x: " + ("y" * (10_000_001)) + "\n"
    large_yaml.write_text(large_content, encoding="utf-8")

    with pytest.raises(ops.GitStateError) as exc_info:
        ops.read_yaml_mapping(large_yaml)

    assert exc_info.value.error == "yaml_too_large"
    assert "10000000" in exc_info.value.message