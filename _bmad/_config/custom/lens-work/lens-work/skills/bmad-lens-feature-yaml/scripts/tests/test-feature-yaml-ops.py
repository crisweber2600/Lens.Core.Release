#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for feature-yaml-ops.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SCRIPT = str(Path(__file__).parent.parent / "feature-yaml-ops.py")
PASS = 0
FAIL = 0


def run(args: list[str]) -> dict:
    """Run the script and return parsed JSON output."""
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


def test_create_and_read():
    print("test_create_and_read", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Create
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--name", "User Authentication",
            "--track", "quickplan",
            "--username", "testuser",
        ])
        assert_eq("create status", result["status"], "pass")
        assert_eq("create exit code", code, 0)
        assert_eq("featureId", result["data"]["featureId"], "auth-login")
        assert_eq("domain", result["data"]["domain"], "platform")
        assert_eq("service", result["data"]["service"], "identity")
        assert_eq("track", result["data"]["track"], "quickplan")
        assert_eq("team lead", result["data"]["team"][0]["role"], "lead")
        assert_eq(
            "docs.path",
            result["data"].get("docs", {}).get("path"),
            "docs/platform/identity/auth-login",
        )
        assert_eq(
            "docs.governance_docs_path",
            result["data"].get("docs", {}).get("governance_docs_path"),
            "features/platform/identity/auth-login/docs",
        )

        # Verify file exists
        feature_path = Path(tmp) / "features" / "platform" / "identity" / "auth-login" / "feature.yaml"
        assert_eq("file exists", feature_path.exists(), True)

        # Read
        result, code = run([
            "read",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
        ])
        assert_eq("read status", result["status"], "pass")
        assert_eq("read name", result["data"]["name"], "User Authentication")

        # Read specific field
        result, code = run([
            "read",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--field", "phase",
        ])
        assert_eq("read field status", result["status"], "pass")
        assert_eq("read field value", result["value"], "preplan")


def test_create_duplicate():
    print("test_create_duplicate", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        args = [
            "create",
            "--governance-repo", tmp,
            "--feature-id", "dup-test",
            "--domain", "core",
            "--service", "api",
            "--name", "Dup Test",
            "--track", "full",
            "--username", "testuser",
        ]
        run(args)
        result, code = run(args)
        assert_eq("duplicate fail", result["status"], "fail")
        assert_eq("duplicate exit code", code, 1)


def test_update_phase():
    print("test_update_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "phase-test",
            "--domain", "core",
            "--service", "api",
            "--name", "Phase Test",
            "--track", "full",
            "--username", "testuser",
        ])

        # Valid transition: preplan -> businessplan
        result, code = run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "phase-test",
            "--set", "phase=businessplan",
            "--username", "testuser",
        ])
        assert_eq("valid transition status", result["status"], "pass")

        # Invalid transition: businessplan -> dev (skipping techplan on full track)
        result, code = run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "phase-test",
            "--set", "phase=dev",
            "--username", "testuser",
        ])
        assert_eq("invalid transition fail", result["status"], "fail")
        assert_eq("invalid transition exit code", code, 1)


def test_update_phase_quickplan():
    print("test_update_phase_quickplan", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "qp-test",
            "--domain", "core",
            "--service", "api",
            "--name", "Quickplan Test",
            "--track", "quickplan",
            "--username", "testuser",
        ])

        # Quickplan allows skipping: preplan -> finalizeplan
        result, code = run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "qp-test",
            "--set", "phase=finalizeplan",
            "--username", "testuser",
        ])
        assert_eq("quickplan skip status", result["status"], "pass")
        assert_eq("quickplan skip exit code", code, 0)


def test_update_field():
    print("test_update_field", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "field-test",
            "--domain", "core",
            "--service", "api",
            "--name", "Field Test",
            "--track", "full",
            "--username", "testuser",
        ])

        result, code = run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "field-test",
            "--set", "priority=high",
            "--set", "description=Updated description",
        ])
        assert_eq("field update status", result["status"], "pass")
        assert_eq("changes count", len(result["changes"]), 2)

        # Verify the update persisted
        result, code = run([
            "read",
            "--governance-repo", tmp,
            "--feature-id", "field-test",
            "--field", "priority",
        ])
        assert_eq("updated priority", result["value"], "high")


