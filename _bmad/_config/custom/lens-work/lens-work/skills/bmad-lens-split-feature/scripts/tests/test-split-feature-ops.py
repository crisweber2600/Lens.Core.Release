#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for split-feature-ops.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SCRIPT = str(Path(__file__).parent.parent / "split-feature-ops.py")
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
# Helpers
# ---------------------------------------------------------------------------


def make_sprint_plan(tmp: str, statuses: dict) -> str:
    """Write a sprint-plan.md with the given story-id -> status mapping."""
    plan_path = Path(tmp) / "sprint-plan.md"
    content = "# Sprint Plan\n\n```yaml\ndevelopment_status:\n"
    for story_id, status in statuses.items():
        content += f"  {story_id}: {status}\n"
    content += "```\n"
    plan_path.write_text(content, encoding="utf-8")
    return str(plan_path)


def make_sprint_plan_pure_yaml(tmp: str, statuses: dict) -> str:
    """Write a sprint-plan.md as pure YAML (development_status section)."""
    plan_path = Path(tmp) / "sprint-plan.yaml"
    data = {"development_status": statuses}
    plan_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return str(plan_path)


def make_story_file(stories_dir: Path, story_id: str, status: str) -> Path:
    """Create a story file with the given status in YAML front matter."""
    stories_dir.mkdir(parents=True, exist_ok=True)
    story_path = stories_dir / f"{story_id}.md"
    story_path.write_text(
        f"---\nstatus: {status}\ntitle: Story {story_id}\n---\n\n# {story_id}\n",
        encoding="utf-8",
    )
    return story_path


def create_source_feature(tmp: str, feature_id: str = "auth-login",
                           domain: str = "platform", service: str = "identity") -> Path:
    """Create a minimal source feature directory with a stories/ sub-dir."""
    feature_dir = Path(tmp) / "features" / domain / service / feature_id
    stories_dir = feature_dir / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)
    feature_yaml = {
        "featureId": feature_id,
        "name": "Auth Login",
        "domain": domain,
        "service": service,
        "phase": "dev",
        "track": "quickplan",
    }
    (feature_dir / "feature.yaml").write_text(yaml.dump(feature_yaml), encoding="utf-8")
    return feature_dir


# ---------------------------------------------------------------------------
# Tests: validate-split
# ---------------------------------------------------------------------------


