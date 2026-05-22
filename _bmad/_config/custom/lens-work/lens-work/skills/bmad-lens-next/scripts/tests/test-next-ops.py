#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for next-ops.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SCRIPT = str(Path(__file__).parent.parent / "next-ops.py")
PASS = 0
FAIL = 0


def run(args: list[str]) -> tuple[dict, int]:
    """Run the script and return (parsed JSON, exit code)."""
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


def make_feature(
    tmp: str,
    feature_id: str,
    phase: str = "preplan",
    track: str = "full",
    extra: dict | None = None,
) -> Path:
    """Write a minimal feature.yaml into the temp governance repo."""
    domain = "core"
    service = "api"
    feature_dir = Path(tmp) / "features" / domain / service / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "featureId": feature_id,
        "name": f"Test {feature_id}",
        "description": "",
        "domain": domain,
        "service": service,
        "phase": phase,
        "track": track,
        "milestones": {
            "businessplan": None,
            "techplan": None,
            "finalizeplan": None,
            "dev-ready": None,
            "dev-complete": None,
        },
        "team": [{"username": "testuser", "role": "lead"}],
        "dependencies": {"depends_on": [], "depended_by": []},
        "target_repos": [],
        "links": {"retrospective": None, "issues": [], "pull_request": None},
        "priority": "medium",
        "created": "2026-04-06T00:00:00Z",
        "updated": "2026-04-06T00:00:00Z",
        "phase_transitions": [{"phase": "preplan", "timestamp": "2026-04-06T00:00:00Z", "user": "testuser"}],
    }
    if extra:
        data.update(extra)
    with open(feature_dir / "feature.yaml", "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return feature_dir / "feature.yaml"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_preplan_phase():
    """Preplan phase → recommends preplan."""
    print("test_preplan_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "preplan-feat", phase="preplan")
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "preplan-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("action preplan", result["recommendation"]["action"], "preplan")
        assert_eq("command", result["recommendation"]["command"], "/preplan")
        assert_eq("no blockers", result["recommendation"]["blockers"], [])


def test_dev_phase():
    """Dev phase → recommends dev."""
    print("test_dev_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(
            tmp,
            "dev-feat",
            phase="dev",
            extra={
                "milestones": {
                    "businessplan": "2026-04-01T00:00:00Z",
                    "techplan": "2026-04-02T00:00:00Z",
                    "finalizeplan": "2026-04-03T00:00:00Z",
                    "dev-ready": None,
                    "dev-complete": None,
                }
            },
        )
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "dev-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("action dev", result["recommendation"]["action"], "dev")
        assert_eq("command", result["recommendation"]["command"], "/dev")
        assert_eq("phase in output", result["phase"], "dev")


def test_complete_phase():
    """Complete phase → recommends complete."""
    print("test_complete_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(
            tmp,
            "done-feat",
            phase="complete",
            extra={
                "milestones": {
                    "businessplan": "2026-04-01T00:00:00Z",
                    "techplan": "2026-04-02T00:00:00Z",
                    "finalizeplan": "2026-04-03T00:00:00Z",
                    "dev-ready": "2026-04-04T00:00:00Z",
                    "dev-complete": "2026-04-05T00:00:00Z",
                }
            },
        )
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "done-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("action complete", result["recommendation"]["action"], "complete")
        assert_eq("command", result["recommendation"]["command"], "/complete")
        assert_eq("no blockers", result["recommendation"]["blockers"], [])


def test_preplan_complete_auto_advance():
    """preplan-complete → auto-advances to businessplan."""
    print("test_preplan_complete_auto_advance", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "advance-feat", phase="preplan-complete")
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "advance-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("action businessplan", result["recommendation"]["action"], "businessplan")
        assert_eq("command", result["recommendation"]["command"], "/businessplan")


def test_businessplan_complete_auto_advance():
    """businessplan-complete → auto-advances to techplan."""
    print("test_businessplan_complete_auto_advance", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(
            tmp,
            "bp-complete-feat",
            phase="businessplan-complete",
            extra={
                "milestones": {
                    "businessplan": "2026-04-01T00:00:00Z",
                    "techplan": None,
                    "finalizeplan": None,
                    "dev-ready": None,
                    "dev-complete": None,
                }
            },
        )
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "bp-complete-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("action techplan", result["recommendation"]["action"], "techplan")
        assert_eq("command", result["recommendation"]["command"], "/techplan")
        assert_eq("no blockers", result["recommendation"]["blockers"], [])


def test_expressplan_phase():
    """ExpressPlan phase → recommends expressplan."""
    print("test_expressplan_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "express-feat", phase="expressplan", track="express")
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "express-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("action expressplan", result["recommendation"]["action"], "expressplan")
        assert_eq("command", result["recommendation"]["command"], "/expressplan")


def test_expressplan_complete_auto_advance():
    """expressplan-complete → auto-advances to finalizeplan (not dev)."""
    print("test_expressplan_complete_auto_advance", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "express-complete-feat", phase="expressplan-complete", track="express")
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "express-complete-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("action finalizeplan", result["recommendation"]["action"], "finalizeplan")
        assert_eq("command", result["recommendation"]["command"], "/finalizeplan")


def test_paused_phase():
    """Paused phase → recommends pause-resume."""
    print("test_paused_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "paused-feat", phase="paused", extra={"paused_from": "techplan"})
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "paused-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("action pause-resume", result["recommendation"]["action"], "pause-resume")
        assert_eq("command", result["recommendation"]["command"], "/pause-resume")


def test_unknown_phase_falls_back_to_help():
    """Unknown phases fall back to /help instead of the removed status command."""
    print("test_unknown_phase_falls_back_to_help", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "unknown-feat", phase="mystery-phase")
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "unknown-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("action help", result["recommendation"]["action"], "help")
        assert_eq("command", result["recommendation"]["command"], "/help")


def test_missing_phase_uses_track_start_phase():
    """Missing phase falls back to the lifecycle start phase for the track."""
    print("test_missing_phase_uses_track_start_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "missing-phase-feat", phase="", track="express")
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "missing-phase-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("phase expressplan", result["phase"], "expressplan")
        assert_eq("action expressplan", result["recommendation"]["action"], "expressplan")


def test_hotfix_track_skips_businessplan_blocker():
    """Techplan on a hotfix track should not require a businessplan milestone."""
    print("test_hotfix_track_skips_businessplan_blocker", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "hotfix-feat", phase="techplan", track="hotfix")
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "hotfix-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("no blockers", result["recommendation"]["blockers"], [])


def test_stale_context_warning():
    """context.stale=true → warning included in recommendation."""
    print("test_stale_context_warning", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "stale-feat", phase="preplan", extra={"context": {"stale": True}})
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "stale-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        warnings = result["recommendation"]["warnings"]
        assert_true("stale warning present", any("context.stale" in w for w in warnings))


def test_feature_not_found():
    """Feature not found → status=fail, exit code 1."""
    print("test_feature_not_found", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "ghost-feat"])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)
        assert_true("error message", "ghost-feat" in result.get("error", ""))


def test_path_traversal_rejected():
    """Path-traversal feature-id → status=fail, exit code 1."""
    print("test_path_traversal_rejected", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "../etc/passwd"])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)
        assert_true("error message", "Invalid feature-id" in result.get("error", ""))


def test_valid_action_command_returned():
    """Dev phase returns a valid non-empty command string."""
    print("test_valid_action_command_returned", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(
            tmp,
            "cmd-feat",
            phase="dev",
            extra={
                "milestones": {
                    "businessplan": "2026-04-01T00:00:00Z",
                    "techplan": "2026-04-02T00:00:00Z",
                    "finalizeplan": "2026-04-03T00:00:00Z",
                    "dev-ready": None,
                    "dev-complete": None,
                }
            },
        )
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "cmd-feat"])
        assert_eq("exit code 0", code, 0)
        command = result["recommendation"]["command"]
        assert_true("command starts with /", command.startswith("/"))
        assert_true("command non-empty", len(command) > 1)


def test_businessplan_phase():
    """Businessplan phase → action=businessplan."""
    print("test_businessplan_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "bp-feat", phase="businessplan")
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "bp-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("action", result["recommendation"]["action"], "businessplan")
        assert_eq("command", result["recommendation"]["command"], "/businessplan")


def test_techplan_phase():
    """Techplan phase → action=techplan."""
    print("test_techplan_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(
            tmp,
            "tp-feat",
            phase="techplan",
            extra={
                "milestones": {
                    "businessplan": "2026-04-01T00:00:00Z",
                    "techplan": None,
                    "finalizeplan": None,
                    "dev-ready": None,
                    "dev-complete": None,
                }
            },
        )
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "tp-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("action", result["recommendation"]["action"], "techplan")
        assert_eq("command", result["recommendation"]["command"], "/techplan")
        assert_eq("no blockers (businessplan milestone set)", result["recommendation"]["blockers"], [])


def test_finalizeplan_phase():
    """FinalizePlan phase → action=finalizeplan."""
    print("test_finalizeplan_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(
            tmp,
            "fp-feat",
            phase="finalizeplan",
            extra={
                "milestones": {
                    "businessplan": "2026-04-01T00:00:00Z",
                    "techplan": "2026-04-02T00:00:00Z",
                    "finalizeplan": None,
                    "dev-ready": None,
                    "dev-complete": None,
                }
            },
        )
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "fp-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("action", result["recommendation"]["action"], "finalizeplan")
        assert_eq("command", result["recommendation"]["command"], "/finalizeplan")
        assert_eq("no blockers (techplan milestone set)", result["recommendation"]["blockers"], [])


def test_missing_entry_milestone_blocker():
    """Techplan phase with no businessplan milestone → blocker surfaced."""
    print("test_missing_entry_milestone_blocker", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "block-feat", phase="techplan")
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "block-feat"])
        assert_eq("status pass", result["status"], "pass")
        blockers = result["recommendation"]["blockers"]
        assert_true("blocker present", len(blockers) > 0)
        assert_true("blocker message", any("business plan" in b.lower() for b in blockers))


