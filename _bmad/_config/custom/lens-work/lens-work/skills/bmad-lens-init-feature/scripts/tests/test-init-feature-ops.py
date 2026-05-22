#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for init-feature-ops.py."""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SCRIPT = str(Path(__file__).parent.parent / "init-feature-ops.py")
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


def git(args: list[str], cwd: str | None = None) -> str:
    """Run a git command for test setup and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed (cwd={cwd}): {(result.stderr or result.stdout).strip()}"
        )
    return result.stdout.strip()


def init_governance_git_repo(root: Path, name: str = "governance") -> tuple[Path, Path]:
    """Create a local bare remote plus a seeded governance clone on main."""
    remote = root / f"{name}-remote.git"
    worktree = root / name

    git(["init", "--bare", "--initial-branch=main", str(remote)])
    git(["clone", str(remote), str(worktree)])
    git(["config", "user.name", "Test User"], cwd=str(worktree))
    git(["config", "user.email", "test@example.com"], cwd=str(worktree))

    (worktree / "README.md").write_text("seed\n", encoding="utf-8")
    git(["add", "README.md"], cwd=str(worktree))
    git(["commit", "-m", "seed"], cwd=str(worktree))
    git(["push", "-u", "origin", "main"], cwd=str(worktree))

    return worktree, remote


def remote_main_sha(remote: Path) -> str:
    """Return the current SHA for refs/heads/main in a bare remote."""
    output = git(["ls-remote", str(remote), "refs/heads/main"])
    return output.split()[0]


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


def canonical_feature_id(domain: str, service: str, feature_slug: str) -> str:
    """Mirror init-feature canonicalization for test expectations."""
    def normalize(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return re.sub(r"-+", "-", normalized)

    return f"{normalize(domain)}-{normalize(service)}-{feature_slug}"


def test_create_feature():
    """Valid feature creation creates feature.yaml, updates feature-index.yaml, creates summary.md."""
    print("test_create_feature", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        expected_feature_id = "platform-identity-auth-refresh"
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "auth-refresh",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Auth Token Refresh",
            "--track", "quickplan",
            "--username", "cweber",
        ])
        assert_eq("create status", result.get("status"), "pass")
        assert_eq("create exit code", code, 0)
        assert_eq("featureId in result", result.get("featureId"), expected_feature_id)
        assert_eq("featureSlug in result", result.get("featureSlug"), "auth-refresh")
        assert_eq("index_updated", result.get("index_updated"), True)
        assert_true("feature_yaml_path in result", result.get("feature_yaml_path"))
        assert_true("summary_path in result", result.get("summary_path"))
        assert_true("container markers returned", len(result.get("container_markers", [])) == 2)
        assert_true("git_commands non-empty", len(result.get("git_commands", [])) > 0)
        assert_true("gh_commands non-empty", len(result.get("gh_commands", [])) > 0)
        assert_eq("governance git executed default false", result.get("governance_git_executed"), False)
        assert_eq("governance commit sha absent by default", result.get("governance_commit_sha"), None)
        assert_eq("remaining git commands stay full plan", result.get("remaining_git_commands"), result.get("git_commands"))
        assert_eq("planning_pr_created", result.get("planning_pr_created"), True)
        assert_eq("starting_phase", result.get("starting_phase"), "businessplan")
        assert_eq("recommended_command", result.get("recommended_command"), "/businessplan")
        assert_eq("router_command", result.get("router_command"), "/next")

        domain_marker = Path(tmp) / "features" / "platform" / "domain.yaml"
        service_marker = Path(tmp) / "features" / "platform" / "identity" / "service.yaml"
        assert_eq("domain marker exists", domain_marker.exists(), True)
        assert_eq("service marker exists", service_marker.exists(), True)

        feature_yaml = Path(tmp) / "features" / "platform" / "identity" / expected_feature_id / "feature.yaml"
        assert_eq("feature.yaml exists", feature_yaml.exists(), True)

        with open(feature_yaml) as f:
            data = yaml.safe_load(f)
        assert_eq("featureId in yaml", data.get("featureId"), expected_feature_id)
        assert_eq("featureSlug in yaml", data.get("featureSlug"), "auth-refresh")
        assert_eq("domain in yaml", data.get("domain"), "platform")
        assert_eq("service in yaml", data.get("service"), "identity")
        assert_eq("phase in yaml", data.get("phase"), "businessplan")
        assert_eq("track in yaml", data.get("track"), "quickplan")
        assert_eq("team lead", data.get("team", [{}])[0].get("role"), "lead")
        assert_eq("team username", data.get("team", [{}])[0].get("username"), "cweber")
        assert_eq("docs.path", data.get("docs", {}).get("path"), f"docs/platform/identity/{expected_feature_id}")
        assert_eq("docs.governance_docs_path", data.get("docs", {}).get("governance_docs_path"), f"features/platform/identity/{expected_feature_id}/docs")

        index_path = Path(tmp) / "feature-index.yaml"
        assert_eq("feature-index.yaml exists", index_path.exists(), True)

        with open(index_path) as f:
            idx = yaml.safe_load(f)
        ids = [e.get("id") for e in idx.get("features", [])]
        assert_true("canonical feature id in index", expected_feature_id in ids)

        entry = next(e for e in idx["features"] if e["id"] == expected_feature_id)
        assert_eq("index entry domain", entry.get("domain"), "platform")
        assert_eq("index entry service", entry.get("service"), "identity")
        assert_eq("index entry featureSlug", entry.get("featureSlug"), "auth-refresh")
        assert_eq("index entry status", entry.get("status"), "businessplan")
        assert_eq("index entry owner", entry.get("owner"), "cweber")
        assert_eq("index entry plan_branch", entry.get("plan_branch"), f"{expected_feature_id}-plan")

        summary_path = Path(tmp) / "features" / "platform" / "identity" / expected_feature_id / "summary.md"
        assert_eq("summary.md exists", summary_path.exists(), True)
        summary_text = summary_path.read_text()
        assert_true("summary contains starting phase", "Status: businessplan" in summary_text)
        assert_true("summary contains feature name", "Auth Token Refresh" in summary_text)
        assert_true("summary contains featureId", expected_feature_id in summary_text)


def test_full_track_starts_in_preplan():
    """Full track starts at preplan and recommends the preplan phase command."""
    print("test_full_track_starts_in_preplan", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        expected_feature_id = "platform-identity-full-feature"
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "full-feature",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Full Feature",
            "--track", "full",
            "--username", "cweber",
        ])

        assert_eq("full create status", result.get("status"), "pass")
        assert_eq("full create exit code", code, 0)
        assert_eq("full featureId", result.get("featureId"), expected_feature_id)
        assert_eq("full featureSlug", result.get("featureSlug"), "full-feature")
        assert_eq("full starting_phase", result.get("starting_phase"), "preplan")
        assert_eq("full recommended_command", result.get("recommended_command"), "/preplan")
        assert_eq("full router_command", result.get("router_command"), "/next")

        feature_yaml = Path(tmp) / "features" / "platform" / "identity" / expected_feature_id / "feature.yaml"
        with open(feature_yaml) as f:
            data = yaml.safe_load(f)
        assert_eq("full phase in yaml", data.get("phase"), "preplan")

        index_path = Path(tmp) / "feature-index.yaml"
        with open(index_path) as f:
            idx = yaml.safe_load(f)
        entry = next(e for e in idx["features"] if e["id"] == expected_feature_id)
        assert_eq("full index status", entry.get("status"), "preplan")


def test_create_domain_marker():
    """Domain container creation writes the governance marker and returns git commands."""
    print("test_create_domain_marker", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create-domain",
            "--governance-repo", tmp,
            "--domain", "platform",
            "--name", "Platform",
            "--username", "cweber",
        ])

        assert_eq("domain create status", result.get("status"), "pass")
        assert_eq("domain create exit code", code, 0)
        assert_eq("domain scope", result.get("scope"), "domain")
        assert_true("domain git commands non-empty", len(result.get("git_commands", [])) > 0)

        marker_path = Path(tmp) / "features" / "platform" / "domain.yaml"
        assert_eq("domain marker exists", marker_path.exists(), True)

        with open(marker_path) as f:
            data = yaml.safe_load(f)
        assert_eq("domain marker kind", data.get("kind"), "domain")
        assert_eq("domain marker id", data.get("id"), "platform")
        assert_eq("domain marker owner", data.get("owner"), "cweber")


def test_create_service_marker_creates_parent_domain():
    """Service container creation creates the service marker and an implicit domain marker when needed."""
    print("test_create_service_marker_creates_parent_domain", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create-service",
            "--governance-repo", tmp,
            "--domain", "platform",
            "--service", "identity",
            "--name", "Identity",
            "--username", "cweber",
        ])

        assert_eq("service create status", result.get("status"), "pass")
        assert_eq("service create exit code", code, 0)
        assert_eq("service scope", result.get("scope"), "service")
        assert_eq("parent domain created", result.get("created_domain_marker"), True)
        assert_eq("two markers created", len(result.get("created_marker_paths", [])), 2)

        domain_marker = Path(tmp) / "features" / "platform" / "domain.yaml"
        service_marker = Path(tmp) / "features" / "platform" / "identity" / "service.yaml"
        assert_eq("implicit domain marker exists", domain_marker.exists(), True)
        assert_eq("service marker exists", service_marker.exists(), True)

        with open(service_marker) as f:
            data = yaml.safe_load(f)
        assert_eq("service marker kind", data.get("kind"), "service")
        assert_eq("service marker name", data.get("name"), "Identity")


def test_duplicate_domain_service_rejected():
    """Duplicate container markers fail with a clear error."""
    print("test_duplicate_domain_service_rejected", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        first_domain, code1 = run([
            "create-domain",
            "--governance-repo", tmp,
            "--domain", "platform",
            "--username", "cweber",
        ])
        assert_eq("first domain status", first_domain.get("status"), "pass")
        assert_eq("first domain exit code", code1, 0)

        second_domain, code2 = run([
            "create-domain",
            "--governance-repo", tmp,
            "--domain", "platform",
            "--username", "cweber",
        ])
        assert_eq("duplicate domain status", second_domain.get("status"), "fail")
        assert_eq("duplicate domain exit code", code2, 1)

        first_service, code3 = run([
            "create-service",
            "--governance-repo", tmp,
            "--domain", "platform",
            "--service", "identity",
            "--username", "cweber",
        ])
        assert_eq("first service status", first_service.get("status"), "pass")
        assert_eq("first service exit code", code3, 0)

        second_service, code4 = run([
            "create-service",
            "--governance-repo", tmp,
            "--domain", "platform",
            "--service", "identity",
            "--username", "cweber",
        ])
        assert_eq("duplicate service status", second_service.get("status"), "fail")
        assert_eq("duplicate service exit code", code4, 1)


def test_index_created_when_missing():
    """feature-index.yaml is created when it does not exist."""
    print("test_index_created_when_missing", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        index_path = Path(tmp) / "feature-index.yaml"
        assert_eq("index absent before create", index_path.exists(), False)

        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "new-feature",
            "--domain", "core",
            "--service", "api",
            "--name", "New Feature",
            "--track", "quickplan",
            "--username", "testuser",
        ])
        assert_eq("create status", result.get("status"), "pass")
        assert_eq("index now exists", index_path.exists(), True)

        with open(index_path) as f:
            idx = yaml.safe_load(f)
        assert_eq("index has one entry", len(idx.get("features", [])), 1)


def test_dry_run():
    """Dry run returns planned operations but creates no files."""
    print("test_dry_run", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "dry-feature",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Dry Feature",
            "--track", "quickplan",
            "--username", "cweber",
            "--dry-run",
        ])
        assert_eq("dry run status", result.get("status"), "pass")
        assert_eq("dry run flag in result", result.get("dry_run"), True)
        assert_eq("dry run exit code", code, 0)
        assert_true("git_commands present", len(result.get("git_commands", [])) > 0)
        assert_true("gh_commands present", len(result.get("gh_commands", [])) > 0)
        assert_eq("dry run governance executed false", result.get("governance_git_executed"), False)
        assert_eq("dry run governance sha absent", result.get("governance_commit_sha"), None)
        assert_eq("dry run remaining git commands stay full plan", result.get("remaining_git_commands"), result.get("git_commands"))
        assert_eq("dry run planning_pr_created", result.get("planning_pr_created"), True)
        assert_eq("dry run starting_phase", result.get("starting_phase"), "businessplan")
        assert_eq("dry run recommended_command", result.get("recommended_command"), "/businessplan")
        assert_eq("dry run router_command", result.get("router_command"), "/next")

        feature_yaml = Path(tmp) / "features" / "platform" / "identity" / "dry-feature" / "feature.yaml"
        assert_eq("feature.yaml not created", feature_yaml.exists(), False)


def test_express_track_defers_planning_pr():
    """Express track creates branches but defers the empty planning PR until artifacts exist."""
    print("test_express_track_defers_planning_pr", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        expected_feature_id = "platform-identity-express-feature"
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "express-feature",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Express Feature",
            "--track", "express",
            "--username", "cweber",
        ])

        assert_eq("express create status", result.get("status"), "pass")
        assert_eq("express create exit code", code, 0)
        assert_eq("express featureId", result.get("featureId"), expected_feature_id)
        assert_eq("express featureSlug", result.get("featureSlug"), "express-feature")
        assert_eq("express planning_pr_created", result.get("planning_pr_created"), False)
        assert_eq("express gh_commands empty", result.get("gh_commands", []), [])
        assert_eq("express starting_phase", result.get("starting_phase"), "expressplan")
        assert_eq("express recommended_command", result.get("recommended_command"), "/expressplan")
        assert_eq("express router_command", result.get("router_command"), "/next")

        feature_yaml = Path(tmp) / "features" / "platform" / "identity" / expected_feature_id / "feature.yaml"
        with open(feature_yaml) as f:
            data = yaml.safe_load(f)
        assert_eq("express phase in yaml", data.get("phase"), "expressplan")

        index_path = Path(tmp) / "feature-index.yaml"
        assert_eq("index created", index_path.exists(), True)
        with open(index_path) as f:
            idx = yaml.safe_load(f)
        entry = next(e for e in idx["features"] if e["id"] == expected_feature_id)
        assert_eq("express index status", entry.get("status"), "expressplan")


def test_invalid_feature_id():
    """Non-kebab-case and path-traversal featureIds are rejected."""
    print("test_invalid_feature_id", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        base = [
            "--governance-repo", tmp,
            "--domain", "core",
            "--service", "api",
            "--name", "Bad",
            "--track", "quickplan",
            "--username", "testuser",
        ]

        result, code = run(["create", "--feature-id", "../../etc/passwd"] + base)
        assert_eq("path traversal rejected", result.get("status"), "fail")
        assert_eq("path traversal exit code", code, 1)
        assert_true("error mentions Invalid", "Invalid" in result.get("error", ""))

        result, code = run(["create", "--feature-id", "CamelCase"] + base)
        assert_eq("uppercase rejected", result.get("status"), "fail")

        result, code = run(["create", "--feature-id", "has spaces"] + base)
        assert_eq("spaces rejected", result.get("status"), "fail")

        result, code = run(["create", "--feature-id", "auth.login_v2"] + base)
        assert_eq("dots/underscores rejected (stricter pattern)", result.get("status"), "fail")

        result, code = run(["create", "--feature-id", "valid-id-123"] + base)
        assert_eq("valid kebab accepted", result.get("status"), "pass")
    assert_eq("valid kebab canonicalized", result.get("featureId"), "core-api-valid-id-123")
    assert_eq("valid kebab featureSlug", result.get("featureSlug"), "valid-id-123")

    result, code = run(["create", "--feature-id", "core-api-canonical-feature"] + base)
    assert_eq("canonical featureId accepted", result.get("status"), "pass")
    assert_eq("canonical featureId preserved", result.get("featureId"), "core-api-canonical-feature")
    assert_eq("canonical featureId slug extracted", result.get("featureSlug"), "canonical-feature")


def test_invalid_domain_service():
    """Path traversal in domain or service is rejected."""
    print("test_invalid_domain_service", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "good-id",
            "--domain", "../evil",
            "--service", "api",
            "--name", "Bad",
            "--track", "quickplan",
            "--username", "testuser",
        ])
        assert_eq("bad domain rejected", result.get("status"), "fail")
        assert_eq("bad domain exit code", code, 1)

        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "good-id2",
            "--domain", "core",
            "--service", "../../etc",
            "--name", "Bad",
            "--track", "quickplan",
            "--username", "testuser",
        ])
        assert_eq("bad service rejected", result.get("status"), "fail")


def test_duplicate_feature():
    """Creating a feature whose ID already exists in feature-index.yaml fails."""
    print("test_duplicate_feature", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        args = [
            "create",
            "--governance-repo", tmp,
            "--feature-id", "dup-check",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Dup Check",
            "--track", "quickplan",
            "--username", "cweber",
        ]
        first, code1 = run(args)
        assert_eq("first create passes", first.get("status"), "pass")
        assert_eq("first create exit code", code1, 0)

        second, code2 = run(args)
        assert_eq("duplicate rejected", second.get("status"), "fail")
        assert_eq("duplicate exit code", code2, 1)
        assert_true("error mentions already exists", "already exists" in second.get("error", ""))


def test_same_local_feature_slug_allowed_in_different_services():
    """The same local feature slug can coexist because the canonical featureId includes domain and service."""
    print("test_same_local_feature_slug_allowed_in_different_services", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        first, code1 = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "shared-name",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Shared Name",
            "--track", "quickplan",
            "--username", "cweber",
        ])
        second, code2 = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "shared-name",
            "--domain", "platform",
            "--service", "payments",
            "--name", "Shared Name",
            "--track", "quickplan",
            "--username", "cweber",
        ])

        assert_eq("first shared-name status", first.get("status"), "pass")
        assert_eq("first shared-name exit code", code1, 0)
        assert_eq("second shared-name status", second.get("status"), "pass")
        assert_eq("second shared-name exit code", code2, 0)
        assert_eq("first shared-name featureId", first.get("featureId"), "platform-identity-shared-name")
        assert_eq("second shared-name featureId", second.get("featureId"), "platform-payments-shared-name")

        with open(Path(tmp) / "feature-index.yaml") as f:
            index = yaml.safe_load(f)
        ids = [entry.get("id") for entry in index.get("features", [])]
        assert_true("identity feature recorded", "platform-identity-shared-name" in ids)
        assert_true("payments feature recorded", "platform-payments-shared-name" in ids)


def test_missing_required_args():
    """Missing required args cause non-zero exit without valid JSON."""
    print("test_missing_required_args", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "incomplete",
            # missing --domain, --service, --name, --username
        ])
        assert_true("missing args fails", code != 0)

        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--domain", "platform",
            "--service", "identity",
            "--name", "No ID",
            "--track", "quickplan",
            "--username", "cweber",
            # missing --feature-id
        ])
        assert_true("missing feature-id fails", code != 0)


def test_track_must_be_explicit():
    """Feature creation fails with a clear error when track is omitted."""
    print("test_track_must_be_explicit", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "missing-track",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Missing Track",
            "--username", "cweber",
        ])
        assert_eq("missing track status", result.get("status"), "fail")
        assert_eq("missing track exit code", code, 1)
        assert_true("missing track error mentions track", "track" in result.get("error", "").lower())


def test_fetch_context_with_existing_index():
    """fetch-context returns related features and depends_on paths."""
    print("test_fetch_context_with_existing_index", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        auth_login_id = canonical_feature_id("platform", "identity", "auth-login")
        auth_refresh_id = canonical_feature_id("platform", "identity", "auth-refresh")
        payment_api_id = canonical_feature_id("commerce", "payments", "payment-api")
        for fid, domain, service in [
            ("auth-login", "platform", "identity"),
            ("auth-refresh", "platform", "identity"),
            ("payment-api", "commerce", "payments"),
        ]:
            run([
                "create",
                "--governance-repo", tmp,
                "--feature-id", fid,
                "--domain", domain,
                "--service", service,
                "--name", fid.replace("-", " ").title(),
                "--track", "quickplan",
                "--username", "cweber",
            ])

        result, code = run([
            "fetch-context",
            "--governance-repo", tmp,
            "--feature-id", auth_login_id,
        ])
        assert_eq("fetch-context status", result.get("status"), "pass")
        assert_eq("fetch-context exit code", code, 0)
        assert_true("related list present", "related" in result)
        assert_true("depends_on list present", "depends_on" in result)
        assert_true("context_paths present", "context_paths" in result)

        related = result.get("related", [])
        assert_true("auth-refresh in related (same domain)", auth_refresh_id in related)
        assert_true("payment-api not in related (diff domain)", payment_api_id not in related)
        assert_true("auth-login not in own related list", auth_login_id not in related)

        context_paths = result.get("context_paths", [])
        assert_true("context paths are summary.md (summaries depth)", all("summary.md" in p for p in context_paths))


def test_fetch_context_full_depth():
    """fetch-context --depth full returns feature.yaml paths for related features."""
    print("test_fetch_context_full_depth", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_a_id = canonical_feature_id("core", "svc", "feat-a")
        for fid in ["feat-a", "feat-b"]:
            run([
                "create",
                "--governance-repo", tmp,
                "--feature-id", fid,
                "--domain", "core",
                "--service", "svc",
                "--name", fid.replace("-", " ").title(),
                "--track", "quickplan",
                "--username", "cweber",
            ])

        result, code = run([
            "fetch-context",
            "--governance-repo", tmp,
            "--feature-id", feature_a_id,
            "--depth", "full",
        ])
        assert_eq("full depth status", result.get("status"), "pass")
        context_paths = result.get("context_paths", [])
        assert_true("full depth returns feature.yaml paths", all("feature.yaml" in p for p in context_paths))


def test_fetch_context_feature_not_found():
    """fetch-context fails when the featureId is not in the index."""
    print("test_fetch_context_feature_not_found", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "some-feature",
            "--domain", "core",
            "--service", "api",
            "--name", "Some Feature",
            "--track", "quickplan",
            "--username", "cweber",
        ])

        result, code = run([
            "fetch-context",
            "--governance-repo", tmp,
            "--feature-id", "nonexistent",
        ])
        assert_eq("not found status", result.get("status"), "fail")
        assert_eq("not found exit code", code, 1)


def test_fetch_context_no_index():
    """fetch-context fails gracefully when feature-index.yaml is absent."""
    print("test_fetch_context_no_index", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "fetch-context",
            "--governance-repo", tmp,
            "--feature-id", "any-feature",
        ])
        assert_eq("no index status", result.get("status"), "fail")
        assert_eq("no index exit code", code, 1)


def test_fetch_context_uses_feature_yaml_dependencies():
    """fetch-context reads depends_on from feature.yaml instead of stale index metadata."""
    print("test_fetch_context_uses_feature_yaml_dependencies", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_a_id = canonical_feature_id("core", "svc", "feat-a")
        feature_b_id = canonical_feature_id("core", "svc", "feat-b")
        for fid in ["feat-a", "feat-b"]:
            run([
                "create",
                "--governance-repo", tmp,
                "--feature-id", fid,
                "--domain", "core",
                "--service", "svc",
                "--name", fid.replace("-", " ").title(),
                "--track", "quickplan",
                "--username", "cweber",
            ])

        feature_path = Path(tmp) / "features" / "core" / "svc" / feature_a_id / "feature.yaml"
        feature_data = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
        feature_data.setdefault("dependencies", {})["depends_on"] = [feature_b_id]
        feature_path.write_text(yaml.dump(feature_data, sort_keys=False), encoding="utf-8")

        dep_docs = Path(tmp) / "features" / "core" / "svc" / feature_b_id / "docs"
        dep_docs.mkdir(parents=True, exist_ok=True)
        (dep_docs / "prd.md").write_text("# Dep PRD\n", encoding="utf-8")

        result, code = run([
            "fetch-context",
            "--governance-repo", tmp,
            "--feature-id", feature_a_id,
            "--depth", "full",
        ])
        assert_eq("feature yaml dep status", result.get("status"), "pass")
        assert_eq("feature yaml dep exit code", code, 0)
        assert_true("depends_on contains canonical feat-b", feature_b_id in result.get("depends_on", []))
        paths = result.get("context_paths", [])
        assert_true("dependency feature yaml included", any(f"{feature_b_id}/feature.yaml" in p for p in paths))
        assert_true("dependency docs included", any(f"{feature_b_id}/docs/prd.md" in p for p in paths))


def test_fetch_context_service_refs_include_service_context():
    """fetch-context returns governance files for explicitly named services."""
    print("test_fetch_context_service_refs_include_service_context", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        auth_login_id = canonical_feature_id("platform", "identity", "auth-login")
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Auth Login",
            "--track", "quickplan",
            "--username", "cweber",
        ])

        service_dir = Path(tmp) / "features" / "platform" / "payments"
        service_dir.mkdir(parents=True, exist_ok=True)
        (service_dir / "service.yaml").write_text("kind: service\nid: platform-payments\n", encoding="utf-8")
        docs_dir = service_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "overview.md").write_text("# Payments\n", encoding="utf-8")
        feature_dir = service_dir / "invoice-sync"
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "summary.md").write_text("# Invoice Sync\n", encoding="utf-8")

        result, code = run([
            "fetch-context",
            "--governance-repo", tmp,
            "--feature-id", auth_login_id,
            "--service-ref", "payments",
        ])
        assert_eq("service ref status", result.get("status"), "pass")
        assert_eq("service ref exit code", code, 0)
        assert_eq("service ref echoed", result.get("service_refs"), ["payments"])
        service_paths = result.get("service_context_paths", [])
        assert_true("service yaml included", any("features/platform/payments/service.yaml" in p for p in service_paths))
        assert_true("service docs included", any("features/platform/payments/docs/overview.md" in p for p in service_paths))
        assert_true("service summary included", any("features/platform/payments/invoice-sync/summary.md" in p for p in service_paths))


def test_fetch_context_service_ref_text_detects_service_context():
    """fetch-context can infer service refs from recent conversation text."""
    print("test_fetch_context_service_ref_text_detects_service_context", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        auth_login_id = canonical_feature_id("platform", "identity", "auth-login")
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Auth Login",
            "--track", "quickplan",
            "--username", "cweber",
        ])

        service_dir = Path(tmp) / "features" / "platform" / "payments"
        service_dir.mkdir(parents=True, exist_ok=True)
        (service_dir / "service.yaml").write_text("kind: service\nid: platform-payments\n", encoding="utf-8")
        docs_dir = service_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "handoff.md").write_text("# Payments Handoff\n", encoding="utf-8")

        result, code = run([
            "fetch-context",
            "--governance-repo", tmp,
            "--feature-id", auth_login_id,
            "--service-ref-text", "We need to coordinate the payments service before drafting the processor plan.",
        ])
        assert_eq("service text status", result.get("status"), "pass")
        assert_eq("service text exit code", code, 0)
        assert_eq("detected service ref", result.get("detected_service_refs"), ["payments"])
        assert_eq("service refs include detected service", result.get("service_refs"), ["payments"])
        service_paths = result.get("service_context_paths", [])
        assert_true("detected service docs included", any("features/platform/payments/docs/handoff.md" in p for p in service_paths))
        assert_eq("no missing service refs", result.get("missing_service_refs"), [])


def test_fetch_context_reports_missing_detected_service_context():
    """fetch-context reports detected services that have no governance docs yet."""
    print("test_fetch_context_reports_missing_detected_service_context", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature_index = {
            "features": [
                {
                    "id": "auth-login",
                    "domain": "platform",
                    "service": "identity",
                    "status": "preplan",
                    "owner": "cweber",
                },
                {
                    "id": "payments-shell",
                    "domain": "platform",
                    "service": "payments",
                    "status": "preplan",
                    "owner": "cweber",
                },
            ]
        }
        Path(tmp, "feature-index.yaml").write_text(
            yaml.dump(feature_index, sort_keys=False),
            encoding="utf-8",
        )

        target_feature_dir = Path(tmp) / "features" / "platform" / "identity" / "auth-login"
        target_feature_dir.mkdir(parents=True, exist_ok=True)
        target_feature = make_feature_yaml_fixture("auth-login", "platform", "identity")
        (target_feature_dir / "feature.yaml").write_text(
            yaml.dump(target_feature, sort_keys=False),
            encoding="utf-8",
        )

        result, code = run([
            "fetch-context",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--service-ref-text", "Payments must be grounded before we continue.",
        ])
        assert_eq("missing detected service status", result.get("status"), "pass")
        assert_eq("missing detected service exit code", code, 0)
        assert_eq("missing detected service ref", result.get("detected_service_refs"), ["payments"])
        assert_eq("missing service refs reported", result.get("missing_service_refs"), ["payments"])
        assert_eq("no service context paths when missing", result.get("service_context_paths"), [])


def test_fetch_context_service_ref_text_scopes_to_target_domain():
    """fetch-context only loads service context from the target feature's domain."""
    print("test_fetch_context_service_ref_text_scopes_to_target_domain", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        platform_auth_id = canonical_feature_id("platform", "identity", "platform-auth")
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "platform-auth",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Platform Auth",
            "--track", "quickplan",
            "--username", "cweber",
        ])

        for domain in ["platform", "core"]:
            service_dir = Path(tmp) / "features" / domain / "payments"
            service_dir.mkdir(parents=True, exist_ok=True)
            (service_dir / "service.yaml").write_text(
                f"kind: service\nid: {domain}-payments\n",
                encoding="utf-8",
            )
            docs_dir = service_dir / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / f"{domain}.md").write_text(f"# {domain} payments\n", encoding="utf-8")

        result, code = run([
            "fetch-context",
            "--governance-repo", tmp,
            "--feature-id", platform_auth_id,
            "--service-ref-text", "We also need the payments service in scope.",
        ])
        assert_eq("domain-scoped service status", result.get("status"), "pass")
        assert_eq("domain-scoped service exit code", code, 0)
        service_paths = result.get("service_context_paths", [])
        assert_true("platform service docs included", any("features/platform/payments/docs/platform.md" in p for p in service_paths))
        assert_true("core service docs excluded", all("features/core/payments/" not in p for p in service_paths))