def test_validate_split_all_pending():
    """All stories pending → pass, all eligible."""
    print("test_validate_split_all_pending", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        plan = make_sprint_plan(tmp, {"story-1": "pending", "story-2": "pending", "story-3": "done"})
        result, code = run([
            "validate-split",
            "--sprint-plan-file", plan,
            "--story-ids", "story-1,story-2,story-3",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("eligible count", len(result["eligible"]), 3)
        assert_eq("blocked empty", result["blocked"], [])
        assert_eq("blockers empty", result["blockers"], [])


def test_validate_split_with_in_progress():
    """One in-progress story → fail, lists blocked ID."""
    print("test_validate_split_with_in_progress", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        plan = make_sprint_plan(tmp, {"story-1": "pending", "story-2": "in-progress"})
        result, code = run([
            "validate-split",
            "--sprint-plan-file", plan,
            "--story-ids", "story-1,story-2",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)
        assert_eq("eligible has story-1", result["eligible"], ["story-1"])
        assert_eq("blocked count", len(result["blocked"]), 1)
        assert_eq("blocked id", result["blocked"][0]["id"], "story-2")
        assert_eq("blocked reason", result["blocked"][0]["reason"], "in-progress")
        assert_eq("blockers list", result["blockers"], ["story-2"])


def test_validate_split_mixed():
    """Mix of pending, in-progress, done → blocked lists only in-progress."""
    print("test_validate_split_mixed", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        plan = make_sprint_plan(tmp, {
            "story-1": "pending",
            "story-2": "in-progress",
            "story-3": "done",
            "story-4": "in-progress",
        })
        result, code = run([
            "validate-split",
            "--sprint-plan-file", plan,
            "--story-ids", "story-1,story-2,story-3,story-4",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("eligible count", len(result["eligible"]), 2)
        assert_true("story-1 eligible", "story-1" in result["eligible"])
        assert_true("story-3 eligible", "story-3" in result["eligible"])
        assert_eq("blocked count", len(result["blocked"]), 2)
        blocked_ids = {b["id"] for b in result["blocked"]}
        assert_true("story-2 blocked", "story-2" in blocked_ids)
        assert_true("story-4 blocked", "story-4" in blocked_ids)


def test_validate_split_unknown_story_is_eligible():
    """Story not in sprint plan is treated as eligible (status unknown)."""
    print("test_validate_split_unknown_story_is_eligible", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        plan = make_sprint_plan(tmp, {"story-1": "pending"})
        result, code = run([
            "validate-split",
            "--sprint-plan-file", plan,
            "--story-ids", "story-1,story-unknown",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("eligible count", len(result["eligible"]), 2)
        assert_true("unknown story eligible", "story-unknown" in result["eligible"])


def test_validate_split_pure_yaml_sprint_plan():
    """Sprint plan as pure YAML file is parsed correctly."""
    print("test_validate_split_pure_yaml_sprint_plan", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        plan = make_sprint_plan_pure_yaml(tmp, {"story-a": "pending", "story-b": "in-progress"})
        result, code = run([
            "validate-split",
            "--sprint-plan-file", plan,
            "--story-ids", "story-a,story-b",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("story-b blocked", result["blockers"], ["story-b"])


def test_validate_split_json_array_story_ids():
    """Story IDs can be passed as JSON array."""
    print("test_validate_split_json_array_story_ids", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        plan = make_sprint_plan(tmp, {"s1": "done", "s2": "pending"})
        result, code = run([
            "validate-split",
            "--sprint-plan-file", plan,
            "--story-ids", '["s1","s2"]',
        ])
        assert_eq("json array pass", result["status"], "pass")
        assert_eq("eligible count", len(result["eligible"]), 2)


# ---------------------------------------------------------------------------
# Tests: create-split-feature
# ---------------------------------------------------------------------------


def test_create_split_feature_creates_feature_yaml():
    """create-split-feature writes a valid feature.yaml."""
    print("test_create_split_feature_creates_feature_yaml", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create-split-feature",
            "--governance-repo", tmp,
            "--source-feature-id", "auth-login",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--new-feature-id", "auth-mfa",
            "--new-name", "MFA Authentication",
            "--track", "quickplan",
            "--username", "testuser",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("new_feature_id", result["new_feature_id"], "auth-mfa")

        feature_yaml_path = Path(tmp) / "features" / "platform" / "identity" / "auth-mfa" / "feature.yaml"
        assert_true("feature.yaml exists", feature_yaml_path.exists())

        with open(feature_yaml_path) as f:
            data = yaml.safe_load(f)
        assert_eq("featureId", data["featureId"], "auth-mfa")
        assert_eq("name", data["name"], "MFA Authentication")
        assert_eq("phase", data["phase"], "preplan")
        assert_eq("track", data["track"], "quickplan")
        assert_eq("split_from", data["split_from"], "auth-login")
        assert_eq("team lead", data["team"][0]["username"], "testuser")
        assert_eq("team role", data["team"][0]["role"], "lead")


def test_create_split_feature_updates_feature_index():
    """create-split-feature updates feature-index.yaml."""
    print("test_create_split_feature_updates_feature_index", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create-split-feature",
            "--governance-repo", tmp,
            "--source-feature-id", "auth-login",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--new-feature-id", "auth-reset",
            "--new-name", "Password Reset",
            "--track", "full",
            "--username", "testuser",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_true("index_updated", result["index_updated"])

        index_path = Path(tmp) / "feature-index.yaml"
        assert_true("index file exists", index_path.exists())

        with open(index_path) as f:
            index = yaml.safe_load(f)
        features = index.get("features", [])
        assert_eq("features count", len(features), 1)
        entry = features[0]
        assert_eq("index featureId", entry["featureId"], "auth-reset")
        assert_eq("index status", entry["status"], "preplan")
        assert_eq("index split_from", entry["split_from"], "auth-login")


def test_create_split_feature_appends_to_existing_index():
    """create-split-feature appends to an existing feature-index.yaml."""
    print("test_create_split_feature_appends_to_existing_index", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Pre-populate index with one entry
        index_path = Path(tmp) / "feature-index.yaml"
        existing_entry = {
            "featureId": "existing-feature",
            "name": "Existing",
            "domain": "core",
            "service": "api",
            "status": "dev",
        }
        index_path.write_text(yaml.dump({"features": [existing_entry]}), encoding="utf-8")

        run([
            "create-split-feature",
            "--governance-repo", tmp,
            "--source-feature-id", "existing-feature",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--new-feature-id", "split-child",
            "--new-name", "Split Child",
            "--track", "quickplan",
            "--username", "testuser",
        ])

        with open(index_path) as f:
            index = yaml.safe_load(f)
        features = index.get("features", [])
        assert_eq("both entries present", len(features), 2)
        ids = {f["featureId"] for f in features}
        assert_true("existing preserved", "existing-feature" in ids)
        assert_true("new added", "split-child" in ids)


def test_create_split_feature_writes_summary_stub():
    """create-split-feature writes a summary.md stub."""
    print("test_create_split_feature_writes_summary_stub", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        run([
            "create-split-feature",
            "--governance-repo", tmp,
            "--source-feature-id", "auth-login",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--new-feature-id", "auth-oauth",
            "--new-name", "OAuth Integration",
            "--track", "quickplan",
            "--username", "testuser",
        ])
        summary_path = Path(tmp) / "features" / "platform" / "identity" / "auth-oauth" / "summary.md"
        assert_true("summary.md exists", summary_path.exists())
        content = summary_path.read_text()
        assert_true("has feature id", "auth-oauth" in content)
        assert_true("has split_from", "auth-login" in content)


def test_create_split_feature_dry_run():
    """Dry-run returns plan without creating files."""
    print("test_create_split_feature_dry_run", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create-split-feature",
            "--governance-repo", tmp,
            "--source-feature-id", "auth-login",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--new-feature-id", "auth-mfa",
            "--new-name", "MFA Authentication",
            "--track", "quickplan",
            "--username", "testuser",
            "--dry-run",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("dry_run flag", result.get("dry_run"), True)
        assert_eq("new_feature_id", result["new_feature_id"], "auth-mfa")

        # No files should be created
        feature_yaml_path = Path(tmp) / "features" / "platform" / "identity" / "auth-mfa" / "feature.yaml"
        assert_false("no file created", feature_yaml_path.exists())


def test_create_split_feature_duplicate_fails():
    """create-split-feature fails if new feature already exists."""
    print("test_create_split_feature_duplicate_fails", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        args = [
            "create-split-feature",
            "--governance-repo", tmp,
            "--source-feature-id", "auth-login",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--new-feature-id", "auth-dup",
            "--new-name", "Dup",
            "--track", "quickplan",
            "--username", "testuser",
        ]
        run(args)  # first create
        result, code = run(args)  # second create
        assert_eq("duplicate fail", result["status"], "fail")
        assert_eq("duplicate exit code", code, 1)


def test_create_split_feature_invalid_id():
    """create-split-feature rejects invalid new feature ID."""
    print("test_create_split_feature_invalid_id", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create-split-feature",
            "--governance-repo", tmp,
            "--source-feature-id", "auth-login",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--new-feature-id", "INVALID ID with spaces!",
            "--new-name", "Bad Name",
            "--track", "quickplan",
            "--username", "testuser",
        ])
        assert_eq("invalid id fails", result["status"], "fail")
        assert_eq("invalid exit code", code, 1)
        assert_true("error mentions id", "new-feature-id" in result.get("error", ""))


# ---------------------------------------------------------------------------
# Tests: move-stories
# ---------------------------------------------------------------------------


def test_move_stories_moves_files():
    """move-stories moves story files to the target feature."""
    print("test_move_stories_moves_files", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        src_dir = create_source_feature(tmp, "auth-login", "platform", "identity")
        stories_dir = src_dir / "stories"
        make_story_file(stories_dir, "story-1", "pending")
        make_story_file(stories_dir, "story-2", "done")

        # Create target feature
        tgt_dir = Path(tmp) / "features" / "platform" / "identity" / "auth-mfa"
        (tgt_dir / "stories").mkdir(parents=True, exist_ok=True)

        result, code = run([
            "move-stories",
            "--governance-repo", tmp,
            "--source-feature-id", "auth-login",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--target-feature-id", "auth-mfa",
            "--target-domain", "platform",
            "--target-service", "identity",
            "--story-ids", "story-1,story-2",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("total_moved", result["total_moved"], 2)

        # Source files gone
        assert_false("story-1 gone from source", (stories_dir / "story-1.md").exists())
        assert_false("story-2 gone from source", (stories_dir / "story-2.md").exists())

        # Target files exist
        tgt_stories = tgt_dir / "stories"
        assert_true("story-1 at target", (tgt_stories / "story-1.md").exists())
        assert_true("story-2 at target", (tgt_stories / "story-2.md").exists())


def test_move_stories_dry_run():
    """Dry-run shows plan without moving files."""
    print("test_move_stories_dry_run", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        src_dir = create_source_feature(tmp, "auth-login", "platform", "identity")
        stories_dir = src_dir / "stories"
        make_story_file(stories_dir, "story-3", "pending")

        result, code = run([
            "move-stories",
            "--governance-repo", tmp,
            "--source-feature-id", "auth-login",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--target-feature-id", "auth-mfa",
            "--target-domain", "platform",
            "--target-service", "identity",
            "--story-ids", "story-3",
            "--dry-run",
        ])
        assert_eq("status pass", result["status"], "pass")
        assert_eq("exit code 0", code, 0)
        assert_eq("dry_run flag", result.get("dry_run"), True)
        assert_eq("total_moved", result["total_moved"], 1)

        # File must still be in source
        assert_true("story-3 still in source", (stories_dir / "story-3.md").exists())


def test_move_stories_blocks_in_progress():
    """move-stories fails if a story is in-progress."""
    print("test_move_stories_blocks_in_progress", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        src_dir = create_source_feature(tmp, "auth-login", "platform", "identity")
        stories_dir = src_dir / "stories"
        make_story_file(stories_dir, "story-good", "pending")
        make_story_file(stories_dir, "story-wip", "in-progress")

        result, code = run([
            "move-stories",
            "--governance-repo", tmp,
            "--source-feature-id", "auth-login",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--target-feature-id", "auth-mfa",
            "--target-domain", "platform",
            "--target-service", "identity",
            "--story-ids", "story-good,story-wip",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)
        assert_true("blocked present", len(result.get("blocked", [])) > 0)
        blocked_ids = {b["id"] for b in result.get("blocked", [])}
        assert_true("story-wip in blocked", "story-wip" in blocked_ids)
        assert_eq("total_moved zero", result["total_moved"], 0)

        # Neither file should have moved
        assert_true("story-good still in source", (stories_dir / "story-good.md").exists())
        assert_true("story-wip still in source", (stories_dir / "story-wip.md").exists())


def test_move_stories_missing_story_fails():
    """move-stories fails if a specified story file doesn't exist."""
    print("test_move_stories_missing_story_fails", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        create_source_feature(tmp, "auth-login", "platform", "identity")

        result, code = run([
            "move-stories",
            "--governance-repo", tmp,
            "--source-feature-id", "auth-login",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--target-feature-id", "auth-mfa",
            "--target-domain", "platform",
            "--target-service", "identity",
            "--story-ids", "nonexistent-story",
        ])
        assert_eq("status fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)


def test_move_stories_invalid_source_id():
    """move-stories rejects invalid source feature ID (slug check)."""
    print("test_move_stories_invalid_source_id", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "move-stories",
            "--governance-repo", tmp,
            "--source-feature-id", "INVALID ID",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--target-feature-id", "auth-mfa",
            "--target-domain", "platform",
            "--target-service", "identity",
            "--story-ids", "story-1",
        ])
        assert_eq("invalid id fail", result["status"], "fail")
        assert_eq("exit code 1", code, 1)


# ---------------------------------------------------------------------------
# Tests: input validation (slug check)
# ---------------------------------------------------------------------------


def test_invalid_feature_id_rejected():
    """Invalid featureId (slug check) is rejected by create-split-feature."""
    print("test_invalid_feature_id_rejected", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # new-feature-id with uppercase
        result, code = run([
            "create-split-feature",
            "--governance-repo", tmp,
            "--source-feature-id", "auth-login",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--new-feature-id", "AuthMFA",
            "--new-name", "Auth MFA",
            "--track", "quickplan",
            "--username", "testuser",
        ])
        assert_eq("uppercase id rejected", result["status"], "fail")
        assert_eq("exit code 1", code, 1)

    with tempfile.TemporaryDirectory() as tmp:
        # new-feature-id with special characters (spaces → will fail slug check)
        result, code = run([
            "create-split-feature",
            "--governance-repo", tmp,
            "--source-feature-id", "auth-login",
            "--source-domain", "platform",
            "--source-service", "identity",
            "--new-feature-id", "bad..start!!",
            "--new-name", "Bad Start",
            "--track", "quickplan",
            "--username", "testuser",
        ])
        assert_eq("special-chars id rejected", result["status"], "fail")
        assert_eq("exit code 1", code, 1)


if __name__ == "__main__":
    test_validate_split_all_pending()
    test_validate_split_with_in_progress()
    test_validate_split_mixed()
    test_validate_split_unknown_story_is_eligible()
    test_validate_split_pure_yaml_sprint_plan()
    test_validate_split_json_array_story_ids()

    test_create_split_feature_creates_feature_yaml()
    test_create_split_feature_updates_feature_index()
    test_create_split_feature_appends_to_existing_index()
    test_create_split_feature_writes_summary_stub()
    test_create_split_feature_dry_run()
    test_create_split_feature_duplicate_fails()
    test_create_split_feature_invalid_id()

    test_move_stories_moves_files()
    test_move_stories_dry_run()
    test_move_stories_blocks_in_progress()
    test_move_stories_missing_story_fails()
    test_move_stories_invalid_source_id()

    test_invalid_feature_id_rejected()

    print(f"\n{'='*40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'='*40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
