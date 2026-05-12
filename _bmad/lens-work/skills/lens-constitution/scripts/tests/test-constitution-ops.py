#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "pytest"]
# ///
"""
Tests for constitution-ops.py — resolve, check-compliance, progressive-display.
All tests operate on real temp-directory governance repo structures.
"""

import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).parent.parent / "constitution-ops.py"


# ---------------------------------------------------------------------------
# Module import fixture (session-scoped to avoid repeated exec_module)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def ops():
    spec = spec_from_file_location("constitution_ops", SCRIPT)
    mod = module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(args: list[str], expect_code: int | None = None) -> dict:
    """Run the script and return parsed JSON output."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
    )
    if expect_code is not None:
        assert result.returncode == expect_code, (
            f"Expected exit {expect_code}, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return json.loads(result.stdout)


def write_constitution(path: Path, data: dict, prose: str = "") -> None:
    """Write a constitution.md file with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{yaml.dump(data)}---\n{prose}", encoding="utf-8")


def write_feature_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data), encoding="utf-8")


def lens_dev_tracks() -> list[str]:
    return ["quickplan", "full", "hotfix", "tech-change", "express", "expressplan"]


@pytest.fixture
def gov_repo(tmp_path: Path) -> Path:
    """Minimal governance repo with only an org constitution."""
    org_path = tmp_path / "constitutions" / "org" / "constitution.md"
    write_constitution(org_path, {"permitted_tracks": ["quickplan", "full", "hotfix", "tech-change"]})
    return tmp_path


