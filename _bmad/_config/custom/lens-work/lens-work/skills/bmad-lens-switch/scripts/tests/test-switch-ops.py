#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for switch-ops.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


SCRIPT = str(Path(__file__).parent.parent / "switch-ops.py")
PASS = 0
FAIL = 0


def find_arg_value(args: list[str], flag: str) -> str | None:
    """Return the value associated with a CLI flag, if present."""
    try:
        index = args.index(flag)
    except ValueError:
        return None
    next_index = index + 1
    if next_index >= len(args):
        return None
    return args[next_index]


def run(args: list[str], cwd: str | None = None) -> tuple[dict, int]:
    """Run the script and return (parsed JSON output, exit code)."""
    if cwd is None:
        cwd = find_arg_value(args, "--governance-repo")

    result = subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    try:
        return json.loads(result.stdout), result.returncode
    except json.JSONDecodeError:
        return {"error": result.stderr, "stdout": result.stdout}, result.returncode


def assert_eq(name: str, actual: object, expected: object) -> None:
    global PASS, FAIL
    if actual == expected:
        PASS += 1
        print(f"  ✓ {name}", file=sys.stderr)
    else:
        FAIL += 1
        print(f"  ✗ {name}: expected {expected!r}, got {actual!r}", file=sys.stderr)


def assert_true(name: str, actual: object) -> None:
    assert_eq(name, bool(actual), True)


