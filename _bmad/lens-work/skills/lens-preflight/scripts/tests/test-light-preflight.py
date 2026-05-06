#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0"]
# ///
"""Focused tests for light-preflight.py."""

from __future__ import annotations

import importlib.util
from argparse import Namespace
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parent.parent / "light-preflight.py"


def load_light_module():
    spec = importlib.util.spec_from_file_location("light_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("schema_version: 1\n", encoding="utf-8")


def test_find_project_root_prefers_workspace_root_from_source_repo_cwd(tmp_path: Path, monkeypatch):
    ops = load_light_module()
    workspace = tmp_path / "workspace"
    source = workspace / "TargetProjects" / "lens-dev" / "new-codebase" / "lens.core.src"
    touch(workspace / "lens.core" / "_bmad" / "lens-work" / "lifecycle.yaml")
    touch(source / "_bmad" / "lens-work" / "lifecycle.yaml")
    monkeypatch.chdir(source)

    assert ops.find_project_root() == workspace.resolve()


def test_find_project_root_supports_standalone_source_repo(tmp_path: Path, monkeypatch):
    ops = load_light_module()
    source = tmp_path / "lens.core.src"
    touch(source / "_bmad" / "lens-work" / "lifecycle.yaml")
    monkeypatch.chdir(source)

    assert ops.find_project_root() == source.resolve()


def test_parser_accepts_documented_arguments():
    ops = load_light_module()

    args = ops.build_parser().parse_args(
        [
            "--caller",
            "onboard",
            "--governance-path",
            "TargetProjects/lens/lens-governance",
            "--request-class",
            "mixed",
        ]
    )

    assert args.caller == "onboard"
    assert args.governance_path == "TargetProjects/lens/lens-governance"
    assert args.request_class == "mixed"


def test_parser_rejects_undocumented_arguments():
    ops = load_light_module()

    with pytest.raises(SystemExit):
        ops.build_parser().parse_args(["--not-real"])


def test_main_delegates_to_full_preflight(tmp_path: Path, monkeypatch):
    ops = load_light_module()
    seen: dict[str, object] = {}

    monkeypatch.setattr(ops, "find_project_root", lambda: tmp_path)
    monkeypatch.setattr(ops, "check_python_version", lambda: (True, "Python 3.12"))

    def fake_delegate(args: Namespace, project_root: Path) -> int:
        seen["caller"] = args.caller
        seen["request_class"] = args.request_class
        seen["project_root"] = project_root
        return 0

    monkeypatch.setattr(ops, "delegate_preflight", fake_delegate)
    monkeypatch.setattr(
        "sys.argv",
        ["light-preflight.py", "--caller", "lens-dev", "--request-class", "mixed"],
    )

    assert ops.main() == 0
    assert seen == {"caller": "lens-dev", "request_class": "mixed", "project_root": tmp_path}
