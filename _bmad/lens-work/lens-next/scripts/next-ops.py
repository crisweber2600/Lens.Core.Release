#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
next-ops.py — Deterministic routing engine for the lens-next skill.

Reads feature.yaml and lifecycle.yaml to produce a structured JSON routing
recommendation. Produces no side effects: no file writes, no git operations.

Usage:
    uv run next-ops.py suggest --feature-id <id> [--governance-repo <path>] [--control-repo <path>]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------

def _find_workspace_root(start: Path) -> Path:
    """Walk up from start to find the workspace root (directory with bmadconfig.yaml
    inside lens.core/_bmad/lens-work/ or containing a TargetProjects/ directory)."""
    candidate = start.resolve()
    for _ in range(20):
        if (candidate / "TargetProjects").is_dir():
            return candidate
        config_check = candidate / "lens.core" / "_bmad" / "lens-work" / "bmadconfig.yaml"
        if config_check.exists():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return start.resolve()


def _load_bmadconfig(workspace_root: Path) -> dict:
    candidates = [
        workspace_root / "_bmad" / "lens-work" / "bmadconfig.yaml",
        workspace_root / "lens.core" / "_bmad" / "lens-work" / "bmadconfig.yaml",
    ]
    for config_path in candidates:
        if config_path.exists():
            with open(config_path, encoding="utf-8") as fh:
                config = yaml.safe_load(fh) or {}
            return config if isinstance(config, dict) else {}
    return {}


def _resolve_governance_repo(workspace_root: Path, override: str | None) -> Path:
    if override:
        return Path(override).resolve()
    config = _load_bmadconfig(workspace_root)
    raw = config.get("governance_repo_path")
    if raw is None or not str(raw).strip():
        raise ValueError(
            "config_missing: governance_repo_path is not set in bmadconfig.yaml "
            "and no --governance-repo override was provided"
        )
    raw = str(raw).replace("{project-root}", str(workspace_root))
    return Path(raw).resolve()


def _resolve_lifecycle_yaml(workspace_root: Path, override: str | None = None) -> Path:
    if override:
        return Path(override).resolve()
    config = _load_bmadconfig(workspace_root)
    release_root = config.get("release_repo_root", "lens.core")
    # release_repo_root is relative to workspace root
    lifecycle_path = workspace_root / release_root / "_bmad" / "lens-work" / "lifecycle.yaml"
    if lifecycle_path.exists():
        return lifecycle_path
    # Fallback: search next to this script (installed module)
    script_dir = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = script_dir / "lifecycle.yaml"
        if candidate.exists():
            return candidate
        candidate2 = script_dir / "_bmad" / "lens-work" / "lifecycle.yaml"
        if candidate2.exists():
            return candidate2
        script_dir = script_dir.parent
    return lifecycle_path  # return even if missing; caller handles missing


_FEATURE_YAML_INDEX_CACHE: dict[Path, dict[str, Path]] = {}


def _build_feature_yaml_index(features_root: Path) -> dict[str, Path]:
    """Build a feature_id → feature.yaml path index for a features root."""
    index: dict[str, Path] = {}
    for candidate in features_root.rglob("feature.yaml"):
        index.setdefault(candidate.parent.name, candidate)
    return index


def _find_feature_yaml(feature_id: str, governance_repo: Path) -> Path | None:
    """Locate feature.yaml for a given feature_id inside the governance repo."""
    features_root = (governance_repo / "features").resolve()
    if not features_root.is_dir():
        return None
    if features_root not in _FEATURE_YAML_INDEX_CACHE:
        _FEATURE_YAML_INDEX_CACHE[features_root] = _build_feature_yaml_index(features_root)
    return _FEATURE_YAML_INDEX_CACHE[features_root].get(feature_id)


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------

# Phases that indicate a dependency feature is sufficiently complete to unblock dependents.
_DEPENDENCY_COMPLETE_PHASES = frozenset(("dev-complete", "complete", "finalizeplan-complete"))
_FEATURE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")


def _empty_result(phase: str = "", track: str = "") -> dict:
    return {
        "status": "",
        "recommendation": "",
        "blockers": [],
        "warnings": [],
        "phase": phase,
        "track": track,
        "error": "",
    }


