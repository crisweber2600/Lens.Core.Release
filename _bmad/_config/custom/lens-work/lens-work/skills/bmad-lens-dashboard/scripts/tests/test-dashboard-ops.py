#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for dashboard-ops.py."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

SCRIPT = str(Path(__file__).parent.parent / "dashboard-ops.py")
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
# Repo fixture helper
# ---------------------------------------------------------------------------


def setup_repo(tmp_dir: str, feature_index: dict) -> None:
    """Initialize a git repo with feature-index.yaml committed on the main branch."""
    subprocess.run(["git", "init", tmp_dir], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", tmp_dir, "config", "user.email", "test@test.com"],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", tmp_dir, "config", "user.name", "Test User"],
        capture_output=True,
    )
    # Ensure default branch is named 'main' on all git versions
    subprocess.run(
        ["git", "-C", tmp_dir, "symbolic-ref", "HEAD", "refs/heads/main"],
        capture_output=True,
    )

    index_path = os.path.join(tmp_dir, "feature-index.yaml")
    with open(index_path, "w") as f:
        yaml.dump(feature_index, f, default_flow_style=False)

    subprocess.run(["git", "-C", tmp_dir, "add", "."], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", tmp_dir, "commit", "-m", "init"],
        capture_output=True,
        check=True,
    )


