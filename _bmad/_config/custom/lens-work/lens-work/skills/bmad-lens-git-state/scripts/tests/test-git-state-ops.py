#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML>=6.0", "pytest>=8.0"]
# ///
"""Tests for git-state-ops.py — uses real temporary git repos."""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest
import yaml

# Ensure the script under test is importable (hyphenated filename requires importlib)
import importlib.util
_script_path = Path(__file__).parent.parent / "git-state-ops.py"
_spec = importlib.util.spec_from_file_location("git_state_ops", _script_path)
ops = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ops)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def repo(tmp_path):
    """Create a minimal git repo with an initial commit on a 'main' branch."""
    subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "init", str(tmp_path)],
        check=True, capture_output=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test User"], check=True, capture_output=True)
    # Initial commit on main
    readme = tmp_path / "README.md"
    readme.write_text("# Test repo\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


def make_branch(repo_path: Path, branch: str, from_branch: str = None):
    """Create a git branch from an existing branch, then return to the original branch."""
    # Get current branch before creating the new one
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True
    )
    original = result.stdout.strip() or "main"
    if from_branch is None:
        from_branch = original
    subprocess.run(
        ["git", "-C", str(repo_path), "checkout", "-b", branch, from_branch],
        check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "checkout", original],
        check=True, capture_output=True
    )


def write_feature_yaml(repo_path: Path, feature_id: str, domain: str = "platform", service: str = "api",
                        phase: str = "dev", track: str = "full", status: str = "active",
                        extra: dict = None):
    """Write a feature.yaml for a feature under features/{domain}/{service}/{featureId}/."""
    feat_dir = repo_path / "features" / domain / service / feature_id
    feat_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "feature_id": feature_id,
        "domain": domain,
        "service": service,
        "phase": phase,
        "track": track,
        "status": status,
    }
    if extra:
        data.update(extra)
    (feat_dir / "feature.yaml").write_text(yaml.dump(data))


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------

class TestGitHelpers:
    def test_branch_exists_true(self, repo):
        make_branch(repo, "my-feature")
        assert ops.branch_exists(str(repo), "my-feature") is True

    def test_branch_exists_false(self, repo):
        assert ops.branch_exists(str(repo), "nonexistent") is False

    def test_list_branches_matching_empty(self, repo):
        results = ops.list_branches_matching(str(repo), "xyz-*")
        assert results == []

    def test_list_branches_matching_finds_branches(self, repo):
        make_branch(repo, "feat-a")
        make_branch(repo, "feat-b")
        results = ops.list_branches_matching(str(repo), "feat-*")
        names = [r["branch"] for r in results]
        assert "feat-a" in names
        assert "feat-b" in names

    def test_list_branches_matching_returns_sha(self, repo):
        make_branch(repo, "sha-test")
        results = ops.list_branches_matching(str(repo), "sha-test")
        assert results[0]["sha"]  # non-empty SHA

    def test_branch_log_returns_entries(self, repo):
        log = ops.branch_log(str(repo), "main", count=5)
        assert isinstance(log, list)
        assert len(log) >= 1

    def test_branch_log_nonexistent_returns_empty(self, repo):
        log = ops.branch_log(str(repo), "ghost-branch", count=5)
        assert log == []

    def test_ahead_count_same_branch_is_zero(self, repo):
        rc, out, _ = ops.git(str(repo), "rev-parse", "--abbrev-ref", "HEAD")
        default_branch = out.strip()
        count = ops.ahead_count(str(repo), default_branch, default_branch)
        assert count == 0

    def test_ahead_count_with_commit(self, repo):
        rc, out, _ = ops.git(str(repo), "rev-parse", "--abbrev-ref", "HEAD")
        default_branch = out.strip()
        # Create a branch with one extra commit
        subprocess.run(["git", "-C", str(repo), "checkout", "-b", "ahead-test"], check=True, capture_output=True)
        (repo / "extra.md").write_text("extra")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "extra commit"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "checkout", default_branch], check=True, capture_output=True)
        count = ops.ahead_count(str(repo), default_branch, "ahead-test")
        assert count == 1