def test_open_issues_warning():
    """More than 3 open issues → warning included."""
    print("test_open_issues_warning", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(
            tmp,
            "issues-feat",
            phase="dev",
            extra={
                "milestones": {
                    "businessplan": "2026-04-01T00:00:00Z",
                    "techplan": "2026-04-02T00:00:00Z",
                    "finalizeplan": "2026-04-03T00:00:00Z",
                    "dev-ready": None,
                    "dev-complete": None,
                },
                "links": {
                    "retrospective": None,
                    "issues": ["issue-1", "issue-2", "issue-3", "issue-4"],
                    "pull_request": None,
                },
            },
        )
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "issues-feat"])
        assert_eq("status pass", result["status"], "pass")
        warnings = result["recommendation"]["warnings"]
        assert_true("issues warning present", any("open issues" in w for w in warnings))


def test_domain_service_fast_path():
    """Direct lookup via --domain/--service works without scanning."""
    print("test_domain_service_fast_path", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "fast-feat", phase="finalizeplan")
        result, code = run([
            "suggest",
            "--governance-repo", tmp,
            "--feature-id", "fast-feat",
            "--domain", "core",
            "--service", "api",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("action", result["recommendation"]["action"], "finalizeplan")


def test_feature_index_lookup():
    """Feature lookup via feature-index.yaml works when domain/service omitted."""
    print("test_feature_index_lookup", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "indexed-feat", phase="preplan")
        # Write a feature-index.yaml
        index_path = Path(tmp) / "feature-index.yaml"
        with open(index_path, "w") as f:
            yaml.dump(
                {"features": [{"featureId": "indexed-feat", "domain": "core", "service": "api"}]},
                f,
            )
        result, code = run(["suggest", "--governance-repo", tmp, "--feature-id", "indexed-feat"])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("action preplan", result["recommendation"]["action"], "preplan")


if __name__ == "__main__":
    test_preplan_phase()
    test_dev_phase()
    test_complete_phase()
    test_preplan_complete_auto_advance()
    test_businessplan_complete_auto_advance()
    test_expressplan_phase()
    test_paused_phase()
    test_missing_phase_uses_track_start_phase()
    test_hotfix_track_skips_businessplan_blocker()
    test_stale_context_warning()
    test_feature_not_found()
    test_path_traversal_rejected()
    test_valid_action_command_returned()
    test_businessplan_phase()
    test_techplan_phase()
    test_finalizeplan_phase()
    test_missing_entry_milestone_blocker()
    test_open_issues_warning()
    test_domain_service_fast_path()
    test_feature_index_lookup()

    print(f"\n{'='*40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'='*40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
