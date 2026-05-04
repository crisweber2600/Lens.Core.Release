#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8.0"]
# ///
"""Focused tests for preflight.py governance sync behavior."""

from __future__ import annotations

import importlib.util
import subprocess
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