# ---------------------------------------------------------------------------
# feature YAML helpers
# ---------------------------------------------------------------------------

class TestFeatureYamlHelpers:
    def test_find_feature_yaml_finds_nested(self, repo):
        write_feature_yaml(repo, "payments-auth")
        path = ops.find_feature_yaml(str(repo), "payments-auth")
        assert path is not None
        assert path.name == "feature.yaml"

    def test_find_feature_yaml_returns_none_for_unknown(self, repo):
        path = ops.find_feature_yaml(str(repo), "nonexistent-feature")
        assert path is None

    def test_load_feature_yaml_valid(self, repo):
        write_feature_yaml(repo, "test-feat")
        path = ops.find_feature_yaml(str(repo), "test-feat")
        data, err = ops.load_feature_yaml(path)
        assert err is None
        assert data["feature_id"] == "test-feat"

    def test_load_feature_yaml_invalid_yaml(self, tmp_path):
        bad_file = tmp_path / "feature.yaml"
        bad_file.write_text("key: [invalid: yaml: ]\n  - broken")
        data, err = ops.load_feature_yaml(bad_file)
        assert err is not None
        assert data is None

    def test_load_feature_yaml_empty_file(self, tmp_path):
        empty_file = tmp_path / "feature.yaml"
        empty_file.write_text("")
        data, err = ops.load_feature_yaml(empty_file)
        assert err is not None  # None parsed as non-dict

    def test_load_feature_yaml_missing_file(self, tmp_path):
        missing = tmp_path / "feature.yaml"
        data, err = ops.load_feature_yaml(missing)
        assert err is not None
        assert data is None


# ---------------------------------------------------------------------------
# cmd_feature_state
# ---------------------------------------------------------------------------

class TestCmdFeatureState:
    def _args(self, repo, feature_id):
        class A:
            include_remote = False
        a = A()
        a.governance_repo = str(repo)
        a.feature_id = feature_id
        return a

    def test_no_yaml(self, repo):
        result = ops.cmd_feature_state(self._args(repo, "ghost-feat"))
        assert result["yaml_on_main"] is False
        assert any("not found" in e for e in result["errors"])

    def test_yaml_present_on_main(self, repo):
        write_feature_yaml(repo, "my-feat", phase="preplan")
        result = ops.cmd_feature_state(self._args(repo, "my-feat"))
        assert result["phase"] == "preplan"
        assert result["yaml_on_main"] is True
        assert result["errors"] == []

    def test_yaml_fields_populated(self, repo):
        write_feature_yaml(repo, "my-feat", phase="dev", track="full", status="active")
        result = ops.cmd_feature_state(self._args(repo, "my-feat"))
        assert result["phase"] == "dev"
        assert result["track"] == "full"
        assert result["status"] == "active"
        assert result["yaml_on_main"] is True

    def test_no_discrepancy_normal_feature(self, repo):
        write_feature_yaml(repo, "healthy-feat", phase="dev", status="active")
        result = ops.cmd_feature_state(self._args(repo, "healthy-feat"))
        assert result["discrepancies"] == []

    def test_yaml_path_is_relative(self, repo):
        write_feature_yaml(repo, "path-feat")
        result = ops.cmd_feature_state(self._args(repo, "path-feat"))
        assert result["yaml_path"] is not None
        assert not result["yaml_path"].startswith("/")  # relative, not absolute


# ---------------------------------------------------------------------------
# cmd_branches
# ---------------------------------------------------------------------------