@pytest.fixture
def full_gov_repo(tmp_path: Path) -> Path:
    """Governance repo with org, platform domain, and auth service constitutions."""
    write_constitution(
        tmp_path / "constitutions" / "org" / "constitution.md",
        {
            "permitted_tracks": ["quickplan", "full", "hotfix", "tech-change"],
            "required_artifacts": {"planning": ["business-plan", "tech-plan"], "dev": ["stories"]},
            "gate_mode": "informational",
            "additional_review_participants": [],
            "enforce_stories": True,
            "enforce_review": True,
        },
    )
    write_constitution(
        tmp_path / "constitutions" / "platform" / "constitution.md",
        {"additional_review_participants": ["security-team"]},
    )
    write_constitution(
        tmp_path / "constitutions" / "platform" / "auth" / "constitution.md",
        {
            "permitted_tracks": ["full", "quickplan"],
            "required_artifacts": {"planning": ["security-review"]},
        },
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests: load_constitution
# ---------------------------------------------------------------------------


class TestLoadConstitution:
    def test_missing_file_returns_empty(self, ops, tmp_path: Path) -> None:
        assert ops.load_constitution(tmp_path / "missing.md") == {}

    def test_file_without_frontmatter_returns_empty(self, ops, tmp_path: Path) -> None:
        f = tmp_path / "constitution.md"
        f.write_text("# Just prose, no frontmatter\n")
        assert ops.load_constitution(f) == {}

    def test_valid_frontmatter_parsed(self, ops, tmp_path: Path) -> None:
        f = tmp_path / "constitution.md"
        write_constitution(f, {"gate_mode": "hard"})
        result = ops.load_constitution(f)
        assert result["gate_mode"] == "hard"

    def test_invalid_yaml_returns_parse_error(self, ops, tmp_path: Path) -> None:
        f = tmp_path / "constitution.md"
        f.write_text("---\n: bad: yaml: [\n---\n")
        result = ops.load_constitution(f)
        assert "_parse_error" in result
        assert isinstance(result["_parse_error"], str) and len(result["_parse_error"]) > 0

    def test_dashes_in_yaml_value_not_split_as_delimiter(self, ops, tmp_path: Path) -> None:
        f = tmp_path / "constitution.md"
        # `separator: ---` should NOT be treated as a closing frontmatter delimiter
        f.write_text("---\ngate_mode: informational\nnotes: contains --- dashes\n---\n# prose\n")
        result = ops.load_constitution(f)
        assert result.get("gate_mode") == "informational"
        assert "_parse_error" not in result

    def test_unknown_keys_flagged(self, ops, tmp_path: Path) -> None:
        f = tmp_path / "constitution.md"
        write_constitution(f, {"gate_mode": "hard", "future_field": "value"})
        result = ops.load_constitution(f)
        assert "_unknown_keys" in result
        assert "future_field" in result["_unknown_keys"]

    def test_known_keys_not_flagged(self, ops, tmp_path: Path) -> None:
        f = tmp_path / "constitution.md"
        write_constitution(f, {"gate_mode": "hard", "enforce_stories": True})
        result = ops.load_constitution(f)
        assert "_unknown_keys" not in result


# ---------------------------------------------------------------------------
# Unit tests: merge_constitutions
# ---------------------------------------------------------------------------


class TestMergeConstitutions:
    def _merge(self, ops, levels: list[dict]) -> tuple[dict, list]:
        return ops.merge_constitutions(levels)

    def test_empty_levels_returns_defaults(self, ops) -> None:
        result, _ = self._merge(ops, [])
        assert set(result["permitted_tracks"]) == set(ops.TRACK_NAMES)
        assert {"standard", "express", "quickdev", "hotfix-express", "spike"}.issubset(
            set(result["permitted_tracks"])
        )

    def test_tracks_intersection(self, ops) -> None:
        result, _ = self._merge(ops, [
            {"permitted_tracks": ["quickplan", "full", "hotfix", "tech-change"]},
            {"permitted_tracks": ["quickplan", "full"]},
        ])
        assert set(result["permitted_tracks"]) == {"quickplan", "full"}

    def test_tracks_intersection_empty_result(self, ops) -> None:
        result, warnings = self._merge(ops, [
            {"permitted_tracks": ["quickplan"]},
            {"permitted_tracks": ["full"]},
        ])
        assert result["permitted_tracks"] == []
        assert any(w["type"] == "empty_permitted_tracks" for w in warnings)

    def test_explicit_empty_permitted_tracks(self, ops) -> None:
        result, warnings = self._merge(ops, [{"permitted_tracks": []}])
        assert result["permitted_tracks"] == []
        assert any(w["type"] == "empty_permitted_tracks" for w in warnings)

    def test_artifacts_union(self, ops) -> None:
        result, _ = self._merge(ops, [
            {"required_artifacts": {"planning": ["business-plan"]}},
            {"required_artifacts": {"planning": ["security-review"]}},
        ])
        assert "business-plan" in result["required_artifacts"]["planning"]
        assert "security-review" in result["required_artifacts"]["planning"]

    def test_artifacts_no_duplicates(self, ops) -> None:
        result, _ = self._merge(ops, [
            {"required_artifacts": {"planning": ["business-plan"]}},
            {"required_artifacts": {"planning": ["business-plan"]}},
        ])
        assert result["required_artifacts"]["planning"].count("business-plan") == 1

    def test_gate_mode_hard_overrides_informational(self, ops) -> None:
        result, _ = self._merge(ops, [
            {"gate_mode": "informational"},
            {"gate_mode": "hard"},
        ])
        assert result["gate_mode"] == "hard"

    def test_gate_mode_informational_does_not_downgrade_hard(self, ops) -> None:
        result, _ = self._merge(ops, [
            {"gate_mode": "hard"},
            {"gate_mode": "informational"},
        ])
        assert result["gate_mode"] == "hard"

    def test_unknown_gate_mode_produces_warning(self, ops) -> None:
        result, warnings = self._merge(ops, [{"gate_mode": "strict"}])
        assert result["gate_mode"] == "informational"  # unchanged
        assert any(w["type"] == "unknown_gate_mode" for w in warnings)

    def test_review_participants_union(self, ops) -> None:
        result, _ = self._merge(ops, [
            {"additional_review_participants": ["security-team"]},
            {"additional_review_participants": ["qa-team"]},
        ])
        assert "security-team" in result["additional_review_participants"]
        assert "qa-team" in result["additional_review_participants"]

    def test_enforce_stories_strongest_wins_true_beats_false(self, ops) -> None:
        result, _ = self._merge(ops, [
            {"enforce_stories": True},
            {"enforce_stories": False},
        ])
        assert result["enforce_stories"] is True

    def test_enforce_stories_false_stays_false_if_no_level_sets_true(self, ops) -> None:
        result, _ = self._merge(ops, [
            {"enforce_stories": False},
            {"enforce_stories": False},
        ])
        assert result["enforce_stories"] is False

    def test_enforce_review_strongest_wins(self, ops) -> None:
        result, _ = self._merge(ops, [
            {"enforce_review": False},
            {"enforce_review": True},
        ])
        assert result["enforce_review"] is True

    def test_new_phase_added_by_lower_level(self, ops) -> None:
        result, _ = self._merge(ops, [
            {},
            {"required_artifacts": {"complete": ["sign-off"]}},
        ])
        assert "sign-off" in result["required_artifacts"]["complete"]

    def test_empty_dict_levels_skipped(self, ops) -> None:
        result, _ = self._merge(ops, [{}, {}, {}])
        assert result["gate_mode"] == "informational"

    def test_unknown_tracks_produce_warning(self, ops) -> None:
        _, warnings = self._merge(ops, [{"permitted_tracks": ["quickplan", "typo-track"]}])
        assert any(w["type"] == "unknown_tracks" for w in warnings)

    def test_invalid_permitted_tracks_type_ignored(self, ops) -> None:
        result, _ = self._merge(ops, [{"permitted_tracks": "all"}])
        # String type — ignored, defaults preserved
        assert set(result["permitted_tracks"]) == set(ops.TRACK_NAMES)

    def test_invalid_artifacts_type_ignored(self, ops) -> None:
        result, _ = self._merge(ops, [{"required_artifacts": ["stories"]}])
        # List instead of dict — ignored
        assert result["required_artifacts"]["planning"] == ["business-plan", "tech-plan"]

    def test_invalid_participants_type_ignored(self, ops) -> None:
        result, _ = self._merge(ops, [{"additional_review_participants": "security-team"}])
        assert result["additional_review_participants"] == []

    def test_unknown_fields_ignored(self, ops) -> None:
        result, _ = self._merge(ops, [{"_unknown_keys": ["x"], "unknown_field": "value"}])
        assert "unknown_field" not in result
        assert result["gate_mode"] == "informational"

    def test_enforce_stories_adds_stories_to_dev_artifacts(self, ops) -> None:
        result, _ = self._merge(ops, [{"enforce_stories": True}])
        assert "stories" in result["required_artifacts"]["dev"]

    def test_enforce_stories_false_does_not_add_if_not_present(self, ops) -> None:
        # Start with a merge where enforce_stories is explicitly false
        result, _ = self._merge(ops, [
            {"enforce_stories": False},
        ])
        # "stories" is in defaults["required_artifacts"]["dev"] already
        # enforce_stories=False doesn't remove it (additive merge) but also doesn't force-add
        assert result["enforce_stories"] is False


# ---------------------------------------------------------------------------
# Unit tests: input validation
# ---------------------------------------------------------------------------


class TestValidateSlug:
    def test_valid_slug(self, ops) -> None:
        err, code = ops._validate_slug("platform", "domain")
        assert err is None and code == 0

    def test_slug_with_hyphen_valid(self, ops) -> None:
        err, code = ops._validate_slug("my-service", "service")
        assert err is None and code == 0

    def test_slug_with_underscore_valid(self, ops) -> None:
        err, code = ops._validate_slug("auth_service", "service")
        assert err is None and code == 0

    def test_empty_slug_rejected(self, ops) -> None:
        err, code = ops._validate_slug("", "domain")
        assert err is not None and code == 1

    def test_dotdot_slug_rejected(self, ops) -> None:
        err, code = ops._validate_slug("../../etc", "domain")
        assert err is not None and code == 1

    def test_slash_slug_rejected(self, ops) -> None:
        err, code = ops._validate_slug("plat/form", "domain")
        assert err is not None and code == 1


# ---------------------------------------------------------------------------
# Integration tests: resolve subcommand
# ---------------------------------------------------------------------------


class TestResolve:
    def test_resolve_org_only(self, gov_repo: Path) -> None:
        out = run(["resolve", "--governance-repo", str(gov_repo), "--domain", "platform", "--service", "auth"])
        assert out["levels_loaded"] == ["org"]
        assert "quickplan" in out["resolved_constitution"]["permitted_tracks"]

    def test_resolve_missing_constitutions_dir(self, tmp_path: Path) -> None:
        out = run(["resolve", "--governance-repo", str(tmp_path), "--domain", "x", "--service", "y"], expect_code=1)
        assert out["error"] == "constitutions_dir_not_found"

    def test_resolve_missing_org_constitution(self, tmp_path: Path) -> None:
        (tmp_path / "constitutions").mkdir()
        out = run(["resolve", "--governance-repo", str(tmp_path), "--domain", "x", "--service", "y"], expect_code=1)
        assert out["error"] == "org_constitution_missing"

    def test_resolve_org_parse_error_is_hard_failure(self, tmp_path: Path) -> None:
        bad = tmp_path / "constitutions" / "org" / "constitution.md"
        bad.parent.mkdir(parents=True)
        bad.write_text("---\n: [broken yaml\n---\n")
        out = run(["resolve", "--governance-repo", str(tmp_path), "--domain", "x", "--service", "y"], expect_code=1)
        assert out["error"] == "org_constitution_parse_error"

    def test_resolve_three_levels(self, full_gov_repo: Path) -> None:
        out = run(["resolve", "--governance-repo", str(full_gov_repo), "--domain", "platform", "--service", "auth"])
        assert set(out["levels_loaded"]) == {"org", "domain", "service"}
        const = out["resolved_constitution"]
        assert "security-team" in const["additional_review_participants"]
        assert set(const["permitted_tracks"]) == {"full", "quickplan"}
        assert "security-review" in const["required_artifacts"]["planning"]

    def test_resolve_with_repo_level(self, full_gov_repo: Path) -> None:
        repo_path = full_gov_repo / "constitutions" / "platform" / "auth" / "my-repo" / "constitution.md"
        write_constitution(repo_path, {"gate_mode": "hard"})
        out = run(["resolve", "--governance-repo", str(full_gov_repo), "--domain", "platform", "--service", "auth", "--repo", "my-repo"])
        assert "repo" in out["levels_loaded"]
        assert out["resolved_constitution"]["gate_mode"] == "hard"

    def test_resolve_domain_only_no_service_file(self, gov_repo: Path) -> None:
        domain_path = gov_repo / "constitutions" / "payments" / "constitution.md"
        write_constitution(domain_path, {"gate_mode": "hard"})
        out = run(["resolve", "--governance-repo", str(gov_repo), "--domain", "payments", "--service", "billing"])
        assert "domain" in out["levels_loaded"]
        assert "service" not in out["levels_loaded"]
        assert out["resolved_constitution"]["gate_mode"] == "hard"

    def test_resolve_dry_run_flag(self, gov_repo: Path) -> None:
        out = run(["resolve", "--governance-repo", str(gov_repo), "--domain", "x", "--service", "y", "--dry-run"])
        assert out.get("dry_run") is True

    def test_resolve_parse_error_produces_warning(self, gov_repo: Path) -> None:
        bad = gov_repo / "constitutions" / "platform" / "constitution.md"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("---\n: [broken yaml\n---\n")
        out = run(["resolve", "--governance-repo", str(gov_repo), "--domain", "platform", "--service", "auth"])
        warnings = out.get("warnings", [])
        assert any(w["type"] == "parse_error" for w in warnings)

    def test_resolve_returns_all_default_fields(self, gov_repo: Path) -> None:
        out = run(["resolve", "--governance-repo", str(gov_repo), "--domain", "x", "--service", "y"])
        const = out["resolved_constitution"]
        for field in ("permitted_tracks", "required_artifacts", "gate_mode",
                      "additional_review_participants", "enforce_stories", "enforce_review"):
            assert field in const

    def test_resolve_path_traversal_domain_rejected(self, gov_repo: Path) -> None:
        out = run(["resolve", "--governance-repo", str(gov_repo), "--domain", "../../etc", "--service", "y"], expect_code=1)
        assert "error" in out

    def test_resolve_path_traversal_service_rejected(self, gov_repo: Path) -> None:
        out = run(["resolve", "--governance-repo", str(gov_repo), "--domain", "x", "--service", "../../../tmp"], expect_code=1)
        assert "error" in out

    def test_resolve_empty_permitted_tracks_warning(self, tmp_path: Path) -> None:
        write_constitution(
            tmp_path / "constitutions" / "org" / "constitution.md",
            {"permitted_tracks": ["quickplan"]},
        )
        write_constitution(
            tmp_path / "constitutions" / "x" / "constitution.md",
            {"permitted_tracks": ["full"]},
        )
        out = run(["resolve", "--governance-repo", str(tmp_path), "--domain", "x", "--service", "y"])
        warnings = out.get("warnings", [])
        assert any(w["type"] == "empty_permitted_tracks" for w in warnings)
        assert out["resolved_constitution"]["permitted_tracks"] == []

    def test_resolve_unknown_key_warning(self, tmp_path: Path) -> None:
        write_constitution(
            tmp_path / "constitutions" / "org" / "constitution.md",
            {"gate_mode": "informational", "future_flag": "value"},
        )
        out = run(["resolve", "--governance-repo", str(tmp_path), "--domain", "x", "--service", "y"])
        warnings = out.get("warnings", [])
        assert any(w["type"] == "unknown_constitution_keys" for w in warnings)

    def test_resolve_lens_dev_new_codebase_keeps_express_track(self, tmp_path: Path) -> None:
        for constitution_path in (
            tmp_path / "constitutions" / "org" / "constitution.md",
            tmp_path / "constitutions" / "lens-dev" / "constitution.md",
            tmp_path / "constitutions" / "lens-dev" / "new-codebase" / "constitution.md",
        ):
            write_constitution(constitution_path, {"permitted_tracks": lens_dev_tracks()})

        out = run([
            "resolve",
            "--governance-repo", str(tmp_path),
            "--domain", "lens-dev",
            "--service", "new-codebase",
        ])

        assert out["levels_loaded"] == ["org", "domain", "service"]
        assert "express" in out["resolved_constitution"]["permitted_tracks"]
        assert not any(w["type"] == "unknown_tracks" for w in out.get("warnings", []))


# ---------------------------------------------------------------------------
# Integration tests: check-compliance subcommand
# ---------------------------------------------------------------------------


class TestCheckCompliance:
    def _make_feature_yaml(self, tmp_path: Path, data: dict) -> Path:
        p = tmp_path / "feature.yaml"
        write_feature_yaml(p, data)
        return p

    def test_compliance_pass_no_artifacts(self, gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"domain": "x", "service": "y", "track": "quickplan"})
        out = run(["check-compliance", "--governance-repo", str(gov_repo), "--feature-id", "my-feature", "--feature-yaml", str(fy), "--phase", "planning"], expect_code=0)
        assert out["feature_id"] == "my-feature"

    def test_compliance_missing_feature_yaml(self, gov_repo: Path) -> None:
        out = run(["check-compliance", "--governance-repo", str(gov_repo), "--feature-id", "x", "--feature-yaml", "/nonexistent/feature.yaml", "--phase", "planning"], expect_code=1)
        assert out["error"] == "feature_yaml_not_found"

    def test_compliance_feature_yaml_parse_error(self, gov_repo: Path, tmp_path: Path) -> None:
        fy = tmp_path / "feature.yaml"
        fy.write_text("domain: [unclosed bracket\n")
        out = run(["check-compliance", "--governance-repo", str(gov_repo), "--feature-id", "x", "--feature-yaml", str(fy), "--phase", "planning"], expect_code=1)
        assert out["error"] == "feature_yaml_parse_error"

    def test_compliance_missing_domain_in_yaml(self, gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"track": "quickplan"})
        out = run(["check-compliance", "--governance-repo", str(gov_repo), "--feature-id", "x", "--feature-yaml", str(fy), "--phase", "planning"], expect_code=1)
        assert out["error"] == "feature_yaml_missing_fields"

    def test_compliance_track_not_permitted_informational_is_pass(self, full_gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"domain": "platform", "service": "auth", "track": "hotfix"})
        out = run(["check-compliance", "--governance-repo", str(full_gov_repo), "--feature-id", "auth-feat", "--feature-yaml", str(fy), "--phase", "planning"], expect_code=0)
        # informational gate → overall PASS or INCOMPLETE (INCOMPLETE when artifacts not provided)
        track_check = next(c for c in out["checks"] if "permitted" in c["requirement"].lower() and "Track" in c["requirement"])
        assert track_check["status"] == "FAIL"
        assert out["status"] in ("PASS", "INCOMPLETE")
        assert out["hard_gate_failures"] == []
        assert len(out["informational_failures"]) >= 1

    def test_compliance_track_not_permitted_hard_gate_returns_code_2(self, tmp_path: Path) -> None:
        gov = tmp_path / "gov"
        write_constitution(gov / "constitutions" / "org" / "constitution.md",
                           {"permitted_tracks": ["full"], "gate_mode": "hard"})
        fy = tmp_path / "feature.yaml"
        write_feature_yaml(fy, {"domain": "x", "service": "y", "track": "quickplan"})
        out = run(["check-compliance", "--governance-repo", str(gov), "--feature-id", "feat",
                   "--feature-yaml", str(fy), "--phase", "planning"], expect_code=2)
        assert out["status"] == "FAIL"
        assert len(out["hard_gate_failures"]) == 1

    def test_compliance_artifacts_pass_when_present(self, full_gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"domain": "platform", "service": "auth", "track": "full"})
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        for name in ["business-plan.md", "tech-plan.md", "security-review.md"]:
            (artifacts / name).write_text("content")
        out = run([
            "check-compliance", "--governance-repo", str(full_gov_repo),
            "--feature-id", "auth-feat", "--feature-yaml", str(fy),
            "--artifacts-path", str(artifacts), "--phase", "planning",
        ], expect_code=0)
        artifact_checks = [c for c in out["checks"] if "Artifact" in c.get("requirement", "")]
        for check in artifact_checks:
            assert check["status"] == "PASS"

    def test_compliance_artifacts_fail_when_missing_informational(self, full_gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"domain": "platform", "service": "auth", "track": "full"})
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        (artifacts / "business-plan.md").write_text("content")
        out = run([
            "check-compliance", "--governance-repo", str(full_gov_repo),
            "--feature-id", "auth-feat", "--feature-yaml", str(fy),
            "--artifacts-path", str(artifacts), "--phase", "planning",
        ], expect_code=0)
        # informational gate → status PASS, but failures listed
        assert out["status"] == "PASS"
        assert out["hard_gate_failures"] == []
        assert len(out["informational_failures"]) >= 2

    def test_compliance_hard_gate_artifact_missing_returns_code_2(self, tmp_path: Path) -> None:
        gov = tmp_path / "gov"
        write_constitution(gov / "constitutions" / "org" / "constitution.md",
                           {"required_artifacts": {"planning": ["biz-plan"]}, "gate_mode": "hard"})
        fy = tmp_path / "feature.yaml"
        write_feature_yaml(fy, {"domain": "x", "service": "y", "track": "quickplan"})
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        out = run([
            "check-compliance", "--governance-repo", str(gov),
            "--feature-id", "feat", "--feature-yaml", str(fy),
            "--artifacts-path", str(artifacts), "--phase", "planning",
        ], expect_code=2)
        assert out["status"] == "FAIL"
        assert len(out["hard_gate_failures"]) >= 1

    def test_compliance_incomplete_when_no_artifacts_path_and_required(self, gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"domain": "x", "service": "y", "track": "quickplan"})
        out = run([
            "check-compliance", "--governance-repo", str(gov_repo),
            "--feature-id", "feat", "--feature-yaml", str(fy), "--phase", "planning",
        ], expect_code=0)
        assert out["status"] == "INCOMPLETE"
        assert out["skipped_artifact_count"] >= 1

    def test_compliance_dry_run_flag(self, gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"domain": "x", "service": "y", "track": "quickplan"})
        out = run(["check-compliance", "--governance-repo", str(gov_repo), "--feature-id", "feat",
                   "--feature-yaml", str(fy), "--phase", "planning", "--dry-run"], expect_code=0)
        assert out.get("dry_run") is True

    def test_compliance_dev_phase_stories_artifact(self, gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"domain": "x", "service": "y", "track": "full"})
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        (artifacts / "stories.md").write_text("content")
        out = run([
            "check-compliance", "--governance-repo", str(gov_repo),
            "--feature-id", "feat", "--feature-yaml", str(fy),
            "--artifacts-path", str(artifacts), "--phase", "dev",
        ], expect_code=0)
        stories_check = next(c for c in out["checks"] if "stories" in c.get("requirement", ""))
        assert stories_check["status"] == "PASS"

    def test_compliance_artifact_found_as_yaml_extension(self, gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"domain": "x", "service": "y", "track": "full"})
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        (artifacts / "business-plan.yaml").write_text("content")
        (artifacts / "tech-plan.yaml").write_text("content")
        out = run([
            "check-compliance", "--governance-repo", str(gov_repo),
            "--feature-id", "feat", "--feature-yaml", str(fy),
            "--artifacts-path", str(artifacts), "--phase", "planning",
        ], expect_code=0)
        bp_check = next(c for c in out["checks"] if "business-plan" in c.get("requirement", ""))
        assert bp_check["status"] == "PASS"

    def test_compliance_artifact_found_as_bare_path(self, gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"domain": "x", "service": "y", "track": "full"})
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        (artifacts / "business-plan").write_text("content")
        (artifacts / "tech-plan").write_text("content")
        out = run([
            "check-compliance", "--governance-repo", str(gov_repo),
            "--feature-id", "feat", "--feature-yaml", str(fy),
            "--artifacts-path", str(artifacts), "--phase", "planning",
        ], expect_code=0)
        bp_check = next(c for c in out["checks"] if "business-plan" in c.get("requirement", ""))
        assert bp_check["status"] == "PASS"

    def test_compliance_default_track_quickplan(self, gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"domain": "x", "service": "y"})  # no track field
        out = run(["check-compliance", "--governance-repo", str(gov_repo), "--feature-id", "feat",
                   "--feature-yaml", str(fy), "--phase", "planning"], expect_code=0)
        assert out["track"] == "quickplan"

    def test_compliance_complete_phase_no_requirements_warning(self, gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"domain": "x", "service": "y", "track": "quickplan"})
        out = run(["check-compliance", "--governance-repo", str(gov_repo), "--feature-id", "feat",
                   "--feature-yaml", str(fy), "--phase", "complete"], expect_code=0)
        warnings = out.get("warnings", [])
        assert any(w["type"] == "no_complete_phase_requirements" for w in warnings)

    def test_compliance_enforce_review_fails_when_no_reviewers(self, tmp_path: Path) -> None:
        gov = tmp_path / "gov"
        write_constitution(gov / "constitutions" / "org" / "constitution.md",
                           {"enforce_review": True, "additional_review_participants": []})
        fy = tmp_path / "feature.yaml"
        write_feature_yaml(fy, {"domain": "x", "service": "y", "track": "quickplan"})
        out = run(["check-compliance", "--governance-repo", str(gov), "--feature-id", "feat",
                   "--feature-yaml", str(fy), "--phase", "planning"], expect_code=0)
        review_check = next((c for c in out["checks"] if "enforce_review" in c.get("requirement", "")), None)
        assert review_check is not None
        assert review_check["status"] == "FAIL"
        assert len(out["informational_failures"]) >= 1

    def test_compliance_enforce_review_passes_when_reviewers_set(self, full_gov_repo: Path, tmp_path: Path) -> None:
        fy = self._make_feature_yaml(tmp_path, {"domain": "platform", "service": "auth", "track": "full"})
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        for name in ["business-plan.md", "tech-plan.md", "security-review.md"]:
            (artifacts / name).write_text("content")
        out = run([
            "check-compliance", "--governance-repo", str(full_gov_repo),
            "--feature-id", "feat", "--feature-yaml", str(fy),
            "--artifacts-path", str(artifacts), "--phase", "planning",
        ], expect_code=0)
        review_check = next((c for c in out["checks"] if "enforce_review" in c.get("requirement", "")), None)
        if review_check:
            assert review_check["status"] == "PASS"

    def test_compliance_permits_express_for_lens_dev_new_codebase(self, tmp_path: Path) -> None:
        gov = tmp_path / "gov"
        for constitution_path in (
            gov / "constitutions" / "org" / "constitution.md",
            gov / "constitutions" / "lens-dev" / "constitution.md",
            gov / "constitutions" / "lens-dev" / "new-codebase" / "constitution.md",
        ):
            write_constitution(constitution_path, {"permitted_tracks": lens_dev_tracks()})
        fy = self._make_feature_yaml(tmp_path, {
            "domain": "lens-dev",
            "service": "new-codebase",
            "track": "express",
        })

        out = run([
            "check-compliance",
            "--governance-repo", str(gov),
            "--feature-id", "lens-dev-new-codebase-dogfood",
            "--feature-yaml", str(fy),
            "--phase", "planning",
        ], expect_code=0)

        track_check = next(c for c in out["checks"] if c["requirement"] == "Track 'express' permitted")
        assert track_check["status"] == "PASS"
        assert out["track"] == "express"
        assert "Track 'express' permitted" not in out["informational_failures"]


