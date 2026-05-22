#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for help-ops.py."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = str(Path(__file__).parent.parent / "help-ops.py")
TOPICS_FILE = str(Path(__file__).parent.parent.parent / "assets" / "help-topics.yaml")

PASS = 0
FAIL = 0


def run(args: list[str]) -> tuple[dict, int]:
    """Run the script and return parsed JSON output and exit code."""
    result = subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout), result.returncode
    except json.JSONDecodeError:
        return {"error": result.stderr, "stdout": result.stdout}, result.returncode


def assert_eq(name: str, actual, expected):
    global PASS, FAIL
    if actual == expected:
        PASS += 1
        print(f"  ✓ {name}", file=sys.stderr)
    else:
        FAIL += 1
        print(f"  ✗ {name}: expected {expected!r}, got {actual!r}", file=sys.stderr)


def assert_true(name: str, actual):
    assert_eq(name, bool(actual), True)


def assert_ge(name: str, actual, minimum):
    global PASS, FAIL
    if actual >= minimum:
        PASS += 1
        print(f"  ✓ {name} ({actual} >= {minimum})", file=sys.stderr)
    else:
        FAIL += 1
        print(f"  ✗ {name}: expected >= {minimum}, got {actual}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Contextual tests
# ---------------------------------------------------------------------------

def test_contextual_preplan():
    print("test_contextual_preplan", file=sys.stderr)
    result, code = run([
        "contextual",
        "--topics-file", TOPICS_FILE,
        "--phase", "preplan",
        "--track", "full",
    ])
    assert_eq("status", result["status"], "pass")
    assert_eq("exit code", code, 0)
    assert_eq("phase echoed", result["phase"], "preplan")
    ids = [t["id"] for t in result["topics"]]
    assert_true("init-feature present for preplan", "init-feature" in ids)


def test_contextual_dev():
    print("test_contextual_dev", file=sys.stderr)
    result, code = run([
        "contextual",
        "--topics-file", TOPICS_FILE,
        "--phase", "dev",
        "--track", "full",
    ])
    assert_eq("status", result["status"], "pass")
    assert_eq("exit code", code, 0)
    ids = [t["id"] for t in result["topics"]]
    # complete and retrospective are dev-specific; at least one should appear
    assert_true("dev-phase topic present", "complete" in ids or "retrospective" in ids)
    # init-feature is preplan-only; should NOT appear for dev
    assert_eq("init-feature absent for dev", "init-feature" not in ids, True)


def test_contextual_limit():
    print("test_contextual_limit", file=sys.stderr)
    result, code = run([
        "contextual",
        "--topics-file", TOPICS_FILE,
        "--phase", "all",
        "--track", "all",
        "--limit", "3",
    ])
    assert_eq("status", result["status"], "pass")
    assert_eq("limit respected", len(result["topics"]) <= 3, True)
    assert_ge("total_available present", result["total_available"], 1)


def test_contextual_default_limit():
    print("test_contextual_default_limit", file=sys.stderr)
    result, code = run([
        "contextual",
        "--topics-file", TOPICS_FILE,
        "--phase", "all",
        "--track", "all",
    ])
    assert_eq("status", result["status"], "pass")
    assert_eq("default limit <= 5", len(result["topics"]) <= 5, True)


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------

def test_search_command_name():
    print("test_search_command_name", file=sys.stderr)
    result, code = run([
        "search",
        "--topics-file", TOPICS_FILE,
        "--query", "retrospective",
    ])
    assert_eq("status", result["status"], "pass")
    assert_eq("exit code", code, 0)
    assert_ge("at least 1 match", result["total"], 1)
    ids = [m["id"] for m in result["matches"]]
    assert_true("retrospective in results", "retrospective" in ids)


def test_search_case_insensitive():
    print("test_search_case_insensitive", file=sys.stderr)
    result_lower, _ = run([
        "search", "--topics-file", TOPICS_FILE, "--query", "status",
    ])
    result_upper, _ = run([
        "search", "--topics-file", TOPICS_FILE, "--query", "STATUS",
    ])
    assert_eq("case insensitive same count", result_lower["total"], result_upper["total"])


def test_search_no_matches():
    print("test_search_no_matches", file=sys.stderr)
    result, code = run([
        "search",
        "--topics-file", TOPICS_FILE,
        "--query", "zzz-nonexistent-xyz",
    ])
    assert_eq("status is pass (not error)", result["status"], "pass")
    assert_eq("exit code 0", code, 0)
    assert_eq("empty matches list", result["matches"], [])
    assert_eq("total is 0", result["total"], 0)


def test_search_partial_match():
    print("test_search_partial_match", file=sys.stderr)
    result, code = run([
        "search",
        "--topics-file", TOPICS_FILE,
        "--query", "feature",
    ])
    assert_eq("status", result["status"], "pass")
    assert_ge("multiple feature matches", result["total"], 2)


# ---------------------------------------------------------------------------
# All topics tests
# ---------------------------------------------------------------------------

def test_all_topics():
    print("test_all_topics", file=sys.stderr)
    result, code = run([
        "all",
        "--topics-file", TOPICS_FILE,
    ])
    assert_eq("status", result["status"], "pass")
    assert_eq("exit code", code, 0)
    # Registry has 14 topics per spec
    assert_ge("total >= 14", result["total"], 14)
    assert_eq("topics count matches total", len(result["topics"]), result["total"])


def test_category_filter():
    print("test_category_filter", file=sys.stderr)
    result, code = run([
        "all",
        "--topics-file", TOPICS_FILE,
        "--category", "lifecycle",
    ])
    assert_eq("status", result["status"], "pass")
    assert_eq("exit code", code, 0)
    assert_ge("lifecycle topics >= 1", result["total"], 1)
    for topic in result["topics"]:
        assert_eq(f"category correct for {topic['id']}", topic["category"], "lifecycle")


def test_category_filter_navigation():
    print("test_category_filter_navigation", file=sys.stderr)
    result, code = run([
        "all",
        "--topics-file", TOPICS_FILE,
        "--category", "navigation",
    ])
    assert_eq("status", result["status"], "pass")
    ids = [t["id"] for t in result["topics"]]
    assert_true("status in navigation", "status" in ids)
    assert_true("next in navigation", "next" in ids)
    assert_true("help in navigation", "help" in ids)


# ---------------------------------------------------------------------------
# Error tests
# ---------------------------------------------------------------------------

def test_missing_topics_file():
    print("test_missing_topics_file", file=sys.stderr)
    result, code = run([
        "contextual",
        "--topics-file", "/nonexistent/path/help-topics.yaml",
        "--phase", "dev",
        "--track", "full",
    ])
    assert_eq("exit code 1", code, 1)
    assert_eq("status fail", result.get("status"), "fail")
    assert_eq("error key", result.get("error"), "topics_file_not_found")


def test_missing_topics_file_search():
    print("test_missing_topics_file_search", file=sys.stderr)
    result, code = run([
        "search",
        "--topics-file", "/nonexistent/path/help-topics.yaml",
        "--query", "anything",
    ])
    assert_eq("exit code 1", code, 1)
    assert_eq("status fail", result.get("status"), "fail")


def test_missing_topics_file_all():
    print("test_missing_topics_file_all", file=sys.stderr)
    result, code = run([
        "all",
        "--topics-file", "/nonexistent/path/help-topics.yaml",
    ])
    assert_eq("exit code 1", code, 1)
    assert_eq("status fail", result.get("status"), "fail")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    test_contextual_preplan()
    test_contextual_dev()
    test_contextual_limit()
    test_contextual_default_limit()
    test_search_command_name()
    test_search_case_insensitive()
    test_search_no_matches()
    test_search_partial_match()
    test_all_topics()
    test_category_filter()
    test_category_filter_navigation()
    test_missing_topics_file()
    test_missing_topics_file_search()
    test_missing_topics_file_all()

    print(f"\n{PASS} passed, {FAIL} failed", file=sys.stderr)
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