def test_create_with_target_repos():
    print("test_create_with_target_repos", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "repo-test",
            "--domain", "plugins",
            "--service", "hermes",
            "--name", "Repo Test",
            "--track", "full",
            "--username", "testuser",
            "--target-repos", "https://github.com/example/Lens.Hermes",
        ])
        assert_eq("target repo create status", result["status"], "pass")
        assert_eq("target repo create exit code", code, 0)

        repo_entry = result["data"]["target_repos"][0]
        assert_eq("target repo name derived", repo_entry["name"], "Lens.Hermes")
        assert_eq("target repo url stored", repo_entry["url"], "https://github.com/example/Lens.Hermes")
        assert_eq("target repo remote_url stored", repo_entry["remote_url"], "https://github.com/example/Lens.Hermes")


def test_update_target_repos_json():
    print("test_update_target_repos_json", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "repo-update",
            "--domain", "plugins",
            "--service", "hermes",
            "--name", "Repo Update",
            "--track", "full",
            "--username", "testuser",
        ])

        payload = json.dumps([
            {
                "name": "Lens.Hermes",
                "url": "https://github.com/example/Lens.Hermes",
                "local_path": "TargetProjects/plugins/hermes/Lens.Hermes",
                "default_branch": "main",
                "visibility": "public",
            }
        ])
        result, code = run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "repo-update",
            "--set", f"target_repos={payload}",
            "--username", "testuser",
        ])
        assert_eq("target repos update status", result["status"], "pass")
        assert_eq("target repos update exit code", code, 0)

        result, code = run([
            "read",
            "--governance-repo", tmp,
            "--feature-id", "repo-update",
        ])
        repo_entry = result["data"]["target_repos"][0]
        assert_eq("target repo name kept", repo_entry["name"], "Lens.Hermes")
        assert_eq("target repo local path stored", repo_entry["local_path"], "TargetProjects/plugins/hermes/Lens.Hermes")
        assert_eq("target repo default branch stored", repo_entry["default_branch"], "main")
        assert_eq("target repo visibility stored", repo_entry["visibility"], "public")
        assert_eq("target repo compatibility url kept", repo_entry["remote_url"], "https://github.com/example/Lens.Hermes")


def test_validate_target_repo_local_path_warning():
    print("test_validate_target_repo_local_path_warning", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "repo-validate",
            "--domain", "plugins",
            "--service", "hermes",
            "--name", "Repo Validate",
            "--track", "full",
            "--username", "testuser",
        ])

        payload = json.dumps([
            {
                "url": "https://github.com/example/Lens.Hermes",
                "local_path": "plugins/hermes/Lens.Hermes",
            }
        ])
        run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "repo-validate",
            "--set", f"target_repos={payload}",
            "--username", "testuser",
        ])

        result, code = run([
            "validate",
            "--governance-repo", tmp,
            "--feature-id", "repo-validate",
        ])
        assert_eq("validate warns on noncanonical local path", result["status"], "warning")
        assert_eq("validate warning exit code", code, 0)
        assert_true(
            "local path warning present",
            any("local_path" in finding["issue"] for finding in result["findings"]),
        )


def test_validate_valid():
    print("test_validate_valid", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "valid-test",
            "--domain", "core",
            "--service", "api",
            "--name", "Valid Test",
            "--track", "full",
            "--username", "testuser",
        ])

        result, code = run([
            "validate",
            "--governance-repo", tmp,
            "--feature-id", "valid-test",
        ])
        assert_eq("validate pass", result["status"], "pass")
        assert_eq("no critical", result["summary"]["critical"], 0)


def test_validate_missing_fields():
    print("test_validate_missing_fields", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Create a malformed feature.yaml manually
        feature_dir = Path(tmp) / "features" / "core" / "api" / "bad-test"
        feature_dir.mkdir(parents=True)
        with open(feature_dir / "feature.yaml", "w") as f:
            yaml.dump({"featureId": "bad-test", "domain": "core", "service": "api"}, f)

        result, code = run([
            "validate",
            "--governance-repo", tmp,
            "--feature-id", "bad-test",
        ])
        assert_eq("validate fail", result["status"], "fail")
        assert_eq("has critical findings", result["summary"]["critical"] > 0, True)


def test_list():
    print("test_list", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Empty
        result, code = run(["list", "--governance-repo", tmp])
        assert_eq("empty list", result["total"], 0)

        # Create two features
        for fid in ["feat-a", "feat-b"]:
            run([
                "create",
                "--governance-repo", tmp,
                "--feature-id", fid,
                "--domain", "core",
                "--service", "api",
                "--name", f"Feature {fid}",
                "--track", "full",
                "--username", "testuser",
            ])

        result, code = run(["list", "--governance-repo", tmp])
        assert_eq("list count", result["total"], 2)


def test_read_not_found():
    print("test_read_not_found", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "read",
            "--governance-repo", tmp,
            "--feature-id", "nonexistent",
        ])
        assert_eq("not found fail", result["status"], "fail")
        assert_eq("not found exit code", code, 1)


def test_input_sanitization():
    """Verify path-traversal and invalid identifiers are rejected."""
    print("test_input_sanitization", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Path traversal attempt
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "../../etc/passwd",
            "--domain", "core",
            "--service", "api",
            "--name", "Evil",
            "--track", "full",
            "--username", "testuser",
        ])
        assert_eq("path traversal rejected", result["status"], "fail")
        assert_true("error mentions invalid", "Invalid" in result.get("error", ""))

        # Spaces in id
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "has spaces",
            "--domain", "core",
            "--service", "api",
            "--name", "Bad",
            "--track", "full",
            "--username", "testuser",
        ])
        assert_eq("spaces rejected", result["status"], "fail")

        # Uppercase rejected
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "CamelCase",
            "--domain", "core",
            "--service", "api",
            "--name", "Bad",
            "--track", "full",
            "--username", "testuser",
        ])
        assert_eq("uppercase rejected", result["status"], "fail")

        # Invalid domain
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "good-id",
            "--domain", "../evil",
            "--service", "api",
            "--name", "Bad",
            "--track", "full",
            "--username", "testuser",
        ])
        assert_eq("bad domain rejected", result["status"], "fail")

        # Valid id with dots and underscores
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "auth.login_v2",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Auth Login v2",
            "--track", "full",
            "--username", "testuser",
        ])
        assert_eq("dots and underscores accepted", result["status"], "pass")


