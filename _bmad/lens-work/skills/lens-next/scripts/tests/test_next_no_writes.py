#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""
test_next_no_writes.py

Regression test: next-ops.py suggest must produce ZERO filesystem writes
regardless of whether the feature is valid, invalid, blocked, or unblocked.

Also audits lens-next/SKILL.md to confirm no write-capable tool calls
appear in the skill instructions.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


SCRIPT = Path(__file__).parent.parent / "next-ops.py"
MODULE_ROOT = SCRIPT.parents[3]  # _bmad/lens-work
SKILL_MD = MODULE_ROOT / "skills" / "lens-next" / "SKILL.md"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_next(args: list[str]) -> tuple[dict, int]:
    """Invoke next-ops.py and return (parsed_json, exit_code)."""
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Non-JSON output from next-ops.py\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
        ) from exc
    return payload, result.returncode


def snapshot_files(root: Path) -> dict[str, str]:
    """Return a mapping of relative-path → content for all files under root."""
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def write_feature(repo: Path, feature_id: str, data: dict) -> Path:
    """Create a feature.yaml at the canonical governance path for feature_id."""
    domain = data.get("domain", "test-domain")
    service = data.get("service", "test-service")
    feature_dir = repo / "features" / domain / service / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "feature.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    return feature_dir


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def governance_repo(tmp_path):
    """Minimal temporary governance repo containing a valid feature."""
    repo = tmp_path / "governance"
    repo.mkdir()
    write_feature(repo, "test-feature-unblocked", {
        "featureId": "test-feature-unblocked",
        "domain": "test-domain",
        "service": "test-service",
        "phase": "preplan",
        "track": "full",
    })
    return repo


# ---------------------------------------------------------------------------
# Tests: no file system writes on valid feature (unblocked)
# ---------------------------------------------------------------------------

def test_no_writes_valid_feature(governance_repo, tmp_path):
    """Running next-ops.py suggest on a valid feature must not modify any files."""
    # Snapshot state of governance repo and tmp_path before the call
    before = snapshot_files(tmp_path)

    payload, _ = run_next([
        "suggest",
        "--feature-id", "test-feature-unblocked",
        "--governance-repo", str(governance_repo),
    ])

    after = snapshot_files(tmp_path)

    assert before == after, (
        f"next-ops.py suggest wrote files unexpectedly.\n"
        f"Added/changed keys: {set(after) - set(before)}"
    )
    assert payload["status"] in ("unblocked", "blocked", "fail")


# ---------------------------------------------------------------------------
# Tests: no file system writes on invalid / missing feature.yaml
# ---------------------------------------------------------------------------

def test_no_writes_missing_feature_yaml(governance_repo, tmp_path):
    """Running next-ops.py suggest with a non-existent feature-id must not write anything."""
    before = snapshot_files(tmp_path)

    payload, exit_code = run_next([
        "suggest",
        "--feature-id", "feature-that-does-not-exist-xyz",
        "--governance-repo", str(governance_repo),
    ])

    after = snapshot_files(tmp_path)

    assert before == after, (
        f"next-ops.py suggest (missing feature) wrote files unexpectedly.\n"
        f"Added/changed keys: {set(after) - set(before)}"
    )
    assert payload["status"] == "fail"
    assert "feature-that-does-not-exist-xyz" in payload["error"]
    assert exit_code != 0


# ---------------------------------------------------------------------------
# Tests: no writes on blocked feature
# ---------------------------------------------------------------------------

def test_no_writes_blocked_feature(tmp_path):
    """Running next-ops.py suggest on a paused feature must not write any files."""
    repo = tmp_path / "governance-blocked"
    repo.mkdir()
    write_feature(repo, "test-feature-paused", {
        "featureId": "test-feature-paused",
        "domain": "test-domain",
        "service": "test-service",
        "phase": "paused",
        "track": "full",
    })

    before = snapshot_files(tmp_path)

    payload, _ = run_next([
        "suggest",
        "--feature-id", "test-feature-paused",
        "--governance-repo", str(repo),
    ])

    after = snapshot_files(tmp_path)

    assert before == after, (
        f"next-ops.py suggest (blocked) wrote files unexpectedly.\n"
        f"Added/changed keys: {set(after) - set(before)}"
    )
    assert payload["status"] == "blocked"