# ---------------------------------------------------------------------------
# Integration tests: progressive-display subcommand
# ---------------------------------------------------------------------------


class TestProgressiveDisplay:
    def test_display_no_filters(self, gov_repo: Path) -> None:
        out = run(["progressive-display", "--governance-repo", str(gov_repo), "--domain", "x", "--service", "y"])
        assert "gate_mode" in out
        assert "additional_review_participants" in out
        assert "enforce_stories" in out
        assert "enforce_review" in out
        assert "required_artifacts_for_phase" not in out
        assert "track_permitted" not in out

    def test_display_full_constitution_available_true_when_org_loaded(self, gov_repo: Path) -> None:
        out = run(["progressive-display", "--governance-repo", str(gov_repo), "--domain", "x", "--service", "y"])
        assert out["full_constitution_available"] is True

    def test_display_full_constitution_available_false_when_org_missing(self, tmp_path: Path) -> None:
        # No org constitution — should fail (org is required) so this tests error propagation
        out = run(["progressive-display", "--governance-repo", str(tmp_path), "--domain", "x", "--service", "y"], expect_code=1)
        assert "error" in out

    def test_display_with_phase(self, full_gov_repo: Path) -> None:
        out = run(["progressive-display", "--governance-repo", str(full_gov_repo), "--domain", "platform", "--service", "auth", "--phase", "planning"])
        assert "required_artifacts_for_phase" in out
        assert "security-review" in out["required_artifacts_for_phase"]

    def test_display_with_track_permitted(self, full_gov_repo: Path) -> None:
        out = run(["progressive-display", "--governance-repo", str(full_gov_repo), "--domain", "platform", "--service", "auth", "--track", "full"])
        assert out["track_permitted"] is True
        assert "permitted_tracks" in out

    def test_display_with_track_not_permitted(self, full_gov_repo: Path) -> None:
        out = run(["progressive-display", "--governance-repo", str(full_gov_repo), "--domain", "platform", "--service", "auth", "--track", "hotfix"])
        assert out["track_permitted"] is False

    def test_display_both_phase_and_track(self, full_gov_repo: Path) -> None:
        out = run(["progressive-display", "--governance-repo", str(full_gov_repo), "--domain", "platform", "--service", "auth", "--phase", "planning", "--track", "quickplan"])
        assert "required_artifacts_for_phase" in out
        assert "track_permitted" in out

    def test_display_levels_loaded_reported(self, full_gov_repo: Path) -> None:
        out = run(["progressive-display", "--governance-repo", str(full_gov_repo), "--domain", "platform", "--service", "auth"])
        assert set(out["levels_loaded"]) == {"org", "domain", "service"}

    def test_display_dry_run_flag(self, gov_repo: Path) -> None:
        out = run(["progressive-display", "--governance-repo", str(gov_repo), "--domain", "x", "--service", "y", "--dry-run"])
        assert out.get("dry_run") is True

    def test_display_missing_constitutions_dir_propagates_error(self, tmp_path: Path) -> None:
        out = run(["progressive-display", "--governance-repo", str(tmp_path), "--domain", "x", "--service", "y"], expect_code=1)
        assert "error" in out

    def test_display_with_repo_level(self, full_gov_repo: Path) -> None:
        repo_path = full_gov_repo / "constitutions" / "platform" / "auth" / "my-repo" / "constitution.md"
        write_constitution(repo_path, {"gate_mode": "hard"})
        out = run(["progressive-display", "--governance-repo", str(full_gov_repo), "--domain", "platform", "--service", "auth", "--repo", "my-repo"])
        assert out["gate_mode"] == "hard"
        assert "repo" in out["levels_loaded"]

    def test_display_reviewers_accumulated_across_levels(self, full_gov_repo: Path) -> None:
        service_extra = full_gov_repo / "constitutions" / "platform" / "auth" / "constitution.md"
        write_constitution(service_extra, {
            "permitted_tracks": ["full", "quickplan"],
            "required_artifacts": {"planning": ["security-review"]},
            "additional_review_participants": ["auth-team"],
        })
        out = run(["progressive-display", "--governance-repo", str(full_gov_repo), "--domain", "platform", "--service", "auth"])
        reviewers = out["additional_review_participants"]
        assert "security-team" in reviewers
        assert "auth-team" in reviewers

    def test_display_enforce_stories_in_output(self, gov_repo: Path) -> None:
        out = run(["progressive-display", "--governance-repo", str(gov_repo), "--domain", "x", "--service", "y"])
        assert "enforce_stories" in out
        assert isinstance(out["enforce_stories"], bool)

    def test_display_enforce_review_in_output(self, gov_repo: Path) -> None:
        out = run(["progressive-display", "--governance-repo", str(gov_repo), "--domain", "x", "--service", "y"])
        assert "enforce_review" in out
        assert isinstance(out["enforce_review"], bool)

    def test_display_express_track_for_lens_dev_new_codebase(self, tmp_path: Path) -> None:
        for constitution_path in (
            tmp_path / "constitutions" / "org" / "constitution.md",
            tmp_path / "constitutions" / "lens-dev" / "constitution.md",
            tmp_path / "constitutions" / "lens-dev" / "new-codebase" / "constitution.md",
        ):
            write_constitution(constitution_path, {"permitted_tracks": lens_dev_tracks()})

        out = run([
            "progressive-display",
            "--governance-repo", str(tmp_path),
            "--domain", "lens-dev",
            "--service", "new-codebase",
            "--track", "express",
        ])

        assert out["track_permitted"] is True
        assert "express" in out["permitted_tracks"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
