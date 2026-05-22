#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for move-feature-ops.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SCRIPT = str(Path(__file__).parent.parent / "move-feature-ops.py")
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_feature(
    tmp: str,
    feature_id: str,
    domain: str,
    service: str,
    *,
    depends_on: list[str] | None = None,
    blocks: list[str] | None = None,
    related: list[str] | None = None,
) -> Path:
    """Create a minimal feature directory with feature.yaml in *tmp*."""
    feature_dir = Path(tmp) / "features" / domain / service / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "featureId": feature_id,
        "name": f"Feature {feature_id}",
        "domain": domain,
        "service": service,
        "phase": "preplan",
        "track": "quickplan",
        "dependencies": {
            "depends_on": depends_on or [],
            "blocks": blocks or [],
            "related": related or [],
        },
    }
    with open(feature_dir / "feature.yaml", "w") as f:
        yaml.dump(data, f)
    return feature_dir


def make_feature_index(tmp: str, entries: list[dict]) -> Path:
    """Create feature-index.yaml in *tmp*."""
    index_path = Path(tmp) / "feature-index.yaml"
    data = {"features": entries}
    with open(index_path, "w") as f:
        yaml.dump(data, f)
    return index_path


def add_sprint_plan(feature_dir: Path, stories: list[dict]) -> None:
    """Write a sprint-plan.yaml with given stories into *feature_dir*."""
    plan = {"stories": stories}
    with open(feature_dir / "sprint-plan.yaml", "w") as f:
        yaml.dump(plan, f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_validate_moveable_feature():
    """validate returns pass for a feature with no blockers."""
    print("test_validate_moveable_feature", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "auth-login", "platform", "identity")

        result, code = run([
            "validate",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--target-domain", "core",
            "--target-service", "sso",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("from domain", result["from"]["domain"], "platform")
        assert_eq("from service", result["from"]["service"], "identity")
        assert_eq("to domain", result["to"]["domain"], "core")
        assert_eq("to service", result["to"]["service"], "sso")
        assert_eq("no blockers", result["blockers"], [])
        assert_eq("no dependents", result["dependent_features"], [])


def test_validate_with_inprogress_stories():
    """validate returns fail when feature has in-progress dev stories."""
    print("test_validate_with_inprogress_stories", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_dir = make_feature(tmp, "auth-login", "platform", "identity")
        add_sprint_plan(feature_dir, [
            {"id": "story-1", "status": "in-progress", "title": "Implement login"},
        ])

        result, code = run([
            "validate",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--target-domain", "core",
            "--target-service", "sso",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)
        assert_true("blockers non-empty", result["blockers"])
        assert_true("blocker mentions story", any("story-1" in b for b in result["blockers"]))


def test_validate_done_stories_also_blocked():
    """validate returns fail when feature has done stories (dev work committed)."""
    print("test_validate_done_stories_also_blocked", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_dir = make_feature(tmp, "auth-login", "platform", "identity")
        add_sprint_plan(feature_dir, [
            {"id": "story-1", "status": "done", "title": "Implement login"},
        ])

        result, code = run([
            "validate",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--target-domain", "core",
            "--target-service", "sso",
        ])
        assert_eq("status fail on done", result["status"], "fail")
        assert_eq("exit code 1", code, 1)


def test_validate_target_already_exists():
    """validate returns fail when target path already exists."""
    print("test_validate_target_already_exists", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "auth-login", "platform", "identity")
        make_feature(tmp, "auth-login", "core", "sso")  # target already exists

        result, code = run([
            "validate",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--target-domain", "core",
            "--target-service", "sso",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)
        assert_true("blocker mentions target", any("already exists" in b for b in result["blockers"]))


def test_validate_detects_dependent_features():
    """validate lists features that depend on the feature being moved."""
    print("test_validate_detects_dependent_features", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "auth-login", "platform", "identity")
        make_feature(tmp, "user-portal", "apps", "web", depends_on=["auth-login"])

        result, code = run([
            "validate",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--target-domain", "core",
            "--target-service", "sso",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_true("dependent found", "user-portal" in result["dependent_features"])


def test_move_updates_directory_path():
    """move relocates the feature directory to the new domain/service path."""
    print("test_move_updates_directory_path", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "auth-login", "platform", "identity")
        old_dir = Path(tmp) / "features" / "platform" / "identity" / "auth-login"
        new_dir = Path(tmp) / "features" / "core" / "sso" / "auth-login"

        result, code = run([
            "move",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--target-domain", "core",
            "--target-service", "sso",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_false("old dir gone", old_dir.exists())
        assert_true("new dir exists", new_dir.exists())
        assert_true("feature.yaml exists at new path", (new_dir / "feature.yaml").exists())


def test_move_updates_feature_yaml():
    """move updates the domain and service fields in feature.yaml."""
    print("test_move_updates_feature_yaml", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "auth-login", "platform", "identity")

        result, code = run([
            "move",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--target-domain", "core",
            "--target-service", "sso",
        ])
        assert_eq("status pass", result["status"], "pass")

        new_yaml = Path(tmp) / "features" / "core" / "sso" / "auth-login" / "feature.yaml"
        with open(new_yaml) as f:
            data = yaml.safe_load(f)
        assert_eq("domain updated", data["domain"], "core")
        assert_eq("service updated", data["service"], "sso")
        assert_eq("featureId unchanged", data["featureId"], "auth-login")


def test_move_updates_feature_index():
    """move updates the domain and service fields in feature-index.yaml."""
    print("test_move_updates_feature_index", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "auth-login", "platform", "identity")
        make_feature_index(tmp, [
            {"id": "auth-login", "domain": "platform", "service": "identity"},
            {"id": "other-feature", "domain": "apps", "service": "web"},
        ])

        result, code = run([
            "move",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--target-domain", "core",
            "--target-service", "sso",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("index_updated true", result["index_updated"], True)

        index_path = Path(tmp) / "feature-index.yaml"
        with open(index_path) as f:
            index_data = yaml.safe_load(f)
        moved_entry = next(e for e in index_data["features"] if e["id"] == "auth-login")
        assert_eq("index domain updated", moved_entry["domain"], "core")
        assert_eq("index service updated", moved_entry["service"], "sso")

        # Other entry unchanged
        other_entry = next(e for e in index_data["features"] if e["id"] == "other-feature")
        assert_eq("other entry domain unchanged", other_entry["domain"], "apps")


def test_move_dry_run():
    """move with --dry-run previews changes without moving anything."""
    print("test_move_dry_run", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "auth-login", "platform", "identity")
        old_dir = Path(tmp) / "features" / "platform" / "identity" / "auth-login"
        new_dir = Path(tmp) / "features" / "core" / "sso" / "auth-login"

        result, code = run([
            "move",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--target-domain", "core",
            "--target-service", "sso",
            "--dry-run",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("dry_run flag", result.get("dry_run"), True)
        assert_true("old dir still exists", old_dir.exists())
        assert_false("new dir not created", new_dir.exists())


def test_patch_references_finds_and_replaces():
    """patch-references replaces old path strings in dependent feature files."""
    print("test_patch_references_finds_and_replaces", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Create the moved feature at its new location
        make_feature(tmp, "auth-login", "core", "sso")

        # Create a dependent feature with a reference to the old path
        dep_dir = make_feature(tmp, "user-portal", "apps", "web")
        ref_file = dep_dir / "tech-plan.md"
        ref_file.write_text(
            "Depends on features/platform/identity/auth-login for session tokens.\n"
        )

        result, code = run([
            "patch-references",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--old-path", "features/platform/identity/auth-login",
            "--new-path", "features/core/sso/auth-login",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("files_patched", result["files_patched"], 1)
        assert_eq("changes count", len(result["changes"]), 1)
        assert_true("change file correct", "tech-plan.md" in result["changes"][0]["file"])

        # Verify the file was actually updated
        updated_content = ref_file.read_text()
        assert_true("old path gone", "features/platform/identity/auth-login" not in updated_content)
        assert_true("new path present", "features/core/sso/auth-login" in updated_content)


def test_patch_references_dry_run():
    """patch-references with --dry-run reports changes without modifying files."""
    print("test_patch_references_dry_run", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "auth-login", "core", "sso")
        dep_dir = make_feature(tmp, "user-portal", "apps", "web")
        ref_file = dep_dir / "tech-plan.md"
        original = "Depends on features/platform/identity/auth-login.\n"
        ref_file.write_text(original)

        result, code = run([
            "patch-references",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--old-path", "features/platform/identity/auth-login",
            "--new-path", "features/core/sso/auth-login",
            "--dry-run",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("dry_run flag", result.get("dry_run"), True)
        assert_eq("files_patched reported", result["files_patched"], 1)

        # File must be unchanged
        assert_eq("file unchanged", ref_file.read_text(), original)


def test_invalid_target_domain():
    """validate and move reject target domains that are not valid slugs."""
    print("test_invalid_target_domain", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "auth-login", "platform", "identity")

        for invalid in ["Core_Platform", "UPPER", "has spaces"]:
            result, code = run([
                "validate",
                "--governance-repo", tmp,
                "--feature-id", "auth-login",
                "--target-domain", invalid,
                "--target-service", "sso",
            ])
            # "has spaces" is split by argparse into separate tokens; check status or error field
            status = result.get("status") or ("fail" if code != 0 else "pass")
            assert_eq(f"invalid domain '{invalid}' fails", status, "fail")


def test_invalid_target_domain_specific():
    """validate rejects uppercase target domain."""
    print("test_invalid_target_domain_specific", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "auth-login", "platform", "identity")

        result, code = run([
            "validate",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--target-domain", "CorePlatform",
            "--target-service", "sso",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)
        assert_true("error mentions invalid", "Invalid" in result.get("error", ""))


def test_feature_not_found():
    """validate and move return fail when the feature does not exist."""
    print("test_feature_not_found", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "validate",
            "--governance-repo", tmp,
            "--feature-id", "nonexistent-feature",
            "--target-domain", "core",
            "--target-service", "sso",
        ])
        assert_eq("validate status fail", result["status"], "fail")
        assert_eq("validate exit code 1", code, 1)
        assert_true("error mentions not found", "not found" in result.get("error", "").lower())

        result, code = run([
            "move",
            "--governance-repo", tmp,
            "--feature-id", "nonexistent-feature",
            "--target-domain", "core",
            "--target-service", "sso",
        ])
        assert_eq("move status fail", result["status"], "fail")
        assert_eq("move exit code 1", code, 1)


def test_patch_references_path_traversal_blocked():
    """patch-references rejects paths containing '..' to prevent directory traversal."""
    print("test_patch_references_path_traversal_blocked", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_feature(tmp, "auth-login", "core", "sso")

        result, code = run([
            "patch-references",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--old-path", "features/../../../etc/passwd",
            "--new-path", "features/core/sso/auth-login",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)
        assert_true("error mentions traversal", "traversal" in result.get("error", "").lower())


def test_patch_references_no_features_dir():
    """patch-references returns pass with 0 patched when features dir missing."""
    print("test_patch_references_no_features_dir", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "patch-references",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--old-path", "features/platform/identity/auth-login",
            "--new-path", "features/core/sso/auth-login",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("files_patched 0", result["files_patched"], 0)
        assert_eq("exit code 0", code, 0)


def test_move_blocks_with_done_story_file():
    """move returns fail when a story-*.yaml file has status done."""
    print("test_move_blocks_with_done_story_file", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_dir = make_feature(tmp, "auth-login", "platform", "identity")
        story_file = feature_dir / "story-001.yaml"
        with open(story_file, "w") as f:
            yaml.dump({"id": "story-001", "status": "done", "title": "Login page"}, f)

        result, code = run([
            "move",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--target-domain", "core",
            "--target-service", "sso",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)
        assert_true("error mentions stories", "story" in result.get("error", "").lower())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_validate_moveable_feature()
    test_validate_with_inprogress_stories()
    test_validate_done_stories_also_blocked()
    test_validate_target_already_exists()
    test_validate_detects_dependent_features()
    test_move_updates_directory_path()
    test_move_updates_feature_yaml()
    test_move_updates_feature_index()
    test_move_dry_run()
    test_patch_references_finds_and_replaces()
    test_patch_references_dry_run()
    test_invalid_target_domain()
    test_invalid_target_domain_specific()
    test_feature_not_found()
    test_patch_references_path_traversal_blocked()
    test_patch_references_no_features_dir()
    test_move_blocks_with_done_story_file()

    print(f"\n{'=' * 40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'=' * 40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