# ---------------------------------------------------------------------------
# Tests: no writes on unknown phase / track
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phase,track", [
    ("unknown-phase-xyz", "full"),
    ("preplan", "unknown-track-xyz"),
])
def test_no_writes_fail_cases(tmp_path, phase, track):
    """next-ops.py suggest must not write files even when it returns status=fail."""
    repo = tmp_path / f"governance-fail-{phase}-{track}"
    repo.mkdir()
    write_feature(repo, "test-feature-fail", {
        "featureId": "test-feature-fail",
        "domain": "test-domain",
        "service": "test-service",
        "phase": phase,
        "track": track,
    })

    before = snapshot_files(tmp_path)

    payload, _ = run_next([
        "suggest",
        "--feature-id", "test-feature-fail",
        "--governance-repo", str(repo),
    ])

    after = snapshot_files(tmp_path)

    assert before == after, (
        f"next-ops.py suggest (fail) wrote files unexpectedly for phase={phase!r} track={track!r}.\n"
        f"Added/changed keys: {set(after) - set(before)}"
    )
    assert payload["status"] == "fail"


# ---------------------------------------------------------------------------
# Audit: SKILL.md must contain no write-capable tool calls
# ---------------------------------------------------------------------------

_WRITE_PATTERNS = [
    r"\bcreate_file\b",
    r"\breplace_string_in_file\b",
    r"\bgit commit\b",
    r"\bgit push\b",
    r"\bedit_file\b",
    r"\bwrite_file\b",
]

# Lines allowed to contain write-related text (e.g., the audit statement itself)
_AUDIT_EXEMPTION_RE = re.compile(
    r"(grep|Audit|audit|must return nothing|No .*(create_file|replace_string|git commit|git push|edit_file|write_file)|"
    r"no `create_file`|no `replace_string_in_file`|no `git commit`|No governance writes|No control-doc writes)"
)


def test_skill_md_no_write_tool_calls():
    """SKILL.md must not instruct the agent to perform write operations."""
    assert SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}"
    text = SKILL_MD.read_text(encoding="utf-8")
    lines = text.splitlines()

    violations = []
    for line_no, line in enumerate(lines, start=1):
        if _AUDIT_EXEMPTION_RE.search(line):
            continue
        for pattern in _WRITE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append((line_no, line.strip(), pattern))

    assert not violations, (
        "SKILL.md contains write-capable tool call references:\n"
        + "\n".join(f"  L{ln}: {text!r} [matched: {pat}]" for ln, text, pat in violations)
    )


# ---------------------------------------------------------------------------
# Routing outcome fixtures and tests
# ---------------------------------------------------------------------------

MINIMAL_LIFECYCLE_YAML = {
    "phases": {
        "preplan": {"auto_advance_to": "/businessplan"},
        "businessplan": {"auto_advance_to": "/techplan"},
        "techplan": {"auto_advance_to": "/finalizeplan"},
        "finalizeplan": {"auto_advance_to": "/dev"},
        "expressplan": {"auto_advance_to": "/finalizeplan"},
    },
    "tracks": {
        "full": {
            "start_phase": "preplan",
            "phases": ["preplan", "businessplan", "techplan", "finalizeplan"],
        },
        "express": {
            "start_phase": "expressplan",
            "phases": ["expressplan", "finalizeplan"],
        },
    },
}


@pytest.fixture()
def lifecycle_yaml(tmp_path):
    """Write a minimal lifecycle.yaml to tmp_path and return its path."""
    path = tmp_path / "lifecycle.yaml"
    path.write_text(yaml.safe_dump(MINIMAL_LIFECYCLE_YAML, sort_keys=False))
    return path


@pytest.mark.parametrize("phase,track,expected_recommendation", [
    ("preplan", "full", "/businessplan"),
    ("preplan-complete", "full", "/businessplan"),
    ("businessplan", "full", "/techplan"),
    ("businessplan-complete", "full", "/techplan"),
    ("techplan", "full", "/finalizeplan"),
    ("techplan-complete", "full", "/finalizeplan"),
    ("finalizeplan", "full", "/dev"),
    ("finalizeplan-complete", "full", "/dev"),
    ("expressplan", "express", "/finalizeplan"),
    ("expressplan-complete", "express", "/finalizeplan"),
    ("finalizeplan", "express", "/dev"),
    ("finalizeplan-complete", "express", "/dev"),
])
def test_routing_outcomes(tmp_path, lifecycle_yaml, phase, track, expected_recommendation):
    """Verify deterministic routing outcomes (status/recommendation) across phases and tracks."""
    repo = tmp_path / "governance"
    repo.mkdir()
    write_feature(repo, "test-routing-feature", {
        "featureId": "test-routing-feature",
        "domain": "test-domain",
        "service": "test-service",
        "phase": phase,
        "track": track,
    })

    payload, exit_code = run_next([
        "suggest",
        "--feature-id", "test-routing-feature",
        "--governance-repo", str(repo),
        "--lifecycle-path", str(lifecycle_yaml),
    ])

    assert payload["status"] == "unblocked", (
        f"Expected unblocked for phase={phase!r} track={track!r}, "
        f"got status={payload['status']!r} error={payload.get('error', '')!r}"
    )
    assert payload["recommendation"] == expected_recommendation, (
        f"Expected recommendation={expected_recommendation!r} for phase={phase!r} track={track!r}, "
        f"got {payload['recommendation']!r}"
    )
    assert payload["blockers"] == []
    assert exit_code == 0