class TestCmdBranches:
    def _args(self, repo, feature_id, query, branch=None):
        class A:
            include_remote = False
        a = A()
        a.governance_repo = str(repo)
        a.feature_id = feature_id
        a.query = query
        a.branch = branch
        return a

    def test_exists_true(self, repo):
        make_branch(repo, "br-feat")
        result = ops.cmd_branches(self._args(repo, "br-feat", "exists", branch="br-feat"))
        assert result["exists"] is True

    def test_exists_false(self, repo):
        result = ops.cmd_branches(self._args(repo, "ghost-feat", "exists", branch="ghost-feat"))
        assert result["exists"] is False

    def test_exists_defaults_to_base_branch(self, repo):
        make_branch(repo, "br-default")
        result = ops.cmd_branches(self._args(repo, "br-default", "exists"))
        assert result["exists"] is True

    def test_list_returns_branches(self, repo):
        make_branch(repo, "list-feat")
        make_branch(repo, "list-feat-plan")
        result = ops.cmd_branches(self._args(repo, "list-feat", "list"))
        names = [b["branch"] for b in result["branches"]]
        assert "list-feat" in names
        assert "list-feat-plan" in names

    def test_list_empty_for_nonexistent(self, repo):
        result = ops.cmd_branches(self._args(repo, "no-such-feat", "list"))
        assert result["count"] == 0
        assert result["branches"] == []

    def test_info_returns_sha(self, repo):
        make_branch(repo, "info-feat")
        result = ops.cmd_branches(self._args(repo, "info-feat", "info", branch="info-feat"))
        assert result["exists"] is True
        assert result["sha"]

    def test_info_nonexistent_branch(self, repo):
        result = ops.cmd_branches(self._args(repo, "gone-feat", "info", branch="gone-feat"))
        assert result["exists"] is False

    def test_info_includes_recent_log(self, repo):
        make_branch(repo, "log-feat")
        result = ops.cmd_branches(self._args(repo, "log-feat", "info", branch="log-feat"))
        assert isinstance(result["recent_log"], list)
        assert len(result["recent_log"]) >= 1

    def test_info_ahead_of_base_is_none_for_base(self, repo):
        make_branch(repo, "base-only")
        result = ops.cmd_branches(self._args(repo, "base-only", "info", branch="base-only"))
        # Querying the base branch itself — ahead count is not applicable
        assert result["commits_ahead_of_base"] is None

    def test_invalid_query_returns_error(self, repo):
        result = ops.cmd_branches(self._args(repo, "any", "badquery"))
        assert "error" in result


# ---------------------------------------------------------------------------
# cmd_active_features
# ---------------------------------------------------------------------------

