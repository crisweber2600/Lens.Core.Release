#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for migrate-ops.py fix-feature-dirs subcommand."""

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


def assert_false(name: str, actual):
    assert_eq(name, bool(actual), False)


def make_governance_repo(tmp: str) -> Path:
    gov = Path(tmp) / "governance"
    (gov / "features").mkdir(parents=True)
    return gov


def write_feature_yaml(gov: Path, domain: str, service: str, dir_name: str, data: dict) -> Path:
    feature_dir = gov / "features" / domain / service / dir_name
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


def make_project_root(tmp: str) -> Path:
    pr = Path(tmp) / "project"
    pr.mkdir(parents=True)
    return pr


def make_docs_dir(project_root: Path, domain: str, service: str, dir_name: str, with_files: bool = True) -> Path:
    docs_dir = project_root / "docs" / domain / service / dir_name / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    if with_files:
        (docs_dir / "index.md").write_text("# Index", encoding="utf-8")
    return docs_dir.parent  # Return the feature-level dir, not the nested docs/


def canonical_feature_yaml(domain: str, service: str, slug: str) -> dict:
    """Feature with correct slug dir but featureId pointing to canonical name."""
    canonical_id = f"{domain}-{service}-{slug}"
    return {
        "name": slug.capitalize(),
        "description": "",
        "featureId": canonical_id,
        "featureSlug": slug,
        "domain": domain,
        "service": service,
        "phase": "preplan",
        "docs": {
            "path": f"docs/{domain}/{service}/{canonical_id}",  # Wrong: uses featureId
            "governance_docs_path": f"features/{domain}/{service}/{canonical_id}/docs",  # Wrong
        },
    }


def canonical_index_entry(domain: str, service: str, slug: str) -> dict:
    canonical_id = f"{domain}-{service}-{slug}"
    return {
        "id": canonical_id,
        "featureId": canonical_id,
        "featureSlug": slug,
        "domain": domain,
        "service": service,
        "status": "preplan",
        "plan_branch": f"{canonical_id}-plan",
    }


# ---------------------------------------------------------------------------


