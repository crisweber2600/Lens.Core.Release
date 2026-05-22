#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tests for retrospective-ops.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = str(Path(__file__).parent.parent / "retrospective-ops.py")
PASS = 0
FAIL = 0


def run(args: list[str]) -> tuple[dict, int]:
    """Run the script and return (parsed JSON output, exit code)."""
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


def assert_false(name: str, actual):
    assert_eq(name, bool(actual), False)


def make_problems(entries: list[dict]) -> str:
    """Build a problems.md string from a list of problem dicts."""
    parts = []
    for e in entries:
        lines = [f"## Problem: {e.get('title', 'Test Problem')}"]
        lines.append(f"- **Phase:** {e.get('phase', 'dev')}")
        lines.append(f"- **Category:** {e.get('category', 'unknown')}")
        lines.append(f"- **Status:** {e.get('status', 'open')}")
        lines.append(f"- **Date:** {e.get('date', '2026-01-01')}")
        if "github_issue" in e:
            lines.append(f"- **GitHub Issue:** {e['github_issue']}")
        lines.append("")
        lines.append(e.get("description", "Problem description."))
        parts.append("\n".join(lines))
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

def test_analyze_multiple_problems():
    """analyze returns correct counts by phase and category."""
    print("test_analyze_multiple_problems", file=sys.stderr)
    entries = [
        {"phase": "techplan", "category": "requirements-gap", "status": "open"},
        {"phase": "businessplan", "category": "requirements-gap", "status": "open"},
        {"phase": "techplan", "category": "requirements-gap", "status": "resolved"},
        {"phase": "techplan", "category": "requirements-gap", "status": "open"},
        {"phase": "dev", "category": "execution-failure", "status": "resolved"},
        {"phase": "dev", "category": "execution-failure", "status": "resolved"},
        {"phase": "dev", "category": "execution-failure", "status": "open"},
        {"phase": "dev", "category": "technical-debt", "status": "resolved"},
        {"phase": "dev", "category": "technical-debt", "status": "resolved"},
        {"phase": "businessplan", "category": "process-gap", "status": "open"},
        {"phase": "finalizeplan", "category": "scope-creep", "status": "resolved"},
        {"phase": "dev", "category": "scope-creep", "status": "open"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        problems_file = Path(tmp) / "problems.md"
        problems_file.write_text(make_problems(entries))

        result, code = run(["analyze", "--problems-file", str(problems_file)])
        assert_eq("exit code 0", code, 0)
        assert_eq("status pass", result["status"], "pass")
        assert_eq("total", result["total"], 12)
        assert_eq("open", result["open"], 6)
        assert_eq("resolved", result["resolved"], 6)
        assert_eq("by_phase techplan", result["by_phase"].get("techplan"), 3)
        assert_eq("by_phase dev", result["by_phase"].get("dev"), 6)
        assert_eq("by_phase businessplan", result["by_phase"].get("businessplan"), 2)
        assert_eq("by_category requirements-gap", result["by_category"].get("requirements-gap"), 4)
        assert_eq("by_category execution-failure", result["by_category"].get("execution-failure"), 3)
        assert_eq("by_category technical-debt", result["by_category"].get("technical-debt"), 2)


def test_analyze_empty_problems():
    """analyze on empty problems.md returns zero counts."""
    print("test_analyze_empty_problems", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        problems_file = Path(tmp) / "problems.md"
        problems_file.write_text("# Problems\n\nNo problems yet.\n")

        result, code = run(["analyze", "--problems-file", str(problems_file)])
        assert_eq("exit code 0", code, 0)
        assert_eq("status pass", result["status"], "pass")
        assert_eq("total zero", result["total"], 0)
        assert_eq("open zero", result["open"], 0)
        assert_eq("resolved zero", result["resolved"], 0)
        assert_eq("patterns empty", result["patterns"], [])


def test_analyze_all_resolved():
    """analyze with only resolved problems counts correctly."""
    print("test_analyze_all_resolved", file=sys.stderr)
    entries = [
        {"phase": "dev", "category": "execution-failure", "status": "resolved"},
        {"phase": "dev", "category": "execution-failure", "status": "resolved"},
        {"phase": "techplan", "category": "execution-failure", "status": "resolved"},
        {"phase": "businessplan", "category": "requirements-gap", "status": "resolved"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        problems_file = Path(tmp) / "problems.md"
        problems_file.write_text(make_problems(entries))

        result, code = run(["analyze", "--problems-file", str(problems_file)])
        assert_eq("exit code 0", code, 0)
        assert_eq("total", result["total"], 4)
        assert_eq("open zero", result["open"], 0)
        assert_eq("resolved all", result["resolved"], 4)


def test_pattern_detection_threshold():
    """Category appearing 3+ times is detected as a pattern."""
    print("test_pattern_detection_threshold", file=sys.stderr)
    entries = [
        {"phase": "techplan", "category": "requirements-gap", "status": "open"},
        {"phase": "businessplan", "category": "requirements-gap", "status": "open"},
        {"phase": "techplan", "category": "requirements-gap", "status": "open"},
        # Below threshold: only 2 occurrences
        {"phase": "dev", "category": "execution-failure", "status": "open"},
        {"phase": "dev", "category": "execution-failure", "status": "open"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        problems_file = Path(tmp) / "problems.md"
        problems_file.write_text(make_problems(entries))

        result, code = run(["analyze", "--problems-file", str(problems_file)])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("one pattern detected", len(result["patterns"]), 1)
        assert_eq("pattern category", result["patterns"][0]["category"], "requirements-gap")
        assert_eq("pattern count", result["patterns"][0]["count"], 3)
        # execution-failure has only 2 — should NOT be in patterns
        pattern_cats = [p["category"] for p in result["patterns"]]
        assert_false("execution-failure not a pattern", "execution-failure" in pattern_cats)


def test_pattern_detection_exactly_three():
    """Exactly 3 occurrences of a category is a pattern."""
    print("test_pattern_detection_exactly_three", file=sys.stderr)
    entries = [
        {"phase": "dev", "category": "technical-debt", "status": "resolved"},
        {"phase": "dev", "category": "technical-debt", "status": "resolved"},
        {"phase": "finalizeplan", "category": "technical-debt", "status": "open"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        problems_file = Path(tmp) / "problems.md"
        problems_file.write_text(make_problems(entries))

        result, code = run(["analyze", "--problems-file", str(problems_file)])
        assert_eq("one pattern", len(result["patterns"]), 1)
        assert_eq("pattern count exactly 3", result["patterns"][0]["count"], 3)


def test_analyze_missing_file():
    """analyze with missing problems file exits 1."""
    print("test_analyze_missing_file", file=sys.stderr)
    result, code = run(["analyze", "--problems-file", "/nonexistent/path/problems.md"])
    assert_eq("exit code 1", code, 1)
    assert_eq("status fail", result["status"], "fail")
    assert_true("error contains problems_file_not_found", "problems_file_not_found" in result.get("error", ""))


# ---------------------------------------------------------------------------
# generate-report
# ---------------------------------------------------------------------------

def test_generate_report_creates_file():
    """generate-report creates retrospective.md at the specified path."""
    print("test_generate_report_creates_file", file=sys.stderr)
    entries = [
        {"phase": "techplan", "category": "requirements-gap", "status": "open"},
        {"phase": "businessplan", "category": "requirements-gap", "status": "resolved"},
        {"phase": "dev", "category": "requirements-gap", "status": "open"},
        {"phase": "dev", "category": "execution-failure", "status": "resolved"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        problems_file = Path(tmp) / "problems.md"
        problems_file.write_text(make_problems(entries))
        output_path = Path(tmp) / "feature-dir" / "retrospective.md"

        result, code = run([
            "generate-report",
            "--problems-file", str(problems_file),
            "--feature-id", "test-feature",
            "--output", str(output_path),
        ])
        assert_eq("exit code 0", code, 0)
        assert_eq("status pass", result["status"], "pass")
        assert_eq("report path matches", result["report_path"], str(output_path))
        assert_true("file created", output_path.exists())
        content = output_path.read_text()
        assert_true("has feature id in title", "test-feature" in content)
        assert_true("has findings section", "## Findings" in content)
        assert_true("has recommendations section", "## Recommendations" in content)


def test_generate_report_includes_pattern():
    """generate-report report references detected patterns."""
    print("test_generate_report_includes_pattern", file=sys.stderr)
    entries = [
        {"phase": "techplan", "category": "requirements-gap", "status": "open"},
        {"phase": "businessplan", "category": "requirements-gap", "status": "open"},
        {"phase": "techplan", "category": "requirements-gap", "status": "resolved"},
        {"phase": "dev", "category": "execution-failure", "status": "open"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        problems_file = Path(tmp) / "problems.md"
        problems_file.write_text(make_problems(entries))
        output_path = Path(tmp) / "retrospective.md"

        result, code = run([
            "generate-report",
            "--problems-file", str(problems_file),
            "--feature-id", "patterned-feature",
            "--output", str(output_path),
        ])
        assert_eq("patterns_found", result["patterns_found"], 1)
        assert_true("recommendations > 0", result["recommendations"] > 0)
        content = output_path.read_text()
        assert_true("requirements-gap mentioned", "requirements-gap" in content.lower())


def test_generate_report_open_problems_table():
    """generate-report includes open problems table when open problems exist."""
    print("test_generate_report_open_problems_table", file=sys.stderr)
    entries = [
        {"title": "Missing spec", "phase": "techplan", "category": "requirements-gap", "status": "open"},
        {"title": "Fixed bug", "phase": "dev", "category": "execution-failure", "status": "resolved"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        problems_file = Path(tmp) / "problems.md"
        problems_file.write_text(make_problems(entries))
        output_path = Path(tmp) / "retrospective.md"

        run([
            "generate-report",
            "--problems-file", str(problems_file),
            "--feature-id", "open-test",
            "--output", str(output_path),
        ])
        content = output_path.read_text()
        assert_true("open problems section", "## Open Problems" in content)
        assert_true("open problem title", "Missing spec" in content)
        assert_false("resolved in open table", "Fixed bug" in content)


def test_generate_report_missing_file():
    """generate-report exits 1 when problems file is missing."""
    print("test_generate_report_missing_file", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "generate-report",
            "--problems-file", "/no/such/file.md",
            "--feature-id", "x",
            "--output", str(Path(tmp) / "retro.md"),
        ])
        assert_eq("exit code 1", code, 1)
        assert_eq("status fail", result["status"], "fail")


# ---------------------------------------------------------------------------
# update-insights
# ---------------------------------------------------------------------------

def test_update_insights_creates_file():
    """update-insights creates insights.md if it doesn't exist."""
    print("test_update_insights_creates_file", file=sys.stderr)
    patterns = [
        {"category": "requirements-gap", "count": 4, "phases": ["techplan", "businessplan"], "pattern": "repeated in planning phases"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        insights_path = Path(tmp) / "insights.md"
        assert_false("file does not exist before", insights_path.exists())

        result, code = run([
            "update-insights",
            "--insights-file", str(insights_path),
            "--patterns", json.dumps(patterns),
            "--feature-id", "new-feature",
        ])
        assert_eq("exit code 0", code, 0)
        assert_eq("status pass", result["status"], "pass")
        assert_eq("new_patterns", result["new_patterns"], 1)
        assert_true("file now exists", insights_path.exists())
        content = insights_path.read_text()
        assert_true("has feature header", "new-feature" in content)
        assert_true("has pattern category", "requirements-gap" in content)


def test_update_insights_appends_not_overwrites():
    """update-insights appends to existing insights.md without overwriting."""
    print("test_update_insights_appends_not_overwrites", file=sys.stderr)
    patterns_1 = [
        {"category": "execution-failure", "count": 3, "phases": ["dev"], "pattern": "concentrated in dev phase"},
    ]
    patterns_2 = [
        {"category": "requirements-gap", "count": 4, "phases": ["techplan"], "pattern": "concentrated in techplan"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        insights_path = Path(tmp) / "insights.md"

        # First write
        run([
            "update-insights",
            "--insights-file", str(insights_path),
            "--patterns", json.dumps(patterns_1),
            "--feature-id", "feature-alpha",
        ])

        # Second write
        run([
            "update-insights",
            "--insights-file", str(insights_path),
            "--patterns", json.dumps(patterns_2),
            "--feature-id", "feature-beta",
        ])

        content = insights_path.read_text()
        assert_true("first feature present", "feature-alpha" in content)
        assert_true("second feature present", "feature-beta" in content)
        assert_true("first pattern present", "execution-failure" in content)
        assert_true("second pattern present", "requirements-gap" in content)


def test_update_insights_dry_run():
    """update-insights with --dry-run does not modify the file."""
    print("test_update_insights_dry_run", file=sys.stderr)
    patterns = [
        {"category": "technical-debt", "count": 3, "phases": ["dev"], "pattern": "concentrated in dev"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        insights_path = Path(tmp) / "insights.md"

        result, code = run([
            "update-insights",
            "--insights-file", str(insights_path),
            "--patterns", json.dumps(patterns),
            "--feature-id", "dry-feature",
            "--dry-run",
        ])
        assert_eq("exit code 0", code, 0)
        assert_eq("status pass", result["status"], "pass")
        assert_eq("dry_run flag true", result["dry_run"], True)
        assert_false("file NOT created in dry-run", insights_path.exists())
        assert_true("preview in output", "preview" in result)


def test_update_insights_missing_parent_dir():
    """update-insights exits 1 when parent directory does not exist."""
    print("test_update_insights_missing_parent_dir", file=sys.stderr)
    patterns = [{"category": "unknown", "count": 3, "phases": ["dev"], "pattern": "test"}]
    result, code = run([
        "update-insights",
        "--insights-file", "/nonexistent/path/to/insights.md",
        "--patterns", json.dumps(patterns),
        "--feature-id", "x",
    ])
    assert_eq("exit code 1", code, 1)
    assert_eq("status fail", result["status"], "fail")
    assert_true("error contains insights_dir_not_found", "insights_dir_not_found" in result.get("error", ""))


def test_update_insights_invalid_json():
    """update-insights exits 1 on invalid --patterns JSON."""
    print("test_update_insights_invalid_json", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        insights_path = Path(tmp) / "insights.md"
        result, code = run([
            "update-insights",
            "--insights-file", str(insights_path),
            "--patterns", "not valid json {{{",
            "--feature-id", "x",
        ])
        assert_eq("exit code 1", code, 1)
        assert_eq("status fail", result["status"], "fail")
        assert_true("error contains invalid_patterns_json", "invalid_patterns_json" in result.get("error", ""))


def test_update_insights_empty_patterns():
    """update-insights with empty patterns list creates file with zero patterns."""
    print("test_update_insights_empty_patterns", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        insights_path = Path(tmp) / "insights.md"
        result, code = run([
            "update-insights",
            "--insights-file", str(insights_path),
            "--patterns", "[]",
            "--feature-id", "no-patterns-feature",
        ])
        assert_eq("exit code 0", code, 0)
        assert_eq("new_patterns zero", result["new_patterns"], 0)
        assert_true("file created", insights_path.exists())
        content = insights_path.read_text()
        assert_true("feature id in file", "no-patterns-feature" in content)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_analyze_unknown_phase_and_category():
    """Problems with unrecognized phase/category are normalized to 'unknown'."""
    print("test_analyze_unknown_phase_and_category", file=sys.stderr)
    raw = """## Problem: Weird one
- **Phase:** invalid-phase
- **Category:** not-a-category
- **Status:** open
- **Date:** 2026-01-01

Something weird happened.
"""
    with tempfile.TemporaryDirectory() as tmp:
        problems_file = Path(tmp) / "problems.md"
        problems_file.write_text(raw)

        result, code = run(["analyze", "--problems-file", str(problems_file)])
        assert_eq("exit code 0", code, 0)
        assert_eq("total 1", result["total"], 1)
        # Phase and category normalized to 'unknown'
        assert_true("phase unknown", "unknown" in result["by_phase"])
        assert_true("category unknown", "unknown" in result["by_category"])


def test_analyze_github_issue_in_report():
    """Open problems with GitHub Issues appear in the report table."""
    print("test_analyze_github_issue_in_report", file=sys.stderr)
    entries = [
        {"title": "Missing auth spec", "phase": "techplan", "category": "requirements-gap",
         "status": "open", "github_issue": "#42"},
        {"title": "Login bug", "phase": "dev", "category": "execution-failure", "status": "open"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        problems_file = Path(tmp) / "problems.md"
        problems_file.write_text(make_problems(entries))
        output_path = Path(tmp) / "retrospective.md"

        run([
            "generate-report",
            "--problems-file", str(problems_file),
            "--feature-id", "issue-test",
            "--output", str(output_path),
        ])
        content = output_path.read_text()
        assert_true("github issue in table", "#42" in content)


if __name__ == "__main__":
    test_analyze_multiple_problems()
    test_analyze_empty_problems()
    test_analyze_all_resolved()
    test_pattern_detection_threshold()
    test_pattern_detection_exactly_three()
    test_analyze_missing_file()
    test_generate_report_creates_file()
    test_generate_report_includes_pattern()
    test_generate_report_open_problems_table()
    test_generate_report_missing_file()
    test_update_insights_creates_file()
    test_update_insights_appends_not_overwrites()
    test_update_insights_dry_run()
    test_update_insights_missing_parent_dir()
    test_update_insights_invalid_json()
    test_update_insights_empty_patterns()
    test_analyze_unknown_phase_and_category()
    test_analyze_github_issue_in_report()

    print(f"\n{'='*40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'='*40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