def assert_false(name: str, actual: object) -> None:
    assert_eq(name, bool(actual), False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def write_index(repo: str, features: list[dict]) -> None:
    """Write a feature-index.yaml to the repo root."""
    path = Path(repo) / "feature-index.yaml"
    with open(path, "w") as f:
        yaml.dump({"features": features}, f, default_flow_style=False)


def write_feature(
    repo: str,
    domain: str,
    service: str,
    feature_id: str,
    data: dict,
) -> None:
    """Write a feature.yaml to the expected path."""
    feature_dir = Path(repo) / "features" / domain / service / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    with open(feature_dir / "feature.yaml", "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def write_domain(repo: str, domain: str, data: dict) -> None:
    """Write a domain.yaml to the expected path."""
    domain_dir = Path(repo) / "features" / domain
    domain_dir.mkdir(parents=True, exist_ok=True)
    with open(domain_dir / "domain.yaml", "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def write_service(repo: str, domain: str, service: str, data: dict) -> None:
    """Write a service.yaml to the expected path."""
    service_dir = Path(repo) / "features" / domain / service
    service_dir.mkdir(parents=True, exist_ok=True)
    with open(service_dir / "service.yaml", "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


SAMPLE_INDEX_ENTRIES = [
    {
        "id": "auth-login",
        "domain": "platform",
        "service": "identity",
        "status": "active",
        "owner": "cweber",
        "summary": "User authentication flow",
    },
    {
        "id": "user-profile",
        "domain": "platform",
        "service": "identity",
        "status": "businessplan-complete",
        "owner": "amelia",
        "summary": "User profile management",
    },
    {
        "id": "legacy-sso",
        "domain": "platform",
        "service": "identity",
        "status": "archived",
        "owner": "cweber",
        "summary": "Old SSO integration",
    },
]

SAMPLE_FEATURE = {
    "featureId": "auth-login",
    "name": "User Authentication",
    "domain": "platform",
    "service": "identity",
    "phase": "dev",
    "track": "quickplan",
    "priority": "high",
    "updated": "2026-03-01T10:00:00Z",
    "dependencies": {
        "depends_on": [],
        "depended_by": [],
    },
    "target_repos": [
        {
            "name": "Lens.Hermes",
            "remote_url": "https://github.com/crisweber2600/Lens.Hermes",
            "local_path": "TargetProjects/plugins/hermes/Lens.Hermes",
            "dev_branch_mode": "feature-id",
            "dev_branch_name": "feature/auth-login",
            "dev_base_branch": "main",
            "final_pr_url": "https://github.com/crisweber2600/Lens.Hermes/pull/12",
            "final_review_report": "docs/implementation-artifacts/dev-adversarial-review.md",
            "final_party_mode_report": "docs/implementation-artifacts/dev-party-mode-review.md",
        }
    ],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_list_features():
    """List features from feature-index.yaml."""
    print("test_list_features", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)

        result, code = run(["list", "--governance-repo", tmp])
        assert_eq("list status", result["status"], "pass")
        assert_eq("list exit code", code, 0)
        # Default filter: everything except archived terminal items
        assert_eq("list visible count", result["total"], 2)
        ids = [f["id"] for f in result["features"]]
        assert_true("contains auth-login", "auth-login" in ids)
        assert_true("contains user-profile", "user-profile" in ids)
        assert_false("excludes archived", "legacy-sso" in ids)
        statuses = {f["id"]: f["status"] for f in result["features"]}
        assert_eq("keeps non-archived phase status", statuses.get("user-profile"), "businessplan-complete")


def test_list_active_filter_excludes_archived():
    """Active filter means non-archived features, not literal status == active."""
    print("test_list_active_filter_excludes_archived", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)

        result, code = run(["list", "--governance-repo", tmp, "--status-filter", "active"])
        assert_eq("active filter status", result["status"], "pass")
        assert_eq("active count", result["total"], 2)
        ids = [f["id"] for f in result["features"]]
        assert_true("active filter keeps auth-login", "auth-login" in ids)
        assert_true("active filter keeps businessplan-complete feature", "user-profile" in ids)
        assert_false("active filter excludes archived", "legacy-sso" in ids)


def test_list_all_includes_archived():
    """All filter includes archived features."""
    print("test_list_all_includes_archived", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)

        result, code = run(["list", "--governance-repo", tmp, "--status-filter", "all"])
        assert_eq("all filter status", result["status"], "pass")
        assert_eq("all count", result["total"], 3)
        ids = [f["id"] for f in result["features"]]
        assert_true("includes archived", "legacy-sso" in ids)


def test_list_missing_index_falls_back_to_domains():
    """List falls back to empty domain inventory when feature-index.yaml is absent."""
    print("test_list_missing_index_falls_back_to_domains", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        result, code = run(["list", "--governance-repo", tmp])
        assert_eq("fallback status", result["status"], "pass")
        assert_eq("fallback exit code", code, 0)
        assert_eq("fallback mode", result.get("mode"), "domains")
        assert_eq("fallback total_domains", result.get("total_domains"), 0)
        assert_eq("fallback total_services", result.get("total_services"), 0)


def test_list_domain_fallback_with_domains():
    """Domain fallback returns domain and service inventory from yaml files."""
    print("test_list_domain_fallback_with_domains", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_domain(tmp, "platform", {
            "kind": "domain", "id": "platform", "name": "Platform",
            "domain": "platform", "status": "active", "owner": "cweber",
        })
        write_service(tmp, "platform", "identity", {
            "kind": "service", "id": "platform-identity", "name": "Identity",
            "domain": "platform", "service": "identity", "status": "active", "owner": "cweber",
        })
        write_domain(tmp, "core", {
            "kind": "domain", "id": "core", "name": "Core",
            "domain": "core", "status": "active", "owner": "ops",
        })
        result, code = run(["list", "--governance-repo", tmp])
        assert_eq("domain fallback status", result["status"], "pass")
        assert_eq("domain fallback exit code", code, 0)
        assert_eq("domain fallback mode", result.get("mode"), "domains")
        assert_eq("domain fallback total_domains", result.get("total_domains"), 2)
        assert_eq("domain fallback total_services", result.get("total_services"), 1)
        domains = result.get("domains", [])
        assert_eq("domain count", len(domains), 2)
        platform = next((d for d in domains if d["id"] == "platform"), None)
        assert_true("platform domain present", platform is not None)
        assert_eq("platform service count", len(platform["services"]), 1)
        assert_eq("service id", platform["services"][0]["id"], "platform-identity")
        core = next((d for d in domains if d["id"] == "core"), None)
        assert_true("core domain present", core is not None)
        assert_eq("core has no services", len(core["services"]), 0)


def test_list_empty_index():
    """List succeeds with zero features when index has empty list."""
    print("test_list_empty_index", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, [])
        result, code = run(["list", "--governance-repo", tmp])
        assert_eq("empty index status", result["status"], "pass")
        assert_eq("empty index total", result["total"], 0)


def test_list_output_fields():
    """List output includes all required fields per feature."""
    print("test_list_output_fields", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)
        result, _ = run(["list", "--governance-repo", tmp])
        for feature in result["features"]:
            for key in ("id", "domain", "service", "status", "owner", "summary"):
                assert_true(f"feature has {key}", key in feature)


def test_list_includes_target_repo_state_when_feature_yaml_exists():
    """List output includes target repo dev state for initialized features."""
    print("test_list_includes_target_repo_state_when_feature_yaml_exists", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)
        write_feature(tmp, "platform", "identity", "auth-login", SAMPLE_FEATURE)

        result, code = run(["list", "--governance-repo", tmp])
        assert_eq("list target repo status", result["status"], "pass")
        assert_eq("list target repo exit code", code, 0)
        feature = next(f for f in result["features"] if f["id"] == "auth-login")
        target_repo = feature.get("target_repo")
        assert_true("list target repo present", target_repo is not None)
        assert_eq("list target repo mode", target_repo["dev_branch_mode"], "feature-id")
        assert_eq("list target repo working branch", target_repo["working_branch"], "feature/auth-login")
        assert_eq("list target repo final pr state", target_repo["final_pr_state"], "created")


def test_list_numbered_menu_fields():
    """List output includes sequential 1-based num field for numbered menu."""
    print("test_list_numbered_menu_fields", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)
        result, code = run(["list", "--governance-repo", tmp])
        assert_eq("list status", result["status"], "pass")
        features = result.get("features", [])
        assert_true("has features", len(features) > 0)
        for i, feature in enumerate(features):
            assert_true(f"feature {i} has num", "num" in feature)
            assert_eq(f"feature {i} num is {i + 1}", feature["num"], i + 1)


def test_switch_existing_feature():
    """Switch to an existing feature validates and returns full context."""
    print("test_switch_existing_feature", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)
        write_feature(tmp, "platform", "identity", "auth-login", SAMPLE_FEATURE)

        result, code = run(["switch", "--governance-repo", tmp, "--feature-id", "auth-login"])
        assert_eq("switch status", result["status"], "pass")
        assert_eq("switch exit code", code, 0)

        feat = result.get("feature", {})
        assert_eq("feature id", feat.get("id"), "auth-login")
        assert_eq("feature phase", feat.get("phase"), "dev")
        assert_eq("feature domain", feat.get("domain"), "platform")
        assert_eq("feature service", feat.get("service"), "identity")
        assert_eq("feature track", feat.get("track"), "quickplan")
        assert_eq("feature priority", feat.get("priority"), "high")
        assert_eq("feature status", feat.get("status"), "active")
        assert_eq("feature owner", feat.get("owner"), "cweber")
        assert_true("stale field present", "stale" in feat)
        assert_true("context_path field present", "context_path" in feat)
        target_repo = feat.get("target_repo")
        assert_true("target repo field present", target_repo is not None)
        assert_eq("switch target repo mode", target_repo.get("dev_branch_mode"), "feature-id")
        assert_eq("switch target repo working branch", target_repo.get("working_branch"), "feature/auth-login")
        assert_eq("switch target repo final pr state", target_repo.get("final_pr_state"), "created")
        context_path = Path(feat["context_path"])
        assert_eq("feature switch default context path", context_path, Path(tmp).parent / ".lens" / "personal" / "context.yaml")
        assert_eq("feature switch context.yaml exists", context_path.exists(), True)
        with open(context_path) as f:
            context_data = yaml.safe_load(f)
        assert_eq("feature switch context domain", context_data.get("domain"), "platform")
        assert_eq("feature switch context service", context_data.get("service"), "identity")

        ctx = result.get("context_to_load", {})
        assert_true("has summaries key", "summaries" in ctx)
        assert_true("has full_docs key", "full_docs" in ctx)


def test_switch_prefers_indexed_feature_path_over_repo_scan():
    """Switch uses the indexed feature path before scanning the whole repo."""
    print("test_switch_prefers_indexed_feature_path_over_repo_scan", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)
        write_feature(tmp, "aaa", "legacy", "auth-login", {
            **SAMPLE_FEATURE,
            "name": "Wrong Feature Copy",
            "domain": "aaa",
            "service": "legacy",
            "phase": "archived",
        })
        write_feature(tmp, "platform", "identity", "auth-login", SAMPLE_FEATURE)

        result, code = run(["switch", "--governance-repo", tmp, "--feature-id", "auth-login"])
        assert_eq("prefer indexed path status", result["status"], "pass")
        assert_eq("prefer indexed path exit code", code, 0)
        feat = result.get("feature", {})
        assert_eq("prefer indexed path name", feat.get("name"), "User Authentication")
        assert_eq("prefer indexed path domain", feat.get("domain"), "platform")
        assert_eq("prefer indexed path service", feat.get("service"), "identity")


def test_switch_nonexistent_feature():
    """Switch to a nonexistent featureId returns fail and exit 1."""
    print("test_switch_nonexistent_feature", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)

        result, code = run(["switch", "--governance-repo", tmp, "--feature-id", "does-not-exist"])
        assert_eq("not found status", result["status"], "fail")
        assert_eq("not found exit code", code, 1)
        assert_true("error mentions feature id", "does-not-exist" in result.get("error", ""))


def test_switch_missing_index_uses_service_id_fallback():
    """Switch falls back to service context when index is missing and feature-id is a service id."""
    print("test_switch_missing_index_uses_service_id_fallback", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_domain(tmp, "plugins", {
            "kind": "domain", "id": "plugins", "name": "Plugins",
            "domain": "plugins", "status": "active", "owner": "cweber",
        })
        write_service(tmp, "plugins", "hermes", {
            "kind": "service", "id": "plugins-hermes", "name": "Hermes",
            "domain": "plugins", "service": "hermes", "status": "active", "owner": "cweber",
        })

        result, code = run([
            "switch", "--governance-repo", tmp, "--feature-id", "plugins-hermes",
        ])
        assert_eq("fallback switch status", result["status"], "pass")
        assert_eq("fallback switch exit code", code, 0)
        assert_eq("fallback mode", result.get("mode"), "service-context")
        service_ctx = result.get("service_context", {})
        assert_eq("service context id", service_ctx.get("id"), "plugins-hermes")
        assert_eq("service context domain", service_ctx.get("domain"), "plugins")
        assert_eq("service context service", service_ctx.get("service"), "hermes")
        fallback_context_path = Path(service_ctx.get("context_path", ""))
        assert_eq("service-id fallback context.yaml exists", fallback_context_path.exists(), True)


def test_switch_missing_index_uses_domain_service_fallback():
    """Switch supports explicit --domain/--service fallback when index is missing."""
    print("test_switch_missing_index_uses_domain_service_fallback", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_domain(tmp, "plugins", {
            "kind": "domain", "id": "plugins", "name": "Plugins",
            "domain": "plugins", "status": "active", "owner": "cweber",
        })
        write_service(tmp, "plugins", "hermes", {
            "kind": "service", "id": "plugins-hermes", "name": "Hermes",
            "domain": "plugins", "service": "hermes", "status": "active", "owner": "cweber",
        })

        result, code = run([
            "switch",
            "--governance-repo", tmp,
            "--feature-id", "any-safe-id",
            "--domain", "plugins",
            "--service", "hermes",
        ])
        assert_eq("explicit fallback status", result["status"], "pass")
        assert_eq("explicit fallback exit code", code, 0)
        assert_eq("explicit fallback mode", result.get("mode"), "service-context")
        service_ctx = result.get("service_context", {})
        assert_eq("explicit service context domain", service_ctx.get("domain"), "plugins")
        assert_eq("explicit service context service", service_ctx.get("service"), "hermes")
        explicit_context_path = Path(service_ctx.get("context_path", ""))
        assert_eq("explicit fallback context.yaml exists", explicit_context_path.exists(), True)


def test_switch_missing_index_writes_context_yaml_when_personal_folder_set():
    """Service-context fallback writes context.yaml when --personal-folder is provided."""
    print("test_switch_missing_index_writes_context_yaml_when_personal_folder_set", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        with tempfile.TemporaryDirectory() as personal_tmp:
            write_domain(tmp, "plugins", {
                "kind": "domain", "id": "plugins", "name": "Plugins",
                "domain": "plugins", "status": "active", "owner": "cweber",
            })
            write_service(tmp, "plugins", "hermes", {
                "kind": "service", "id": "plugins-hermes", "name": "Hermes",
                "domain": "plugins", "service": "hermes", "status": "active", "owner": "cweber",
            })

            result, code = run([
                "switch",
                "--governance-repo", tmp,
                "--feature-id", "plugins-hermes",
                "--personal-folder", personal_tmp,
            ])
            assert_eq("personal fallback status", result["status"], "pass")
            assert_eq("personal fallback exit code", code, 0)
            context_path = Path(personal_tmp) / "context.yaml"
            assert_eq("context.yaml exists", context_path.exists(), True)
            with open(context_path) as f:
                context_data = yaml.safe_load(f)
            assert_eq("context domain", context_data.get("domain"), "plugins")
            assert_eq("context service", context_data.get("service"), "hermes")
            assert_eq("context updated_by", context_data.get("updated_by"), "lens-switch")


def test_switch_missing_index_invalid_service_selection_fails():
    """Missing index still fails cleanly when selected service cannot be resolved."""
    print("test_switch_missing_index_invalid_service_selection_fails", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_domain(tmp, "plugins", {
            "kind": "domain", "id": "plugins", "name": "Plugins",
            "domain": "plugins", "status": "active", "owner": "cweber",
        })

        result, code = run([
            "switch", "--governance-repo", tmp, "--feature-id", "plugins-hermes",
        ])
        assert_eq("invalid service fallback status", result["status"], "fail")
        assert_eq("invalid service fallback exit code", code, 1)
        assert_true("invalid service error message", "no matching service context" in result.get("error", "").lower())


def test_switch_returns_context_depends_on():
    """Switch loads full_docs paths for depends_on dependencies."""
    print("test_switch_returns_context_depends_on", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        extra_entry = {
            "id": "oauth-provider",
            "domain": "platform",
            "service": "auth",
            "status": "active",
            "owner": "cweber",
            "summary": "OAuth2 provider",
        }
        write_index(tmp, SAMPLE_INDEX_ENTRIES + [extra_entry])

        feature_with_deps = {
            **SAMPLE_FEATURE,
            "dependencies": {
                "depends_on": ["oauth-provider"],
                "depended_by": [],
            },
        }
        write_feature(tmp, "platform", "identity", "auth-login", feature_with_deps)

        result, code = run(["switch", "--governance-repo", tmp, "--feature-id", "auth-login"])
        assert_eq("switch status", result["status"], "pass")
        full_docs = result.get("context_to_load", {}).get("full_docs", [])
        assert_true(
            "full_doc for oauth-provider",
            any("oauth-provider" in p for p in full_docs),
        )
        assert_true(
            "full_doc is tech-plan",
            any("tech-plan.md" in p for p in full_docs),
        )


def test_switch_returns_context_related():
    """Switch loads summary paths for related dependencies."""
    print("test_switch_returns_context_related", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)

        feature_with_related = {
            **SAMPLE_FEATURE,
            "dependencies": {
                "depends_on": [],
                "depended_by": [],
                "related": ["user-profile"],
            },
        }
        write_feature(tmp, "platform", "identity", "auth-login", feature_with_related)

        result, code = run(["switch", "--governance-repo", tmp, "--feature-id", "auth-login"])
        assert_eq("switch status", result["status"], "pass")
        summaries = result.get("context_to_load", {}).get("summaries", [])
        assert_true(
            "summary for user-profile",
            any("user-profile" in p for p in summaries),
        )
        assert_true(
            "summary is summary.md",
            any("summary.md" in p for p in summaries),
        )


def test_switch_stale_detection():
    """Switch detects stale features (updated > 30 days ago)."""
    print("test_switch_stale_detection", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)

        stale_feature = {**SAMPLE_FEATURE, "updated": "2020-01-01T00:00:00Z"}
        write_feature(tmp, "platform", "identity", "auth-login", stale_feature)

        result, code = run(["switch", "--governance-repo", tmp, "--feature-id", "auth-login"])
        assert_eq("switch status", result["status"], "pass")
        assert_eq("stale is true", result["feature"]["stale"], True)


def test_switch_not_stale_recent():
    """Switch marks recently-updated features as not stale."""
    print("test_switch_not_stale_recent", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)
        # Use a recent timestamp — write feature with fixed recent date
        recent_feature = {**SAMPLE_FEATURE, "updated": "2099-01-01T00:00:00Z"}
        write_feature(tmp, "platform", "identity", "auth-login", recent_feature)

        result, code = run(["switch", "--governance-repo", tmp, "--feature-id", "auth-login"])
        assert_eq("switch status", result["status"], "pass")
        assert_eq("stale is false", result["feature"]["stale"], False)


def test_context_paths_with_depends_on_and_related():
    """context-paths returns full_docs for depends_on and summaries for related."""
    print("test_context_paths_with_depends_on_and_related", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        extra_entries = [
            {
                "id": "oauth-provider",
                "domain": "platform",
                "service": "auth",
                "status": "active",
                "owner": "cweber",
                "summary": "OAuth2 provider",
            },
            {
                "id": "audit-log",
                "domain": "platform",
                "service": "compliance",
                "status": "active",
                "owner": "cweber",
                "summary": "Audit logging service",
            },
        ]
        write_index(tmp, SAMPLE_INDEX_ENTRIES + extra_entries)

        feature_data = {
            **SAMPLE_FEATURE,
            "dependencies": {
                "depends_on": ["oauth-provider"],
                "depended_by": [],
                "related": ["audit-log"],
            },
        }
        write_feature(tmp, "platform", "identity", "auth-login", feature_data)

        result, code = run([
            "context-paths",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
        ])
        assert_eq("context-paths status", result["status"], "pass")
        assert_eq("exit code", code, 0)

        full_docs = result.get("full_docs", [])
        summaries = result.get("summaries", [])

        assert_true("full_doc for oauth-provider", any("oauth-provider" in p for p in full_docs))
        assert_true("full_doc is tech-plan", any("tech-plan.md" in p for p in full_docs))
        assert_true("summary for audit-log", any("audit-log" in p for p in summaries))
        assert_true("summary is summary.md", any("summary.md" in p for p in summaries))
        assert_false("audit-log not in full_docs", any("audit-log" in p for p in full_docs))


def test_context_paths_with_blocks():
    """context-paths returns full_docs for blocks dependencies."""
    print("test_context_paths_with_blocks", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        extra_entry = {
            "id": "user-profile",
            "domain": "platform",
            "service": "identity",
            "status": "active",
            "owner": "amelia",
            "summary": "User profile management",
        }
        write_index(tmp, [extra_entry])

        feature_data = {
            **SAMPLE_FEATURE,
            "featureId": "data-migration",
            "dependencies": {
                "depends_on": [],
                "depended_by": [],
                "blocks": ["user-profile"],
            },
        }
        write_feature(tmp, "platform", "identity", "data-migration", feature_data)

        result, code = run([
            "context-paths",
            "--governance-repo", tmp,
            "--feature-id", "data-migration",
            "--domain", "platform",
            "--service", "identity",
        ])
        assert_eq("blocks context status", result["status"], "pass")
        full_docs = result.get("full_docs", [])
        assert_true("full_doc for user-profile", any("user-profile" in p for p in full_docs))
        assert_true("full_doc is tech-plan", any("tech-plan.md" in p for p in full_docs))


def test_context_paths_no_dependencies():
    """context-paths returns empty lists when feature has no dependencies."""
    print("test_context_paths_no_dependencies", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)
        write_feature(tmp, "platform", "identity", "auth-login", SAMPLE_FEATURE)

        result, code = run([
            "context-paths",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
        ])
        assert_eq("no deps status", result["status"], "pass")
        assert_eq("no deps exit code", code, 0)
        assert_eq("summaries empty", result.get("summaries"), [])
        assert_eq("full_docs empty", result.get("full_docs"), [])


def test_context_paths_not_found():
    """context-paths returns fail when feature does not exist."""
    print("test_context_paths_not_found", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)

        result, code = run([
            "context-paths",
            "--governance-repo", tmp,
            "--feature-id", "ghost-feature",
            "--domain", "platform",
            "--service", "identity",
        ])
        assert_eq("not found status", result["status"], "fail")
        assert_eq("not found exit code", code, 1)


def test_path_traversal_in_feature_id():
    """Path traversal in featureId is rejected with exit 1."""
    print("test_path_traversal_in_feature_id", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        write_index(tmp, SAMPLE_INDEX_ENTRIES)

        for evil_id in ["../../etc/passwd", "../evil", "has spaces", "CamelCase"]:
            result, code = run(["switch", "--governance-repo", tmp, "--feature-id", evil_id])
            assert_eq(f"traversal rejected ({evil_id!r}) status", result["status"], "fail")
            assert_eq(f"traversal rejected ({evil_id!r}) exit", code, 1)

        # context-paths also rejects
        result, code = run([
            "context-paths",
            "--governance-repo", tmp,
            "--feature-id", "../../etc/passwd",
            "--domain", "platform",
            "--service", "identity",
        ])
        assert_eq("context-paths traversal rejected", result["status"], "fail")
        assert_eq("context-paths traversal exit", code, 1)


def test_depends_on_not_duplicated_in_summaries():
    """Features in depends_on are in full_docs, not summaries, even if also in related."""
    print("test_depends_on_not_duplicated_in_summaries", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        extra_entry = {
            "id": "oauth-provider",
            "domain": "platform",
            "service": "auth",
            "status": "active",
            "owner": "cweber",
            "summary": "OAuth2 provider",
        }
        write_index(tmp, SAMPLE_INDEX_ENTRIES + [extra_entry])

        # oauth-provider is in both depends_on AND related — should only be in full_docs
        feature_data = {
            **SAMPLE_FEATURE,
            "dependencies": {
                "depends_on": ["oauth-provider"],
                "depended_by": [],
                "related": ["oauth-provider"],
            },
        }
        write_feature(tmp, "platform", "identity", "auth-login", feature_data)

        result, code = run([
            "context-paths",
            "--governance-repo", tmp,
            "--feature-id", "auth-login",
            "--domain", "platform",
            "--service", "identity",
        ])
        assert_eq("dedup status", result["status"], "pass")
        full_docs = result.get("full_docs", [])
        summaries = result.get("summaries", [])
        assert_true("oauth-provider in full_docs", any("oauth-provider" in p for p in full_docs))
        assert_false("oauth-provider not in summaries", any("oauth-provider" in p for p in summaries))


def init_git_repo(path: str) -> None:
    """Initialize a bare git repo with an initial commit."""
    subprocess.run(["git", "init", path], capture_output=True, check=True)
    subprocess.run(["git", "-C", path, "config", "user.email", "test@test.com"], capture_output=True, check=True)
    subprocess.run(["git", "-C", path, "config", "user.name", "Test"], capture_output=True, check=True)
    sentinel = Path(path) / ".gitkeep"
    sentinel.write_text("")
    subprocess.run(["git", "-C", path, "add", ".gitkeep"], capture_output=True, check=True)
    subprocess.run(["git", "-C", path, "commit", "-m", "init"], capture_output=True, check=True)


def create_branch(repo: str, branch: str) -> None:
    """Create a branch in the given repo."""
    subprocess.run(["git", "-C", repo, "checkout", "-b", branch], capture_output=True, check=True)
    subprocess.run(["git", "-C", repo, "checkout", "-"], capture_output=True, check=True)


def test_switch_with_control_repo_existing_plan_branch():
    """Switch with --control-repo checks out {featureId}-plan when branch exists."""
    print("test_switch_with_control_repo_existing_plan_branch", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as ctrl_tmp:
            write_index(gov_tmp, SAMPLE_INDEX_ENTRIES)
            write_feature(gov_tmp, "platform", "identity", "auth-login", SAMPLE_FEATURE)
            init_git_repo(ctrl_tmp)
            create_branch(ctrl_tmp, "auth-login-plan")

            result, code = run([
                "switch",
                "--governance-repo", gov_tmp,
                "--feature-id", "auth-login",
                "--control-repo", ctrl_tmp,
            ])
            assert_eq("switch with ctrl repo status", result["status"], "pass")
            assert_eq("switch with ctrl repo exit code", code, 0)
            assert_eq("plan_branch in result", result.get("plan_branch"), "auth-login-plan")
            assert_eq("branch_switched true", result.get("branch_switched"), True)
            assert_false("no branch_error", bool(result.get("branch_error")))
            feat = result.get("feature", {})
            context_path = Path(feat.get("context_path", ""))
            assert_eq(
                "ctrl repo default context path",
                context_path,
                Path(ctrl_tmp) / ".lens" / "personal" / "context.yaml",
            )
            assert_eq("ctrl repo context.yaml exists", context_path.exists(), True)

            head = subprocess.run(
                ["git", "-C", ctrl_tmp, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            assert_eq("ctrl repo HEAD is plan branch", head, "auth-login-plan")


def test_switch_with_control_repo_missing_plan_branch():
    """Switch with --control-repo returns branch_switched: false when plan branch absent."""
    print("test_switch_with_control_repo_missing_plan_branch", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as ctrl_tmp:
            write_index(gov_tmp, SAMPLE_INDEX_ENTRIES)
            write_feature(gov_tmp, "platform", "identity", "auth-login", SAMPLE_FEATURE)
            init_git_repo(ctrl_tmp)

            result, code = run([
                "switch",
                "--governance-repo", gov_tmp,
                "--feature-id", "auth-login",
                "--control-repo", ctrl_tmp,
            ])
            assert_eq("missing branch status", result["status"], "pass")
            assert_eq("missing branch exit code", code, 0)
            assert_eq("plan_branch present", result.get("plan_branch"), "auth-login-plan")
            assert_eq("branch_switched false", result.get("branch_switched"), False)
            assert_true("branch_error populated", bool(result.get("branch_error")))


def test_switch_without_control_repo_defaults_to_current_directory():
    """Switch without --control-repo checks out in the current working directory."""
    print("test_switch_without_control_repo_defaults_to_current_directory", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as ctrl_tmp:
            write_index(gov_tmp, SAMPLE_INDEX_ENTRIES)
            write_feature(gov_tmp, "platform", "identity", "auth-login", SAMPLE_FEATURE)
            init_git_repo(ctrl_tmp)
            create_branch(ctrl_tmp, "auth-login-plan")

            result, code = run([
                "switch", "--governance-repo", gov_tmp, "--feature-id", "auth-login",
            ], cwd=ctrl_tmp)
            assert_eq("default ctrl repo status", result["status"], "pass")
            assert_eq("default ctrl repo exit code", code, 0)
            assert_eq("default plan_branch present", result.get("plan_branch"), "auth-login-plan")
            assert_eq("default branch_switched true", result.get("branch_switched"), True)
            assert_false("default has no branch_error", bool(result.get("branch_error")))

            head = subprocess.run(
                ["git", "-C", ctrl_tmp, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True,
            ).stdout.strip()
            assert_eq("default ctrl repo HEAD is plan branch", head, "auth-login-plan")


def test_switch_service_context_with_control_repo_existing_branch():
    """Service-context fallback with --control-repo checks out the plan branch."""
    print("test_switch_service_context_with_control_repo_existing_branch", file=sys.stderr)
    with tempfile.TemporaryDirectory() as gov_tmp:
        with tempfile.TemporaryDirectory() as ctrl_tmp:
            write_domain(gov_tmp, "plugins", {
                "kind": "domain", "id": "plugins", "name": "Plugins",
                "domain": "plugins", "status": "active", "owner": "cweber",
            })
            write_service(gov_tmp, "plugins", "hermes", {
                "kind": "service", "id": "plugins-hermes", "name": "Hermes",
                "domain": "plugins", "service": "hermes", "status": "active", "owner": "cweber",
            })
            init_git_repo(ctrl_tmp)
            create_branch(ctrl_tmp, "plugins-hermes-plan")

            result, code = run([
                "switch",
                "--governance-repo", gov_tmp,
                "--feature-id", "plugins-hermes",
                "--control-repo", ctrl_tmp,
            ])
            assert_eq("svc ctx ctrl repo status", result["status"], "pass")
            assert_eq("svc ctx plan_branch", result.get("plan_branch"), "plugins-hermes-plan")
            assert_eq("svc ctx branch_switched", result.get("branch_switched"), True)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> None:
    test_list_features()
    test_list_active_filter_excludes_archived()
    test_list_all_includes_archived()
    test_list_missing_index_falls_back_to_domains()
    test_list_domain_fallback_with_domains()
    test_list_empty_index()
    test_list_output_fields()
    test_list_includes_target_repo_state_when_feature_yaml_exists()
    test_list_numbered_menu_fields()
    test_switch_existing_feature()
    test_switch_nonexistent_feature()
    test_switch_missing_index_uses_service_id_fallback()
    test_switch_missing_index_uses_domain_service_fallback()
    test_switch_missing_index_writes_context_yaml_when_personal_folder_set()
    test_switch_missing_index_invalid_service_selection_fails()
    test_switch_returns_context_depends_on()
    test_switch_returns_context_related()
    test_switch_stale_detection()
    test_switch_not_stale_recent()
    test_context_paths_with_depends_on_and_related()
    test_context_paths_with_blocks()
    test_context_paths_no_dependencies()
    test_context_paths_not_found()
    test_path_traversal_in_feature_id()
    test_depends_on_not_duplicated_in_summaries()
    test_switch_with_control_repo_existing_plan_branch()
    test_switch_with_control_repo_missing_plan_branch()
    test_switch_without_control_repo_defaults_to_current_directory()
    test_switch_service_context_with_control_repo_existing_branch()

    total = PASS + FAIL
    print(f"\n{PASS}/{total} tests passed", file=sys.stderr)

    if FAIL > 0:
        print(f"{FAIL} test(s) FAILED", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