def test_fetch_context_service_context_without_service_marker():
    """fetch-context can still load child summaries when a service marker is missing."""
    print("test_fetch_context_service_context_without_service_marker", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        auth_login_id = canonical_feature_id("platform", "identity", "auth-login")
        run([
            "create",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Auth Login",
            "--track", "quickplan",
            "--username", "cweber",
        ])

        payments_feature_dir = Path(tmp) / "features" / "platform" / "payments" / "invoice-sync"
        payments_feature_dir.mkdir(parents=True, exist_ok=True)
        (payments_feature_dir / "summary.md").write_text("# Invoice Sync\n", encoding="utf-8")

        result, code = run([
            "fetch-context",
            "--governance-repo", tmp,
            "--feature-id", auth_login_id,
            "--service-ref", "payments",
        ])
        assert_eq("summary-only service status", result.get("status"), "pass")
        assert_eq("summary-only service exit code", code, 0)
        assert_true(
            "summary-only service included",
            any("features/platform/payments/invoice-sync/summary.md" in p for p in result.get("service_context_paths", [])),
        )
        assert_eq("summary-only service not marked missing", result.get("missing_service_refs"), [])


def test_control_repo_git_commands():
    """When control-repo differs from governance-repo, follow-up uses git-orchestration branch creation."""
    print("test_control_repo_git_commands", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as ctrl_tmp:
            expected_feature_id = canonical_feature_id("platform", "svc", "ctrl-test")
            result, code = run([
                "create",
                "--governance-repo", gov_tmp,
                "--control-repo", ctrl_tmp,
                "--feature-id", "ctrl-test",
                "--domain", "platform",
                "--service", "svc",
                "--name", "Control Repo Test",
                "--track", "quickplan",
                "--username", "cweber",
                "--dry-run",
            ])
            assert_eq("ctrl repo dry run status", result.get("status"), "pass")
            git_cmds = result.get("git_commands", [])
            assert_true(
                "ctrl repo commands returned separately",
                len(result.get("control_repo_git_commands", [])) > 0,
            )
            assert_true(
                "ctrl repo checkout in git commands",
                any(ctrl_tmp in c for c in git_cmds),
            )
            assert_true(
                "gov repo checkout in git commands",
                any(gov_tmp in c for c in git_cmds),
            )
            assert_true(
                "control repo branch creation delegated to git orchestration",
                any("git-orchestration-ops.py create-feature-branches" in c for c in git_cmds),
            )
            assert_true(
                "control repo command includes governance repo",
                any(f"--governance-repo {gov_tmp}" in c for c in git_cmds),
            )
            assert_true(
                "control repo command includes working repo",
                any(f"--repo {ctrl_tmp}" in c for c in git_cmds),
            )
            assert_true(
                "control repo command includes feature id",
                any(f"--feature-id {expected_feature_id}" in c for c in git_cmds),
            )
            activation_cmds = result.get("control_repo_activation_commands", [])
            assert_true(
                "control repo activation commands returned separately",
                len(activation_cmds) > 0,
            )
            assert_true(
                "activation routes through switch ops",
                any("switch-ops.py switch" in c for c in activation_cmds),
            )
            assert_true(
                "activation command includes governance repo",
                any(f"--governance-repo {gov_tmp}" in c for c in activation_cmds),
            )
            assert_true(
                "activation command includes control repo",
                any(f"--control-repo {ctrl_tmp}" in c for c in activation_cmds),
            )
            assert_true(
                "activation command includes feature id",
                any(f"--feature-id {expected_feature_id}" in c for c in activation_cmds),
            )
            assert_eq(
                "remaining commands append activation",
                result.get("remaining_commands"),
                result.get("remaining_git_commands") + activation_cmds,
            )
            assert_true(
                "raw checkout feature command removed",
                not any(f"git -C {ctrl_tmp} checkout -b {expected_feature_id}" == c for c in git_cmds),
            )
            assert_true(
                "raw checkout plan command removed",
                not any(f"git -C {ctrl_tmp} checkout -b {expected_feature_id}-plan" == c for c in git_cmds),
            )


def test_control_repo_activation_commands_include_personal_folder():
    """Feature follow-up activation preserves the configured personal folder."""
    print("test_control_repo_activation_commands_include_personal_folder", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as ctrl_tmp:
            with tempfile.TemporaryDirectory() as personal_tmp:
                result, code = run([
                    "create",
                    "--governance-repo", gov_tmp,
                    "--control-repo", ctrl_tmp,
                    "--feature-id", "ctrl-test",
                    "--domain", "platform",
                    "--service", "svc",
                    "--name", "Control Repo Test",
                    "--track", "quickplan",
                    "--username", "cweber",
                    "--personal-folder", personal_tmp,
                    "--dry-run",
                ])

                assert_eq("activation personal folder status", result.get("status"), "pass")
                assert_eq("activation personal folder exit code", code, 0)
                activation_cmds = result.get("control_repo_activation_commands", [])
                assert_true("activation commands present", activation_cmds)
                assert_true(
                    "activation command carries personal folder",
                    any(f"--personal-folder {personal_tmp}" in c for c in activation_cmds),
                )


def test_create_feature_execute_governance_git():
    """Feature creation can publish governance artifacts automatically while leaving control-repo follow-up explicit."""
    print("test_create_feature_execute_governance_git", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        governance_repo, remote = init_governance_git_repo(root)
        control_repo = root / "control"
        control_repo.mkdir(parents=True, exist_ok=True)
        expected_feature_id = "platform-identity-auth-refresh"

        result, code = run([
            "create",
            "--governance-repo", str(governance_repo),
            "--control-repo", str(control_repo),
            "--feature-id", "auth-refresh",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Auth Token Refresh",
            "--track", "quickplan",
            "--username", "cweber",
            "--execute-governance-git",
        ])

        assert_eq("feature execute status", result.get("status"), "pass")
        assert_eq("feature execute exit code", code, 0)
        assert_eq("feature governance git executed", result.get("governance_git_executed"), True)
        assert_true("feature governance commit sha present", result.get("governance_commit_sha"))
        assert_true("feature governance git commands present", result.get("governance_git_commands"))
        assert_true("feature control repo git commands present", result.get("control_repo_git_commands"))
        assert_true("feature control repo activation commands present", result.get("control_repo_activation_commands"))
        assert_eq(
            "feature remaining commands limited to control repo",
            result.get("remaining_git_commands"),
            result.get("control_repo_git_commands"),
        )
        assert_eq(
            "feature remaining commands append activation",
            result.get("remaining_commands"),
            result.get("control_repo_git_commands") + result.get("control_repo_activation_commands"),
        )
        assert_true("feature gh commands still present", result.get("gh_commands"))

        feature_yaml = governance_repo / "features" / "platform" / "identity" / expected_feature_id / "feature.yaml"
        summary_path = governance_repo / "features" / "platform" / "identity" / expected_feature_id / "summary.md"
        assert_eq("feature yaml exists after publish", feature_yaml.exists(), True)
        assert_eq("summary exists after publish", summary_path.exists(), True)
        assert_eq(
            "feature short sha matches repo head",
            result.get("governance_commit_sha"),
            git(["rev-parse", "--short", "HEAD"], cwd=str(governance_repo)),
        )
        assert_eq(
            "feature remote main updated",
            remote_main_sha(remote),
            git(["rev-parse", "HEAD"], cwd=str(governance_repo)),
        )


def test_create_feature_execute_governance_git_dry_run_skips_git():
    """Dry-run with automatic governance enabled should still only preview feature publish commands."""
    print("test_create_feature_execute_governance_git_dry_run_skips_git", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as ctrl_tmp:
            expected_feature_id = "platform-identity-auth-refresh"
            result, code = run([
                "create",
                "--governance-repo", gov_tmp,
                "--control-repo", ctrl_tmp,
                "--feature-id", "auth-refresh",
                "--domain", "platform",
                "--service", "identity",
                "--name", "Auth Token Refresh",
                "--track", "quickplan",
                "--username", "cweber",
                "--execute-governance-git",
                "--dry-run",
            ])

            assert_eq("feature execute dry-run status", result.get("status"), "pass")
            assert_eq("feature execute dry-run exit code", code, 0)
            assert_eq("feature execute dry-run executed flag", result.get("governance_git_executed"), False)
            assert_eq("feature execute dry-run commit sha", result.get("governance_commit_sha"), None)
            assert_eq(
                "feature execute dry-run remaining commands stay full plan",
                result.get("remaining_git_commands"),
                result.get("git_commands"),
            )
            assert_eq(
                "feature execute dry-run remaining commands append activation",
                result.get("remaining_commands"),
                result.get("remaining_git_commands") + result.get("control_repo_activation_commands"),
            )
            assert_true("feature execute dry-run governance commands present", result.get("governance_git_commands"))
            assert_true("feature execute dry-run control repo commands present", result.get("control_repo_git_commands"))
            assert_true("feature execute dry-run activation commands present", result.get("control_repo_activation_commands"))
            assert_eq(
                "dry-run feature yaml absent",
                (Path(gov_tmp) / "features" / "platform" / "identity" / expected_feature_id / "feature.yaml").exists(),
                False,
            )


def test_create_feature_execute_governance_git_requires_clean_repo():
    """Feature auto-publish fails fast when the governance repo has local changes."""
    print("test_create_feature_execute_governance_git_requires_clean_repo", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        governance_repo, _remote = init_governance_git_repo(root)
        expected_feature_id = "platform-identity-auth-refresh"

        dirty_file = governance_repo / "DIRTY.md"
        dirty_file.write_text("dirty\n", encoding="utf-8")

        result, code = run([
            "create",
            "--governance-repo", str(governance_repo),
            "--feature-id", "auth-refresh",
            "--domain", "platform",
            "--service", "identity",
            "--name", "Auth Token Refresh",
            "--track", "quickplan",
            "--username", "cweber",
            "--execute-governance-git",
        ])

        assert_eq("feature dirty repo status", result.get("status"), "fail")
        assert_eq("feature dirty repo exit code", code, 1)
        assert_true("feature dirty repo surfaced preflight error", "Governance git preflight failed" in (result.get("error") or ""))
        assert_eq(
            "feature yaml not created after dirty preflight failure",
            (governance_repo / "features" / "platform" / "identity" / expected_feature_id / "feature.yaml").exists(),
            False,
        )


def make_feature_yaml_fixture(feature_id: str, domain: str, service: str) -> dict:
    """Return a minimal feature.yaml payload for fetch-context tests."""
    return {
        "name": feature_id.replace("-", " ").title(),
        "description": "",
        "featureId": feature_id,
        "domain": domain,
        "service": service,
        "phase": "preplan",
        "track": "quickplan",
        "milestones": {},
        "team": [{"username": "cweber", "role": "lead"}],
        "dependencies": {"depends_on": [], "depended_by": []},
        "target_repos": [],
        "links": {"retrospective": None, "issues": [], "pull_request": None},
        "priority": "medium",
        "created": "2026-04-10T00:00:00Z",
        "updated": "2026-04-10T00:00:00Z",
        "phase_transitions": [],
        "docs": {
            "path": f"docs/{domain}/{service}/{feature_id}",
            "governance_docs_path": f"features/{domain}/{service}/{feature_id}/docs",
        },
    }


def test_create_domain_creates_constitution():
    """Domain creation writes a constitution.md in constitutions/{domain}/."""
    print("test_create_domain_creates_constitution", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create-domain",
            "--governance-repo", tmp,
            "--domain", "platform",
            "--name", "Platform",
            "--username", "cweber",
        ])
        assert_eq("domain create status", result.get("status"), "pass")
        assert_eq("domain create exit code", code, 0)
        assert_true("constitution_path in result", result.get("constitution_path"))

        constitution_path = Path(tmp) / "constitutions" / "platform" / "constitution.md"
        assert_eq("domain constitution exists", constitution_path.exists(), True)

        content = constitution_path.read_text(encoding="utf-8")
        assert_true("constitution has frontmatter", content.startswith("---"))
        assert_true("constitution has permitted_tracks", "permitted_tracks" in content)
        assert_true("constitution references domain name", "Platform" in content)
        assert_true("constitution lists governance rules", "enforce_stories: true" in content)


def test_create_service_creates_constitutions():
    """Service creation writes constitutions for both the service and its parent domain when absent."""
    print("test_create_service_creates_constitutions", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "create-service",
            "--governance-repo", tmp,
            "--domain", "platform",
            "--service", "identity",
            "--name", "Identity",
            "--username", "cweber",
        ])
        assert_eq("service create status", result.get("status"), "pass")
        assert_eq("service create exit code", code, 0)
        assert_true("constitution_path in result", result.get("constitution_path"))
        assert_eq("domain constitution auto-created flag", result.get("created_domain_constitution"), True)

        domain_constitution = Path(tmp) / "constitutions" / "platform" / "constitution.md"
        service_constitution = Path(tmp) / "constitutions" / "platform" / "identity" / "constitution.md"
        assert_eq("domain constitution exists", domain_constitution.exists(), True)
        assert_eq("service constitution exists", service_constitution.exists(), True)

        service_content = service_constitution.read_text(encoding="utf-8")
        assert_true("service constitution has frontmatter", service_content.startswith("---"))
        assert_true("service constitution references domain", "platform" in service_content)
        assert_true("service constitution references service name", "Identity" in service_content)
        assert_true("service constitution mentions inherits", "Inherits" in service_content)


def test_create_domain_with_target_projects():
    """Domain creation scaffolds TargetProjects/{domain}/.gitkeep when --target-projects-root is provided."""
    print("test_create_domain_with_target_projects", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as workspace_tmp:
            tp_root = str(Path(workspace_tmp) / "TargetProjects")
            result, code = run([
                "create-domain",
                "--governance-repo", gov_tmp,
                "--domain", "platform",
                "--name", "Platform",
                "--username", "cweber",
                "--target-projects-root", tp_root,
            ])
            assert_eq("domain tp create status", result.get("status"), "pass")
            assert_eq("domain tp create exit code", code, 0)
            assert_true("target_projects_path in result", result.get("target_projects_path"))

            gitkeep = Path(tp_root) / "platform" / ".gitkeep"
            assert_eq("domain .gitkeep exists", gitkeep.exists(), True)

            git_cmds = result.get("git_commands", [])
            assert_true(
                "workspace git add in commands",
                any("TargetProjects/platform/.gitkeep" in c for c in git_cmds),
            )
            assert_true(
                "workspace git commit in commands",
                any("scaffold(domain)" in c for c in git_cmds),
            )


def test_create_service_with_target_projects():
    """Service creation scaffolds TargetProjects/{domain}/{service}/.gitkeep when --target-projects-root is provided."""
    print("test_create_service_with_target_projects", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as workspace_tmp:
            tp_root = str(Path(workspace_tmp) / "TargetProjects")
            result, code = run([
                "create-service",
                "--governance-repo", gov_tmp,
                "--domain", "platform",
                "--service", "identity",
                "--name", "Identity",
                "--username", "cweber",
                "--target-projects-root", tp_root,
            ])
            assert_eq("service tp create status", result.get("status"), "pass")
            assert_eq("service tp create exit code", code, 0)
            assert_true("target_projects_path in result", result.get("target_projects_path"))

            gitkeep = Path(tp_root) / "platform" / "identity" / ".gitkeep"
            assert_eq("service .gitkeep exists", gitkeep.exists(), True)

            git_cmds = result.get("git_commands", [])
            assert_true(
                "workspace git add in commands",
                any("TargetProjects/platform/identity/.gitkeep" in c for c in git_cmds),
            )
            assert_true(
                "workspace git commit in commands",
                any("scaffold(service)" in c for c in git_cmds),
            )


def test_create_domain_with_docs_root():
    """Domain creation scaffolds docs/{domain}/.gitkeep when --docs-root is provided."""
    print("test_create_domain_with_docs_root", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as workspace_tmp:
            docs_root = str(Path(workspace_tmp) / "docs")
            result, code = run([
                "create-domain",
                "--governance-repo", gov_tmp,
                "--domain", "platform",
                "--name", "Platform",
                "--username", "cweber",
                "--docs-root", docs_root,
            ])
            assert_eq("domain docs create status", result.get("status"), "pass")
            assert_eq("domain docs create exit code", code, 0)
            assert_true("docs_path in result", result.get("docs_path"))

            gitkeep = Path(docs_root) / "platform" / ".gitkeep"
            assert_eq("domain docs .gitkeep exists", gitkeep.exists(), True)

            git_cmds = result.get("git_commands", [])
            assert_true(
                "docs git add in commands",
                any("docs/platform/.gitkeep" in c for c in git_cmds),
            )
            assert_true(
                "docs git commit in commands",
                any("scaffold(domain)" in c for c in git_cmds),
            )


def test_create_service_with_docs_root():
    """Service creation scaffolds docs/{domain}/{service}/.gitkeep when --docs-root is provided."""
    print("test_create_service_with_docs_root", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as workspace_tmp:
            docs_root = str(Path(workspace_tmp) / "docs")
            result, code = run([
                "create-service",
                "--governance-repo", gov_tmp,
                "--domain", "platform",
                "--service", "identity",
                "--name", "Identity",
                "--username", "cweber",
                "--docs-root", docs_root,
            ])
            assert_eq("service docs create status", result.get("status"), "pass")
            assert_eq("service docs create exit code", code, 0)
            assert_true("service docs_path in result", result.get("docs_path"))

            gitkeep = Path(docs_root) / "platform" / "identity" / ".gitkeep"
            assert_eq("service docs .gitkeep exists", gitkeep.exists(), True)

            git_cmds = result.get("git_commands", [])
            assert_true(
                "service docs git add in commands",
                any("docs/platform/identity/.gitkeep" in c for c in git_cmds),
            )
            assert_true(
                "service docs git commit in commands",
                any("scaffold(service)" in c for c in git_cmds),
            )


def test_create_domain_execute_governance_git():
    """Domain creation can sync, commit, and push governance artifacts while leaving workspace git manual."""
    print("test_create_domain_execute_governance_git", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        governance_repo, remote = init_governance_git_repo(root)
        workspace_root = root / "workspace"
        target_projects_root = workspace_root / "TargetProjects"
        docs_root = workspace_root / "docs"

        result, code = run([
            "create-domain",
            "--governance-repo", str(governance_repo),
            "--domain", "platform",
            "--name", "Platform",
            "--username", "cweber",
            "--target-projects-root", str(target_projects_root),
            "--docs-root", str(docs_root),
            "--execute-governance-git",
        ])

        assert_eq("domain execute status", result.get("status"), "pass")
        assert_eq("domain execute exit code", code, 0)
        assert_eq("domain governance git executed", result.get("governance_git_executed"), True)
        assert_true("domain governance commit sha present", result.get("governance_commit_sha"))
        assert_true("domain governance git commands present", result.get("governance_git_commands"))
        assert_true("domain workspace git commands present", result.get("workspace_git_commands"))
        assert_eq(
            "domain remaining commands limited to workspace",
            result.get("remaining_git_commands"),
            result.get("workspace_git_commands"),
        )

        marker_path = governance_repo / "features" / "platform" / "domain.yaml"
        constitution_path = governance_repo / "constitutions" / "platform" / "constitution.md"
        assert_eq("domain marker pushed locally", marker_path.exists(), True)
        assert_eq("domain constitution pushed locally", constitution_path.exists(), True)
        assert_eq(
            "domain short sha matches repo head",
            result.get("governance_commit_sha"),
            git(["rev-parse", "--short", "HEAD"], cwd=str(governance_repo)),
        )
        assert_eq(
            "domain remote main updated",
            remote_main_sha(remote),
            git(["rev-parse", "HEAD"], cwd=str(governance_repo)),
        )


def test_create_service_execute_governance_git():
    """Service creation can sync, commit, and push governance artifacts on main automatically."""
    print("test_create_service_execute_governance_git", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        governance_repo, remote = init_governance_git_repo(root)

        result, code = run([
            "create-service",
            "--governance-repo", str(governance_repo),
            "--domain", "platform",
            "--service", "identity",
            "--name", "Identity",
            "--username", "cweber",
            "--execute-governance-git",
        ])

        assert_eq("service execute status", result.get("status"), "pass")
        assert_eq("service execute exit code", code, 0)
        assert_eq("service governance git executed", result.get("governance_git_executed"), True)
        assert_true("service governance commit sha present", result.get("governance_commit_sha"))
        assert_eq("service remaining commands empty", result.get("remaining_git_commands"), [])
        assert_eq("service workspace commands empty", result.get("workspace_git_commands"), [])
        assert_eq("service created domain marker flag", result.get("created_domain_marker"), True)
        assert_eq("service created domain constitution flag", result.get("created_domain_constitution"), True)

        domain_marker = governance_repo / "features" / "platform" / "domain.yaml"
        service_marker = governance_repo / "features" / "platform" / "identity" / "service.yaml"
        service_constitution = governance_repo / "constitutions" / "platform" / "identity" / "constitution.md"
        assert_eq("service domain marker exists", domain_marker.exists(), True)
        assert_eq("service marker exists", service_marker.exists(), True)
        assert_eq("service constitution exists", service_constitution.exists(), True)
        assert_eq(
            "service short sha matches repo head",
            result.get("governance_commit_sha"),
            git(["rev-parse", "--short", "HEAD"], cwd=str(governance_repo)),
        )
        assert_eq(
            "service remote main updated",
            remote_main_sha(remote),
            git(["rev-parse", "HEAD"], cwd=str(governance_repo)),
        )


def test_create_domain_execute_governance_git_dry_run_skips_git():
    """Dry-run with automatic governance enabled should still only preview commands."""
    print("test_create_domain_execute_governance_git_dry_run_skips_git", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        result, code = run([
            "create-domain",
            "--governance-repo", gov_tmp,
            "--domain", "platform",
            "--username", "cweber",
            "--execute-governance-git",
            "--dry-run",
        ])

        assert_eq("domain execute dry-run status", result.get("status"), "pass")
        assert_eq("domain execute dry-run exit code", code, 0)
        assert_eq("domain execute dry-run executed flag", result.get("governance_git_executed"), False)
        assert_eq("domain execute dry-run commit sha", result.get("governance_commit_sha"), None)
        assert_eq(
            "domain execute dry-run remaining commands stay full plan",
            result.get("remaining_git_commands"),
            result.get("git_commands"),
        )
        assert_eq("dry-run domain marker absent", (Path(gov_tmp) / "features" / "platform" / "domain.yaml").exists(), False)


def test_create_domain_execute_governance_git_syncs_before_duplicate_check():
    """Automatic governance git pulls latest main before checking for duplicate domains."""
    print("test_create_domain_execute_governance_git_syncs_before_duplicate_check", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        governance_repo, remote = init_governance_git_repo(root, "primary")
        secondary_repo = root / "secondary"

        git(["clone", str(remote), str(secondary_repo)])
        git(["config", "user.name", "Test User"], cwd=str(secondary_repo))
        git(["config", "user.email", "test@example.com"], cwd=str(secondary_repo))

        pushed_result, pushed_code = run([
            "create-domain",
            "--governance-repo", str(secondary_repo),
            "--domain", "platform",
            "--username", "cweber",
            "--execute-governance-git",
        ])
        assert_eq("secondary domain create status", pushed_result.get("status"), "pass")
        assert_eq("secondary domain create exit code", pushed_code, 0)

        stale_result, stale_code = run([
            "create-domain",
            "--governance-repo", str(governance_repo),
            "--domain", "platform",
            "--username", "cweber",
            "--execute-governance-git",
        ])

        assert_eq("stale clone duplicate status", stale_result.get("status"), "fail")
        assert_eq("stale clone duplicate exit code", stale_code, 1)
        assert_true("stale clone duplicate surfaced marker error", "already exists" in (stale_result.get("error") or ""))
        assert_eq(
            "stale clone pulled duplicate marker before failing",
            (governance_repo / "features" / "platform" / "domain.yaml").exists(),
            True,
        )


def test_create_domain_writes_context_yaml():
    """create-domain with --personal-folder writes context.yaml with domain, service=null, updated_by=new-domain."""
    print("test_create_domain_writes_context_yaml", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as personal_tmp:
            result, code = run([
                "create-domain",
                "--governance-repo", gov_tmp,
                "--domain", "platform",
                "--username", "cweber",
                "--personal-folder", personal_tmp,
            ])
            assert_eq("create-domain with personal-folder status", result.get("status"), "pass")
            assert_eq("exit code", code, 0)
            assert_true("context_path in result", result.get("context_path"))

            context_path = Path(personal_tmp) / "context.yaml"
            assert_eq("context.yaml exists", context_path.exists(), True)

            with open(context_path) as f:
                ctx = yaml.safe_load(f)
            assert_eq("context domain", ctx.get("domain"), "platform")
            assert_eq("context service is null", ctx.get("service"), None)
            assert_eq("context updated_by", ctx.get("updated_by"), "new-domain")
            assert_true("context updated_at set", ctx.get("updated_at"))


def test_create_service_writes_context_yaml():
    """create-service with --personal-folder writes context.yaml with domain+service, updated_by=new-service."""
    print("test_create_service_writes_context_yaml", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as personal_tmp:
            result, code = run([
                "create-service",
                "--governance-repo", gov_tmp,
                "--domain", "platform",
                "--service", "identity",
                "--username", "cweber",
                "--personal-folder", personal_tmp,
            ])
            assert_eq("create-service with personal-folder status", result.get("status"), "pass")
            assert_eq("exit code", code, 0)
            assert_true("context_path in result", result.get("context_path"))

            context_path = Path(personal_tmp) / "context.yaml"
            assert_eq("context.yaml exists", context_path.exists(), True)

            with open(context_path) as f:
                ctx = yaml.safe_load(f)
            assert_eq("context domain", ctx.get("domain"), "platform")
            assert_eq("context service", ctx.get("service"), "identity")
            assert_eq("context updated_by", ctx.get("updated_by"), "new-service")
            assert_true("context updated_at set", ctx.get("updated_at"))


def test_create_domain_no_personal_folder_skips_context():
    """create-domain without --personal-folder does not write context.yaml and result has no context_path key."""
    print("test_create_domain_no_personal_folder_skips_context", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        result, code = run([
            "create-domain",
            "--governance-repo", gov_tmp,
            "--domain", "platform",
            "--username", "cweber",
        ])
        assert_eq("status still pass", result.get("status"), "pass")
        assert_eq("no context_path key in result", "context_path" in result, False)


def test_read_context_returns_domain_service():
    """read-context returns domain and service from a previously written context.yaml."""
    print("test_read_context_returns_domain_service", file=sys.stderr)
    with tempfile.TemporaryDirectory() as personal_tmp:
        # First write a context.yaml via create-service
        with tempfile.TemporaryDirectory() as gov_tmp:
            run([
                "create-service",
                "--governance-repo", gov_tmp,
                "--domain", "commerce",
                "--service", "payments",
                "--username", "cweber",
                "--personal-folder", personal_tmp,
            ])

        # Now read it back
        result, code = run([
            "read-context",
            "--personal-folder", personal_tmp,
        ])
        assert_eq("read-context status", result.get("status"), "pass")
        assert_eq("exit code", code, 0)
        assert_eq("read-context domain", result.get("domain"), "commerce")
        assert_eq("read-context service", result.get("service"), "payments")
        assert_eq("read-context updated_by", result.get("updated_by"), "new-service")
        assert_true("read-context updated_at set", result.get("updated_at"))


def test_read_context_not_found():
    """read-context returns status=not-found when no context.yaml exists."""
    print("test_read_context_not_found", file=sys.stderr)
    with tempfile.TemporaryDirectory() as empty_tmp:
        result, code = run([
            "read-context",
            "--personal-folder", empty_tmp,
        ])
        assert_eq("status not-found", result.get("status"), "not-found")
        assert_true("error message present", result.get("error"))
        assert_eq("exit code is non-zero", code, 1)


if __name__ == "__main__":
    test_create_feature()
    test_full_track_starts_in_preplan()
    test_create_domain_marker()
    test_create_service_marker_creates_parent_domain()
    test_duplicate_domain_service_rejected()
    test_index_created_when_missing()
    test_dry_run()
    test_express_track_defers_planning_pr()
    test_invalid_feature_id()
    test_invalid_domain_service()
    test_duplicate_feature()
    test_missing_required_args()
    test_track_must_be_explicit()
    test_fetch_context_with_existing_index()
    test_fetch_context_full_depth()
    test_fetch_context_feature_not_found()
    test_fetch_context_no_index()
    test_fetch_context_uses_feature_yaml_dependencies()
    test_fetch_context_service_refs_include_service_context()
    test_fetch_context_service_ref_text_detects_service_context()
    test_fetch_context_reports_missing_detected_service_context()
    test_fetch_context_service_ref_text_scopes_to_target_domain()
    test_fetch_context_service_context_without_service_marker()
    test_control_repo_git_commands()
    test_create_domain_creates_constitution()
    test_create_service_creates_constitutions()
    test_create_domain_with_target_projects()
    test_create_service_with_target_projects()
    test_create_domain_with_docs_root()
    test_create_service_with_docs_root()
    test_create_feature_execute_governance_git()
    test_create_feature_execute_governance_git_dry_run_skips_git()
    test_create_feature_execute_governance_git_requires_clean_repo()
    test_create_domain_execute_governance_git()
    test_create_service_execute_governance_git()
    test_create_domain_execute_governance_git_dry_run_skips_git()
    test_create_domain_execute_governance_git_syncs_before_duplicate_check()
    test_create_domain_writes_context_yaml()
    test_create_service_writes_context_yaml()
    test_create_domain_no_personal_folder_skips_context()
    test_read_context_returns_domain_service()
    test_read_context_not_found()

    print(f"\nResults: {PASS} passed, {FAIL} failed", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
