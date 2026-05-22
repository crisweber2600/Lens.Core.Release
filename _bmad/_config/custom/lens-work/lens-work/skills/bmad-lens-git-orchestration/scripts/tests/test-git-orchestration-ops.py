#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML>=6.0", "pytest>=8.0"]
# ///
"""Tests for git-orchestration-ops.py — uses real temporary git repos."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# Ensure the script under test is importable (hyphenated filename requires importlib)
_script_path = Path(__file__).parent.parent / "git-orchestration-ops.py"
_spec = importlib.util.spec_from_file_location("git_orchestration_ops", _script_path)
ops = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ops)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def repo(tmp_path):
    """Minimal git repo with initial commit on main, configured with a fake remote."""
    subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "init", str(tmp_path)],
        check=True, capture_output=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test User"], check=True, capture_output=True)
    readme = tmp_path / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


@pytest.fixture()
def repo_pair(tmp_path):
    """Two repos: 'remote' (bare) and 'local' (cloned from remote). Simulates push/pull."""
    return init_repo_pair(tmp_path)


def init_repo_pair(tmp_path: Path, default_branch: str = "main"):
    """Create a local clone paired with a bare remote using the requested default branch."""
    remote_path = tmp_path / "remote.git"
    local_path = tmp_path / "local"
    # Create bare remote
    subprocess.run(
        ["git", "-c", f"init.defaultBranch={default_branch}", "init", "--bare", str(remote_path)],
        check=True, capture_output=True
    )
    # Clone from remote
    subprocess.run(["git", "clone", str(remote_path), str(local_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(local_path), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(local_path), "config", "user.name", "Test User"], check=True, capture_output=True)
    # Initial commit
    readme = local_path / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(["git", "-C", str(local_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(local_path), "commit", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(local_path), "push", "-u", "origin", default_branch], check=True, capture_output=True)
    return local_path, remote_path


def write_feature_yaml(repo_path: Path, feature_id: str, *, domain: str = "platform",
                       service: str = "api", phase: str = "preplan", status: str = "active") -> Path:
    """Write a feature.yaml into features/{domain}/{service}/{feature_id}/feature.yaml."""
    feat_dir = repo_path / "features" / domain / service / feature_id
    feat_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = feat_dir / "feature.yaml"
    yaml_path.write_text(yaml.dump({
        "featureId": feature_id,
        "feature_id": feature_id,
        "domain": domain,
        "service": service,
        "phase": phase,
        "status": status,
        "docs": {
            "path": f"docs/{domain}/{service}/{feature_id}",
            "governance_docs_path": f"features/{domain}/{service}/{feature_id}/docs",
        },
    }))
    return yaml_path


def make_branch(repo_path: Path, branch: str) -> None:
    """Create a local branch (no remote needed)."""
    current = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(["git", "-C", str(repo_path), "checkout", "-b", branch], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_path), "checkout", current], check=True, capture_output=True)


def _no_args(**kwargs):
    """Build a simple namespace object."""
    class A:
        dry_run = False
        default_branch = None
    a = A()
    for k, v in kwargs.items():
        setattr(a, k, v)
    return a


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestValidateSlug:
    def test_valid_slug(self):
        assert ops.validate_slug("payments-auth-oauth") is None

    def test_single_char(self):
        assert ops.validate_slug("a") is None

    def test_leading_hyphen(self):
        assert ops.validate_slug("-bad") is not None

    def test_trailing_hyphen(self):
        assert ops.validate_slug("bad-") is not None

    def test_uppercase(self):
        assert ops.validate_slug("BadSlug") is not None

    def test_slash(self):
        assert ops.validate_slug("feat/bad") is not None

    def test_empty(self):
        assert ops.validate_slug("") is not None


class TestGitVersion:
    def test_passes_on_current_git(self):
        assert ops.check_git_version() is None


class TestCurrentBranch:
    def test_returns_main(self, repo):
        assert ops.current_branch(str(repo)) == "main"


class TestBranchExists:
    def test_main_exists(self, repo):
        assert ops.branch_exists(str(repo), "main") is True

    def test_missing_branch(self, repo):
        assert ops.branch_exists(str(repo), "no-such") is False

    def test_created_branch_exists(self, repo):
        make_branch(repo, "test-feat")
        assert ops.branch_exists(str(repo), "test-feat") is True


class TestVerifyClean:
    def test_clean_repo(self, repo):
        assert ops.verify_clean(str(repo)) is None

    def test_dirty_repo(self, repo):
        (repo / "dirty.txt").write_text("dirty")
        assert ops.verify_clean(str(repo)) is not None


class TestFindFeatureYaml:
    def test_finds_yaml(self, repo):
        write_feature_yaml(repo, "find-me")
        result = ops.find_feature_yaml(str(repo), "find-me")
        assert result is not None
        assert result.name == "feature.yaml"

    def test_returns_none_for_unknown(self, repo):
        result = ops.find_feature_yaml(str(repo), "ghost-feat")
        assert result is None


# ---------------------------------------------------------------------------
# cmd_create_feature_branches
# ---------------------------------------------------------------------------

class TestCreateFeatureBranches:
    def _args(self, repo, feature_id, dry_run=False, default_branch=None):
        return _no_args(
            governance_repo=str(repo),
            feature_id=feature_id,
            repo=None,
            default_branch=default_branch,
            dry_run=dry_run,
        )

    def test_invalid_feature_id_rejected(self, repo):
        result, code = ops.cmd_create_feature_branches(self._args(repo, "Bad/Id"))
        assert code == 1
        assert result["error"] == "invalid_feature_id"

    def test_missing_feature_yaml_rejected(self, repo):
        result, code = ops.cmd_create_feature_branches(self._args(repo, "no-yaml-feat"))
        assert code == 1
        assert result["error"] == "feature_yaml_not_found"

    def test_branch_already_exists_rejected(self, repo):
        write_feature_yaml(repo, "existing-feat")
        make_branch(repo, "existing-feat")
        result, code = ops.cmd_create_feature_branches(self._args(repo, "existing-feat"))
        assert code == 1
        assert result["error"] == "branch_already_exists"

    def test_dry_run_no_branches_created(self, repo):
        write_feature_yaml(repo, "dry-feat")
        result, code = ops.cmd_create_feature_branches(self._args(repo, "dry-feat", dry_run=True))
        assert code == 0
        assert result["dry_run"] is True
        # Branches should NOT exist (dry run)
        assert not ops.branch_exists(str(repo), "dry-feat")
        assert not ops.branch_exists(str(repo), "dry-feat-plan")

    def test_dry_run_returns_expected_fields(self, repo):
        write_feature_yaml(repo, "dry-fields")
        result, code = ops.cmd_create_feature_branches(self._args(repo, "dry-fields", dry_run=True))
        assert code == 0
        assert result["base_branch"] == "dry-fields"
        assert result["plan_branch"] == "dry-fields-plan"
        assert result["created_from"] == "main"

    def test_creates_both_branches_with_real_remote(self, repo_pair):
        local, remote = repo_pair
        write_feature_yaml(local, "new-feat")
        result, code = ops.cmd_create_feature_branches(_no_args(
            governance_repo=str(local),
            feature_id="new-feat",
            repo=None,
            default_branch=None,
            dry_run=False,
        ))
        assert code == 0
        assert ops.branch_exists(str(local), "new-feat")
        assert ops.branch_exists(str(local), "new-feat-plan")

    def test_detects_remote_default_branch_when_not_overridden(self, tmp_path):
        local, remote = init_repo_pair(tmp_path, default_branch="develop")
        write_feature_yaml(local, "develop-feat")
        result, code = ops.cmd_create_feature_branches(_no_args(
            governance_repo=str(local),
            feature_id="develop-feat",
            repo=None,
            default_branch=None,
            dry_run=False,
        ))
        assert code == 0
        assert result["created_from"] == "develop"
        assert ops.branch_exists(str(local), "develop-feat")
        assert ops.branch_exists(str(local), "develop-feat-plan")


# ---------------------------------------------------------------------------
# cmd_commit_artifacts
# ---------------------------------------------------------------------------

class TestCommitArtifacts:
    def _args(self, repo, feature_id, files, description, phase=None, push=False, dry_run=False):
        return _no_args(
            repo=str(repo),
            governance_repo=str(repo),
            feature_id=feature_id,
            files=files,
            description=description,
            phase=phase,
            push=push,
            no_confirm=True,
            dry_run=dry_run,
        )

    def test_no_files_returns_error(self, repo):
        result, code = ops.cmd_commit_artifacts(self._args(repo, "f", [], "desc"))
        assert code == 1
        assert result["error"] == "no_files_specified"

    def test_missing_file_returns_error(self, repo):
        result, code = ops.cmd_commit_artifacts(self._args(repo, "f", ["no-such.md"], "desc"))
        assert code == 1
        assert result["error"] == "file_not_found"

    def test_commits_existing_file(self, repo):
        make_branch(repo, "commit-feat")
        subprocess.run(["git", "-C", str(repo), "checkout", "commit-feat"], check=True, capture_output=True)
        (repo / "artifact.md").write_text("content")
        result, code = ops.cmd_commit_artifacts(self._args(repo, "commit-feat", ["artifact.md"], "initial artifact", phase="preplan"))
        assert code == 0
        assert result["commit_sha"] != ""
        assert "commit-feat" in result["commit_message"]

    def test_phase_auto_resolved_from_yaml(self, repo):
        write_feature_yaml(repo, "phase-feat", phase="plan")
        make_branch(repo, "phase-feat")
        subprocess.run(["git", "-C", str(repo), "checkout", "phase-feat"], check=True, capture_output=True)
        (repo / "doc.md").write_text("doc")
        result, code = ops.cmd_commit_artifacts(
            self._args(repo, "phase-feat", ["doc.md"], "test doc", phase=None)
        )
        assert code == 0
        assert "[plan]" in result["commit_message"]

    def test_dry_run_does_not_commit(self, repo):
        (repo / "artifact-dry.md").write_text("hi")
        result, code = ops.cmd_commit_artifacts(
            self._args(repo, "feat", ["artifact-dry.md"], "dry test", phase="dev", dry_run=True)
        )
        assert code == 0
        assert result["dry_run"] is True
        # File should NOT be committed — git status should still show it
        status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True)
        assert "artifact-dry.md" in status.stdout


# ---------------------------------------------------------------------------
# cmd_create_dev_branch
# ---------------------------------------------------------------------------

class TestCreateDevBranch:
    def _args(self, repo, feature_id, username, dry_run=False):
        return _no_args(
            governance_repo=str(repo),
            feature_id=feature_id,
            username=username,
            repo=None,
            dry_run=dry_run,
        )

    def test_invalid_username_rejected(self, repo):
        make_branch(repo, "dev-feat")
        result, code = ops.cmd_create_dev_branch(self._args(repo, "dev-feat", "Bad User"))
        assert code == 1
        assert result["error"] == "invalid_username"

    def test_missing_base_branch_rejected(self, repo):
        result, code = ops.cmd_create_dev_branch(self._args(repo, "no-base", "alice"))
        assert code == 1
        assert result["error"] == "base_branch_not_found"

    def test_creates_dev_branch(self, repo_pair):
        local, remote = repo_pair
        make_branch(local, "devb-feat")
        subprocess.run(["git", "-C", str(local), "push", "--set-upstream", "origin", "devb-feat"], check=True, capture_output=True)
        result, code = ops.cmd_create_dev_branch(_no_args(
            governance_repo=str(local),
            feature_id="devb-feat",
            username="alice",
            repo=None,
            dry_run=False,
        ))
        assert code == 0
        assert ops.branch_exists(str(local), "devb-feat-dev-alice")

    def test_dry_run_no_branch_created(self, repo):
        make_branch(repo, "dry-devb")
        result, code = ops.cmd_create_dev_branch(self._args(repo, "dry-devb", "alice", dry_run=True))
        assert code == 0
        assert result["dry_run"] is True
        assert not ops.branch_exists(str(repo), "dry-devb-dev-alice")

    def test_dry_run_returns_expected_fields(self, repo):
        make_branch(repo, "dry-devb2")
        result, code = ops.cmd_create_dev_branch(self._args(repo, "dry-devb2", "bob", dry_run=True))
        assert code == 0
        assert result["dev_branch"] == "dry-devb2-dev-bob"
        assert result["parent_branch"] == "dry-devb2"

    def test_duplicate_dev_branch_rejected(self, repo):
        make_branch(repo, "dup-base")
        make_branch(repo, "dup-base-dev-alice")
        result, code = ops.cmd_create_dev_branch(self._args(repo, "dup-base", "alice"))
        assert code == 1
        assert result["error"] == "branch_already_exists"


class TestBuildDevBranchName:
    def test_feature_id_mode(self):
        assert ops.build_dev_branch_name("payments-auth", "feature-id") == "feature/payments-auth"

    def test_feature_id_mode_uses_feature_slug_override(self):
        assert ops.build_dev_branch_name(
            "platform-identity-payments-auth",
            "feature-id",
            feature_slug="payments-auth",
        ) == "feature/payments-auth"

    def test_feature_id_username_mode(self):
        assert ops.build_dev_branch_name("payments-auth", "feature-id-username", "alice") == "feature/payments-auth-alice"

    def test_direct_default_returns_empty_branch_name(self):
        assert ops.build_dev_branch_name("payments-auth", "direct-default") == ""


class TestPrepareDevBranch:
    def _args(self, repo, feature_id, mode, username=None, feature_slug=None, base_branch=None, dry_run=False):
        return _no_args(
            repo=str(repo),
            feature_id=feature_id,
            mode=mode,
            username=username,
            feature_slug=feature_slug,
            base_branch=base_branch,
            dry_run=dry_run,
        )

    def test_invalid_mode_rejected(self, repo):
        result, code = ops.cmd_prepare_dev_branch(self._args(repo, "payments-auth", "weird-mode", dry_run=True))
        assert code == 1
        assert result["error"] == "invalid_mode"

    def test_direct_default_checks_out_default_branch(self, repo_pair):
        local, remote = repo_pair
        make_branch(local, "scratch")
        subprocess.run(["git", "-C", str(local), "checkout", "scratch"], check=True, capture_output=True)

        result, code = ops.cmd_prepare_dev_branch(self._args(local, "payments-auth", "direct-default", dry_run=False))

        assert code == 0
        assert result["working_branch"] == "main"
        assert result["requires_pr"] is False
        assert ops.current_branch(str(local)) == "main"

    def test_feature_id_mode_creates_and_pushes_working_branch(self, repo_pair):
        local, remote = repo_pair

        result, code = ops.cmd_prepare_dev_branch(self._args(local, "payments-auth", "feature-id", dry_run=False))

        assert code == 0
        assert result["working_branch"] == "feature/payments-auth"
        assert result["created"] is True
        assert result["requires_pr"] is True
        assert ops.branch_exists(str(local), "feature/payments-auth") is True
        assert ops.current_branch(str(local)) == "feature/payments-auth"

    def test_feature_id_mode_uses_short_feature_slug(self, repo_pair):
        local, remote = repo_pair

        result, code = ops.cmd_prepare_dev_branch(self._args(
            local,
            "platform-identity-payments-auth",
            "feature-id",
            feature_slug="payments-auth",
            dry_run=False,
        ))

        assert code == 0
        assert result["feature_slug"] == "payments-auth"
        assert result["working_branch"] == "feature/payments-auth"
        assert ops.branch_exists(str(local), "feature/payments-auth") is True
        assert ops.current_branch(str(local)) == "feature/payments-auth"

    def test_feature_id_username_mode_reuses_remote_branch(self, repo_pair):
        local, remote = repo_pair
        branch = "feature/payments-auth-alice"
        subprocess.run(["git", "-C", str(local), "checkout", "-b", branch], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(local), "push", "--set-upstream", "origin", branch], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(local), "checkout", "main"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(local), "branch", "-D", branch], check=True, capture_output=True)

        result, code = ops.cmd_prepare_dev_branch(self._args(local, "payments-auth", "feature-id-username", username="alice", dry_run=False))

        assert code == 0
        assert result["working_branch"] == branch
        assert result["created"] is False
        assert result["reused"] is True
        assert ops.current_branch(str(local)) == branch


# ---------------------------------------------------------------------------
# cmd_merge_plan (direct strategy — no gh CLI needed)
# ---------------------------------------------------------------------------

class TestMergePlanDirect:
    def _args(self, repo, feature_id, strategy="direct", delete_after=False, dry_run=False):
        return _no_args(
            governance_repo=str(repo),
            feature_id=feature_id,
            repo=None,
            strategy=strategy,
            auto_merge=False,
            delete_after_merge=delete_after,
            dry_run=dry_run,
        )

    def test_missing_base_branch_rejected(self, repo):
        make_branch(repo, "only-plan-merge")
        result, code = ops.cmd_merge_plan(self._args(repo, "no-base-merge"))
        assert code == 1
        assert result["error"] == "base_branch_not_found"

    def test_missing_plan_branch_rejected(self, repo):
        make_branch(repo, "no-plan-merge")
        result, code = ops.cmd_merge_plan(self._args(repo, "no-plan-merge"))
        assert code == 1
        assert result["error"] == "plan_branch_not_found"

    def test_dry_run_direct(self, repo):
        make_branch(repo, "drym-feat")
        make_branch(repo, "drym-feat-plan")
        result, code = ops.cmd_merge_plan(self._args(repo, "drym-feat", dry_run=True))
        assert code == 0
        assert result["dry_run"] is True

    def test_direct_merge_succeeds(self, repo_pair):
        local, remote = repo_pair
        make_branch(local, "merge-feat")
        subprocess.run(["git", "-C", str(local), "push", "--set-upstream", "origin", "merge-feat"], check=True, capture_output=True)
        make_branch(local, "merge-feat-plan")
        subprocess.run(["git", "-C", str(local), "checkout", "merge-feat-plan"], check=True, capture_output=True)
        (local / "plan.md").write_text("plan content")
        subprocess.run(["git", "-C", str(local), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(local), "commit", "-m", "add plan"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(local), "push", "--set-upstream", "origin", "merge-feat-plan"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(local), "checkout", "main"], check=True, capture_output=True)
        result, code = ops.cmd_merge_plan(_no_args(
            governance_repo=str(local),
            feature_id="merge-feat",
            repo=None,
            strategy="direct",
            delete_after_merge=False,
            dry_run=False,
        ))
        assert code == 0
        assert result["plan_branch_deleted"] is False


# ---------------------------------------------------------------------------
# cmd_push
# ---------------------------------------------------------------------------

class TestPush:
    def _args(self, repo, branch=None, dry_run=False):
        return _no_args(
            governance_repo=str(repo),
            repo=None,
            branch=branch,
            dry_run=dry_run,
        )

    def test_dry_run(self, repo):
        result, code = ops.cmd_push(self._args(repo, dry_run=True))
        assert code == 0
        assert result["dry_run"] is True

    def test_no_remote_returns_error(self, repo):
        # repo has no origin set up — push should fail
        result, code = ops.cmd_push(self._args(repo))
        assert code == 1

    def test_push_succeeds_with_remote(self, repo_pair):
        local, remote = repo_pair
        (local / "new.md").write_text("new")
        subprocess.run(["git", "-C", str(local), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(local), "commit", "-m", "new file"], check=True, capture_output=True)
        result, code = ops.cmd_push(_no_args(
            governance_repo=str(local),
            repo=None,
            branch=None,
            dry_run=False,
        ))
        assert code == 0
        assert result["branch"] == "main"


class TestPublishToGovernance:
    def test_publish_to_governance_copies_phase_artifacts(self, tmp_path):
        governance = tmp_path / "governance"
        control = tmp_path / "control"
        governance.mkdir()
        control.mkdir()

        write_feature_yaml(governance, "publish-feat", domain="platform", service="identity", phase="preplan")

        control_docs = control / "docs" / "platform" / "identity" / "publish-feat"
        control_docs.mkdir(parents=True, exist_ok=True)
        (control_docs / "product-brief.md").write_text("# Product Brief\n")
        (control_docs / "research.md").write_text("# Research\n")

        result, code = ops.cmd_publish_to_governance(_no_args(
            governance_repo=str(governance),
            control_repo=str(control),
            feature_id="publish-feat",
            phase="preplan",
            artifact=[],
            dry_run=False,
        ))
        assert code == 0
        assert (governance / "features" / "platform" / "identity" / "publish-feat" / "docs" / "product-brief.md").exists()
        assert (governance / "features" / "platform" / "identity" / "publish-feat" / "docs" / "research.md").exists()
        assert "brainstorm" in result["missing_artifacts"]

    def test_publish_to_governance_copies_research_files_from_research_subdir(self, tmp_path):
        governance = tmp_path / "governance"
        control = tmp_path / "control"
        governance.mkdir()
        control.mkdir()

        write_feature_yaml(governance, "publish-research-subdir", domain="platform", service="identity", phase="preplan")

        control_docs = control / "docs" / "platform" / "identity" / "publish-research-subdir"
        research_dir = control_docs / "research"
        research_dir.mkdir(parents=True, exist_ok=True)
        nested_research = research_dir / "technical-auth-research-2026-04-14.md"
        nested_research.write_text("# Research\n")

        result, code = ops.cmd_publish_to_governance(_no_args(
            governance_repo=str(governance),
            control_repo=str(control),
            feature_id="publish-research-subdir",
            phase="preplan",
            artifact=["research"],
            dry_run=False,
        ))
        assert code == 0
        assert str(nested_research) in result["copied_from"]
        assert (governance / "features" / "platform" / "identity" / "publish-research-subdir" / "docs" / "technical-auth-research-2026-04-14.md").exists()

    def test_publish_to_governance_dry_run_reports_targets(self, tmp_path):
        governance = tmp_path / "governance"
        control = tmp_path / "control"
        governance.mkdir()
        control.mkdir()

        write_feature_yaml(governance, "dry-publish", domain="platform", service="identity", phase="businessplan")

        control_docs = control / "docs" / "platform" / "identity" / "dry-publish"
        control_docs.mkdir(parents=True, exist_ok=True)
        (control_docs / "prd.md").write_text("# PRD\n")

        result, code = ops.cmd_publish_to_governance(_no_args(
            governance_repo=str(governance),
            control_repo=str(control),
            feature_id="dry-publish",
            phase="businessplan",
            artifact=[],
            dry_run=True,
        ))
        assert code == 0
        assert result["dry_run"] is True
        assert any(path.endswith("features/platform/identity/dry-publish/docs/prd.md") for path in result["published_files"])
        assert not (governance / "features" / "platform" / "identity" / "dry-publish" / "docs" / "prd.md").exists()

    def test_publish_to_governance_copies_story_files_from_supported_shapes(self, tmp_path):
        governance = tmp_path / "governance"
        control = tmp_path / "control"
        governance.mkdir()
        control.mkdir()

        write_feature_yaml(governance, "story-publish", domain="platform", service="identity", phase="finalizeplan")

        control_docs = control / "docs" / "platform" / "identity" / "story-publish"
        control_docs.mkdir(parents=True, exist_ok=True)
        (control_docs / "1-2-user-auth.md").write_text("# Story 1-2\n")
        (control_docs / "dev-story-legacy.md").write_text("# Legacy Story\n")
        stories_dir = control_docs / "stories"
        stories_dir.mkdir()
        (stories_dir / "2-1-admin-audit.yaml").write_text("status: ready-for-dev\n")

        result, code = ops.cmd_publish_to_governance(_no_args(
            governance_repo=str(governance),
            control_repo=str(control),
            feature_id="story-publish",
            phase="finalizeplan",
            artifact=["story-files"],
            dry_run=False,
        ))

        assert code == 0
        target_root = governance / "features" / "platform" / "identity" / "story-publish" / "docs"
        assert (target_root / "1-2-user-auth.md").exists()
        assert (target_root / "dev-story-legacy.md").exists()
        assert (target_root / "2-1-admin-audit.yaml").exists()
        assert result["missing_artifacts"] == []

    def test_publish_to_governance_finalizeplan_includes_review_report(self, tmp_path):
        governance = tmp_path / "governance"
        control = tmp_path / "control"
        governance.mkdir()
        control.mkdir()

        write_feature_yaml(governance, "review-publish", domain="platform", service="identity", phase="finalizeplan")

        control_docs = control / "docs" / "platform" / "identity" / "review-publish"
        control_docs.mkdir(parents=True, exist_ok=True)
        (control_docs / "finalizeplan-review.md").write_text("# Final Review\n")

        result, code = ops.cmd_publish_to_governance(_no_args(
            governance_repo=str(governance),
            control_repo=str(control),
            feature_id="review-publish",
            phase="finalizeplan",
            artifact=["review-report"],
            dry_run=False,
        ))

        assert code == 0
        target = governance / "features" / "platform" / "identity" / "review-publish" / "docs" / "finalizeplan-review.md"
        assert target.exists()
        assert result["missing_artifacts"] == []


class TestMergePlanPRStrategy:
    def test_pr_strategy_reuses_existing_pr_and_enables_auto_merge(self, repo, monkeypatch):
        make_branch(repo, "pr-feat")
        make_branch(repo, "pr-feat-plan")

        real_run = subprocess.run
        gh_calls: list[list[str]] = []

        def fake_run(cmd, *args, **kwargs):
            if cmd[:3] == ["gh", "pr", "list"]:
                gh_calls.append(cmd)
                return subprocess.CompletedProcess(cmd, 0, stdout='[{"url":"https://example.test/pr/7","autoMergeRequest":null}]', stderr="")
            if cmd[:3] == ["gh", "pr", "merge"]:
                gh_calls.append(cmd)
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            return real_run(cmd, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", fake_run)

        result, code = ops.cmd_merge_plan(_no_args(
            governance_repo=str(repo),
            feature_id="pr-feat",
            repo=None,
            strategy="pr",
            auto_merge=True,
            delete_after_merge=False,
            dry_run=False,
        ))

        assert code == 0
        assert result["created"] is False
        assert result["pr_url"] == "https://example.test/pr/7"
        assert result["auto_merge_enabled"] is True
        assert any(call[:3] == ["gh", "pr", "list"] for call in gh_calls)
        assert any(call[:3] == ["gh", "pr", "merge"] for call in gh_calls)


class TestCreatePr:
    def test_create_pr_dry_run(self, repo):
        make_branch(repo, "feature-pr")
        result, code = ops.cmd_create_pr(_no_args(
            governance_repo=str(repo),
            repo=None,
            base="main",
            head="feature-pr",
            title="Test PR",
            body="Dry run",
            auto_merge=True,
            dry_run=True,
        ))
        assert code == 0
        assert result["pr_url"] == "(dry-run)"
        assert result["auto_merge_requested"] is True

    def test_create_pr_creates_new_pr(self, repo, monkeypatch):
        make_branch(repo, "feature-pr2")

        real_run = subprocess.run
        gh_calls: list[list[str]] = []

        def fake_run(cmd, *args, **kwargs):
            if cmd[:3] == ["gh", "pr", "list"]:
                gh_calls.append(cmd)
                return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")
            if cmd[:3] == ["gh", "pr", "create"]:
                gh_calls.append(cmd)
                return subprocess.CompletedProcess(cmd, 0, stdout="https://example.test/pr/8\n", stderr="")
            return real_run(cmd, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", fake_run)

        result, code = ops.cmd_create_pr(_no_args(
            governance_repo=str(repo),
            repo=None,
            base="main",
            head="feature-pr2",
            title="Feature PR",
            body="Create PR",
            auto_merge=False,
            dry_run=False,
        ))

        assert code == 0
        assert result["created"] is True
        assert result["pr_url"] == "https://example.test/pr/8"
        assert any(call[:3] == ["gh", "pr", "create"] for call in gh_calls)



# ---------------------------------------------------------------------------
# CLI integration (subprocess)
# ---------------------------------------------------------------------------

class TestCLIIntegration:
    def _script(self):
        return str(_script_path)

    def test_create_feature_branches_dry_run(self, repo):
        write_feature_yaml(repo, "cli-test-feat")
        proc = subprocess.run(
            ["uv", "run", "--script", self._script(),
             "create-feature-branches",
             "--governance-repo", str(repo),
             "--feature-id", "cli-test-feat",
             "--dry-run"],
            capture_output=True, text=True
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["dry_run"] is True
        assert data["base_branch"] == "cli-test-feat"

    def test_invalid_feature_id_exit_1(self, repo):
        proc = subprocess.run(
            ["uv", "run", "--script", self._script(),
             "create-feature-branches",
             "--governance-repo", str(repo),
             "--feature-id", "Bad/Id"],
            capture_output=True, text=True
        )
        assert proc.returncode == 1
        data = json.loads(proc.stdout)
        assert data["error"] == "invalid_feature_id"

    def test_create_dev_branch_dry_run(self, repo):
        make_branch(repo, "cli-dev-feat")
        proc = subprocess.run(
            ["uv", "run", "--script", self._script(),
             "create-dev-branch",
             "--governance-repo", str(repo),
             "--feature-id", "cli-dev-feat",
             "--username", "alice",
             "--dry-run"],
            capture_output=True, text=True
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["dev_branch"] == "cli-dev-feat-dev-alice"

    def test_prepare_dev_branch_dry_run(self, repo):
        proc = subprocess.run(
            ["uv", "run", "--script", self._script(),
             "prepare-dev-branch",
             "--repo", str(repo),
             "--feature-id", "cli-feature",
             "--mode", "feature-id",
             "--dry-run"],
            capture_output=True, text=True
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["working_branch"] == "feature/cli-feature"

    def test_prepare_dev_branch_dry_run_with_feature_slug(self, repo):
        proc = subprocess.run(
            ["uv", "run", "--script", self._script(),
             "prepare-dev-branch",
             "--repo", str(repo),
             "--feature-id", "platform-identity-cli-feature",
             "--feature-slug", "cli-feature",
             "--mode", "feature-id",
             "--dry-run"],
            capture_output=True, text=True
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["feature_slug"] == "cli-feature"
        assert data["working_branch"] == "feature/cli-feature"


# ---------------------------------------------------------------------------
# Quality-fix coverage tests
# ---------------------------------------------------------------------------

class TestCommitArtifactsBranchGuard:
    """B-2: commit-artifacts must enforce branch membership."""
    def _args(self, repo, feature_id, files, description, phase="dev", push=False, dry_run=False):
        return _no_args(
            repo=str(repo),
            governance_repo=str(repo),
            feature_id=feature_id,
            files=files,
            description=description,
            phase=phase,
            push=push,
            no_confirm=True,
            dry_run=dry_run,
        )

    def test_wrong_branch_returns_error(self, repo):
        # On main, committing for a different feature_id
        (repo / "file.md").write_text("content")
        result, code = self._args_and_run(repo, "other-feat", ["file.md"])
        assert code == 1
        assert result["error"] == "wrong_branch"
        assert result["current"] == "main"

    def _args_and_run(self, repo, feature_id, files):
        a = self._args(repo, feature_id, files, "test desc")
        return ops.cmd_commit_artifacts(a)

    def test_correct_base_branch_allowed(self, repo):
        make_branch(repo, "allowed-feat")
        subprocess.run(["git", "-C", str(repo), "checkout", "allowed-feat"], check=True, capture_output=True)
        (repo / "art.md").write_text("content")
        result, code = ops.cmd_commit_artifacts(self._args(repo, "allowed-feat", ["art.md"], "desc", phase="dev"))
        assert code == 0

    def test_plan_branch_allowed(self, repo):
        make_branch(repo, "planb-feat")
        make_branch(repo, "planb-feat-plan")
        subprocess.run(["git", "-C", str(repo), "checkout", "planb-feat-plan"], check=True, capture_output=True)
        (repo / "plan.md").write_text("plan")
        result, code = ops.cmd_commit_artifacts(self._args(repo, "planb-feat", ["plan.md"], "plan desc", phase="plan"))
        assert code == 0

    def test_dev_branch_allowed(self, repo):
        make_branch(repo, "devb-feat")
        make_branch(repo, "devb-feat-dev-alice")
        subprocess.run(["git", "-C", str(repo), "checkout", "devb-feat-dev-alice"], check=True, capture_output=True)
        (repo / "impl.md").write_text("impl")
        result, code = ops.cmd_commit_artifacts(self._args(repo, "devb-feat", ["impl.md"], "impl desc", phase="dev"))
        assert code == 0


class TestCommitArtifactsPushFlag:
    """TC-2: --push flag path coverage."""
    def test_push_flag_commits_and_pushes(self, repo_pair):
        local, remote = repo_pair
        make_branch(local, "push-feat")
        subprocess.run(["git", "-C", str(local), "push", "--set-upstream", "origin", "push-feat"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(local), "checkout", "push-feat"], check=True, capture_output=True)
        (local / "pushed.md").write_text("pushed content")
        result, code = ops.cmd_commit_artifacts(_no_args(
            repo=str(local),
            governance_repo=str(local),
            feature_id="push-feat",
            files=["pushed.md"],
            description="pushed artifact",
            phase="dev",
            push=True,
            no_confirm=True,
            dry_run=False,
        ))
        assert code == 0
        assert result["pushed"] is True


class TestCommitArtifactsNothingToCommit:
    """TC-3: nothing_to_commit error path."""
    def test_nothing_to_commit_returns_error(self, repo):
        make_branch(repo, "ntc-feat")
        subprocess.run(["git", "-C", str(repo), "checkout", "ntc-feat"], check=True, capture_output=True)
        # Create and commit a file
        (repo / "already.md").write_text("committed")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "pre-commit"], check=True, capture_output=True)
        # Attempt to commit the same file again (no changes)
        result, code = ops.cmd_commit_artifacts(_no_args(
            repo=str(repo),
            governance_repo=str(repo),
            feature_id="ntc-feat",
            files=["already.md"],
            description="re-commit",
            phase="dev",
            push=False,
            no_confirm=True,
            dry_run=False,
        ))
        assert code == 1
        assert result["error"] == "nothing_to_commit"


class TestMergePlanDeleteAfterMerge:
    """TC-1: --delete-after-merge logic coverage."""
    def test_delete_after_merge_removes_plan_branch(self, repo_pair):
        local, remote = repo_pair
        make_branch(local, "del-feat")
        subprocess.run(["git", "-C", str(local), "push", "--set-upstream", "origin", "del-feat"], check=True, capture_output=True)
        make_branch(local, "del-feat-plan")
        subprocess.run(["git", "-C", str(local), "checkout", "del-feat-plan"], check=True, capture_output=True)
        (local / "plan.md").write_text("plan")
        subprocess.run(["git", "-C", str(local), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(local), "commit", "-m", "plan"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(local), "push", "--set-upstream", "origin", "del-feat-plan"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(local), "checkout", "main"], check=True, capture_output=True)
        result, code = ops.cmd_merge_plan(_no_args(
            governance_repo=str(local),
            feature_id="del-feat",
            repo=None,
            strategy="direct",
            delete_after_merge=True,
            dry_run=False,
        ))
        assert code == 0
        assert result["plan_branch_deleted"] is True
        assert not ops.branch_exists(str(local), "del-feat-plan")


class TestMergePlanDirtyTree:
    """SQ-3/ES-6: verify_clean() guard before merge-plan checkout."""
    def test_dirty_tree_rejected(self, repo):
        make_branch(repo, "dirty-merge")
        make_branch(repo, "dirty-merge-plan")
        # Make working tree dirty
        (repo / "dirty.txt").write_text("uncommitted")
        result, code = ops.cmd_merge_plan(_no_args(
            governance_repo=str(repo),
            feature_id="dirty-merge",
            repo=None,
            strategy="direct",
            delete_after_merge=False,
            dry_run=False,
        ))
        assert code == 1
        assert result["error"] == "dirty_working_tree"


class TestMergePlanPRDryRun:
    """TC-4: merge-plan PR strategy dry-run path."""
    def test_pr_dry_run_returns_placeholder_url(self, repo):
        make_branch(repo, "pr-dry-feat")
        make_branch(repo, "pr-dry-feat-plan")
        result, code = ops.cmd_merge_plan(_no_args(
            governance_repo=str(repo),
            feature_id="pr-dry-feat",
            repo=None,
            strategy="pr",
            delete_after_merge=False,
            dry_run=True,
        ))
        assert code == 0
        assert result["pr_url"] == "(dry-run)"
        assert result["dry_run"] is True


class TestCreateFeatureBranchesPlanAlreadyExists:
    """TC-5: plan branch already exists (not base) should be rejected."""
    def test_plan_branch_already_exists_rejected(self, repo):
        write_feature_yaml(repo, "plan-exists-feat")
        make_branch(repo, "plan-exists-feat-plan")
        result, code = ops.cmd_create_feature_branches(_no_args(
            governance_repo=str(repo),
            feature_id="plan-exists-feat",
            repo=None,
            default_branch="main",
            dry_run=False,
        ))
        assert code == 1
        assert result["error"] == "branch_already_exists"
        assert result["branch"] == "plan-exists-feat-plan"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