class TestCmdActiveFeatures:
    def _args(self, repo, domain=None, phase=None, track=None):
        class A:
            pass
        a = A()
        a.governance_repo = str(repo)
        a.domain = domain
        a.phase = phase
        a.track = track
        a.status = None
        a.limit = None
        a.include_remote = False
        return a

    def test_empty_repo_returns_empty(self, repo):
        result = ops.cmd_active_features(self._args(repo))
        assert result["total_active"] == 0
        assert result["features"] == []

    def test_finds_active_feature(self, repo):
        write_feature_yaml(repo, "active-feat", phase="dev", status="active")
        result = ops.cmd_active_features(self._args(repo))
        ids = [f["feature_id"] for f in result["features"]]
        assert "active-feat" in ids

    def test_filters_by_domain(self, repo):
        write_feature_yaml(repo, "feat-a", domain="billing", service="api", phase="dev", status="active")
        write_feature_yaml(repo, "feat-b", domain="shipping", service="api", phase="dev", status="active")
        result = ops.cmd_active_features(self._args(repo, domain="billing"))
        ids = [f["feature_id"] for f in result["features"]]
        assert "feat-a" in ids
        assert "feat-b" not in ids

    def test_filters_by_phase(self, repo):
        write_feature_yaml(repo, "in-dev", phase="dev", status="active")
        write_feature_yaml(repo, "in-review", phase="review", status="active")
        result = ops.cmd_active_features(self._args(repo, phase="dev"))
        ids = [f["feature_id"] for f in result["features"]]
        assert "in-dev" in ids
        assert "in-review" not in ids

    def test_filters_by_track(self, repo):
        write_feature_yaml(repo, "hotfix-1", track="hotfix", phase="dev", status="active")
        write_feature_yaml(repo, "full-1", track="full", phase="dev", status="active")
        result = ops.cmd_active_features(self._args(repo, track="hotfix"))
        ids = [f["feature_id"] for f in result["features"]]
        assert "hotfix-1" in ids
        assert "full-1" not in ids

    def test_ghost_yaml_for_malformed_yaml(self, repo):
        bad_dir = repo / "features" / "platform" / "api" / "bad-feat"
        bad_dir.mkdir(parents=True, exist_ok=True)
        (bad_dir / "feature.yaml").write_text(": invalid: yaml: [")
        result = ops.cmd_active_features(self._args(repo))
        assert len(result["ghost_yamls"]) >= 1

    def test_multiple_features_all_returned(self, repo):
        for i in range(3):
            fid = f"feat-{i}"
            write_feature_yaml(repo, fid, service=f"svc{i}", phase="dev", status="active")
        result = ops.cmd_active_features(self._args(repo))
        assert result["total_active"] == 3

    def test_complete_feature_excluded_by_default(self, repo):
        write_feature_yaml(repo, "finished-feat", phase="done", status="complete")
        result = ops.cmd_active_features(self._args(repo))
        ids = [f["feature_id"] for f in result["features"]]
        assert "finished-feat" not in ids

    def test_paused_feature_included(self, repo):
        write_feature_yaml(repo, "paused-feat", phase="dev", status="paused")
        result = ops.cmd_active_features(self._args(repo))
        ids = [f["feature_id"] for f in result["features"]]
        assert "paused-feat" in ids

    def test_result_includes_yaml_path(self, repo):
        write_feature_yaml(repo, "path-check-feat", phase="dev", status="active")
        result = ops.cmd_active_features(self._args(repo))
        feat = next((f for f in result["features"] if f["feature_id"] == "path-check-feat"), None)
        assert feat is not None
        assert feat["yaml_path"].endswith("feature.yaml")
        assert not feat["yaml_path"].startswith("/")


# ---------------------------------------------------------------------------
# New behavior tests — quality fix coverage
# ---------------------------------------------------------------------------

class TestGitVersion:
    def test_version_check_passes_on_current_git(self):
        err = ops.check_git_version()
        assert err is None, f"Expected None but got: {err}"


class TestGetAllLocalBranches:
    def test_returns_main(self, repo):
        branches = ops.get_all_local_branches(str(repo))
        assert "main" in branches

    def test_returns_created_branch(self, repo):
        make_branch(repo, "new-branch")
        branches = ops.get_all_local_branches(str(repo))
        assert "new-branch" in branches

    def test_empty_on_invalid_repo(self, tmp_path):
        branches = ops.get_all_local_branches(str(tmp_path))
        assert branches == set()


class TestFeatureStateSummaryField:
    def _args(self, repo, feature_id):
        class A:
            include_remote = False
        a = A()
        a.governance_repo = str(repo)
        a.feature_id = feature_id
        return a

    def test_summary_present_in_output(self, repo):
        write_feature_yaml(repo, "summ-feat", phase="dev", status="active")
        result = ops.cmd_feature_state(self._args(repo, "summ-feat"))
        assert "summary" in result
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    def test_summary_ok_when_healthy(self, repo):
        write_feature_yaml(repo, "ok-feat", phase="dev", status="active")
        result = ops.cmd_feature_state(self._args(repo, "ok-feat"))
        assert result["discrepancies"] == []
        assert "WARNING" not in result["summary"]
        assert "no discrepancies" in result["summary"]

    def test_summary_contains_error_when_yaml_missing(self, repo):
        result = ops.cmd_feature_state(self._args(repo, "no-yaml"))
        assert "ERROR" in result["summary"]