def stale_date() -> str:
    """Return an ISO 8601 date 30 days in the past."""
    return (datetime.now(timezone.utc) - timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def recent_date() -> str:
    """Return an ISO 8601 date 1 day in the past."""
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def make_feature(
    feature_id: str,
    domain: str = "platform",
    service: str = "api",
    phase: str = "dev",
    track: str = "quickplan",
    last_updated: str | None = None,
    dependencies: dict | None = None,
) -> dict:
    """Build a minimal feature dict for test fixtures."""
    return {
        "featureId": feature_id,
        "name": f"Feature {feature_id}",
        "domain": domain,
        "service": service,
        "phase": phase,
        "track": track,
        "priority": "medium",
        "lastUpdated": last_updated or recent_date(),
        "dependencies": dependencies or {"depends_on": [], "blocks": [], "related": []},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_collect_with_populated_feature_index():
    print("test_collect_with_populated_feature_index", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        index = {
            "features": [
                make_feature("auth-login", domain="platform", service="identity"),
                make_feature("billing-core", domain="commerce", service="billing"),
            ]
        }
        setup_repo(tmp, index)
        result, code = run(["collect", "--governance-repo", tmp])
        assert_eq("status", result["status"], "pass")
        assert_eq("exit code", code, 0)
        assert_eq("feature count", len(result["features"]), 2)
        assert_eq("domain count", result["domain_count"], 2)
        ids = [f["featureId"] for f in result["features"]]
        assert_true("auth-login present", "auth-login" in ids)
        assert_true("billing-core present", "billing-core" in ids)


def test_collect_with_empty_feature_index():
    print("test_collect_with_empty_feature_index", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        setup_repo(tmp, {"features": []})
        result, code = run(["collect", "--governance-repo", tmp])
        assert_eq("status", result["status"], "pass")
        assert_eq("exit code", code, 0)
        assert_eq("feature count", len(result["features"]), 0)
        assert_eq("stale count", result["stale_count"], 0)
        assert_eq("domain count", result["domain_count"], 0)


def test_collect_stale_count_correct():
    print("test_collect_stale_count_correct", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        index = {
            "features": [
                # stale: dev phase, 30 days old
                make_feature("old-feature", phase="dev", last_updated=stale_date()),
                # not stale: dev phase, 1 day old
                make_feature("fresh-feature", phase="dev", last_updated=recent_date()),
                # not stale: complete phase (not active)
                make_feature("done-feature", phase="complete", last_updated=stale_date()),
            ]
        }
        setup_repo(tmp, index)
        result, code = run(["collect", "--governance-repo", tmp])
        assert_eq("status", result["status"], "pass")
        assert_eq("stale count is 1", result["stale_count"], 1)
        stale_ids = [f["featureId"] for f in result["features"] if f["stale"]]
        assert_eq("stale feature id", stale_ids, ["old-feature"])


def test_dependency_data_extracts_nodes_and_edges():
    print("test_dependency_data_extracts_nodes_and_edges", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        index = {
            "features": [
                make_feature(
                    "feat-a",
                    dependencies={"depends_on": ["feat-b"], "blocks": [], "related": []},
                ),
                make_feature("feat-b"),
            ]
        }
        setup_repo(tmp, index)
        result, code = run(["dependency-data", "--governance-repo", tmp])
        assert_eq("status", result["status"], "pass")
        assert_eq("exit code", code, 0)
        assert_eq("node count", len(result["nodes"]), 2)
        assert_eq("edge count", len(result["edges"]), 1)
        edge = result["edges"][0]
        assert_eq("edge from", edge["from"], "feat-a")
        assert_eq("edge to", edge["to"], "feat-b")
        assert_eq("edge type", edge["type"], "depends_on")
        node_ids = [n["id"] for n in result["nodes"]]
        assert_true("feat-a node", "feat-a" in node_ids)
        assert_true("feat-b node", "feat-b" in node_ids)


def test_dependency_data_with_no_dependencies():
    print("test_dependency_data_with_no_dependencies", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        index = {
            "features": [
                make_feature("solo-feature"),
            ]
        }
        setup_repo(tmp, index)
        result, code = run(["dependency-data", "--governance-repo", tmp])
        assert_eq("status", result["status"], "pass")
        assert_eq("node count", len(result["nodes"]), 1)
        assert_eq("edge count (no deps)", len(result["edges"]), 0)


def test_generate_creates_html_file():
    print("test_generate_creates_html_file", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        index = {
            "features": [
                make_feature("test-feature"),
            ]
        }
        setup_repo(tmp, index)
        output_path = os.path.join(tmp, "out", "dashboard.html")
        result, code = run([
            "generate",
            "--governance-repo", tmp,
            "--output", output_path,
        ])
        assert_eq("status", result["status"], "pass")
        assert_eq("exit code", code, 0)
        assert_true("output file exists", Path(output_path).exists())
        assert_true("features_included", result["features_included"] >= 1)
        assert_true("generated_at present", bool(result.get("generated_at")))


def test_generate_with_custom_output_path():
    print("test_generate_with_custom_output_path", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        index = {"features": [make_feature("custom-out-feature")]}
        setup_repo(tmp, index)
        custom_output = os.path.join(tmp, "custom", "path", "my-dashboard.html")
        result, code = run([
            "generate",
            "--governance-repo", tmp,
            "--output", custom_output,
        ])
        assert_eq("status", result["status"], "pass")
        assert_true("custom output exists", Path(custom_output).exists())
        assert_true("output_path in result", "output_path" in result)
        assert_true("output_path ends with html", result["output_path"].endswith(".html"))


def test_html_file_contains_feature_ids():
    print("test_html_file_contains_feature_ids", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        index = {
            "features": [
                make_feature("my-unique-feature-id"),
                make_feature("another-unique-feature", domain="commerce"),
            ]
        }
        setup_repo(tmp, index)
        output_path = os.path.join(tmp, "dashboard.html")
        run(["generate", "--governance-repo", tmp, "--output", output_path])
        html = Path(output_path).read_text(encoding="utf-8")
        assert_true("first feature id in HTML", "my-unique-feature-id" in html)
        assert_true("second feature id in HTML", "another-unique-feature" in html)


def test_missing_governance_repo_exits_1():
    print("test_missing_governance_repo_exits_1", file=sys.stderr)
    nonexistent = "/nonexistent/path/to/governance/repo"
    for subcmd in ["collect", "dependency-data"]:
        result, code = run([subcmd, "--governance-repo", nonexistent])
        assert_eq(f"{subcmd} status fail", result["status"], "fail")
        assert_eq(f"{subcmd} exit code 1", code, 1)
        assert_true(f"{subcmd} error message", "error" in result)

    with tempfile.TemporaryDirectory() as tmp:
        result, code = run([
            "generate",
            "--governance-repo", nonexistent,
            "--output", os.path.join(tmp, "out.html"),
        ])
        assert_eq("generate status fail", result["status"], "fail")
        assert_eq("generate exit code 1", code, 1)


def test_collect_with_json_output_file():
    print("test_collect_with_json_output_file", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        index = {"features": [make_feature("output-test-feat")]}
        setup_repo(tmp, index)
        output_file = os.path.join(tmp, "collected.json")
        result, code = run([
            "collect",
            "--governance-repo", tmp,
            "--output", output_file,
        ])
        assert_eq("status", result["status"], "pass")
        assert_true("output file created", Path(output_file).exists())
        with open(output_file) as f:
            saved = json.load(f)
        assert_eq("saved status", saved["status"], "pass")
        assert_eq("saved feature count", len(saved["features"]), 1)


def test_dependency_data_all_edge_types():
    print("test_dependency_data_all_edge_types", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        index = {
            "features": [
                make_feature(
                    "hub-feature",
                    dependencies={
                        "depends_on": ["dep-a"],
                        "blocks": ["dep-b"],
                        "related": ["dep-c"],
                    },
                ),
                make_feature("dep-a"),
                make_feature("dep-b"),
                make_feature("dep-c"),
            ]
        }
        setup_repo(tmp, index)
        result, code = run(["dependency-data", "--governance-repo", tmp])
        assert_eq("status", result["status"], "pass")
        assert_eq("edge count", len(result["edges"]), 3)
        edge_types = {e["type"] for e in result["edges"]}
        assert_true("has depends_on", "depends_on" in edge_types)
        assert_true("has blocks", "blocks" in edge_types)
        assert_true("has related", "related" in edge_types)


def test_stale_feature_no_last_updated():
    print("test_stale_feature_no_last_updated", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        feature = make_feature("no-date-feature", phase="dev")
        del feature["lastUpdated"]
        setup_repo(tmp, {"features": [feature]})
        result, code = run(["collect", "--governance-repo", tmp])
        assert_eq("status", result["status"], "pass")
        # No lastUpdated on active phase = stale
        assert_eq("stale count", result["stale_count"], 1)


def test_generate_html_has_sections():
    print("test_generate_html_has_sections", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        index = {"features": [make_feature("section-test")]}
        setup_repo(tmp, index)
        output_path = os.path.join(tmp, "sections.html")
        run(["generate", "--governance-repo", tmp, "--output", output_path])
        html = Path(output_path).read_text(encoding="utf-8")
        for section_id in ["overview", "dependencies", "problems", "sprint", "team", "retro"]:
            assert_true(f"section #{section_id}", f'id="{section_id}"' in html)


if __name__ == "__main__":
    test_collect_with_populated_feature_index()
    test_collect_with_empty_feature_index()
    test_collect_stale_count_correct()
    test_dependency_data_extracts_nodes_and_edges()
    test_dependency_data_with_no_dependencies()
    test_generate_creates_html_file()
    test_generate_with_custom_output_path()
    test_html_file_contains_feature_ids()
    test_missing_governance_repo_exits_1()
    test_collect_with_json_output_file()
    test_dependency_data_all_edge_types()
    test_stale_feature_no_last_updated()
    test_generate_html_has_sections()

    print(f"\n{'=' * 40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'=' * 40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)