def test_routing_paused_state(tmp_path, lifecycle_yaml):
    """Paused feature must return status=blocked with the standard pause message."""
    repo = tmp_path / "governance"
    repo.mkdir()
    write_feature(repo, "test-paused", {
        "featureId": "test-paused",
        "domain": "test-domain",
        "service": "test-service",
        "phase": "paused",
        "track": "full",
    })

    payload, _ = run_next([
        "suggest",
        "--feature-id", "test-paused",
        "--governance-repo", str(repo),
        "--lifecycle-path", str(lifecycle_yaml),
    ])

    assert payload["status"] == "blocked"
    assert any("paused" in b for b in payload["blockers"])


def test_routing_unknown_phase(tmp_path, lifecycle_yaml):
    """Unknown phase must return status=fail with a descriptive error."""
    repo = tmp_path / "governance"
    repo.mkdir()
    write_feature(repo, "test-unknown-phase", {
        "featureId": "test-unknown-phase",
        "domain": "test-domain",
        "service": "test-service",
        "phase": "nonexistent-phase-xyz",
        "track": "full",
    })

    payload, exit_code = run_next([
        "suggest",
        "--feature-id", "test-unknown-phase",
        "--governance-repo", str(repo),
        "--lifecycle-path", str(lifecycle_yaml),
    ])

    assert payload["status"] == "fail"
    assert "nonexistent-phase-xyz" in payload["error"] or "Unknown phase" in payload["error"]
    assert exit_code != 0


def test_routing_unknown_track(tmp_path, lifecycle_yaml):
    """Unknown track must return status=fail with a descriptive error."""
    repo = tmp_path / "governance"
    repo.mkdir()
    write_feature(repo, "test-unknown-track", {
        "featureId": "test-unknown-track",
        "domain": "test-domain",
        "service": "test-service",
        "phase": "preplan",
        "track": "nonexistent-track-xyz",
    })

    payload, exit_code = run_next([
        "suggest",
        "--feature-id", "test-unknown-track",
        "--governance-repo", str(repo),
        "--lifecycle-path", str(lifecycle_yaml),
    ])

    assert payload["status"] == "fail"
    assert "nonexistent-track-xyz" in payload["error"] or "Unknown track" in payload["error"]
    assert exit_code != 0


@pytest.mark.parametrize("field_name,field_value,expected_error", [
    ("warnings", "review pending", "warnings"),
    ("dependencies", ["dep-feature"], "dependencies"),
    ("dependencies", {"depends_on": "dep-feature"}, "depends_on"),
    ("dependencies", {"depends_on": [123]}, "depends_on"),
])
def test_malformed_feature_yaml_fields_fail_cleanly(
    tmp_path, lifecycle_yaml, field_name, field_value, expected_error,
):
    """Malformed optional feature.yaml fields must fail cleanly without tracebacks."""
    repo = tmp_path / "governance"
    repo.mkdir()
    feature = {
        "featureId": "test-malformed-fields",
        "domain": "test-domain",
        "service": "test-service",
        "phase": "preplan",
        "track": "full",
        field_name: field_value,
    }
    write_feature(repo, "test-malformed-fields", feature)

    payload, exit_code = run_next([
        "suggest",
        "--feature-id", "test-malformed-fields",
        "--governance-repo", str(repo),
        "--lifecycle-path", str(lifecycle_yaml),
    ])

    assert payload["status"] == "fail"
    assert expected_error in payload["error"]
    assert exit_code != 0


def test_missing_dependency_feature_blocks(tmp_path, lifecycle_yaml):
    """A declared dependency with no feature.yaml must be surfaced as a blocker."""
    repo = tmp_path / "governance"
    repo.mkdir()
    write_feature(repo, "test-missing-dep", {
        "featureId": "test-missing-dep",
        "domain": "test-domain",
        "service": "test-service",
        "phase": "finalizeplan",
        "track": "full",
        "dependencies": {"depends_on": ["dep-feature-missing"]},
    })

    payload, exit_code = run_next([
        "suggest",
        "--feature-id", "test-missing-dep",
        "--governance-repo", str(repo),
        "--lifecycle-path", str(lifecycle_yaml),
    ])

    assert payload["status"] == "blocked"
    assert any("dep-feature-missing" in blocker for blocker in payload["blockers"])
    assert exit_code == 0


