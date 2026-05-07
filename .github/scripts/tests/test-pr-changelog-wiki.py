#!/usr/bin/env python3
"""Focused tests for the PR changelog wiki updater."""

from __future__ import annotations

import io
import importlib.util
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "pr_changelog_wiki.py"
SPEC = importlib.util.spec_from_file_location("pr_changelog_wiki", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_extract_accomplishments_prefers_summary_section():
    body = """
## Summary
- Adds the daily wiki update workflow
- Tracks already-processed pull requests

## Testing
- Focused pytest
""".strip()

    assert MODULE.extract_accomplishments(body, "Fallback title") == [
        "Adds the daily wiki update workflow",
        "Tracks already-processed pull requests",
    ]


def test_render_pull_request_entry_includes_accomplishments_and_truncates_files():
    files = tuple(
        MODULE.PullFile(
            filename=f"src/file-{index}.py",
            status="modified",
            additions=index,
            deletions=0,
            changes=index,
        )
        for index in range(1, 28)
    )
    pr = MODULE.PullRequestSummary(
        number=42,
        title="Add automated wiki changelog",
        url="https://github.com/example/repo/pull/42",
        author="octocat",
        merged_at="2026-05-06T12:00:00Z",
        body="## Summary\n- Writes changelog entries to the wiki",
        base_ref="main",
        head_ref="feature/wiki-log",
        files=files,
    )

    text = MODULE.render_pull_request_entry(pr)

    assert "## PR #42: Add automated wiki changelog" in text
    assert "- Areas: `src`" in text
    assert "- Writes changelog entries to the wiki" in text
    assert "`src/file-1.py`" in text
    assert "_2 additional files omitted for brevity_" in text


def test_render_changelog_page_prepends_new_entries_and_updates_header():
    existing = """# Pull Request Change Log

This page is updated automatically from merged pull requests in `owner/repo`.

_Last updated: old_

---

## PR #1: Existing entry
""".strip()

    rendered = MODULE.render_changelog_page(
        existing,
        ["## PR #2: New entry\n"],
        "owner/repo",
        "2026-05-06T22:00:00Z",
    )

    assert rendered.startswith("# Pull Request Change Log")
    assert "_Last updated: 2026-05-06T22:00:00Z_" in rendered
    assert rendered.index("## PR #2: New entry") < rendered.index("## PR #1: Existing entry")


def test_render_home_page_adds_and_replaces_managed_block():
    initial = MODULE.render_home_page("", "PR-Change-Log.md", "2026-05-06T22:00:00Z")
    updated = MODULE.render_home_page(initial, "PR-Change-Log.md", "2026-05-07T00:00:00Z")

    assert initial.count(MODULE.HOME_MARKER_START) == 1
    assert "[Pull Request Change Log](PR-Change-Log)" in initial
    assert updated.count(MODULE.HOME_MARKER_START) == 1
    assert "_Last PR changelog update: 2026-05-07T00:00:00Z_" in updated


def test_select_unprocessed_pulls_respects_processing_cap():
    pulls = [
        {"number": 5},
        {"number": 4},
        {"number": 3},
        {"number": 2},
    ]

    selected = MODULE.select_unprocessed_pulls(pulls, {4}, 2)

    assert [pull["number"] for pull in selected] == [5, 3]


def test_request_json_retries_with_timeout(monkeypatch):
    attempts: list[int] = []
    sleeps: list[int] = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        attempts.append(timeout)
        if len(attempts) == 1:
            raise URLError("temporary outage")
        return _Response()

    monkeypatch.setattr(MODULE, "urlopen", fake_urlopen)
    monkeypatch.setattr(MODULE.time, "sleep", sleeps.append)

    response_data = MODULE.request_json("https://api.github.com/example", "token")

    assert response_data == {"ok": True}
    assert attempts == [MODULE.REQUEST_TIMEOUT_SECONDS, MODULE.REQUEST_TIMEOUT_SECONDS]
    assert sleeps == [1]


def test_request_json_raises_after_retryable_http_error_exhausted(monkeypatch):
    response = io.BytesIO(b"busy")

    def fake_urlopen(request, timeout):
        raise HTTPError("https://api.github.com/example", 503, "busy", {}, response)

    monkeypatch.setattr(MODULE, "urlopen", fake_urlopen)
    monkeypatch.setattr(MODULE.time, "sleep", lambda seconds: None)

    try:
        MODULE.request_json("https://api.github.com/example", "token")
    except RuntimeError as exc:
        assert "503" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for exhausted retries")


def test_retry_delay_uses_exponential_backoff():
    assert MODULE._retry_delay(1) == 1
    assert MODULE._retry_delay(2) == 2
    assert MODULE._retry_delay(3) == 4