def test_track_specific_transitions():
    """Verify track-specific phase transition rules."""
    print("test_track_specific_transitions", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Hotfix: preplan -> dev should be allowed
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "hotfix-test",
            "--domain", "core",
            "--service", "api",
            "--name", "Hotfix",
            "--track", "hotfix",
            "--username", "testuser",
        ])
        result, code = run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "hotfix-test",
            "--set", "phase=dev",
            "--username", "testuser",
        ])
        assert_eq("hotfix preplan->dev allowed", result["status"], "pass")

        # Spike: preplan -> dev should be allowed
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "spike-test",
            "--domain", "core",
            "--service", "api",
            "--name", "Spike",
            "--track", "spike",
            "--username", "testuser",
        ])
        result, code = run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "spike-test",
            "--set", "phase=dev",
            "--username", "testuser",
        ])
        assert_eq("spike preplan->dev allowed", result["status"], "pass")

        # Express: preplan -> expressplan allowed, preplan -> businessplan blocked
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "express-test",
            "--domain", "core",
            "--service", "api",
            "--name", "Express",
            "--track", "express",
            "--username", "testuser",
        ])
        result, code = run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "express-test",
            "--set", "phase=expressplan",
            "--username", "testuser",
        ])
        assert_eq("express preplan->expressplan allowed", result["status"], "pass")

        # Tech-change: preplan -> techplan allowed
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "techchange-test",
            "--domain", "core",
            "--service", "api",
            "--name", "Tech Change",
            "--track", "tech-change",
            "--username", "testuser",
        ])
        result, code = run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "techchange-test",
            "--set", "phase=techplan",
            "--username", "testuser",
        ])
        assert_eq("techchange preplan->techplan allowed", result["status"], "pass")

        # Full track: preplan -> dev should be blocked
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "full-strict",
            "--domain", "core",
            "--service", "api",
            "--name", "Full Strict",
            "--track", "full",
            "--username", "testuser",
        ])
        result, code = run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "full-strict",
            "--set", "phase=dev",
            "--username", "testuser",
        ])
        assert_eq("full preplan->dev blocked", result["status"], "fail")


def test_bidirectional_dependency_sync():
    """Verify dependency updates sync bidirectionally."""
    print("test_bidirectional_dependency_sync", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Create two features
        for fid in ["feat-upstream", "feat-downstream"]:
            run([
                "create",
                "--governance-repo", tmp,
                "--feature-id", fid,
                "--domain", "core",
                "--service", "api",
                "--name", f"Feature {fid}",
                "--track", "full",
                "--username", "testuser",
            ])

        # Set downstream depends on upstream
        result, code = run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "feat-downstream",
            "--set", "dependencies.depends_on=feat-upstream",
            "--username", "testuser",
        ])
        assert_eq("dep update status", result["status"], "pass")

        # Verify upstream now has downstream in depended_by
        result, code = run([
            "read",
            "--governance-repo", tmp,
            "--feature-id", "feat-upstream",
        ])
        depended_by = result["data"].get("dependencies", {}).get("depended_by", [])
        assert_true("bidirectional sync added", "feat-downstream" in depended_by)

        # Remove the dependency
        result, code = run([
            "update",
            "--governance-repo", tmp,
            "--feature-id", "feat-downstream",
            "--set", "dependencies.depends_on=",
            "--username", "testuser",
        ])
        assert_eq("dep remove status", result["status"], "pass")

        # Verify upstream no longer has downstream in depended_by
        result, code = run([
            "read",
            "--governance-repo", tmp,
            "--feature-id", "feat-upstream",
        ])
        depended_by = result["data"].get("dependencies", {}).get("depended_by", [])
        assert_eq("bidirectional sync removed", "feat-downstream" in depended_by, False)


