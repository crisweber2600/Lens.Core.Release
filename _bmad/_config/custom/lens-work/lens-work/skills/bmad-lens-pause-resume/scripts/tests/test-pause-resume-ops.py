#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for pause-resume-ops.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SCRIPT = str(Path(__file__).parent.parent / "pause-resume-ops.py")
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


def make_feature(tmp: str, feature_id: str = "auth-login", domain: str = "platform",
                 service: str = "identity", phase: str = "techplan") -> Path:
    """Write a minimal feature.yaml for testing."""
    feature_dir = Path(tmp) / "features" / domain / service / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    feature_path = feature_dir / "feature.yaml"
    data = {
        "featureId": feature_id,
        "name": "Test Feature",
        "domain": domain,
        "service": service,
        "phase": phase,
        "track": "full",
        "priority": "medium",
        "created": "2026-04-01T00:00:00Z",
        "updated_at": "2026-04-01T00:00:00Z",
    }
    with open(feature_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return feature_path


def base_args(tmp: str, feature_id: str = "auth-login", domain: str = "platform",
              service: str = "identity") -> list[str]:
    return ["--governance-repo", tmp, "--feature-id", feature_id,
            "--domain", domain, "--service", service]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pause_feature():
    print("test_pause_feature", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, phase="techplan")

        result, code = run(["pause"] + base_args(tmp) + ["--reason", "Blocked on contract"])
        assert_eq("pause status", result["status"], "pass")
        assert_eq("pause exit code", code, 0)
        assert_eq("paused_from", result["paused_from"], "techplan")
        assert_eq("reason", result["reason"], "Blocked on contract")
        assert_true("paused_at set", result.get("paused_at"))

        # Verify file was updated
        feature_path = Path(tmp) / "features" / "platform" / "identity" / "auth-login" / "feature.yaml"
        with open(feature_path) as f:
            data = yaml.safe_load(f)
        assert_eq("phase in file", data["phase"], "paused")
        assert_eq("paused_from in file", data["paused_from"], "techplan")
        assert_eq("pause_reason in file", data["pause_reason"], "Blocked on contract")
        assert_true("paused_at in file", data.get("paused_at"))


def test_resume_feature():
    print("test_resume_feature", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, phase="techplan")

        # Pause first
        run(["pause"] + base_args(tmp) + ["--reason", "Taking a break"])

        # Resume
        result, code = run(["resume"] + base_args(tmp))
        assert_eq("resume status", result["status"], "pass")
        assert_eq("resume exit code", code, 0)
        assert_eq("resumed_to_phase", result["resumed_to_phase"], "techplan")
        assert_true("was_paused_since set", result.get("was_paused_since"))

        # Verify file was updated
        feature_path = Path(tmp) / "features" / "platform" / "identity" / "auth-login" / "feature.yaml"
        with open(feature_path) as f:
            data = yaml.safe_load(f)
        assert_eq("phase restored", data["phase"], "techplan")
        assert_eq("paused_from cleared", data.get("paused_from"), None)
        assert_eq("pause_reason cleared", data.get("pause_reason"), None)
        assert_eq("paused_at cleared", data.get("paused_at"), None)


def test_pause_already_paused():
    print("test_pause_already_paused", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, phase="techplan")
        run(["pause"] + base_args(tmp) + ["--reason", "First pause"])

        result, code = run(["pause"] + base_args(tmp) + ["--reason", "Second pause"])
        assert_eq("double-pause fail", result["status"], "fail")
        assert_eq("double-pause exit code", code, 1)
        assert_true("error mentions paused", "already paused" in result.get("error", "").lower())


def test_resume_non_paused():
    print("test_resume_non_paused", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, phase="dev")

        result, code = run(["resume"] + base_args(tmp))
        assert_eq("resume non-paused fail", result["status"], "fail")
        assert_eq("resume non-paused exit code", code, 1)
        assert_true("error mentions not paused", "not paused" in result.get("error", "").lower())


def test_pause_without_reason():
    print("test_pause_without_reason", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, phase="businessplan")

        # argparse makes --reason required, so omitting it produces a non-zero exit
        raw = subprocess.run(
            [sys.executable, SCRIPT, "pause",
             "--governance-repo", tmp, "--feature-id", "auth-login",
             "--domain", "platform", "--service", "identity"],
            capture_output=True, text=True,
        )
        assert_eq("missing reason exit code", raw.returncode, 2)

        # Empty string: argparse still passes it through, script rejects
        result, code = run(["pause"] + base_args(tmp) + ["--reason", "   "])
        assert_eq("blank reason fail", result["status"], "fail")
        assert_eq("blank reason exit code", code, 1)
        assert_true("error mentions reason", "reason" in result.get("error", "").lower())


def test_dry_run_pause():
    print("test_dry_run_pause", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_path = make_feature(tmp, phase="finalizeplan")
        with open(feature_path) as f:
            before = f.read()

        result, code = run(["pause"] + base_args(tmp) + ["--reason", "Dry run test", "--dry-run"])
        assert_eq("dry-run pause status", result["status"], "pass")
        assert_eq("dry-run pause exit code", code, 0)
        assert_eq("dry_run flag", result.get("dry_run"), True)

        # File must be unchanged
        with open(feature_path) as f:
            after = f.read()
        assert_eq("file unchanged after dry-run", before, after)


def test_dry_run_resume():
    print("test_dry_run_resume", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, phase="techplan")
        run(["pause"] + base_args(tmp) + ["--reason", "To dry-run resume"])

        feature_path = Path(tmp) / "features" / "platform" / "identity" / "auth-login" / "feature.yaml"
        with open(feature_path) as f:
            before = f.read()

        result, code = run(["resume"] + base_args(tmp) + ["--dry-run"])
        assert_eq("dry-run resume status", result["status"], "pass")
        assert_eq("dry_run flag", result.get("dry_run"), True)

        with open(feature_path) as f:
            after = f.read()
        assert_eq("file unchanged after dry-run resume", before, after)


def test_status_paused():
    print("test_status_paused", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, phase="dev")
        run(["pause"] + base_args(tmp) + ["--reason", "Waiting for review"])

        result, code = run(["status"] + base_args(tmp))
        assert_eq("status pass", result["status"], "pass")
        assert_eq("paused flag", result["paused"], True)
        assert_eq("phase", result["phase"], "paused")
        assert_eq("paused_from", result["paused_from"], "dev")
        assert_eq("pause_reason", result["pause_reason"], "Waiting for review")
        assert_true("paused_at", result.get("paused_at"))


def test_status_not_paused():
    print("test_status_not_paused", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, phase="preplan")

        result, code = run(["status"] + base_args(tmp))
        assert_eq("status pass", result["status"], "pass")
        assert_eq("not paused", result["paused"], False)
        assert_eq("phase", result["phase"], "preplan")
        assert_eq("paused_from empty", result["paused_from"], "")
        assert_eq("pause_reason empty", result["pause_reason"], "")
        assert_eq("paused_at empty", result["paused_at"], "")


def test_feature_not_found():
    print("test_feature_not_found", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        for subcmd in ["pause", "resume", "status"]:
            extra = ["--reason", "test"] if subcmd == "pause" else []
            result, code = run([subcmd, "--governance-repo", tmp,
                                 "--feature-id", "nonexistent",
                                 "--domain", "x", "--service", "y"] + extra)
            assert_eq(f"{subcmd} not-found fail", result["status"], "fail")
            assert_eq(f"{subcmd} not-found exit code", code, 1)


if __name__ == "__main__":
    test_pause_feature()
    test_resume_feature()
    test_pause_already_paused()
    test_resume_non_paused()
    test_pause_without_reason()
    test_dry_run_pause()
    test_dry_run_resume()
    test_status_paused()
    test_status_not_paused()
    test_feature_not_found()

    print(f"\n{'='*40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'='*40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
