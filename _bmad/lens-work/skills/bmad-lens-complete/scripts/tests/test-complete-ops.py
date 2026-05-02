#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for complete-ops.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SCRIPT = str(Path(__file__).parent.parent / "complete-ops.py")
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


def assert_false(name: str, actual):
    assert_eq(name, bool(actual), False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_feature(tmp: str, feature_id: str, domain: str, service: str, phase: str = "dev") -> Path:
    """Create a minimal feature.yaml in the temp governance repo."""
    feature_dir = Path(tmp) / "features" / domain / service / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    feature_path = feature_dir / "feature.yaml"
    data = {
        "featureId": feature_id,
        "name": f"Test Feature {feature_id}",
        "domain": domain,
        "service": service,
        "phase": phase,
        "track": "quickplan",
        "priority": "medium",
        "created_at": "2026-01-01T00:00:00Z",
    }
    with open(feature_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return feature_path


def make_index(tmp: str, entries: list[dict]) -> Path:
    """Create a feature-index.yaml with the given entries."""
    index_path = Path(tmp) / "feature-index.yaml"
    data = {"features": entries}
    with open(index_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return index_path


def make_retrospective(tmp: str, feature_id: str, domain: str, service: str) -> Path:
    """Write a retrospective.md to the feature directory."""
    retro_path = Path(tmp) / "features" / domain / service / feature_id / "retrospective.md"
    retro_path.write_text("# Retrospective\n\nAll good.\n")
    return retro_path


# ---------------------------------------------------------------------------
# check-preconditions tests
# ---------------------------------------------------------------------------

def test_check_preconditions_dev_phase_pass():
    print("test_check_preconditions_dev_phase_pass", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "feat-dev", "platform", "api", phase="dev")
        make_retrospective(tmp, "feat-dev", "platform", "api")

        result, code = run([
            "check-preconditions",
            "--governance-repo", tmp,
            "--feature-id", "feat-dev",
            "--domain", "platform",
            "--service", "api",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("phase is dev", result["phase"], "dev")
        assert_eq("retrospective exists", result["retrospective_exists"], True)
        assert_eq("no blockers", result["blockers"], [])
        assert_eq("no issues", result["issues"], [])


def test_check_preconditions_preplan_blocker():
    print("test_check_preconditions_preplan_blocker", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "feat-preplan", "platform", "api", phase="preplan")

        result, code = run([
            "check-preconditions",
            "--governance-repo", tmp,
            "--feature-id", "feat-preplan",
            "--domain", "platform",
            "--service", "api",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)
        assert_true("has blockers", result["blockers"])
        assert_true("blocker mentions phase", any("preplan" in b for b in result["blockers"]))


def test_check_preconditions_missing_retrospective_warn():
    print("test_check_preconditions_missing_retrospective_warn", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "feat-no-retro", "platform", "api", phase="dev")
        # No retrospective.md

        result, code = run([
            "check-preconditions",
            "--governance-repo", tmp,
            "--feature-id", "feat-no-retro",
            "--domain", "platform",
            "--service", "api",
        ])
        assert_eq("status warn", result["status"], "warn")
        assert_eq("exit code 0 (warn is not fail)", code, 0)
        assert_eq("retrospective_exists false", result["retrospective_exists"], False)
        assert_true("has issue about retrospective", result["issues"])
        assert_eq("no blockers", result["blockers"], [])


def test_check_preconditions_complete_phase_pass():
    print("test_check_preconditions_complete_phase_pass", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "feat-complete", "platform", "api", phase="complete")
        make_retrospective(tmp, "feat-complete", "platform", "api")

        result, code = run([
            "check-preconditions",
            "--governance-repo", tmp,
            "--feature-id", "feat-complete",
            "--domain", "platform",
            "--service", "api",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("phase is complete", result["phase"], "complete")


# ---------------------------------------------------------------------------
# finalize tests
# ---------------------------------------------------------------------------

def test_finalize_updates_feature_yaml_phase():
    print("test_finalize_updates_feature_yaml_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_path = make_feature(tmp, "feat-fin", "core", "svc", phase="dev")
        make_index(tmp, [{"featureId": "feat-fin", "status": "active", "updated_at": "2026-01-01T00:00:00Z"}])

        result, code = run([
            "finalize",
            "--governance-repo", tmp,
            "--feature-id", "feat-fin",
            "--domain", "core",
            "--service", "svc",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("feature_id", result["feature_id"], "feat-fin")
        assert_true("archived_at set", result.get("archived_at"))

        # Verify feature.yaml was updated
        with open(feature_path) as f:
            updated = yaml.safe_load(f)
        assert_eq("phase updated to complete", updated["phase"], "complete")
        assert_true("completed_at set", updated.get("completed_at"))


def test_finalize_updates_feature_index():
    print("test_finalize_updates_feature_index", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "feat-idx", "core", "svc", phase="dev")
        index_path = make_index(tmp, [
            {"featureId": "feat-idx", "status": "active", "updated_at": "2026-01-01T00:00:00Z"},
            {"featureId": "other-feat", "status": "active", "updated_at": "2026-01-01T00:00:00Z"},
        ])

        result, code = run([
            "finalize",
            "--governance-repo", tmp,
            "--feature-id", "feat-idx",
            "--domain", "core",
            "--service", "svc",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("index_updated true", result["index_updated"], True)

        # Verify index was updated
        with open(index_path) as f:
            index = yaml.safe_load(f)
        entries = {e["featureId"]: e for e in index["features"]}
        assert_eq("feat-idx archived", entries["feat-idx"]["status"], "archived")
        assert_eq("other-feat unchanged", entries["other-feat"]["status"], "active")


def test_finalize_dry_run_no_changes():
    print("test_finalize_dry_run_no_changes", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_path = make_feature(tmp, "feat-dry", "core", "svc", phase="dev")
        original_mtime = feature_path.stat().st_mtime

        result, code = run([
            "finalize",
            "--governance-repo", tmp,
            "--feature-id", "feat-dry",
            "--domain", "core",
            "--service", "svc",
            "--dry-run",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("dry_run flag set", result.get("dry_run"), True)
        assert_eq("exit code 0", code, 0)

        # Verify feature.yaml was NOT modified
        new_mtime = feature_path.stat().st_mtime
        assert_eq("file not modified", new_mtime, original_mtime)

        # Verify feature still has original phase
        with open(feature_path) as f:
            data = yaml.safe_load(f)
        assert_eq("phase unchanged", data["phase"], "dev")


def test_finalize_writes_summary_md():
    print("test_finalize_writes_summary_md", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_path = make_feature(tmp, "feat-sum", "core", "svc", phase="dev")
        feature_dir = feature_path.parent

        run([
            "finalize",
            "--governance-repo", tmp,
            "--feature-id", "feat-sum",
            "--domain", "core",
            "--service", "svc",
        ])

        summary_path = feature_dir / "summary.md"
        assert_eq("summary.md written", summary_path.exists(), True)
        content = summary_path.read_text()
        assert_true("summary contains feature id", "feat-sum" in content)
        assert_true("summary contains archived header", "Archive Summary" in content)


# ---------------------------------------------------------------------------
# archive-status tests
# ---------------------------------------------------------------------------

def test_archive_status_completed_feature():
    print("test_archive_status_completed_feature", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_path = make_feature(tmp, "feat-done", "core", "svc", phase="complete")
        # Add completed_at
        with open(feature_path) as f:
            data = yaml.safe_load(f)
        data["completed_at"] = "2026-04-06T02:03:34Z"
        with open(feature_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        result, code = run([
            "archive-status",
            "--governance-repo", tmp,
            "--feature-id", "feat-done",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("archived true", result["archived"], True)
        assert_eq("phase complete", result["phase"], "complete")
        assert_eq("completed_at", result["completed_at"], "2026-04-06T02:03:34Z")


def test_archive_status_in_progress_feature():
    print("test_archive_status_in_progress_feature", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "feat-wip", "core", "svc", phase="dev")

        result, code = run([
            "archive-status",
            "--governance-repo", tmp,
            "--feature-id", "feat-wip",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("archived false", result["archived"], False)
        assert_eq("phase dev", result["phase"], "dev")


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

def test_feature_not_found_exits_1():
    print("test_feature_not_found_exits_1", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "check-preconditions",
            "--governance-repo", tmp,
            "--feature-id", "nonexistent-feature",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)
        assert_true("blockers mention not found", any("not found" in b for b in result.get("blockers", [])))


def test_finalize_feature_not_found_exits_1():
    print("test_finalize_feature_not_found_exits_1", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "finalize",
            "--governance-repo", tmp,
            "--feature-id", "ghost-feature",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)
        assert_true("error mentions not found", "not found" in result.get("error", ""))


def test_archive_status_not_found_exits_1():
    print("test_archive_status_not_found_exits_1", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "archive-status",
            "--governance-repo", tmp,
            "--feature-id", "ghost-feature",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    tests = [
        test_check_preconditions_dev_phase_pass,
        test_check_preconditions_preplan_blocker,
        test_check_preconditions_missing_retrospective_warn,
        test_check_preconditions_complete_phase_pass,
        test_finalize_updates_feature_yaml_phase,
        test_finalize_updates_feature_index,
        test_finalize_dry_run_no_changes,
        test_finalize_writes_summary_md,
        test_archive_status_completed_feature,
        test_archive_status_in_progress_feature,
        test_feature_not_found_exits_1,
        test_finalize_feature_not_found_exits_1,
        test_archive_status_not_found_exits_1,
    ]

    for test in tests:
        test()

    print(f"\n{'='*50}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)

    if FAIL > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