def test_list_with_filters():
    """Verify list filtering by phase, domain, track."""
    print("test_list_with_filters", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Create features in different domains/tracks
        run([
            "create", "--governance-repo", tmp, "--feature-id", "f1",
            "--domain", "platform", "--service", "auth",
            "--name", "F1", "--track", "quickplan", "--username", "testuser",
        ])
        run([
            "create", "--governance-repo", tmp, "--feature-id", "f2",
            "--domain", "core", "--service", "api",
            "--name", "F2", "--track", "full", "--username", "testuser",
        ])
        run([
            "create", "--governance-repo", tmp, "--feature-id", "f3",
            "--domain", "platform", "--service", "billing",
            "--name", "F3", "--track", "full", "--username", "testuser",
        ])

        # Filter by domain
        result, code = run(["list", "--governance-repo", tmp, "--domain", "platform"])
        assert_eq("filter domain count", result["total"], 2)

        # Filter by track
        result, code = run(["list", "--governance-repo", tmp, "--track", "full"])
        assert_eq("filter track count", result["total"], 2)

        # Filter by domain + track
        result, code = run(["list", "--governance-repo", tmp, "--domain", "platform", "--track", "full"])
        assert_eq("filter domain+track count", result["total"], 1)

        # No match
        result, code = run(["list", "--governance-repo", tmp, "--domain", "nonexistent"])
        assert_eq("filter no match", result["total"], 0)


def test_validate_exit_code_warning():
    """Verify validate returns exit 0 for warning status (medium findings)."""
    print("test_validate_exit_code_warning", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Create two features where A depends on B but B doesn't know about A
        run([
            "create", "--governance-repo", tmp, "--feature-id", "dep-a",
            "--domain", "core", "--service", "api",
            "--name", "A", "--track", "full", "--username", "testuser",
        ])
        run([
            "create", "--governance-repo", tmp, "--feature-id", "dep-b",
            "--domain", "core", "--service", "api",
            "--name", "B", "--track", "full", "--username", "testuser",
        ])

        # Manually add dep without bidirectional sync
        feat_a_path = Path(tmp) / "features" / "core" / "api" / "dep-a" / "feature.yaml"
        with open(feat_a_path) as f:
            data = yaml.safe_load(f)
        data["dependencies"]["depends_on"] = ["dep-b"]
        with open(feat_a_path, "w") as f:
            yaml.dump(data, f)

        result, code = run([
            "validate", "--governance-repo", tmp, "--feature-id", "dep-a",
        ])
        assert_eq("validate warning status", result["status"], "warning")
        assert_eq("warning exit code 0", code, 0)


def test_yaml_parse_errors_surfaced():
    """Verify corrupted YAML files are reported in list, not silently swallowed."""
    print("test_yaml_parse_errors_surfaced", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        # Create a valid feature
        run([
            "create", "--governance-repo", tmp, "--feature-id", "good-one",
            "--domain", "core", "--service", "api",
            "--name", "Good", "--track", "full", "--username", "testuser",
        ])

        # Create a corrupted feature.yaml
        bad_dir = Path(tmp) / "features" / "core" / "api" / "corrupt-one"
        bad_dir.mkdir(parents=True)
        with open(bad_dir / "feature.yaml", "w") as f:
            f.write(":\n  bad: yaml: [\ninvalid\n")

        result, code = run(["list", "--governance-repo", tmp])
        assert_eq("list still works", result["total"], 1)
        assert_true("parse errors reported", "parse_errors" in result)
        assert_eq("parse error count", len(result["parse_errors"]), 1)


if __name__ == "__main__":
    test_create_and_read()
    test_create_duplicate()
    test_update_phase()
    test_update_phase_quickplan()
    test_update_field()
    test_create_with_target_repos()
    test_update_target_repos_json()
    test_validate_target_repo_local_path_warning()
    test_validate_valid()
    test_validate_missing_fields()
    test_list()
    test_read_not_found()
    test_input_sanitization()
    test_track_specific_transitions()
    test_bidirectional_dependency_sync()
    test_list_with_filters()
    test_validate_exit_code_warning()
    test_yaml_parse_errors_surfaced()

    print(f"\n{'='*40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'='*40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
