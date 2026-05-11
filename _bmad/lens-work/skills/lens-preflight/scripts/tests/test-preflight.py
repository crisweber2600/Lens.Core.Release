#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0"]
# ///
"""Focused tests for preflight.py request-policy behavior."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT = Path(__file__).parent.parent / "preflight.py"


def load_preflight_module():
    spec = importlib.util.spec_from_file_location("preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def init_main_repo_with_remote(base_tmp: Path) -> tuple[Path, Path]:
    remote = base_tmp / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)

    gov = base_tmp / "gov"
    subprocess.run(["git", "clone", str(remote), str(gov)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(gov), "checkout", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(gov), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(gov), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(gov), "commit", "--allow-empty", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(gov), "push", "-u", "origin", "main"], check=True, capture_output=True)
    return remote, gov


def test_sync_governance_repo_warns_for_read_only_requests(tmp_path: Path):
    ops = load_preflight_module()
    _, gov = init_main_repo_with_remote(tmp_path)

    ok, detail = ops.sync_governance_repo(gov, request_class="read-only")

    assert ok is True
    assert detail.startswith("warn:")
    assert "read-only request" in detail


def test_sync_governance_repo_warns_for_control_write_requests_on_dirty_feature_branch(tmp_path: Path):
    ops = load_preflight_module()
    _, gov = init_main_repo_with_remote(tmp_path)

    subprocess.run(["git", "-C", str(gov), "checkout", "-b", "feature/test-branch"], check=True, capture_output=True)
    (gov / "LOCAL.txt").write_text("local\n", encoding="utf-8")

    ok, detail = ops.sync_governance_repo(gov, request_class="control-write")

    assert ok is True
    assert detail.startswith("warn:")
    assert "skipping mutable governance sync" in detail


def test_sync_control_repo_blocks_mutating_request_when_worktree_dirty(tmp_path: Path):
    ops = load_preflight_module()
    _, control = init_main_repo_with_remote(tmp_path)
    (control / "LOCAL.txt").write_text("local\n", encoding="utf-8")

    ok, detail = ops.sync_control_repo(control, request_class="mixed")

    assert ok is False
    assert detail.startswith("block:")
    assert "policy-blocked sync" in detail


def test_pre_request_sync_corrects_dirty_control_repo(tmp_path: Path):
    ops = load_preflight_module()
    _, control = init_main_repo_with_remote(tmp_path)
    (control / "LOCAL.txt").write_text("local\n", encoding="utf-8")

    decision = ops.run_pre_request_sync_with_correction(control, "control", "mixed")

    assert decision.outcome == "pull-only"
    assert "pulled origin/main" in decision.detail
    status = subprocess.run(
        ["git", "-C", str(control), "status", "--short"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout.strip() == ""
    ahead = subprocess.run(
        ["git", "-C", str(control), "rev-list", "--count", "origin/main..HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert ahead.stdout.strip() == "0"


def test_pre_request_sync_corrects_dirty_governance_repo(tmp_path: Path):
    ops = load_preflight_module()
    _, governance = init_main_repo_with_remote(tmp_path)
    (governance / "feature-index.yaml").write_text("features: []\n", encoding="utf-8")

    decision = ops.run_pre_request_sync_with_correction(
        governance,
        "governance",
        "mixed",
        preferred_branch="main",
    )

    assert decision.outcome == "pull-only"
    assert "pulled origin/main" in decision.detail
    status = subprocess.run(
        ["git", "-C", str(governance), "status", "--short"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout.strip() == ""
    ahead = subprocess.run(
        ["git", "-C", str(governance), "rev-list", "--count", "origin/main..HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert ahead.stdout.strip() == "0"


def test_sync_control_repo_warns_for_governance_write_requests_when_worktree_dirty(tmp_path: Path):
    ops = load_preflight_module()
    _, control = init_main_repo_with_remote(tmp_path)
    (control / "LOCAL.txt").write_text("local\n", encoding="utf-8")

    ok, detail = ops.sync_control_repo(control, request_class="governance-write")

    assert ok is True
    assert detail.startswith("warn:")
    assert "skipping mutable control sync for governance-write request" in detail


def test_sync_control_repo_pulls_clean_mutating_request(tmp_path: Path):
    ops = load_preflight_module()
    remote, control = init_main_repo_with_remote(tmp_path)

    peer = tmp_path / "peer"
    subprocess.run(["git", "clone", str(remote), str(peer)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(peer), "checkout", "-b", "main", "origin/main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(peer), "config", "user.email", "peer@example.com"], check=True)
    subprocess.run(["git", "-C", str(peer), "config", "user.name", "Peer User"], check=True)
    (peer / "REMOTE.txt").write_text("remote\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(peer), "add", "REMOTE.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(peer), "commit", "-m", "peer update"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(peer), "push", "origin", "main"], check=True, capture_output=True)

    ok, detail = ops.sync_control_repo(control, request_class="mixed")

    assert ok is True
    assert detail.startswith("pull-only:")
    assert "pulled origin/main" in detail


def test_pre_request_sync_switches_to_dev_branch_when_feature_remote_was_deleted(tmp_path: Path):
    ops = load_preflight_module()
    _, control = init_main_repo_with_remote(tmp_path)

    feature_branch = "lens-dev-new-codebase-example"
    dev_branch = f"{feature_branch}-dev"
    subprocess.run(["git", "-C", str(control), "checkout", "-b", feature_branch], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(control), "push", "-u", "origin", feature_branch], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(control), "checkout", "-b", dev_branch, "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(control), "push", "-u", "origin", dev_branch], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(control), "checkout", feature_branch], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(control), "push", "origin", f":{feature_branch}"], check=True, capture_output=True)

    decision = ops.pre_request_sync(control, "control", "mixed")

    assert decision.outcome == "pull-only"
    assert decision.branch == dev_branch
    assert f"origin/{feature_branch} missing after branch cleanup" in decision.detail
    assert f"switched to {dev_branch}" in decision.detail
    current_branch = subprocess.run(
        ["git", "-C", str(control), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert current_branch.stdout.strip() == dev_branch


def test_sync_release_repo_resets_hard_and_retries_when_pull_is_blocked(tmp_path: Path):
    ops = load_preflight_module()
    remote, release = init_main_repo_with_remote(tmp_path)

    (release / "tracked.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(release), "add", "tracked.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(release), "commit", "-m", "add tracked"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(release), "push", "origin", "main"], check=True, capture_output=True)

    peer = tmp_path / "peer"
    subprocess.run(["git", "clone", str(remote), str(peer)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(peer), "checkout", "-b", "main", "origin/main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(peer), "config", "user.email", "peer@example.com"], check=True)
    subprocess.run(["git", "-C", str(peer), "config", "user.name", "Peer User"], check=True)
    (peer / "tracked.txt").write_text("remote\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(peer), "add", "tracked.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(peer), "commit", "-m", "add tracked"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(peer), "push", "origin", "main"], check=True, capture_output=True)

    (release / "tracked.txt").write_text("local blocker\n", encoding="utf-8")

    ok, detail = ops.sync_release_repo(release)

    assert ok is True
    assert detail == "pull blocked; reset --hard; pulled origin"
    assert (release / "tracked.txt").read_text(encoding="utf-8") == "remote\n"
    status_result = subprocess.run(
        ["git", "-C", str(release), "status", "--short"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert status_result.stdout.strip() == ""


def test_classify_request_prefers_explicit_override():
    ops = load_preflight_module()

    assert ops.classify_request("lens-constitution", "mixed") == "mixed"


def test_classify_request_marks_no_governance_write_planning_callers_as_control_write():
    ops = load_preflight_module()

    assert ops.classify_request("lens-expressplan") == "control-write"
    assert ops.classify_request("lens-preplan") == "control-write"


def test_classify_request_marks_governance_only_callers_as_governance_write():
    ops = load_preflight_module()

    assert ops.classify_request("lens-discover") == "governance-write"
    assert ops.classify_request("lens-new-domain") == "governance-write"
    assert ops.classify_request("lens-new-service") == "governance-write"


def test_post_request_sync_decision_defaults_only_for_touched_repos():
    ops = load_preflight_module()

    assert ops.post_request_sync_decision("control", touched=False, request_class="mixed").outcome == "no-op"
    assert ops.post_request_sync_decision("control", touched=True, request_class="mixed").outcome == "commit-push"
    assert ops.post_request_sync_decision("governance", touched=True, request_class="mixed").outcome == "publish"


def test_ensure_lens_version_file_seeds_from_lifecycle_when_missing(tmp_path: Path):
    ops = load_preflight_module()
    project_root = tmp_path / "workspace"
    lifecycle = project_root / "lens.core" / "_bmad" / "lens-work" / "lifecycle.yaml"

    lifecycle.parent.mkdir(parents=True)
    lifecycle.write_text("schema_version: 4\n", encoding="utf-8")

    assert ops.ensure_lens_version_file(project_root) == "4.0.0"
    assert (project_root / ".lens" / "LENS_VERSION").read_text(encoding="utf-8") == "4.0.0"


def test_main_forces_release_refresh_on_develop_even_when_timestamp_is_fresh(tmp_path: Path, monkeypatch):
    ops = load_preflight_module()
    project_root = tmp_path / "workspace"
    release = project_root / "lens.core"
    lifecycle = release / "_bmad" / "lens-work" / "lifecycle.yaml"
    release_github = release / ".github"
    personal = project_root / ".lens" / "personal"
    governance = project_root / "TargetProjects" / "lens" / "lens-governance"

    lifecycle.parent.mkdir(parents=True)
    lifecycle.write_text("schema_version: 4\n", encoding="utf-8")
    release_github.mkdir(parents=True)
    personal.mkdir(parents=True)
    governance.mkdir(parents=True)
    (project_root / ".lens" / "LENS_VERSION").write_text("4.0.0", encoding="utf-8")
    (project_root / ".lens" / "governance-setup.yaml").write_text(
        f"governance_repo_path: {governance.as_posix()}\n",
        encoding="utf-8",
    )
    (personal / ".preflight-timestamp").write_text(
        datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        encoding="utf-8",
    )

    control_syncs: list[Path] = []
    release_syncs: list[Path] = []

    def fake_sync_release(repo: Path):
        release_syncs.append(repo)
        return True, "pulled origin"

    def fake_pre_request_sync(repo: Path, repo_label: str, request_class: str, preferred_branch=None):
        control_syncs.append(repo)
        return ops.RepoSyncDecision(repo_label, "pull-only", "policy ok", True)

    monkeypatch.chdir(project_root)
    monkeypatch.setattr(sys, "argv", ["preflight.py", "--caller", "lens-dev"])
    monkeypatch.setattr(ops, "sync_release_repo", fake_sync_release)
    monkeypatch.setattr(ops, "pre_request_sync", fake_pre_request_sync)
    monkeypatch.setattr(ops, "publish_touched_repo", lambda repo, repo_label: (True, "policy ok"))
    monkeypatch.setattr(ops, "release_branch_name", lambda _: "develop")

    assert ops.main() == 0
    assert release_syncs == [release]
    assert control_syncs == [project_root, governance]


def test_main_skips_release_refresh_when_timestamp_is_fresh_off_develop(tmp_path: Path, monkeypatch):
    ops = load_preflight_module()
    project_root = tmp_path / "workspace"
    release = project_root / "lens.core"
    lifecycle = release / "_bmad" / "lens-work" / "lifecycle.yaml"
    release_github = release / ".github"
    personal = project_root / ".lens" / "personal"
    governance = project_root / "TargetProjects" / "lens" / "lens-governance"

    lifecycle.parent.mkdir(parents=True)
    lifecycle.write_text("schema_version: 4\n", encoding="utf-8")
    release_github.mkdir(parents=True)
    personal.mkdir(parents=True)
    governance.mkdir(parents=True)
    (project_root / ".lens" / "LENS_VERSION").write_text("4.0.0", encoding="utf-8")
    (project_root / ".lens" / "governance-setup.yaml").write_text(
        f"governance_repo_path: {governance.as_posix()}\n",
        encoding="utf-8",
    )
    (personal / ".preflight-timestamp").write_text(
        datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        encoding="utf-8",
    )

    release_syncs: list[Path] = []
    request_syncs: list[str] = []

    def fake_sync_release(repo: Path):
        release_syncs.append(repo)
        return True, "pulled origin"

    def fake_pre_request_sync(repo: Path, repo_label: str, request_class: str, preferred_branch=None):
        request_syncs.append(repo_label)
        outcome = "warn" if repo_label == "governance" else "no-op"
        detail = "governance freshness deferred for read-only request" if repo_label == "governance" else "policy noop"
        return ops.RepoSyncDecision(repo_label, outcome, detail, False)

    monkeypatch.chdir(project_root)
    monkeypatch.setattr(sys, "argv", ["preflight.py", "--caller", "lens-constitution"])
    monkeypatch.setattr(ops, "sync_release_repo", fake_sync_release)
    monkeypatch.setattr(ops, "pre_request_sync", fake_pre_request_sync)
    monkeypatch.setattr(ops, "release_branch_name", lambda _: "main")

    assert ops.main() == 0
    assert release_syncs == []
    assert request_syncs == ["control", "governance"]


def test_main_syncs_agents_file_and_records_hash(tmp_path: Path, monkeypatch):
    ops = load_preflight_module()
    project_root = tmp_path / "workspace"
    release = project_root / "lens.core"
    lifecycle = release / "_bmad" / "lens-work" / "lifecycle.yaml"
    release_github = release / ".github"
    personal = project_root / ".lens" / "personal"
    governance = project_root / "TargetProjects" / "lens" / "lens-governance"

    lifecycle.parent.mkdir(parents=True)
    lifecycle.write_text("schema_version: 4\n", encoding="utf-8")
    release_github.mkdir(parents=True)
    personal.mkdir(parents=True)
    governance.mkdir(parents=True)
    (release / "AGENTS.md").write_text("release agents\n", encoding="utf-8")
    (project_root / ".lens" / "LENS_VERSION").write_text("4.0.0", encoding="utf-8")
    (project_root / ".lens" / "governance-setup.yaml").write_text(
        f"governance_repo_path: {governance.as_posix()}\n",
        encoding="utf-8",
    )

    def fake_sync_release(repo: Path):
        return True, "pulled origin"

    def fake_pre_request_sync(repo: Path, repo_label: str, request_class: str, preferred_branch=None):
        return ops.RepoSyncDecision(repo_label, "pull-only", "policy ok", True)

    monkeypatch.chdir(project_root)
    monkeypatch.setattr(sys, "argv", ["preflight.py", "--caller", "lens-dev"])
    monkeypatch.setattr(ops, "sync_release_repo", fake_sync_release)
    monkeypatch.setattr(ops, "pre_request_sync", fake_pre_request_sync)
    monkeypatch.setattr(ops, "publish_touched_repo", lambda repo, repo_label: (True, "policy ok"))
    monkeypatch.setattr(ops, "release_branch_name", lambda _: "develop")

    assert ops.main() == 0
    assert (project_root / "AGENTS.md").read_text(encoding="utf-8") == "release agents\n"

    expected_hash = ops.sha256_file(release / "AGENTS.md")
    hash_manifest = (personal / ".github-hashes").read_text(encoding="utf-8")
    assert f"{expected_hash}  AGENTS.md" in hash_manifest