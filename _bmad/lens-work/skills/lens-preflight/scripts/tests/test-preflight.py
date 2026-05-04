#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0"]
# ///
"""Focused tests for preflight.py governance sync behavior."""

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


def test_sync_governance_repo_auto_commits_pulls_and_pushes_local_changes(tmp_path: Path):
    ops = load_preflight_module()
    remote, gov = init_main_repo_with_remote(tmp_path)

    peer = tmp_path / "peer"
    subprocess.run(["git", "clone", str(remote), str(peer)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(peer), "checkout", "-b", "main", "origin/main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(peer), "config", "user.email", "peer@example.com"], check=True)
    subprocess.run(["git", "-C", str(peer), "config", "user.name", "Peer User"], check=True)
    (peer / "REMOTE.txt").write_text("remote\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(peer), "add", "REMOTE.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(peer), "commit", "-m", "peer update"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(peer), "push", "origin", "main"], check=True, capture_output=True)

    (gov / "LOCAL.txt").write_text("local\n", encoding="utf-8")

    ok, detail = ops.sync_governance_repo(gov)

    assert ok is True
    assert "committed local changes" in detail
    assert "pushed 1 local commit(s)" in detail
    status_result = subprocess.run(
        ["git", "-C", str(gov), "status", "--short"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert status_result.stdout.strip() == ""
    remote_local = subprocess.run(
        ["git", "--git-dir", str(remote), "show", "main:LOCAL.txt"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert remote_local.stdout == "local\n"
    remote_remote = subprocess.run(
        ["git", "--git-dir", str(remote), "show", "main:REMOTE.txt"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert remote_remote.stdout == "remote\n"


def test_sync_control_repo_auto_commits_pulls_and_pushes_local_changes(tmp_path: Path):
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

    (control / "LOCAL.txt").write_text("local\n", encoding="utf-8")

    ok, detail = ops.sync_control_repo(control)

    assert ok is True
    assert "committed local changes" in detail
    assert "pulled origin/main" in detail
    assert "pushed 1 local commit(s)" in detail
    status_result = subprocess.run(
        ["git", "-C", str(control), "status", "--short"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert status_result.stdout.strip() == ""
    remote_local = subprocess.run(
        ["git", "--git-dir", str(remote), "show", "main:LOCAL.txt"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert remote_local.stdout == "local\n"
    remote_remote = subprocess.run(
        ["git", "--git-dir", str(remote), "show", "main:REMOTE.txt"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert remote_remote.stdout == "remote\n"


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


def test_main_syncs_control_and_governance_even_when_timestamp_is_fresh(tmp_path: Path, monkeypatch):
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
    governance_syncs: list[Path] = []

    def fake_sync_release(repo: Path):
        release_syncs.append(repo)
        return True, "pulled origin"

    def fake_sync_control(repo: Path):
        control_syncs.append(repo)
        return True, "synced main; pulled origin/main"

    def fake_sync_governance(repo: Path):
        governance_syncs.append(repo)
        return True, "synced main; pulled origin/main"

    monkeypatch.chdir(project_root)
    monkeypatch.setattr(sys, "argv", ["preflight.py"])
    monkeypatch.setattr(ops, "sync_release_repo", fake_sync_release)
    monkeypatch.setattr(ops, "sync_control_repo", fake_sync_control)
    monkeypatch.setattr(ops, "sync_governance_repo", fake_sync_governance)

    assert ops.main() == 0
    assert release_syncs == [release]
    assert control_syncs == [project_root, project_root]
    assert governance_syncs == [governance]