#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tests for log-problem-ops.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = str(Path(__file__).parent.parent / "log-problem-ops.py")
PASS = 0
FAIL = 0

BASE_ARGS = [
    "--governance-repo", "",  # filled per-test
    "--feature-id", "test-feature",
    "--domain", "core",
    "--service", "api",
]


def run(args: list[str]) -> tuple[dict, int]:
    """Run the script and return (parsed JSON output, return code)."""
    result = subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout), result.returncode
    except json.JSONDecodeError:
        return {"error": result.stderr, "stdout": result.stdout}, result.returncode


def assert_eq(name: str, actual, expected) -> None:
    global PASS, FAIL
    if actual == expected:
        PASS += 1
        print(f"  ✓ {name}", file=sys.stderr)
    else:
        FAIL += 1
        print(f"  ✗ {name}: expected {expected!r}, got {actual!r}", file=sys.stderr)


def assert_true(name: str, actual) -> None:
    assert_eq(name, bool(actual), True)


def assert_false(name: str, actual) -> None:
    assert_eq(name, bool(actual), False)


def log_args(tmp: str, **overrides) -> list[str]:
    """Build a standard log command args list."""
    defaults = {
        "governance_repo": tmp,
        "feature_id": "test-feature",
        "domain": "core",
        "service": "api",
        "phase": "dev",
        "category": "tech-debt",
        "title": "Test problem",
        "description": "A test problem description",
    }
    defaults.update(overrides)
    return [
        "log",
        "--governance-repo", defaults["governance_repo"],
        "--feature-id", defaults["feature_id"],
        "--domain", defaults["domain"],
        "--service", defaults["service"],
        "--phase", defaults["phase"],
        "--category", defaults["category"],
        "--title", defaults["title"],
        "--description", defaults["description"],
    ]


def resolve_args(tmp: str, entry_id: str, resolution: str = "Fixed it") -> list[str]:
    """Build a standard resolve command args list."""
    return [
        "resolve",
        "--governance-repo", tmp,
        "--feature-id", "test-feature",
        "--domain", "core",
        "--service", "api",
        "--entry-id", entry_id,
        "--resolution", resolution,
    ]


def list_args(tmp: str, **kwargs) -> list[str]:
    """Build a standard list command args list."""
    args = [
        "list",
        "--governance-repo", tmp,
        "--feature-id", "test-feature",
        "--domain", "core",
        "--service", "api",
    ]
    if "status" in kwargs:
        args += ["--status", kwargs["status"]]
    if "category" in kwargs:
        args += ["--category", kwargs["category"]]
    return args


def problems_path(tmp: str) -> Path:
    return Path(tmp) / "features" / "core" / "api" / "test-feature" / "problems.md"


# ── Tests ──────────────────────────────────────────────────────────────────


