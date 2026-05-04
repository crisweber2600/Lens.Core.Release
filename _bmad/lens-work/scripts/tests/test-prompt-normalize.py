#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0"]
# ///
"""Tests for prompt-normalize.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parent.parent / "prompt-normalize.py"


def load_prompt_module():
    spec = importlib.util.spec_from_file_location("prompt_normalize", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_normalize_file_replaces_literal_crlf_tokens(tmp_path: Path):
    ops = load_prompt_module()
    prompt = tmp_path / "lens-demo.prompt.md"
    prompt.write_text("FIRST\\r\\nSECOND\\r\\n", encoding="utf-8")

    result = ops.normalize_file(prompt, check=False, dry_run=False)

    assert result == {"path": str(prompt), "changed": True}
    assert prompt.read_text(encoding="utf-8") == "FIRST\nSECOND\n"


def test_check_mode_reports_change_without_writing(tmp_path: Path):
    ops = load_prompt_module()
    prompt = tmp_path / "lens-demo.prompt.md"
    prompt.write_text("FIRST\\r\\nSECOND", encoding="utf-8")

    result = ops.normalize_file(prompt, check=True, dry_run=False)

    assert result["changed"] is True
    assert prompt.read_text(encoding="utf-8") == "FIRST\\r\\nSECOND"


def test_iter_prompt_files_scans_prompt_markdown_only(tmp_path: Path):
    ops = load_prompt_module()
    prompts = tmp_path / ".github" / "prompts"
    prompts.mkdir(parents=True)
    keep = prompts / "lens-demo.prompt.md"
    skip = prompts / "notes.md"
    keep.write_text("ok", encoding="utf-8")
    skip.write_text("skip", encoding="utf-8")

    assert ops.iter_prompt_files([prompts]) == [keep]


def test_iter_prompt_files_skips_non_prompt_explicit_file(tmp_path: Path):
    ops = load_prompt_module()
    non_prompt = tmp_path / "notes.md"
    non_prompt.write_text("content", encoding="utf-8")

    assert ops.iter_prompt_files([non_prompt]) == []


def test_iter_prompt_files_accepts_explicit_prompt_file(tmp_path: Path):
    ops = load_prompt_module()
    prompt = tmp_path / "lens-demo.prompt.md"
    prompt.write_text("content", encoding="utf-8")

    assert ops.iter_prompt_files([prompt]) == [prompt]
