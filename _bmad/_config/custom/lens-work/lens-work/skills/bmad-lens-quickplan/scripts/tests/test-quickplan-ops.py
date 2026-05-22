#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for quickplan-ops.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = str(Path(__file__).parent.parent / "quickplan-ops.py")
PASS = 0
FAIL = 0


def run(args: list[str]) -> tuple[dict, int]:
    """Run the script with given args and return (parsed_json, exit_code)."""
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


def make_plan_doc(doc_type: str) -> str:
    """Return a valid planning document with all required frontmatter fields."""
    return (
        "---\n"
        "feature: test-feature\n"
        f"doc_type: {doc_type}\n"
        "status: draft\n"
        "goal: Test the planning workflow\n"
        "key_decisions:\n"
        "  - Use Python\n"
        "  - Atomic commits\n"
        "open_questions:\n"
        "  - How to handle rollbacks?\n"
        "depends_on: []\n"
        "blocks: []\n"
        "updated_at: '2026-04-06T02:03:34Z'\n"
        "---\n"
        "\n"
        "# Test Plan\n"
        "\n"
        "Content goes here.\n"
    )


def test_validate_valid_frontmatter():
    print("test_validate_valid_frontmatter", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        doc_path = Path(tmp) / "business-plan.md"
        doc_path.write_text(make_plan_doc("business-plan"))

        result, code = run([
            "validate-frontmatter",
            "--file", str(doc_path),
            "--doc-type", "business-plan",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("no missing fields", result["missing_fields"], [])
        assert_eq("no issues", result["issues"], [])
        assert_eq("doc_type returned", result["doc_type"], "business-plan")


def test_validate_missing_required_fields():
    print("test_validate_missing_required_fields", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Missing 'goal' and 'blocks'
        content = (
            "---\n"
            "feature: test\n"
            "doc_type: tech-plan\n"
            "status: draft\n"
            "key_decisions: []\n"
            "open_questions: []\n"
            "depends_on: []\n"
            "updated_at: '2026-04-06T00:00:00Z'\n"
            "---\n"
            "\n"
            "# Doc\n"
        )
        doc_path = Path(tmp) / "tech-plan.md"
        doc_path.write_text(content)

        result, code = run([
            "validate-frontmatter",
            "--file", str(doc_path),
            "--doc-type", "tech-plan",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 2", code, 2)
        assert_true("missing goal reported", "goal" in result["missing_fields"])
        assert_true("missing blocks reported", "blocks" in result["missing_fields"])


def test_validate_invalid_doc_type():
    print("test_validate_invalid_doc_type", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Doc says business-plan but we validate as tech-plan
        doc_path = Path(tmp) / "plan.md"
        doc_path.write_text(make_plan_doc("business-plan"))

        result, code = run([
            "validate-frontmatter",
            "--file", str(doc_path),
            "--doc-type", "tech-plan",
        ])
        assert_eq("status fail on mismatch", result["status"], "fail")
        assert_eq("exit code 2", code, 2)
        assert_true("mismatch issue reported", any("mismatch" in i for i in result["issues"]))


def test_validate_unknown_doc_type_in_file():
    print("test_validate_unknown_doc_type_in_file", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        content = make_plan_doc("business-plan").replace(
            "doc_type: business-plan", "doc_type: unknown-type"
        )
        doc_path = Path(tmp) / "plan.md"
        doc_path.write_text(content)

        result, code = run([
            "validate-frontmatter",
            "--file", str(doc_path),
            "--doc-type", "business-plan",
        ])
        assert_eq("status fail for unknown type", result["status"], "fail")
        assert_eq("exit code 2", code, 2)
        assert_true("invalid doc_type issue present", any("Invalid doc_type" in i for i in result["issues"]))


def test_validate_invalid_iso_date():
    print("test_validate_invalid_iso_date", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        content = make_plan_doc("business-plan").replace(
            "updated_at: '2026-04-06T02:03:34Z'", "updated_at: not-a-date"
        )
        doc_path = Path(tmp) / "business-plan.md"
        doc_path.write_text(content)

        result, code = run([
            "validate-frontmatter",
            "--file", str(doc_path),
            "--doc-type", "business-plan",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 2", code, 2)
        assert_true("date issue reported", any("updated_at" in i for i in result["issues"]))


def test_validate_file_not_found():
    print("test_validate_file_not_found", file=sys.stderr)
    result, code = run([
        "validate-frontmatter",
        "--file", "/nonexistent/path/business-plan.md",
        "--doc-type", "business-plan",
    ])
    assert_eq("status fail", result["status"], "fail")
    assert_eq("exit code 1", code, 1)


def test_extract_summary_valid():
    print("test_extract_summary_valid", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        doc_path = Path(tmp) / "business-plan.md"
        doc_path.write_text(make_plan_doc("business-plan"))

        result, code = run([
            "extract-summary",
            "--file", str(doc_path),
            "--feature-id", "test-feature",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("feature", result["summary"]["feature"], "test-feature")
        assert_eq("goal", result["summary"]["goal"], "Test the planning workflow")
        assert_eq("doc_type", result["summary"]["doc_type"], "business-plan")
        assert_eq("status field", result["summary"]["status"], "draft")
        assert_true("key_decisions is list", isinstance(result["summary"]["key_decisions"], list))
        assert_true("open_questions is list", isinstance(result["summary"]["open_questions"], list))
        assert_eq("key_decisions count", len(result["summary"]["key_decisions"]), 2)


def test_extract_summary_file_not_found():
    print("test_extract_summary_file_not_found", file=sys.stderr)
    result, code = run([
        "extract-summary",
        "--file", "/nonexistent/plan.md",
        "--feature-id", "some-feature",
    ])
    assert_eq("status fail", result["status"], "fail")
    assert_eq("exit code 1", code, 1)


def test_check_plan_state_no_artifacts():
    print("test_check_plan_state_no_artifacts", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "check-plan-state",
            "--governance-repo", tmp,
            "--feature-id", "new-feature",
            "--domain", "core",
            "--service", "api",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("business_plan false", result["artifacts"]["business_plan"], False)
        assert_eq("tech_plan false", result["artifacts"]["tech_plan"], False)
        assert_eq("sprint_plan false", result["artifacts"]["sprint_plan"], False)
        assert_eq("stories false", result["artifacts"]["stories"], False)
        assert_eq("phase preplan", result["phase"], "preplan")


def test_check_plan_state_with_business_plan():
    print("test_check_plan_state_with_business_plan", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_dir = Path(tmp) / "features" / "core" / "api" / "my-feature"
        feature_dir.mkdir(parents=True)
        (feature_dir / "business-plan.md").write_text(make_plan_doc("business-plan"))

        result, code = run([
            "check-plan-state",
            "--governance-repo", tmp,
            "--feature-id", "my-feature",
            "--domain", "core",
            "--service", "api",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("business_plan true", result["artifacts"]["business_plan"], True)
        assert_eq("tech_plan false", result["artifacts"]["tech_plan"], False)
        assert_eq("phase businessplan", result["phase"], "businessplan")


def test_check_plan_state_tech_plan_phase():
    print("test_check_plan_state_tech_plan_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_dir = Path(tmp) / "features" / "platform" / "payments" / "billing-v2"
        feature_dir.mkdir(parents=True)
        (feature_dir / "business-plan.md").write_text(make_plan_doc("business-plan"))
        (feature_dir / "tech-plan.md").write_text(make_plan_doc("tech-plan"))

        result, code = run([
            "check-plan-state",
            "--governance-repo", tmp,
            "--feature-id", "billing-v2",
            "--domain", "platform",
            "--service", "payments",
        ])
        assert_eq("tech_plan true", result["artifacts"]["tech_plan"], True)
        assert_eq("phase techplan", result["phase"], "techplan")


def test_check_plan_state_all_artifacts():
    print("test_check_plan_state_all_artifacts", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_dir = Path(tmp) / "features" / "core" / "api" / "full-feature"
        feature_dir.mkdir(parents=True)
        (feature_dir / "business-plan.md").write_text(make_plan_doc("business-plan"))
        (feature_dir / "tech-plan.md").write_text(make_plan_doc("tech-plan"))
        (feature_dir / "sprint-plan.md").write_text(make_plan_doc("sprint-plan"))
        (feature_dir / "stories").mkdir()

        result, code = run([
            "check-plan-state",
            "--governance-repo", tmp,
            "--feature-id", "full-feature",
            "--domain", "core",
            "--service", "api",
        ])
        assert_eq("business_plan true", result["artifacts"]["business_plan"], True)
        assert_eq("tech_plan true", result["artifacts"]["tech_plan"], True)
        assert_eq("sprint_plan true", result["artifacts"]["sprint_plan"], True)
        assert_eq("stories true", result["artifacts"]["stories"], True)
        assert_eq("phase dev", result["phase"], "dev")


def test_path_traversal_feature_id():
    print("test_path_traversal_feature_id", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "check-plan-state",
            "--governance-repo", tmp,
            "--feature-id", "../evil",
            "--domain", "core",
            "--service", "api",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_true("non-zero exit code", code != 0)
        assert_true("issue reported", len(result.get("issues", [])) > 0)


def test_path_traversal_domain():
    print("test_path_traversal_domain", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "check-plan-state",
            "--governance-repo", tmp,
            "--feature-id", "my-feature",
            "--domain", "../evil",
            "--service", "api",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_true("non-zero exit code", code != 0)
        assert_true("issue reported", len(result.get("issues", [])) > 0)


def test_path_traversal_service():
    print("test_path_traversal_service", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "check-plan-state",
            "--governance-repo", tmp,
            "--feature-id", "my-feature",
            "--domain", "core",
            "--service", "../etc",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_true("non-zero exit code", code != 0)


if __name__ == "__main__":
    test_validate_valid_frontmatter()
    test_validate_missing_required_fields()
    test_validate_invalid_doc_type()
    test_validate_unknown_doc_type_in_file()
    test_validate_invalid_iso_date()
    test_validate_file_not_found()
    test_extract_summary_valid()
    test_extract_summary_file_not_found()
    test_check_plan_state_no_artifacts()
    test_check_plan_state_with_business_plan()
    test_check_plan_state_tech_plan_phase()
    test_check_plan_state_all_artifacts()
    test_path_traversal_feature_id()
    test_path_traversal_domain()
    test_path_traversal_service()

    print(f"\n{'='*40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'='*40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