def test_dry_run_shows_proposed_renames():
    print("\ntest_dry_run_shows_proposed_renames", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        # Dir is named after featureId, not featureSlug
        write_feature_yaml(gov, "old-project", "src", "old-project-src-init",
                           canonical_feature_yaml("old-project", "src", "init"))
        write_feature_index(gov, [canonical_index_entry("old-project", "src", "init")])

        result, code = run([
            "fix-feature-dirs",
            "--governance-repo", str(gov),
            "--dry-run",
        ])
        assert_eq("exit code", code, 0)
        assert_eq("status", result.get("status"), "pass")
        assert_eq("dry_run flag", result.get("dry_run"), True)
        assert_eq("total_fixed", result.get("total_fixed"), 1)

        rec = result["fixed"][0]
        assert_eq("old_dir_name", rec["old_dir_name"], "old-project-src-init")
        assert_eq("feature_slug", rec["feature_slug"], "init")
        assert_eq("governance_dir status", rec["governance_dir"]["status"], "would-rename")
        assert_eq("feature_yaml_status", rec["feature_yaml_status"], "would-update")

        # Dry run: governance dir must NOT be renamed
        old_dir = gov / "features" / "old-project" / "src" / "old-project-src-init"
        new_dir = gov / "features" / "old-project" / "src" / "init"
        assert_true("old governance dir still exists", old_dir.is_dir())
        assert_false("new governance dir NOT created", new_dir.exists())


def test_renames_governance_dir():
    print("\ntest_renames_governance_dir", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "old-project", "src", "old-project-src-init",
                           canonical_feature_yaml("old-project", "src", "init"))
        write_feature_index(gov, [canonical_index_entry("old-project", "src", "init")])

        result, code = run(["fix-feature-dirs", "--governance-repo", str(gov)])
        assert_eq("exit code", code, 0)
        assert_eq("status", result.get("status"), "pass")
        assert_eq("total_fixed", result.get("total_fixed"), 1)

        rec = result["fixed"][0]
        assert_eq("governance_dir status", rec["governance_dir"]["status"], "renamed")

        old_dir = gov / "features" / "old-project" / "src" / "old-project-src-init"
        new_dir = gov / "features" / "old-project" / "src" / "init"
        assert_false("old governance dir gone", old_dir.exists())
        assert_true("new governance dir created", new_dir.is_dir())
        assert_true("feature.yaml exists in new dir", (new_dir / "feature.yaml").is_file())


def test_updates_docs_paths_in_feature_yaml():
    print("\ntest_updates_docs_paths_in_feature_yaml", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "old-project", "src", "old-project-src-init",
                           canonical_feature_yaml("old-project", "src", "init"))
        write_feature_index(gov, [canonical_index_entry("old-project", "src", "init")])

        run(["fix-feature-dirs", "--governance-repo", str(gov)])

        new_yaml_path = gov / "features" / "old-project" / "src" / "init" / "feature.yaml"
        raw = yaml.safe_load(new_yaml_path.read_text())
        assert_eq("docs.path uses slug", raw["docs"]["path"], "docs/old-project/src/init")
        assert_eq("docs.governance_docs_path uses slug", raw["docs"]["governance_docs_path"],
                  "features/old-project/src/init/docs")
        # featureId and featureSlug unchanged
        assert_eq("featureId preserved", raw["featureId"], "old-project-src-init")
        assert_eq("featureSlug preserved", raw["featureSlug"], "init")


def test_renames_project_root_docs_dir():
    print("\ntest_renames_project_root_docs_dir", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "old-project", "src", "old-project-src-init",
                           canonical_feature_yaml("old-project", "src", "init"))
        write_feature_index(gov, [canonical_index_entry("old-project", "src", "init")])

        pr = make_project_root(tmp)
        make_docs_dir(pr, "old-project", "src", "old-project-src-init", with_files=True)

        result, code = run([
            "fix-feature-dirs",
            "--governance-repo", str(gov),
            "--project-root", str(pr),
        ])
        assert_eq("exit code", code, 0)
        rec = result["fixed"][0]
        assert_eq("docs_dir status", rec["docs_dir"]["status"], "renamed")

        old_docs = pr / "docs" / "old-project" / "src" / "old-project-src-init"
        new_docs = pr / "docs" / "old-project" / "src" / "init"
        assert_false("old docs dir gone", old_docs.exists())
        assert_true("new docs dir created", new_docs.is_dir())
        assert_true("index.md preserved", (new_docs / "docs" / "index.md").is_file())


def test_docs_dir_dry_run_not_renamed():
    print("\ntest_docs_dir_dry_run_not_renamed", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "old-project", "src", "old-project-src-init",
                           canonical_feature_yaml("old-project", "src", "init"))
        write_feature_index(gov, [canonical_index_entry("old-project", "src", "init")])

        pr = make_project_root(tmp)
        make_docs_dir(pr, "old-project", "src", "old-project-src-init", with_files=True)

        result, _ = run([
            "fix-feature-dirs",
            "--governance-repo", str(gov),
            "--project-root", str(pr),
            "--dry-run",
        ])
        rec = result["fixed"][0]
        assert_eq("docs_dir dry-run status", rec["docs_dir"]["status"], "would-rename")

        old_docs = pr / "docs" / "old-project" / "src" / "old-project-src-init"
        assert_true("old docs dir still exists in dry-run", old_docs.is_dir())


def test_docs_dir_not_found_reported():
    print("\ntest_docs_dir_not_found_reported", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "old-project", "src", "old-project-src-init",
                           canonical_feature_yaml("old-project", "src", "init"))
        write_feature_index(gov, [canonical_index_entry("old-project", "src", "init")])

        pr = make_project_root(tmp)
        # No docs dir created

        result, code = run([
            "fix-feature-dirs",
            "--governance-repo", str(gov),
            "--project-root", str(pr),
        ])
        assert_eq("exit code", code, 0)
        rec = result["fixed"][0]
        assert_eq("docs_dir not-found", rec["docs_dir"]["status"], "not-found")
        # Governance dir still renamed
        assert_eq("governance_dir renamed", rec["governance_dir"]["status"], "renamed")


def test_already_correct_dirs_not_fixed():
    print("\ntest_already_correct_dirs_not_fixed", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        # Dir name already equals featureSlug
        write_feature_yaml(gov, "platform", "identity", "auth", {
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
        })
        write_feature_index(gov, [{"id": "platform-identity-auth", "featureId": "platform-identity-auth",
                                    "featureSlug": "auth", "domain": "platform", "service": "identity",
                                    "status": "preplan", "plan_branch": "platform-identity-auth-plan"}])

        result, code = run(["fix-feature-dirs", "--governance-repo", str(gov)])
        assert_eq("exit code", code, 0)
        assert_eq("status", result.get("status"), "pass")
        assert_eq("total_fixed", result.get("total_fixed"), 0)
        assert_eq("fixed list empty", result.get("fixed"), [])


def test_multiple_features_only_wrong_ones_fixed():
    print("\ntest_multiple_features_only_wrong_ones_fixed", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        # Feature A: dir uses featureId (wrong)
        write_feature_yaml(gov, "old-project", "src", "old-project-src-init",
                           canonical_feature_yaml("old-project", "src", "init"))
        # Feature B: dir already correct
        write_feature_yaml(gov, "platform", "identity", "auth", {
            "name": "Auth",
            "featureId": "platform-identity-auth",
            "featureSlug": "auth",
            "domain": "platform",
            "service": "identity",
            "phase": "preplan",
        })
        write_feature_index(gov, [
            canonical_index_entry("old-project", "src", "init"),
            {"id": "platform-identity-auth", "featureId": "platform-identity-auth",
             "featureSlug": "auth", "domain": "platform", "service": "identity",
             "status": "preplan", "plan_branch": "platform-identity-auth-plan"},
        ])

        result, code = run(["fix-feature-dirs", "--governance-repo", str(gov)])
        assert_eq("exit code", code, 0)
        assert_eq("total_scanned", result.get("total_scanned"), 2)
        assert_eq("total_fixed", result.get("total_fixed"), 1)
        assert_eq("fixed feature slug", result["fixed"][0]["feature_slug"], "init")

        # Correct feature untouched
        auth_dir = gov / "features" / "platform" / "identity" / "auth"
        assert_true("auth dir still exists", auth_dir.is_dir())


def test_governance_repo_not_found():
    print("\ntest_governance_repo_not_found", file=sys.stderr)
    result, code = run([
        "fix-feature-dirs",
        "--governance-repo", "/nonexistent/path",
    ])
    assert_eq("exit code non-zero", code, 1)


def test_project_root_not_found():
    print("\ntest_project_root_not_found", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "old-project", "src", "old-project-src-init",
                           canonical_feature_yaml("old-project", "src", "init"))
        write_feature_index(gov, [canonical_index_entry("old-project", "src", "init")])

        result, code = run([
            "fix-feature-dirs",
            "--governance-repo", str(gov),
            "--project-root", "/nonexistent/path",
        ])
        assert_eq("exit code non-zero", code, 1)
        assert_eq("error field present", "error" in result, True)


def test_proposed_docs_in_dry_run():
    """Dry-run output includes the proposed corrected docs paths."""
    print("\ntest_proposed_docs_in_dry_run", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        gov = make_governance_repo(tmp)
        write_feature_yaml(gov, "old-project", "src", "old-project-src-init",
                           canonical_feature_yaml("old-project", "src", "init"))
        write_feature_index(gov, [canonical_index_entry("old-project", "src", "init")])

        result, code = run(["fix-feature-dirs", "--governance-repo", str(gov), "--dry-run"])
        rec = result["fixed"][0]
        proposed = rec.get("proposed_docs", {})
        assert_eq("proposed path uses slug", proposed.get("path"), "docs/old-project/src/init")
        assert_eq("proposed governance_docs_path uses slug", proposed.get("governance_docs_path"),
                  "features/old-project/src/init/docs")


if __name__ == "__main__":
    test_dry_run_shows_proposed_renames()
    test_renames_governance_dir()
    test_updates_docs_paths_in_feature_yaml()
    test_renames_project_root_docs_dir()
    test_docs_dir_dry_run_not_renamed()
    test_docs_dir_not_found_reported()
    test_already_correct_dirs_not_fixed()
    test_multiple_features_only_wrong_ones_fixed()
    test_governance_repo_not_found()
    test_project_root_not_found()
    test_proposed_docs_in_dry_run()

    print(f"\n{'='*40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'='*40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