def test_log_creates_file():
    print("test_log_creates_file", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run(log_args(tmp))

        assert_eq("log status", result["status"], "pass")
        assert_eq("log exit code", code, 0)
        assert_true("entry_id present", result.get("entry_id", "").startswith("prob-"))
        assert_eq("problem status open", result["problem"]["status"], "open")

        path = problems_path(tmp)
        assert_eq("file created", path.exists(), True)

        content = path.read_text()
        assert_true("title in file", "Test problem" in content)
        assert_true("phase tagged", "dev" in content)
        assert_true("category tagged", "tech-debt" in content)
        assert_true("status open in file", "Status:** open" in content)
        assert_true("entry id in file", result["entry_id"] in content)


def test_log_appends_not_overwrites():
    print("test_log_appends_not_overwrites", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        run(log_args(tmp, title="First problem", description="First desc"))
        run(log_args(tmp, title="Second problem", description="Second desc"))

        content = problems_path(tmp).read_text()
        assert_eq("two entries", content.count("## Problem:"), 2)
        assert_true("first present", "First problem" in content)
        assert_true("second present", "Second problem" in content)


def test_resolve_problem():
    print("test_resolve_problem", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        log_result, _ = run(log_args(tmp, title="Resolve me", description="needs fix"))
        entry_id = log_result["entry_id"]

        result, code = run(resolve_args(tmp, entry_id, "Applied patch v2"))

        assert_eq("resolve status", result["status"], "pass")
        assert_eq("resolve exit code", code, 0)
        assert_eq("entry_id returned", result["entry_id"], entry_id)
        assert_eq("resolution returned", result["resolution"], "Applied patch v2")

        # Verify file was updated
        content = problems_path(tmp).read_text()
        assert_true("status resolved", "Status:** resolved" in content)
        assert_true("resolution text", "Applied patch v2" in content)


def test_list_all_open_resolved():
    print("test_list_all_open_resolved", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Log 3 problems
        r1, _ = run(log_args(tmp, title="Problem 1", description="d1"))
        r2, _ = run(log_args(tmp, title="Problem 2", description="d2"))
        run(log_args(tmp, title="Problem 3", description="d3"))

        # Resolve 1
        run(resolve_args(tmp, r1["entry_id"], "Fixed 1"))

        # List all
        result, code = run(list_args(tmp, status="all"))
        assert_eq("list all status", result["status"], "pass")
        assert_eq("list all total", result["total"], 3)
        assert_eq("list all open count", result["open"], 2)
        assert_eq("list all resolved count", result["resolved"], 1)
        assert_eq("list all exit code", code, 0)

        # List open only
        result, _ = run(list_args(tmp, status="open"))
        assert_eq("list open total", result["total"], 2)
        assert_eq("list open problems count", len(result["problems"]), 2)
        assert_true("all open statuses", all(p["status"] == "open" for p in result["problems"]))

        # List resolved only
        result, _ = run(list_args(tmp, status="resolved"))
        assert_eq("list resolved total", result["total"], 1)
        assert_eq("resolved entry_id", result["problems"][0]["entry_id"], r1["entry_id"])

        # List default (all)
        result, _ = run(list_args(tmp))
        assert_eq("list default total", result["total"], 3)

        # Resolve second; check counts update
        run(resolve_args(tmp, r2["entry_id"], "Fixed 2"))
        result, _ = run(list_args(tmp, status="all"))
        assert_eq("after 2nd resolve open", result["open"], 1)
        assert_eq("after 2nd resolve resolved", result["resolved"], 2)


def test_list_category_filter():
    print("test_list_category_filter", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        run(log_args(tmp, title="Tech debt 1", category="tech-debt"))
        run(log_args(tmp, title="Tech debt 2", category="tech-debt"))
        run(log_args(tmp, title="Scope creep 1", category="scope-creep"))
        run(log_args(tmp, title="Dep issue 1", category="dependency-issue"))

        result, _ = run(list_args(tmp, category="tech-debt"))
        assert_eq("tech-debt count", result["total"], 2)
        assert_true(
            "all tech-debt",
            all(p["category"] == "tech-debt" for p in result["problems"]),
        )

        result, _ = run(list_args(tmp, category="scope-creep"))
        assert_eq("scope-creep count", result["total"], 1)

        result, _ = run(list_args(tmp, category="process-breakdown"))
        assert_eq("no process-breakdown", result["total"], 0)

        # Category + status filter combined
        result, _ = run(list_args(tmp, status="open", category="tech-debt"))
        assert_eq("open tech-debt count", result["total"], 2)


def test_invalid_phase_rejected():
    print("test_invalid_phase_rejected", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run(log_args(tmp, phase="invalid-phase"))
        assert_eq("invalid phase status", result["status"], "fail")
        assert_eq("invalid phase exit code", code, 1)
        assert_true("error mentions phase", "phase" in result.get("error", "").lower())
        # File must NOT be created
        assert_false("file not created", problems_path(tmp).exists())


def test_invalid_category_rejected():
    print("test_invalid_category_rejected", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run(log_args(tmp, category="not-a-category"))
        assert_eq("invalid category status", result["status"], "fail")
        assert_eq("invalid category exit code", code, 1)
        assert_true("error mentions category", "category" in result.get("error", "").lower())
        assert_false("file not created", problems_path(tmp).exists())


def test_path_traversal_rejected():
    print("test_path_traversal_rejected", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Path traversal in feature-id
        result, code = run(log_args(tmp, feature_id="../../etc/passwd"))
        assert_eq("traversal feature-id fail", result["status"], "fail")
        assert_eq("traversal exit code", code, 1)

        # Path traversal in domain
        result, code = run(log_args(tmp, domain="../../../root"))
        assert_eq("traversal domain fail", result["status"], "fail")

        # Path traversal in service
        result, code = run(log_args(tmp, service="../../secret"))
        assert_eq("traversal service fail", result["status"], "fail")

        # Uppercase (invalid)
        result, code = run(log_args(tmp, feature_id="MyFeature"))
        assert_eq("uppercase feature-id fail", result["status"], "fail")


def test_dry_run():
    print("test_dry_run", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run(log_args(tmp) + ["--dry-run"])

        assert_eq("dry-run status", result["status"], "pass")
        assert_eq("dry-run exit code", code, 0)
        assert_eq("dry-run flag", result.get("dry_run"), True)
        assert_true("entry_id present", result.get("entry_id", "").startswith("prob-"))
        # File must NOT be created
        assert_false("file not created", problems_path(tmp).exists())


def test_creates_missing_problems_md():
    print("test_creates_missing_problems_md", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Create only the feature directory — no problems.md yet
        feature_dir = Path(tmp) / "features" / "core" / "api" / "test-feature"
        feature_dir.mkdir(parents=True)
        assert_false("no problems.md yet", problems_path(tmp).exists())

        result, code = run(log_args(tmp))

        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("file created", problems_path(tmp).exists(), True)

        content = problems_path(tmp).read_text()
        assert_true("header present", "# Problems" in content)
        assert_true("entry present", "## Problem:" in content)


def test_list_missing_problems_md():
    print("test_list_missing_problems_md", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run(list_args(tmp))
        assert_eq("list missing file status", result["status"], "pass")
        assert_eq("total 0", result["total"], 0)
        assert_eq("open 0", result["open"], 0)
        assert_eq("resolved 0", result["resolved"], 0)
        assert_eq("empty problems", result["problems"], [])
        assert_eq("list exit code", code, 0)


def test_resolve_not_found():
    print("test_resolve_not_found", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Create a problem first
        run(log_args(tmp))

        # Try to resolve a non-existent entry
        result, code = run(resolve_args(tmp, "prob-99990101T000000Z"))
        assert_eq("resolve not found status", result["status"], "fail")
        assert_eq("resolve not found exit code", code, 1)
        assert_true("error mentions entry", "not found" in result.get("error", "").lower())


# ── Main ───────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    test_log_creates_file()
    test_log_appends_not_overwrites()
    test_resolve_problem()
    test_list_all_open_resolved()
    test_list_category_filter()
    test_invalid_phase_rejected()
    test_invalid_category_rejected()
    test_path_traversal_rejected()
    test_dry_run()
    test_creates_missing_problems_md()
    test_list_missing_problems_md()
    test_resolve_not_found()

    print(f"\n{'=' * 40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'=' * 40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
