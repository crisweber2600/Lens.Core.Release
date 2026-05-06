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


def test_sync_control_repo_blocks_mutating_request_when_worktree_dirty(tmp_path: Path):
    ops = load_preflight_module()
    _, control = init_main_repo_with_remote(tmp_path)
    (control / "LOCAL.txt").write_text("local\n", encoding="utf-8")

    ok, detail = ops.sync_control_repo(control, request_class="mixed")

    assert ok is False
    assert detail.startswith("block:")
    assert "policy-blocked sync" in detail


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


def test_post_request_sync_decision_defaults_only_for_touched_repos():
    ops = load_preflight_module()

    assert ops.post_request_sync_decision("control", touched=False, request_class="mixed").outcome == "no-op"
    assert ops.post_request_sync_decision("control", touched=True, request_class="mixed").outcome == "commit-push"
    assert ops.post_request_sync_decision("governance", touched=True, request_class="mixed").outcome == "publish"


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