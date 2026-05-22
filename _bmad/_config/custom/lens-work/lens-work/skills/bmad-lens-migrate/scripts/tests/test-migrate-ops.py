#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for migrate-ops.py."""

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


def make_branch_dir(tmp: str, branch_name: str) -> Path:
    """Create a legacy branch directory in the branches/ folder."""
    d = Path(tmp) / "branches" / branch_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command inside *repo*."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result


def init_remote_source_repo(tmp: str) -> Path:
    """Create a git source repo with an origin remote for branch-doc tests."""
    remote = Path(tmp) / "remote.git"
    source = Path(tmp) / "source"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "clone", str(remote), str(source)], check=True, capture_output=True, text=True)
    run_git(source, "config", "user.name", "testuser")
    run_git(source, "config", "user.email", "test@example.com")

    (source / "README.md").write_text("seed\n", encoding="utf-8")
    run_git(source, "add", "README.md")
    run_git(source, "commit", "-m", "seed")
    run_git(source, "push", "-u", "origin", "HEAD:main")
    return source


def create_remote_branch_with_files(source: Path, branch_name: str, files: dict[str, str]) -> None:
    """Create or replace a remote branch with a tracked set of files."""
    run_git(source, "checkout", "-B", branch_name, "origin/main")
    for relative_path, content in files.items():
        target = source / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    run_git(source, "add", *sorted(files))
    run_git(source, "commit", "-m", f"add {branch_name} doc")
    run_git(source, "push", "-u", "origin", branch_name)


def create_remote_branch_with_file(source: Path, branch_name: str, relative_path: str, content: str) -> None:
    """Create or update a remote branch with a single tracked file."""
    create_remote_branch_with_files(source, branch_name, {relative_path: content})


