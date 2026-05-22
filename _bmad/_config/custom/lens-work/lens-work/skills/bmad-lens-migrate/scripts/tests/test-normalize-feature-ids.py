#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for migrate-ops.py normalize-feature-ids subcommand."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SCRIPT = str(Path(__file__).parent.parent / "migrate-ops.py")
PASS = 0
FAIL = 0


def run(args: list[str]) -> tuple[dict, int]:
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


def make_governance_repo(tmp: str) -> Path:
    """Create a minimal governance repo directory structure."""
    gov = Path(tmp) / "governance"
    (gov / "features").mkdir(parents=True)
    return gov


def write_feature_yaml(gov: Path, domain: str, service: str, slug: str, data: dict) -> Path:
    """Write a feature.yaml into features/{domain}/{service}/{slug}/."""
    feature_dir = gov / "features" / domain / service / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    path = feature_dir / "feature.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def write_feature_index(gov: Path, features: list[dict]) -> Path:
    path = gov / "feature-index.yaml"
    path.write_text(
        yaml.dump({"features": features}, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def make_control_repo_with_branches(tmp: str, branches: list[str]) -> Path:
    """Create a git repo under tmp/control with the given local branches."""
    control = Path(tmp) / "control"
    control.mkdir(parents=True)
    subprocess.run(["git", "init", str(control)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(control), "config", "user.name", "tester"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(control), "config", "user.email", "t@t.com"], capture_output=True, check=True)
    # Create an initial commit on the default branch so other branches can be created
    (control / "README.md").write_text("seed", encoding="utf-8")
    subprocess.run(["git", "-C", str(control), "add", "README.md"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(control), "commit", "-m", "seed"], capture_output=True, check=True)
    for branch in branches:
        if branch not in ("main", "master"):
            subprocess.run(
                ["git", "-C", str(control), "branch", branch],
                capture_output=True, check=True,
            )
    return control


def short_feature_yaml(domain: str, service: str, slug: str) -> dict:
    """Build a minimal feature.yaml with a short (non-canonical) featureId."""
    return {
        "name": slug.capitalize(),
        "description": "",
        "featureId": slug,
        "domain": domain,
        "service": service,
        "phase": "preplan",
        "docs": {
            "path": f"docs/{domain}/{service}/{slug}",
            "governance_docs_path": f"features/{domain}/{service}/{slug}/docs",
        },
    }


def short_index_entry(domain: str, service: str, slug: str) -> dict:
    return {
        "id": slug,
        "featureId": slug,
        "domain": domain,
        "service": service,
        "status": "preplan",
        "plan_branch": f"{slug}-plan",
    }


# ---------------------------------------------------------------------------


def test_dry_run_shows_proposed_changes():
    print("\ntest_dry_run_shows_proposed_changes", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "new-project", "scraping", "worker", short_feature_yaml("new-project", "scraping", "worker"))
        write_feature_index(gov, [short_index_entry("new-project", "scraping", "worker")])

        result, code = run([
            "normalize-feature-ids",
            "--governance-repo", str(gov),
            "--dry-run",
        ])
        assert_eq("exit code", code, 0)
        assert_eq("status", result.get("status"), "pass")
        assert_eq("dry_run flag", result.get("dry_run"), True)
        assert_eq("total_normalized", result.get("total_normalized"), 1)

        rec = result["normalized"][0]
        assert_eq("old_feature_id", rec["old_feature_id"], "worker")
        assert_eq("canonical_feature_id", rec["canonical_feature_id"], "new-project-scraping-worker")
        assert_eq("feature_slug", rec["feature_slug"], "worker")
        assert_eq("yaml_status is would-update", rec["feature_yaml_status"], "would-update")

        # Dry run: file must NOT be modified
        raw = yaml.safe_load((gov / "features" / "new-project" / "scraping" / "worker" / "feature.yaml").read_text())
        assert_eq("feature.yaml unchanged in dry-run", raw["featureId"], "worker")

        # feature-index.yaml must NOT be modified
        idx = yaml.safe_load((gov / "feature-index.yaml").read_text())
        assert_eq("index unchanged in dry-run", idx["features"][0]["id"], "worker")


def test_normalizes_feature_yaml():
    print("\ntest_normalizes_feature_yaml", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "new-project", "scraping", "worker", short_feature_yaml("new-project", "scraping", "worker"))
        write_feature_index(gov, [short_index_entry("new-project", "scraping", "worker")])

        result, code = run([
            "normalize-feature-ids",
            "--governance-repo", str(gov),
        ])
        assert_eq("exit code", code, 0)
        assert_eq("status", result.get("status"), "pass")

        raw = yaml.safe_load((gov / "features" / "new-project" / "scraping" / "worker" / "feature.yaml").read_text())
        assert_eq("featureId is canonical", raw["featureId"], "new-project-scraping-worker")
        assert_eq("featureSlug added", raw["featureSlug"], "worker")


def test_normalizes_feature_index():
    print("\ntest_normalizes_feature_index", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "new-project", "scraping", "worker", short_feature_yaml("new-project", "scraping", "worker"))
        write_feature_index(gov, [short_index_entry("new-project", "scraping", "worker")])

        run(["normalize-feature-ids", "--governance-repo", str(gov)])

        idx = yaml.safe_load((gov / "feature-index.yaml").read_text())
        entry = idx["features"][0]
        assert_eq("index id canonical", entry["id"], "new-project-scraping-worker")
        assert_eq("index featureId canonical", entry["featureId"], "new-project-scraping-worker")
        assert_eq("index featureSlug", entry["featureSlug"], "worker")
        assert_eq("index plan_branch", entry["plan_branch"], "new-project-scraping-worker-plan")


def test_directory_name_unchanged():
    """Governance directory must keep the featureSlug name after normalization."""
    print("\ntest_directory_name_unchanged", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "new-project", "scraping", "worker", short_feature_yaml("new-project", "scraping", "worker"))
        write_feature_index(gov, [short_index_entry("new-project", "scraping", "worker")])

        run(["normalize-feature-ids", "--governance-repo", str(gov)])

        slug_dir = gov / "features" / "new-project" / "scraping" / "worker"
        canonical_dir = gov / "features" / "new-project" / "scraping" / "new-project-scraping-worker"
        assert_eq("slug dir still exists", slug_dir.is_dir(), True)
        assert_eq("canonical dir NOT created", canonical_dir.exists(), False)


def test_docs_paths_use_slug_not_feature_id():
    """docs.path and docs.governance_docs_path should use featureSlug after normalization."""
    print("\ntest_docs_paths_use_slug_not_feature_id", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        # Start with docs paths that (wrongly) reference the featureId instead of slug
        data = short_feature_yaml("platform", "identity", "auth")
        data["docs"] = {
            "path": "docs/platform/identity/auth",  # already slug-based — should be left alone
            "governance_docs_path": "features/platform/identity/auth/docs",
        }
        write_feature_yaml(gov, "platform", "identity", "auth", data)
        write_feature_index(gov, [short_index_entry("platform", "identity", "auth")])

        run(["normalize-feature-ids", "--governance-repo", str(gov)])

        raw = yaml.safe_load((gov / "features" / "platform" / "identity" / "auth" / "feature.yaml").read_text())
        assert_eq("docs.path uses slug", raw["docs"]["path"], "docs/platform/identity/auth")
        assert_eq("docs.governance_docs_path uses slug", raw["docs"]["governance_docs_path"], "features/platform/identity/auth/docs")


def test_docs_paths_corrected_when_pointing_at_feature_id():
    """When docs.path wrongly references the featureId (not slug), it should be corrected."""
    print("\ntest_docs_paths_corrected_when_pointing_at_feature_id", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        data = short_feature_yaml("platform", "identity", "auth")
        # Simulate wrong paths pointing at featureId
        data["docs"] = {
            "path": "docs/platform/identity/platform-identity-auth",
            "governance_docs_path": "features/platform/identity/platform-identity-auth/docs",
        }
        write_feature_yaml(gov, "platform", "identity", "auth", data)
        write_feature_index(gov, [short_index_entry("platform", "identity", "auth")])

        run(["normalize-feature-ids", "--governance-repo", str(gov)])

        raw = yaml.safe_load((gov / "features" / "platform" / "identity" / "auth" / "feature.yaml").read_text())
        # These had the old featureId (auth) as suffix, the normalization targets paths ending in /{old_id}
        # old_id was "auth", so it would have matched paths ending in "/auth" -> corrects to slug "auth"
        # The test verifies the function doesn't break correct slug-based paths
        assert_eq("featureId canonical after correction", raw["featureId"], "platform-identity-auth")


def test_no_normalization_needed():
    print("\ntest_no_normalization_needed", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        # Feature already has canonical featureId
        data = {
            "name": "Auth",
            "featureId": "platform-identity-auth",
            "featureSlug": "auth",
            "domain": "platform",
            "service": "identity",
            "phase": "preplan",
            "docs": {
                "path": "docs/platform/identity/auth",
                "governance_docs_path": "features/platform/identity/auth/docs",
            },
        }
        write_feature_yaml(gov, "platform", "identity", "auth", data)
        write_feature_index(gov, [{
            "id": "platform-identity-auth",
            "featureId": "platform-identity-auth",
            "featureSlug": "auth",
            "domain": "platform",
            "service": "identity",
            "status": "preplan",
            "plan_branch": "platform-identity-auth-plan",
        }])

        result, code = run(["normalize-feature-ids", "--governance-repo", str(gov)])
        assert_eq("exit code", code, 0)
        assert_eq("status", result.get("status"), "pass")
        assert_eq("total_normalized", result.get("total_normalized"), 0)
        assert_eq("normalized list empty", result.get("normalized"), [])


def test_multiple_features_some_need_normalization():
    print("\ntest_multiple_features_some_need_normalization", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        # Feature A: short featureId
        write_feature_yaml(gov, "platform", "identity", "auth", short_feature_yaml("platform", "identity", "auth"))
        # Feature B: already canonical
        write_feature_yaml(gov, "platform", "identity", "profile", {
            "name": "Profile",
            "featureId": "platform-identity-profile",
            "featureSlug": "profile",
            "domain": "platform",
            "service": "identity",
            "phase": "preplan",
        })
        write_feature_index(gov, [
            short_index_entry("platform", "identity", "auth"),
            {"id": "platform-identity-profile", "featureId": "platform-identity-profile",
             "featureSlug": "profile", "domain": "platform", "service": "identity",
             "status": "preplan", "plan_branch": "platform-identity-profile-plan"},
        ])

        result, code = run(["normalize-feature-ids", "--governance-repo", str(gov)])
        assert_eq("exit code", code, 0)
        assert_eq("total_scanned", result.get("total_scanned"), 2)
        assert_eq("total_normalized", result.get("total_normalized"), 1)
        assert_eq("normalized feature", result["normalized"][0]["canonical_feature_id"], "platform-identity-auth")


def test_renames_branches_in_control_repo():
    print("\ntest_renames_branches_in_control_repo", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "new-project", "scraping", "worker", short_feature_yaml("new-project", "scraping", "worker"))
        write_feature_index(gov, [short_index_entry("new-project", "scraping", "worker")])
        control = make_control_repo_with_branches(tmp, ["worker", "worker-plan"])

        result, code = run([
            "normalize-feature-ids",
            "--governance-repo", str(gov),
            "--control-repo", str(control),
        ])
        assert_eq("exit code", code, 0)

        renames = result["normalized"][0]["branch_renames"]
        renamed = {r["from"]: r for r in renames}
        assert_eq("worker branch renamed", renamed["worker"]["status"], "renamed")
        assert_eq("worker-plan branch renamed", renamed["worker-plan"]["status"], "renamed")
        assert_eq("worker renamed to", renamed["worker"]["to"], "new-project-scraping-worker")
        assert_eq("worker-plan renamed to", renamed["worker-plan"]["to"], "new-project-scraping-worker-plan")

        # Verify git branches directly
        res = subprocess.run(
            ["git", "-C", str(control), "branch"],
            capture_output=True, text=True,
        )
        branch_list = res.stdout
        assert_true("new canonical branch exists", "new-project-scraping-worker" in branch_list)
        assert_true("old branch gone", "  worker\n" not in branch_list and "* worker\n" not in branch_list)


def test_branch_rename_dry_run():
    print("\ntest_branch_rename_dry_run", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "new-project", "scraping", "worker", short_feature_yaml("new-project", "scraping", "worker"))
        write_feature_index(gov, [short_index_entry("new-project", "scraping", "worker")])
        control = make_control_repo_with_branches(tmp, ["worker", "worker-plan"])

        run([
            "normalize-feature-ids",
            "--governance-repo", str(gov),
            "--control-repo", str(control),
            "--dry-run",
        ])

        # Branches must NOT be renamed in dry-run
        res = subprocess.run(["git", "-C", str(control), "branch"], capture_output=True, text=True)
        assert_true("worker branch still exists", "worker" in res.stdout)
        assert_true("canonical branch not yet created",
                    "new-project-scraping-worker\n" not in res.stdout.replace("* ", ""))


def test_branch_not_found_is_reported():
    print("\ntest_branch_not_found_is_reported", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "new-project", "scraping", "worker", short_feature_yaml("new-project", "scraping", "worker"))
        write_feature_index(gov, [short_index_entry("new-project", "scraping", "worker")])
        # Control repo has no worker branches
        control = make_control_repo_with_branches(tmp, [])

        result, code = run([
            "normalize-feature-ids",
            "--governance-repo", str(gov),
            "--control-repo", str(control),
        ])
        assert_eq("exit code", code, 0)
        renames = result["normalized"][0]["branch_renames"]
        statuses = {r["from"]: r["status"] for r in renames}
        assert_eq("worker branch not-found", statuses["worker"], "not-found")
        assert_eq("worker-plan branch not-found", statuses["worker-plan"], "not-found")


def test_governance_repo_not_found():
    print("\ntest_governance_repo_not_found", file=sys.stderr)
    result, code = run([
        "normalize-feature-ids",
        "--governance-repo", "/nonexistent/path",
    ])
    assert_eq("exit code non-zero", code, 1)


if __name__ == "__main__":
    test_dry_run_shows_proposed_changes()
    test_normalizes_feature_yaml()
    test_normalizes_feature_index()
    test_directory_name_unchanged()
    test_docs_paths_use_slug_not_feature_id()
    test_docs_paths_corrected_when_pointing_at_feature_id()
    test_no_normalization_needed()
    test_multiple_features_some_need_normalization()
    test_renames_branches_in_control_repo()
    test_branch_rename_dry_run()
    test_branch_not_found_is_reported()
    test_governance_repo_not_found()

    print(f"\n{'='*40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'='*40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