class TestExitCodeDiscrepancy:
    """Exit code behavior for feature-state (HO-2)."""

    def test_exit_0_when_clean(self, repo):
        import subprocess as sp
        script = str(Path(__file__).parent.parent / "git-state-ops.py")
        write_feature_yaml(repo, "clean-exit", phase="dev", status="active")
        proc = sp.run(
            ["uv", "run", "--script", script, "feature-state",
             "--governance-repo", str(repo), "--feature-id", "clean-exit"],
            capture_output=True, text=True
        )
        assert proc.returncode == 0


class TestBranchListGlobFix:
    """MO-1: list query should not match features with a common prefix."""
    def _args(self, repo, feature_id, query, branch=None):
        class A:
            include_remote = False
        a = A()
        a.governance_repo = str(repo)
        a.feature_id = feature_id
        a.query = query
        a.branch = branch
        return a

    def test_list_does_not_match_longer_prefix(self, repo):
        # 'auth' should NOT match 'authorization' branch
        make_branch(repo, "auth")
        make_branch(repo, "authorization")
        result = ops.cmd_branches(self._args(repo, "auth", "list"))
        names = [b["branch"] for b in result["branches"]]
        assert "auth" in names
        assert "authorization" not in names

    def test_list_matches_exact_and_suffixed(self, repo):
        make_branch(repo, "auth")
        make_branch(repo, "auth-plan")
        make_branch(repo, "auth-dev-alice")
        result = ops.cmd_branches(self._args(repo, "auth", "list"))
        names = [b["branch"] for b in result["branches"]]
        assert "auth" in names
        assert "auth-plan" in names
        assert "auth-dev-alice" in names


class TestActiveFeatureStatusFilter:
    """MO-2: --status filter on active-features."""
    def _args(self, repo, status=None, domain=None, phase=None, track=None):
        class A:
            pass
        a = A()
        a.governance_repo = str(repo)
        a.domain = domain
        a.phase = phase
        a.track = track
        a.status = status
        a.limit = None
        a.include_remote = False
        return a

    def test_filter_active_only(self, repo):
        write_feature_yaml(repo, "active-s", phase="dev", status="active")
        write_feature_yaml(repo, "paused-s", phase="dev", status="paused")
        result = ops.cmd_active_features(self._args(repo, status="active"))
        ids = [f["feature_id"] for f in result["features"]]
        assert "active-s" in ids
        assert "paused-s" not in ids

    def test_filter_paused_only(self, repo):
        write_feature_yaml(repo, "active-t", phase="dev", status="active")
        write_feature_yaml(repo, "paused-t", phase="dev", status="paused")
        result = ops.cmd_active_features(self._args(repo, status="paused"))
        ids = [f["feature_id"] for f in result["features"]]
        assert "paused-t" in ids
        assert "active-t" not in ids


class TestActiveFeatureLimitFlag:
    """HO-3: --limit flag caps active-features results."""
    def _args(self, repo, limit=None):
        class A:
            pass
        a = A()
        a.governance_repo = str(repo)
        a.domain = None
        a.phase = None
        a.track = None
        a.status = None
        a.limit = limit
        a.include_remote = False
        return a

    def test_limit_caps_results(self, repo):
        for i in range(5):
            fid = f"lim-feat-{i}"
            write_feature_yaml(repo, fid, service=f"s{i}", phase="dev", status="active")
        result = ops.cmd_active_features(self._args(repo, limit=3))
        assert len(result["features"]) <= 3
        assert result["limited"] is True

    def test_no_limit_returns_all(self, repo):
        for i in range(3):
            fid = f"nolim-feat-{i}"
            write_feature_yaml(repo, fid, service=f"s{i}", phase="dev", status="active")
        result = ops.cmd_active_features(self._args(repo, limit=None))
        assert result["total_active"] == 3
        assert result["limited"] is False


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