def write_text_file(root: Path, relative_path: str, content: str) -> Path:
    """Write a UTF-8 text file under *root* and return its path."""
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def test_scan_detects_legacy():
    """scan detects legacy feature directories."""
    print("test_scan_detects_legacy", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_branch_dir(tmp, "platform-identity-auth-login")

        result, code = run(["scan", "--governance-repo", tmp])
        assert_eq("scan status", result["status"], "pass")
        assert_eq("scan exit code", code, 0)
        assert_eq("scan total", result["total"], 1)
        assert_true("has legacy_features", len(result["legacy_features"]) == 1)


def test_scan_derives_components():
    """scan derives domain/service/featureId from old naming."""
    print("test_scan_derives_components", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_branch_dir(tmp, "platform-identity-auth-login")
        make_branch_dir(tmp, "platform-identity-auth-login-planning")
        make_branch_dir(tmp, "platform-identity-auth-login-dev")

        result, code = run(["scan", "--governance-repo", tmp])
        assert_eq("scan status", result["status"], "pass")
        assert_eq("total features", result["total"], 1)

        feature = result["legacy_features"][0]
        assert_eq("derived_domain", feature["derived_domain"], "platform")
        assert_eq("derived_service", feature["derived_service"], "identity")
        assert_eq("feature_id", feature["feature_id"], "auth-login")
        assert_eq("old_id", feature["old_id"], "platform-identity-auth-login")
        assert_true("has planning milestone", "planning" in feature["milestones"])
        assert_true("has dev milestone", "dev" in feature["milestones"])
        assert_eq("proposed base_branch", feature["proposed"]["base_branch"], "auth-login")
        assert_eq("proposed plan_branch", feature["proposed"]["plan_branch"], "auth-login-plan")


def test_scan_empty_branches():
    """scan returns empty plan when no branches dir exists."""
    print("test_scan_empty_branches", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run(["scan", "--governance-repo", tmp])
        assert_eq("empty scan status", result["status"], "pass")
        assert_eq("empty scan total", result["total"], 0)
        assert_eq("empty scan exit code", code, 0)


def test_scan_multiple_features():
    """scan groups multiple features correctly."""
    print("test_scan_multiple_features", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_branch_dir(tmp, "platform-identity-auth-login")
        make_branch_dir(tmp, "core-api-user-mgmt")
        make_branch_dir(tmp, "core-api-user-mgmt-dev")

        result, code = run(["scan", "--governance-repo", tmp])
        assert_eq("scan status", result["status"], "pass")
        assert_eq("total features", result["total"], 2)

        ids = [f["feature_id"] for f in result["legacy_features"]]
        assert_true("has auth-login", "auth-login" in ids)
        assert_true("has user-mgmt", "user-mgmt" in ids)

        user_mgmt = next(f for f in result["legacy_features"] if f["feature_id"] == "user-mgmt")
        assert_true("user-mgmt has dev milestone", "dev" in user_mgmt["milestones"])


def test_scan_keeps_prefixed_feature_names_separate():
    """scan does not misclassify a sibling feature as a milestone when names share a prefix."""
    print("test_scan_keeps_prefixed_feature_names_separate", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_branch_dir(tmp, "platform-identity-auth")
        make_branch_dir(tmp, "platform-identity-auth-login")
        make_branch_dir(tmp, "platform-identity-auth-login-dev")

        result, code = run(["scan", "--governance-repo", tmp])
        assert_eq("scan status", result["status"], "pass")
        assert_eq("scan exit code", code, 0)
        assert_eq("total features", result["total"], 2)

        features = {feature["feature_id"]: feature for feature in result["legacy_features"]}
        assert_true("has auth feature", "auth" in features)
        assert_true("has auth-login feature", "auth-login" in features)
        assert_eq("auth has no milestones", features["auth"]["milestones"], [])
        assert_eq("auth-login has only dev milestone", features["auth-login"]["milestones"], ["dev"])


def test_scan_preserves_multi_hyphen_feature_id():
    """scan preserves a multi-hyphen feature id and its milestone branch."""
    print("test_scan_preserves_multi_hyphen_feature_id", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_branch_dir(tmp, "plugins-hermes-hermes-lens-plugin")
        make_branch_dir(tmp, "plugins-hermes-hermes-lens-plugin-dev")

        result, code = run(["scan", "--governance-repo", tmp])
        assert_eq("scan status", result["status"], "pass")
        assert_eq("scan exit code", code, 0)
        assert_eq("total features", result["total"], 1)

        feature = result["legacy_features"][0]
        assert_eq("derived_domain", feature["derived_domain"], "plugins")
        assert_eq("derived_service", feature["derived_service"], "hermes")
        assert_eq("feature_id", feature["feature_id"], "hermes-lens-plugin")
        assert_eq("old_id", feature["old_id"], "plugins-hermes-hermes-lens-plugin")
        assert_eq("milestones", feature["milestones"], ["dev"])


def test_migrate_feature_creates_yaml():
    """migrate-feature creates feature.yaml."""
    print("test_migrate_feature_creates_yaml", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "migrate-feature",
            "--governance-repo", tmp,
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
        ])
        assert_eq("migrate status", result["status"], "pass")
        assert_eq("migrate exit code", code, 0)
        assert_eq("feature_yaml_created", result["feature_yaml_created"], True)

        feature_path = Path(tmp) / "features" / "platform" / "identity" / "auth-login" / "feature.yaml"
        assert_eq("feature.yaml exists", feature_path.exists(), True)

        with open(feature_path) as f:
            data = yaml.safe_load(f)
        assert_eq("featureId field", data["featureId"], "auth-login")
        assert_eq("domain field", data["domain"], "platform")
        assert_eq("service field", data["service"], "identity")
        assert_eq("migrated_from field", data["migrated_from"], "platform-identity-auth-login")
        assert_eq("phase field", data["phase"], "preplan")
        assert_true("has team lead", data["team"][0]["role"] == "lead")
        assert_true("has milestones map", isinstance(data.get("milestones"), dict))


def test_migrate_feature_creates_index_entry():
    """migrate-feature creates feature-index.yaml entry."""
    print("test_migrate_feature_creates_index_entry", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "migrate-feature",
            "--governance-repo", tmp,
            "--old-id", "core-api-user-mgmt",
            "--feature-id", "user-mgmt",
            "--domain", "core",
            "--service", "api",
            "--username", "testuser",
        ])
        assert_eq("migrate status", result["status"], "pass")
        assert_eq("index_updated", result["index_updated"], True)

        index_path = Path(tmp) / "feature-index.yaml"
        assert_eq("feature-index.yaml exists", index_path.exists(), True)

        with open(index_path) as f:
            index = yaml.safe_load(f)

        feature_ids = [e.get("id") or e.get("featureId") for e in index.get("features", [])]
        assert_true("feature in index", "user-mgmt" in feature_ids)

        entry = next(e for e in index["features"] if (e.get("id") or e.get("featureId")) == "user-mgmt")
        assert_eq("index entry domain", entry["domain"], "core")
        assert_eq("index entry migrated_from", entry["migrated_from"], "core-api-user-mgmt")
        assert_eq("index entry id", entry["id"], "user-mgmt")
        assert_eq("index entry compatibility featureId", entry["featureId"], "user-mgmt")


def test_migrate_feature_dry_run():
    """migrate-feature dry-run makes no changes."""
    print("test_migrate_feature_dry_run", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "migrate-feature",
            "--governance-repo", tmp,
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
            "--dry-run",
        ])
        assert_eq("dry_run status", result["status"], "pass")
        assert_eq("dry_run flag", result["dry_run"], True)
        assert_eq("dry_run no yaml created", result["feature_yaml_created"], False)
        assert_eq("dry_run no index updated", result["index_updated"], False)
        assert_true("planned_actions present", len(result.get("planned_actions", [])) > 0)
        assert_true(
            "summary path uses feature directory",
            any("features/platform/identity/auth-login/summary.md" in action for action in result.get("planned_actions", [])),
        )

        feature_path = Path(tmp) / "features" / "platform" / "identity" / "auth-login" / "feature.yaml"
        assert_eq("feature.yaml not created in dry run", feature_path.exists(), False)

        index_path = Path(tmp) / "feature-index.yaml"
        assert_eq("index not created in dry run", index_path.exists(), False)


def test_check_conflicts_no_conflict():
    """check-conflicts returns pass when target path is free."""
    print("test_check_conflicts_no_conflict", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "check-conflicts",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
        ])
        assert_eq("no conflict status", result["status"], "pass")
        assert_eq("conflict false", result["conflict"], False)
        assert_eq("exit code 0", code, 0)


def test_check_conflicts_conflict():
    """check-conflicts returns conflict when target path exists."""
    print("test_check_conflicts_conflict", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_dir = Path(tmp) / "features" / "platform" / "identity" / "auth-login"
        feature_dir.mkdir(parents=True)
        with open(feature_dir / "feature.yaml", "w") as f:
            yaml.dump({"featureId": "auth-login"}, f)

        result, code = run([
            "check-conflicts",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
        ])
        assert_eq("conflict status", result["status"], "conflict")
        assert_eq("conflict true", result["conflict"], True)
        assert_true("existing_path set", bool(result.get("existing_path")))
        assert_eq("conflict exit code", code, 0)


def test_invalid_feature_id():
    """Invalid feature-id slug is rejected with exit code 1."""
    print("test_invalid_feature_id", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "migrate-feature",
            "--governance-repo", tmp,
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "Auth_Login!",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
        ])
        assert_eq("invalid id status", result["status"], "fail")
        assert_eq("invalid id exit code", code, 1)
        assert_true("error mentions Invalid", "Invalid" in result.get("error", ""))


def test_invalid_domain():
    """Invalid domain (path traversal) is rejected."""
    print("test_invalid_domain", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "migrate-feature",
            "--governance-repo", tmp,
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "../evil",
            "--service", "identity",
            "--username", "testuser",
        ])
        assert_eq("invalid domain status", result["status"], "fail")
        assert_eq("invalid domain exit code", code, 1)


def test_governance_repo_not_found():
    """Governance repo not found causes exit code 1."""
    print("test_governance_repo_not_found", file=sys.stderr)
    result, code = run([
        "scan",
        "--governance-repo", "/nonexistent/path/to/repo/xyz123",
    ])
    assert_eq("missing repo exit code", code, 1)


def test_governance_repo_not_found_migrate():
    """Governance repo not found on migrate-feature causes exit code 1."""
    print("test_governance_repo_not_found_migrate", file=sys.stderr)
    result, code = run([
        "migrate-feature",
        "--governance-repo", "/nonexistent/path/xyz123",
        "--old-id", "platform-identity-auth",
        "--feature-id", "auth",
        "--domain", "platform",
        "--service", "identity",
        "--username", "testuser",
    ])
    assert_eq("missing repo exit code (migrate)", code, 1)


def test_migrate_feature_resolves_governance_repo_from_control_repo_path():
    """migrate-feature resolves the governance repo when the control repo path is passed by mistake."""
    print("test_migrate_feature_resolves_governance_repo_from_control_repo_path", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        control = Path(tmp) / "control"
        governance = control / "TargetProjects" / "lens" / "lens-governance"
        (control / "lens.core").mkdir(parents=True, exist_ok=True)
        governance.mkdir(parents=True, exist_ok=True)

        result, code = run([
            "migrate-feature",
            "--governance-repo", str(control),
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
            "--control-repo", str(control),
        ])
        assert_eq("resolved governance status", result["status"], "pass")
        assert_eq("resolved governance exit code", code, 0)

        feature_path = governance / "features" / "platform" / "identity" / "auth-login" / "feature.yaml"
        wrong_feature_path = control / "features" / "platform" / "identity" / "auth-login" / "feature.yaml"
        assert_eq("feature written into governance repo", feature_path.exists(), True)
        assert_eq("feature not written into control repo root", wrong_feature_path.exists(), False)
        assert_true(
            "warning mentions governance resolution",
            any("Resolved governance repo" in warning for warning in result.get("warnings", [])),
        )


def test_scan_detects_conflict():
    """scan surfaces conflict when new-model feature.yaml already exists."""
    print("test_scan_detects_conflict", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_branch_dir(tmp, "platform-identity-auth-login")

        # Pre-create the target feature.yaml
        feature_dir = Path(tmp) / "features" / "platform" / "identity" / "auth-login"
        feature_dir.mkdir(parents=True)
        with open(feature_dir / "feature.yaml", "w") as f:
            yaml.dump({"featureId": "auth-login"}, f)

        result, code = run(["scan", "--governance-repo", tmp])
        assert_eq("scan with conflict status", result["status"], "pass")
        assert_eq("conflicts detected", len(result["conflicts"]), 1)
        assert_eq("conflict old_id", result["conflicts"][0]["old_id"], "platform-identity-auth-login")


def test_migrate_feature_preserves_legacy_state():
    """migrate-feature preserves phase, track, transitions, and context from legacy state."""
    print("test_migrate_feature_preserves_legacy_state", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        branch = make_branch_dir(tmp, "platform-identity-auth-login")
        with open(branch / "initiative-state.yaml", "w") as f:
            yaml.dump(
                {
                    "phase": "techplan",
                    "track": "hotfix",
                    "created": "2026-04-01T00:00:00Z",
                    "last_updated": "2026-04-02T00:00:00Z",
                    "phase_transitions": [
                        {"phase": "preplan", "timestamp": "2026-04-01T00:00:00Z", "user": "legacy"},
                        {"phase": "techplan", "timestamp": "2026-04-02T00:00:00Z", "user": "legacy"},
                    ],
                    "context": {"last_pulled": "2026-04-02T12:00:00Z", "stale": True},
                    "milestones": {"techplan": "2026-04-02T00:00:00Z"},
                },
                f,
                sort_keys=False,
            )

        result, code = run([
            "migrate-feature",
            "--governance-repo", tmp,
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
        ])
        assert_eq("migrate status", result["status"], "pass")
        assert_eq("migrate exit code", code, 0)
        assert_true("legacy state path returned", result.get("legacy_state_path") is not None)

        feature_path = Path(tmp) / "features" / "platform" / "identity" / "auth-login" / "feature.yaml"
        with open(feature_path) as f:
            data = yaml.safe_load(f)

        assert_eq("phase preserved", data["phase"], "techplan")
        assert_eq("track preserved", data["track"], "hotfix")
        assert_eq("created preserved", data["created"], "2026-04-01T00:00:00Z")
        assert_eq("updated preserved", data["updated"], "2026-04-02T00:00:00Z")
        assert_eq("transition count preserved", len(data["phase_transitions"]), 2)
        assert_eq("context stale preserved", data["context"]["stale"], True)
        assert_eq("techplan milestone preserved", data["milestones"]["techplan"], "2026-04-02T00:00:00Z")


def test_migrate_feature_ignores_prefixed_sibling_branch_when_deriving_phase():
    """migrate-feature ignores sibling feature branches that merely share the same prefix."""
    print("test_migrate_feature_ignores_prefixed_sibling_branch_when_deriving_phase", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        make_branch_dir(tmp, "platform-identity-auth")
        make_branch_dir(tmp, "platform-identity-auth-login")

        result, code = run([
            "migrate-feature",
            "--governance-repo", tmp,
            "--old-id", "platform-identity-auth",
            "--feature-id", "auth",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
        ])
        assert_eq("migrate status", result["status"], "pass")
        assert_eq("migrate exit code", code, 0)

        feature_path = Path(tmp) / "features" / "platform" / "identity" / "auth" / "feature.yaml"
        with open(feature_path) as f:
            data = yaml.safe_load(f)
        assert_eq("phase remains preplan", data["phase"], "preplan")


def test_migrate_feature_creates_summary_and_problems_in_feature_dir():
    """migrate-feature writes summary.md and problems.md into the feature directory."""
    print("test_migrate_feature_creates_summary_and_problems_in_feature_dir", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "migrate-feature",
            "--governance-repo", tmp,
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
        ])
        assert_eq("migrate status", result["status"], "pass")
        assert_eq("migrate exit code", code, 0)
        assert_eq("problems created", result["problems_created"], True)

        feature_dir = Path(tmp) / "features" / "platform" / "identity" / "auth-login"
        summary_path = feature_dir / "summary.md"
        problems_path = feature_dir / "problems.md"
        legacy_summary_dir = Path(tmp) / "summaries"

        assert_eq("summary.md exists in feature dir", summary_path.exists(), True)
        assert_eq("problems.md exists in feature dir", problems_path.exists(), True)
        assert_eq("no legacy summaries dir created", legacy_summary_dir.exists(), False)
        assert_true("summary mentions migrated from", "Migrated from legacy branch" in summary_path.read_text())
        assert_true("problems template rendered", "Feature: platform/identity/auth-login" in problems_path.read_text())


def test_migrate_feature_copies_legacy_artifacts():
    """migrate-feature copies legacy planning artifacts when present."""
    print("test_migrate_feature_copies_legacy_artifacts", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        branch = make_branch_dir(tmp, "platform-identity-auth-login")
        artifacts_dir = branch / "_bmad-output" / "lens-work" / "planning-artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "tech-plan.md").write_text("legacy tech plan", encoding="utf-8")

        result, code = run([
            "migrate-feature",
            "--governance-repo", tmp,
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
        ])
        assert_eq("migrate status", result["status"], "pass")
        assert_eq("migrate exit code", code, 0)
        assert_eq("artifact copied list", result["artifacts_copied"], ["tech-plan.md"])

        copied_artifact = Path(tmp) / "features" / "platform" / "identity" / "auth-login" / "tech-plan.md"
        assert_eq("copied artifact exists", copied_artifact.exists(), True)
        assert_eq("copied artifact content", copied_artifact.read_text(encoding="utf-8"), "legacy tech plan")


def test_migrate_feature_mirrors_base_and_milestone_branch_docs():
    """migrate-feature mirrors branch docs into the dossier and migrates canonical docs into governance only."""
    print("test_migrate_feature_mirrors_base_and_milestone_branch_docs", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        governance = Path(tmp) / "governance"
        governance.mkdir(parents=True, exist_ok=True)
        source = init_remote_source_repo(tmp)
        create_remote_branch_with_file(
            source,
            "platform-identity-auth-login",
            "docs/platform/identity/feature/auth-login/base.md",
            "base branch doc\n",
        )
        create_remote_branch_with_file(
            source,
            "platform-identity-auth-login-dev",
            "docs/platform/identity/feature/auth-login/dev.md",
            "dev branch doc\n",
        )

        result, code = run([
            "migrate-feature",
            "--governance-repo", str(governance),
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
            "--source-repo", str(source),
            "--control-repo", tmp,
        ])
        assert_eq("migrate status", result["status"], "pass")
        assert_eq("migrate exit code", code, 0)
        assert_true("documents discovered from both branches", result["documents_discovered_count"] >= 2)

        dossier = Path(tmp) / "docs" / "lens-work" / "migrations" / "platform" / "identity" / "auth-login"
        base_mirror = dossier / "sources" / "branch-docs" / "platform-identity-auth-login" / "branch-docs-compat" / "base.md"
        dev_mirror = dossier / "sources" / "branch-docs" / "platform-identity-auth-login-dev" / "branch-docs-compat" / "dev.md"
        governance_docs = governance / "features" / "platform" / "identity" / "auth-login" / "docs"
        assert_eq("base branch mirrored", base_mirror.exists(), True)
        assert_eq("dev branch mirrored", dev_mirror.exists(), True)
        assert_eq("base branch migrated to governance docs", (governance_docs / "base.md").exists(), True)
        assert_eq("dev branch migrated to governance docs", (governance_docs / "dev.md").exists(), True)
        assert_eq("no canonical dossier docs created", (dossier / "docs").exists(), False)

        audit = result["document_audit"]
        branch_counts = {entry["branch"]: entry for entry in audit["branches"]}
        assert_eq("control feature document count", audit["control_feature_documents"], 2)
        assert_eq("governance feature document count", audit["governance_feature_documents"], 2)
        assert_eq(
            "base branch control doc count",
            branch_counts["platform-identity-auth-login"]["control_repo_documents"],
            1,
        )
        assert_eq(
            "dev branch control doc count",
            branch_counts["platform-identity-auth-login-dev"]["control_repo_documents"],
            1,
        )
        assert_eq(
            "base branch governance doc count",
            branch_counts["platform-identity-auth-login"]["governance_repo_documents"],
            1,
        )
        assert_eq(
            "dev branch governance doc count",
            branch_counts["platform-identity-auth-login-dev"]["governance_repo_documents"],
            1,
        )

        record_path = dossier / "migration-record.yaml"
        record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        assert_eq("record discovered count", record["documents"]["discovered_count"], 2)
        assert_eq("record canonical count", record["documents"]["canonical_count"], 2)
        assert_eq(
            "record governance document count",
            record["documents"]["document_audit"]["governance_feature_documents"],
            2,
        )


def test_migrate_feature_reads_legacy_paths_for_renamed_feature():
    """Renamed features read legacy source paths but still write governance docs to the requested feature id."""
    print("test_migrate_feature_reads_legacy_paths_for_renamed_feature", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        governance = Path(tmp) / "governance"
        governance.mkdir(parents=True, exist_ok=True)
        source = init_remote_source_repo(tmp)
        create_remote_branch_with_file(
            source,
            "platform-identity-auth-login-base",
            "docs/platform/identity/auth-login-base/prd.md",
            "legacy feature doc\n",
        )

        result, code = run([
            "migrate-feature",
            "--governance-repo", str(governance),
            "--old-id", "platform-identity-auth-login-base",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
            "--source-repo", str(source),
            "--control-repo", tmp,
        ])
        assert_eq("migrate status", result["status"], "pass")
        assert_eq("migrate exit code", code, 0)
        assert_eq("legacy feature reported", result["legacy_feature"], "auth-login-base")

        governance_doc = governance / "features" / "platform" / "identity" / "auth-login" / "docs" / "prd.md"
        mirror_doc = (
            Path(tmp)
            / "docs"
            / "lens-work"
            / "migrations"
            / "platform"
            / "identity"
            / "auth-login"
            / "sources"
            / "branch-docs"
            / "platform-identity-auth-login-base"
            / "branch-docs-flat"
            / "prd.md"
        )
        assert_eq("governance doc exists", governance_doc.exists(), True)
        assert_eq("governance doc content", governance_doc.read_text(encoding="utf-8"), "legacy feature doc\n")
        assert_eq("legacy path mirrored", mirror_doc.exists(), True)


def test_migrate_feature_prefers_branch_docs_over_branch_bmad_output():
    """Branch docs win over feature-scoped branch _bmad-output when relative paths collide."""
    print("test_migrate_feature_prefers_branch_docs_over_branch_bmad_output", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        governance = Path(tmp) / "governance"
        governance.mkdir(parents=True, exist_ok=True)
        source = init_remote_source_repo(tmp)
        create_remote_branch_with_files(
            source,
            "platform-identity-auth-login",
            {
                "docs/platform/identity/auth-login/prd.md": "branch docs wins\n",
                "_bmad-output/lens-work/initiatives/platform/identity/auth-login/prd.md": "branch bmad loses\n",
                "_bmad-output/lens-work/initiatives/platform/identity/initiative.yaml": "shared should stay out\n",
                "_bmad-output/lens-work/initiatives/platform/identity/other/keep.md": "sibling should stay out\n",
            },
        )

        result, code = run([
            "migrate-feature",
            "--governance-repo", str(governance),
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
            "--source-repo", str(source),
            "--control-repo", tmp,
        ])
        assert_eq("migrate status", result["status"], "pass")
        assert_eq("migrate exit code", code, 0)

        governance_doc = governance / "features" / "platform" / "identity" / "auth-login" / "docs" / "prd.md"
        dossier = Path(tmp) / "docs" / "lens-work" / "migrations" / "platform" / "identity" / "auth-login"
        docs_mirror = dossier / "sources" / "branch-docs" / "platform-identity-auth-login" / "branch-docs-flat" / "prd.md"
        bmad_mirror = dossier / "sources" / "bmad-output" / "platform-identity-auth-login" / "branch-bmad-output" / "prd.md"
        shared_mirror = dossier / "sources" / "bmad-output" / "platform-identity-auth-login" / "branch-bmad-output" / "initiative.yaml"
        sibling_mirror = dossier / "sources" / "bmad-output" / "platform-identity-auth-login" / "branch-bmad-output" / "keep.md"

        assert_eq("docs content wins", governance_doc.read_text(encoding="utf-8"), "branch docs wins\n")
        assert_eq("docs mirrored", docs_mirror.exists(), True)
        assert_eq("bmad mirrored", bmad_mirror.exists(), True)
        assert_eq("shared initiative not mirrored", shared_mirror.exists(), False)
        assert_eq("sibling feature file not mirrored", sibling_mirror.exists(), False)

        record = yaml.safe_load((dossier / "migration-record.yaml").read_text(encoding="utf-8"))
        branch_counts = {entry["branch"]: entry for entry in record["documents"]["document_audit"]["branches"]}
        assert_eq(
            "branch audit tracks docs location",
            branch_counts["platform-identity-auth-login"]["governance_repo_by_source"]["branch-docs-flat"],
            1,
        )


def test_dry_run_skips_working_tree_fallback_when_branch_sources_exist():
    """Working-tree docs and _bmad-output stay out of discovery when the branch family already has feature sources."""
    print("test_dry_run_skips_working_tree_fallback_when_branch_sources_exist", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        governance = Path(tmp) / "governance"
        governance.mkdir(parents=True, exist_ok=True)
        source = init_remote_source_repo(tmp)
        create_remote_branch_with_files(
            source,
            "platform-identity-auth-login",
            {
                "docs/platform/identity/feature/auth-login/prd.md": "branch compat\n",
                "_bmad-output/lens-work/initiatives/platform/identity/auth-login/notes.md": "branch bmad\n",
            },
        )
        write_text_file(source, "docs/platform/identity/auth-login/prd.md", "working tree docs\n")
        write_text_file(
            source,
            "_bmad-output/lens-work/initiatives/platform/identity/auth-login/local.md",
            "working tree bmad\n",
        )

        result, code = run([
            "migrate-feature",
            "--governance-repo", str(governance),
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
            "--source-repo", str(source),
            "--control-repo", tmp,
            "--dry-run",
        ])
        assert_eq("dry run status", result["status"], "pass")
        assert_eq("dry run exit code", code, 0)

        source_locations = {entry["source_location"] for entry in result["documents_discovered"]}
        assert_true("branch compat discovered", "branch-docs-compat" in source_locations)
        assert_true("branch bmad discovered", "branch-bmad-output" in source_locations)
        assert_eq("no working-tree docs fallback", "working-tree-docs-fallback" in source_locations, False)
        assert_eq(
            "no working-tree bmad fallback",
            "working-tree-bmad-output-fallback" in source_locations,
            False,
        )


def test_dry_run_uses_working_tree_fallback_when_branch_sources_missing():
    """Working-tree docs and _bmad-output become fallback sources when no branch family content exists."""
    print("test_dry_run_uses_working_tree_fallback_when_branch_sources_missing", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        governance = Path(tmp) / "governance"
        governance.mkdir(parents=True, exist_ok=True)
        source = Path(tmp) / "source"
        source.mkdir(parents=True, exist_ok=True)
        write_text_file(source, "docs/platform/identity/auth-login/prd.md", "working tree docs\n")
        write_text_file(
            source,
            "_bmad-output/lens-work/initiatives/platform/identity/auth-login/local.md",
            "working tree bmad\n",
        )

        result, code = run([
            "migrate-feature",
            "--governance-repo", str(governance),
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
            "--source-repo", str(source),
            "--control-repo", tmp,
            "--dry-run",
        ])
        assert_eq("dry run status", result["status"], "pass")
        assert_eq("dry run exit code", code, 0)

        source_locations = {entry["source_location"] for entry in result["documents_discovered"]}
        assert_true("working-tree docs fallback discovered", "working-tree-docs-fallback" in source_locations)
        assert_true(
            "working-tree bmad fallback discovered",
            "working-tree-bmad-output-fallback" in source_locations,
        )


def test_cleanup_only_deletes_feature_scoped_source_artifacts():
    """cleanup removes only the legacy flat docs path and feature-local _bmad-output artifacts."""
    print("test_cleanup_only_deletes_feature_scoped_source_artifacts", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        governance = Path(tmp) / "governance"
        governance.mkdir(parents=True, exist_ok=True)
        make_branch_dir(str(governance), "platform-identity-auth-login-base")

        source = Path(tmp) / "source"
        source.mkdir(parents=True, exist_ok=True)
        write_text_file(source, "docs/platform/identity/auth-login-base/prd.md", "legacy flat docs\n")
        compat_doc = write_text_file(source, "docs/platform/identity/feature/auth-login-base/compat.md", "compat docs\n")
        feature_yaml = write_text_file(
            source,
            "_bmad-output/lens-work/initiatives/platform/identity/auth-login-base.yaml",
            "feature yaml\n",
        )
        feature_dir_file = write_text_file(
            source,
            "_bmad-output/lens-work/initiatives/platform/identity/auth-login-base/notes.md",
            "feature dir file\n",
        )
        shared_yaml = write_text_file(
            source,
            "_bmad-output/lens-work/initiatives/platform/identity/initiative.yaml",
            "shared yaml\n",
        )
        sibling_file = write_text_file(
            source,
            "_bmad-output/lens-work/initiatives/platform/identity/other/keep.md",
            "sibling file\n",
        )

        migrate_result, migrate_code = run([
            "migrate-feature",
            "--governance-repo", str(governance),
            "--old-id", "platform-identity-auth-login-base",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
            "--source-repo", str(source),
            "--control-repo", tmp,
        ])
        assert_eq("migrate status", migrate_result["status"], "pass")
        assert_eq("migrate exit code", migrate_code, 0)

        cleanup_result, cleanup_code = run([
            "cleanup",
            "--governance-repo", str(governance),
            "--old-id", "platform-identity-auth-login-base",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--source-repo", str(source),
            "--control-repo", tmp,
            "--actor", "testuser",
        ])
        assert_eq("cleanup status", cleanup_result["status"], "pass")
        assert_eq("cleanup exit code", cleanup_code, 0)

        cleaned_sources = {entry["source"] for entry in cleanup_result["cleaned"]}
        assert_true("flat docs deleted", "source-repo-docs-flat" in cleaned_sources)
        assert_true("feature yaml deleted", "source-bmad-output-feature-file" in cleaned_sources)
        assert_true("feature dir deleted", "source-bmad-output-feature-dir" in cleaned_sources)
        assert_eq("flat docs removed", (source / "docs" / "platform" / "identity" / "auth-login-base").exists(), False)
        assert_eq("compat docs preserved", compat_doc.exists(), True)
        assert_eq("feature yaml removed", feature_yaml.exists(), False)
        assert_eq("feature dir file removed", feature_dir_file.exists(), False)
        assert_eq("shared yaml preserved", shared_yaml.exists(), True)
        assert_eq("sibling feature preserved", sibling_file.exists(), True)


def test_verify_fails_when_dossier_mirror_is_missing():
    """verify fails when a recorded mirrored source file is missing from the control-repo dossier."""
    print("test_verify_fails_when_dossier_mirror_is_missing", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        governance = Path(tmp) / "governance"
        governance.mkdir(parents=True, exist_ok=True)
        source = init_remote_source_repo(tmp)
        create_remote_branch_with_file(
            source,
            "platform-identity-auth-login",
            "docs/platform/identity/feature/auth-login/prd.md",
            "prd\n",
        )

        migrate_result, migrate_code = run([
            "migrate-feature",
            "--governance-repo", str(governance),
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
            "--source-repo", str(source),
            "--control-repo", tmp,
        ])
        assert_eq("migrate status", migrate_result["status"], "pass")
        assert_eq("migrate exit code", migrate_code, 0)

        dossier = Path(tmp) / "docs" / "lens-work" / "migrations" / "platform" / "identity" / "auth-login"
        mirror_path = dossier / "sources" / "branch-docs" / "platform-identity-auth-login" / "branch-docs-compat" / "prd.md"
        mirror_path.unlink()

        verify_result, verify_code = run([
            "verify",
            "--governance-repo", str(governance),
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--source-repo", str(source),
            "--control-repo", tmp,
        ])
        assert_eq("verify status", verify_result["status"], "fail")
        assert_eq("verify exit code", verify_code, 1)
        mirror_check = next(c for c in verify_result["checks"] if c["name"] == "mirrored_documents")
        assert_eq("mirror check fails", mirror_check["result"], "fail")


def test_cleanup_writes_approval_and_receipt_artifacts():
    """cleanup writes durable approval and receipt artifacts before and after deletion."""
    print("test_cleanup_writes_approval_and_receipt_artifacts", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        governance = Path(tmp) / "governance"
        governance.mkdir(parents=True, exist_ok=True)
        make_branch_dir(str(governance), "platform-identity-auth-login")

        migrate_result, migrate_code = run([
            "migrate-feature",
            "--governance-repo", str(governance),
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--username", "testuser",
            "--control-repo", tmp,
        ])
        assert_eq("migrate status", migrate_result["status"], "pass")
        assert_eq("migrate exit code", migrate_code, 0)

        cleanup_result, cleanup_code = run([
            "cleanup",
            "--governance-repo", str(governance),
            "--old-id", "platform-identity-auth-login",
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--control-repo", tmp,
            "--actor", "testuser",
        ])
        assert_eq("cleanup exit code", cleanup_code, 0)
        assert_true("approval path returned", bool(cleanup_result.get("approval_record_path")))
        assert_true("receipt path returned", bool(cleanup_result.get("cleanup_receipt_path")))

        approval_path = Path(tmp) / cleanup_result["approval_record_path"]
        receipt_path = Path(tmp) / cleanup_result["cleanup_receipt_path"]
        assert_eq("approval file exists", approval_path.exists(), True)
        assert_eq("receipt file exists", receipt_path.exists(), True)

        receipt = yaml.safe_load(receipt_path.read_text(encoding="utf-8"))
        assert_eq("receipt actor", receipt["executed_by"], "testuser")
        assert_true("legacy branch directory deleted", not (governance / "branches" / "platform-identity-auth-login").exists())


if __name__ == "__main__":
    test_scan_detects_legacy()
    test_scan_derives_components()
    test_scan_empty_branches()
    test_scan_multiple_features()
    test_migrate_feature_creates_yaml()
    test_migrate_feature_creates_index_entry()
    test_migrate_feature_dry_run()
    test_check_conflicts_no_conflict()
    test_check_conflicts_conflict()
    test_invalid_feature_id()
    test_invalid_domain()
    test_governance_repo_not_found()
    test_governance_repo_not_found_migrate()
    test_migrate_feature_resolves_governance_repo_from_control_repo_path()
    test_scan_detects_conflict()
    test_migrate_feature_preserves_legacy_state()
    test_migrate_feature_creates_summary_and_problems_in_feature_dir()
    test_migrate_feature_copies_legacy_artifacts()
    test_migrate_feature_mirrors_base_and_milestone_branch_docs()
    test_migrate_feature_reads_legacy_paths_for_renamed_feature()
    test_migrate_feature_prefers_branch_docs_over_branch_bmad_output()
    test_dry_run_skips_working_tree_fallback_when_branch_sources_exist()
    test_dry_run_uses_working_tree_fallback_when_branch_sources_missing()
    test_cleanup_only_deletes_feature_scoped_source_artifacts()
    test_verify_fails_when_dossier_mirror_is_missing()
    test_cleanup_writes_approval_and_receipt_artifacts()

    print(f"\n{'='*40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'='*40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