def _fail_result(message: str, phase: str = "", track: str = "",
                 warnings: list[str] | None = None) -> dict:
    result = _empty_result(phase, track)
    result["status"] = "fail"
    result["error"] = message
    if warnings is not None:
        result["warnings"] = warnings
    return result


def _normalize_warnings(raw_warnings: object) -> tuple[list[str], str | None]:
    if raw_warnings is None:
        return [], None
    if isinstance(raw_warnings, list):
        return [str(warning) for warning in raw_warnings], None
    return [], "feature.yaml field 'warnings' must be a list when present"


def _normalize_depends_on(dependencies: object) -> tuple[list[str], str | None]:
    if dependencies is None:
        return [], None
    if not isinstance(dependencies, dict):
        return [], "feature.yaml field 'dependencies' must be a mapping when present"
    depends_on = dependencies.get("depends_on", [])
    if depends_on is None:
        return [], None
    if not isinstance(depends_on, list):
        return [], "feature.yaml field 'dependencies.depends_on' must be a list when present"
    invalid = [dep for dep in depends_on if not isinstance(dep, str) or not dep.strip()]
    if invalid:
        return [], "feature.yaml field 'dependencies.depends_on' must contain non-empty strings"
    return depends_on, None


def suggest(feature_id: str, governance_repo_override: str | None,
            control_repo_override: str | None,
            lifecycle_path_override: str | None = None) -> dict:
    workspace_root = _find_workspace_root(Path(__file__).resolve().parent)

    if not feature_id or not _FEATURE_ID_RE.fullmatch(feature_id):
        return _fail_result(
            "feature-id must be lowercase alphanumeric with optional dots, underscores, or hyphens, "
            "start and end with an alphanumeric character, and cannot be empty"
        )

    # --- Resolve governance repo ---
    try:
        governance_repo = _resolve_governance_repo(workspace_root, governance_repo_override)
    except ValueError as exc:
        return _fail_result(str(exc))

    # --- Find feature.yaml ---
    feature_yaml_path = _find_feature_yaml(feature_id, governance_repo)
    if not feature_yaml_path or not feature_yaml_path.exists():
        return _fail_result(f"feature.yaml not found for feature: {feature_id}")

    try:
        with open(feature_yaml_path, encoding="utf-8") as fh:
            feature_data = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as exc:
        return _fail_result(
            f"failed to read or parse feature.yaml for feature {feature_id}: {exc}"
        )

    if not isinstance(feature_data, dict):
        return _fail_result(f"feature.yaml for {feature_id} must be a mapping")

    phase: str = feature_data.get("phase", "")
    track: str = feature_data.get("track", "full")

    if not phase:
        return _fail_result(f"feature.yaml for {feature_id} has no 'phase' field", phase, track)

    # --- Handle paused state (M1 decision: Option A — blocker report) ---
    if phase == "paused":
        result = _empty_result(phase, track)
        result["status"] = "blocked"
        result["blockers"] = [
            "feature is paused; use the pause-resume skill or the retained recovery path"
        ]
        return result

    # --- Load lifecycle.yaml ---
    lifecycle_path = _resolve_lifecycle_yaml(workspace_root, lifecycle_path_override)
    if not lifecycle_path.exists():
        return _fail_result(f"lifecycle.yaml not found at {lifecycle_path}", phase, track)

    try:
        with open(lifecycle_path, encoding="utf-8") as fh:
            lifecycle: dict = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as exc:
        return _fail_result(
            f"Failed to read or parse lifecycle.yaml at {lifecycle_path}: {exc}",
            phase,
            track,
        )

    if not isinstance(lifecycle, dict):
        return _fail_result(f"lifecycle.yaml at {lifecycle_path} must be a mapping", phase, track)

    phases: dict = lifecycle.get("phases", {})
    tracks: dict = lifecycle.get("tracks", {})

    if not isinstance(phases, dict) or not isinstance(tracks, dict) or not phases or not tracks:
        return _fail_result(
            "lifecycle.yaml must define non-empty 'phases' and 'tracks' mappings",
            phase,
            track,
        )

    # --- Validate track ---
    if track not in tracks:
        return _fail_result(f"Unknown track: {track}", phase, track)

    # --- Normalize phase for lookup ---
    # "expressplan-complete", "preplan-complete", etc. → strip "-complete" suffix
    lookup_phase = phase
    if phase.endswith("-complete"):
        lookup_phase = phase[: -len("-complete")]

    # --- Find phase definition in lifecycle ---
    phase_def = phases.get(lookup_phase)
    if not phase_def:
        # Check if it's a track-start mismatch (missing phase for this track)
        track_def = tracks.get(track, {})
        track_phases = track_def.get("phases", [])
        start_phase = track_def.get("start_phase", "")
        if track_phases and lookup_phase not in track_phases:
            return _fail_result(
                f"Phase '{phase}' is not a valid phase for track '{track}'. "
                f"Valid phases: {track_phases}. Starting phase: {start_phase}",
                phase,
                track,
            )
        return _fail_result(f"Unknown phase: {phase}", phase, track)

    # --- Resolve auto_advance_to ---
    auto_advance: str | None = phase_def.get("auto_advance_to")
    if not auto_advance:
        return _fail_result(
            f"No auto_advance_to defined for phase '{lookup_phase}' in lifecycle.yaml",
            phase,
            track,
        )

    # --- Check blockers (feature.yaml dependencies field) ---
    blockers: list[str] = []
    # Surface any explicit warnings recorded in feature.yaml
    warnings, warnings_error = _normalize_warnings(feature_data.get("warnings", []))
    if warnings_error:
        return _fail_result(warnings_error, phase, track)

    depends_on, dependencies_error = _normalize_depends_on(feature_data.get("dependencies", {}))
    if dependencies_error:
        return _fail_result(dependencies_error, phase, track, warnings)
    for dep in depends_on:
        dep_feature_yaml = _find_feature_yaml(dep, governance_repo)
        if not dep_feature_yaml or not dep_feature_yaml.exists():
            blockers.append(f"Dependency '{dep}' feature.yaml was not found")
            continue
        try:
            with open(dep_feature_yaml, encoding="utf-8") as fh:
                dep_data = yaml.safe_load(fh) or {}
        except (OSError, yaml.YAMLError) as exc:
            return _fail_result(
                f"Invalid dependency feature.yaml for '{dep}' at '{dep_feature_yaml}': {exc}",
                phase,
                track,
                warnings,
            )
        if not isinstance(dep_data, dict):
            return _fail_result(
                f"Dependency feature.yaml for '{dep}' must be a mapping",
                phase,
                track,
                warnings,
            )
        dep_phase = dep_data.get("phase", "")
        if dep_phase not in _DEPENDENCY_COMPLETE_PHASES:
            blockers.append(
                f"Dependency '{dep}' is not yet complete (phase: {dep_phase})"
            )

    if blockers:
        result = _empty_result(phase, track)
        result["status"] = "blocked"
        result["blockers"] = blockers
        result["warnings"] = warnings
        result["recommendation"] = auto_advance
        return result

    return {
        "status": "unblocked",
        "recommendation": auto_advance,
        "blockers": [],
        "warnings": warnings,
        "phase": phase,
        "track": track,
        "error": "",
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Routing engine for the lens-next conductor."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- suggest subcommand ---
    suggest_parser = subparsers.add_parser(
        "suggest",
        help="Resolve the next recommended phase for a feature.",
    )
    suggest_parser.add_argument(
        "--feature-id",
        required=True,
        help="The feature ID to resolve (e.g. lens-dev-new-codebase-next)",
    )
    suggest_parser.add_argument(
        "--governance-repo",
        default=None,
        help="Override path to governance repo root",
    )
    suggest_parser.add_argument(
        "--control-repo",
        default=None,
        help="Override path to control repo root (unused currently but accepted for compatibility)",
    )
    suggest_parser.add_argument(
        "--lifecycle-path",
        default=None,
        help="Override path to lifecycle.yaml (primarily for testing)",
    )

    args = parser.parse_args()

    if args.command == "suggest":
        result = suggest(
            feature_id=args.feature_id,
            governance_repo_override=args.governance_repo,
            control_repo_override=args.control_repo,
            lifecycle_path_override=args.lifecycle_path,
        )
        print(json.dumps(result, indent=2))
        if result["status"] == "fail":
            sys.exit(1)


if __name__ == "__main__":
    main()