def test_invalid_feature_id_fails_before_lookup(governance_repo):
    """feature-id input is constrained before path/index lookup."""
    payload, exit_code = run_next([
        "suggest",
        "--feature-id", "../bad-feature",
        "--governance-repo", str(governance_repo),
    ])

    assert payload["status"] == "fail"
    assert "feature-id" in payload["error"]
    assert exit_code != 0


def test_feature_id_with_dots_and_underscores_passes_validation(governance_repo):
    """feature-id containing dots and underscores must pass the regex and proceed to lookup."""
    # The ID does not exist in the governance repo, so we expect a "not found" error,
    # not a feature-id validation error — proving the pattern now accepts dots/underscores.
    payload, exit_code = run_next([
        "suggest",
        "--feature-id", "my.feature_id",
        "--governance-repo", str(governance_repo),
    ])

    assert payload["status"] == "fail"
    # Must fail on lookup, not on ID validation
    assert "feature-id" not in payload["error"]
    assert exit_code != 0


def test_feature_id_ending_with_hyphen_fails_validation(governance_repo):
    """feature-id ending with a non-alphanumeric character must be rejected."""
    payload, exit_code = run_next([
        "suggest",
        "--feature-id", "bad-feature-",
        "--governance-repo", str(governance_repo),
    ])

    assert payload["status"] == "fail"
    assert "feature-id" in payload["error"]
    assert exit_code != 0


def test_lifecycle_yaml_must_be_mapping(tmp_path):
    """A YAML-valid but non-mapping lifecycle file must fail with a clear error."""
    repo = tmp_path / "governance"
    repo.mkdir()
    write_feature(repo, "test-bad-lifecycle", {
        "featureId": "test-bad-lifecycle",
        "domain": "test-domain",
        "service": "test-service",
        "phase": "preplan",
        "track": "full",
    })
    lifecycle_path = tmp_path / "lifecycle.yaml"
    lifecycle_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    payload, exit_code = run_next([
        "suggest",
        "--feature-id", "test-bad-lifecycle",
        "--governance-repo", str(repo),
        "--lifecycle-path", str(lifecycle_path),
    ])

    assert payload["status"] == "fail"
    assert "lifecycle.yaml" in payload["error"]
    assert "mapping" in payload["error"]
    assert exit_code != 0


def test_routing_warnings_passthrough(tmp_path, lifecycle_yaml):
    """Warnings in feature.yaml are surfaced in the unblocked result."""
    repo = tmp_path / "governance"
    repo.mkdir()
    write_feature(repo, "test-with-warnings", {
        "featureId": "test-with-warnings",
        "domain": "test-domain",
        "service": "test-service",
        "phase": "preplan",
        "track": "full",
        "warnings": ["This feature has a pending architecture review"],
    })

    payload, exit_code = run_next([
        "suggest",
        "--feature-id", "test-with-warnings",
        "--governance-repo", str(repo),
        "--lifecycle-path", str(lifecycle_yaml),
    ])

    assert payload["status"] == "unblocked"
    assert payload["warnings"] == ["This feature has a pending architecture review"]
    assert payload["recommendation"] == "/businessplan"
    assert exit_code == 0


def test_routing_blocked_by_dependency(tmp_path, lifecycle_yaml):
    """Feature with an incomplete dependency must return status=blocked."""
    repo = tmp_path / "governance"
    repo.mkdir()
    write_feature(repo, "dep-feature-incomplete", {
        "featureId": "dep-feature-incomplete",
        "domain": "test-domain",
        "service": "test-service",
        "phase": "preplan",
        "track": "full",
    })
    write_feature(repo, "test-blocked-feature", {
        "featureId": "test-blocked-feature",
        "domain": "test-domain",
        "service": "test-service",
        "phase": "finalizeplan",
        "track": "full",
        "dependencies": {"depends_on": ["dep-feature-incomplete"]},
    })

    payload, _ = run_next([
        "suggest",
        "--feature-id", "test-blocked-feature",
        "--governance-repo", str(repo),
        "--lifecycle-path", str(lifecycle_yaml),
    ])

    assert payload["status"] == "blocked"
    assert any("dep-feature-incomplete" in b for b in payload["blockers"])
