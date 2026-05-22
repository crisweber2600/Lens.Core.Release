#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Next-action recommendation for Lens features.

Reads feature.yaml and derives the most contextually appropriate next action
based on lifecycle phase, track type, outstanding issues, and staleness flags.
"""

import argparse
from functools import lru_cache
import json
import re
import sys
from pathlib import Path

import yaml


SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
COMPLETE_SUFFIX = "-complete"
LIFECYCLE_PATH = Path(__file__).resolve().parents[3] / "lifecycle.yaml"

# Legacy track names still appear in existing feature.yaml files.
LEGACY_TRACK_ALIASES: dict[str, str] = {
    "quickplan": "feature",
}

# Next-phase gates that can be inferred from feature.yaml milestones.
# Some phases, such as businessplan and finalizeplan, are validated through phase state
# rather than a dedicated milestone field in feature.yaml.
ENTRY_MILESTONE_RULES: dict[str, tuple[str, str, str | None]] = {
    "techplan": ("businessplan", "Business plan milestone not completed", "businessplan"),
    "finalizeplan": ("techplan", "Tech plan milestone not completed", "techplan"),
    "dev": ("finalizeplan", "Finalize plan milestone not completed", "finalizeplan"),
    "complete": ("dev-complete", "Dev-complete milestone not set", None),
}


@lru_cache(maxsize=1)
def load_lifecycle() -> dict:
    """Load and cache the lifecycle contract."""
    try:
        with open(LIFECYCLE_PATH) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as exc:
        raise RuntimeError(f"Failed to read lifecycle.yaml: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Failed to read lifecycle.yaml: expected a top-level mapping")

    return data


def normalize_track(track: str, lifecycle: dict) -> str:
    """Map feature.yaml track names onto lifecycle track keys."""
    tracks = lifecycle.get("tracks") or {}
    if track in tracks:
        return track
    return LEGACY_TRACK_ALIASES.get(track, track)


def get_track_definition(track: str, lifecycle: dict) -> dict:
    """Return the lifecycle track definition, accounting for legacy aliases."""
    tracks = lifecycle.get("tracks") or {}
    return tracks.get(normalize_track(track, lifecycle), {})


def get_effective_phase(data: dict, lifecycle: dict) -> str:
    """Return the current phase, falling back to the lifecycle start phase for the track."""
    phase = (data.get("phase") or "").strip()
    if phase:
        return phase

    track_def = get_track_definition(str(data.get("track") or ""), lifecycle)
    return str(track_def.get("start_phase") or "preplan")


def build_phase_recommendation(data: dict, phase: str, lifecycle: dict) -> dict:
    """Resolve the action/command pair from lifecycle phase state."""
    phases = lifecycle.get("phases") or {}

    if phase.endswith(COMPLETE_SUFFIX):
        completed_phase = phase[: -len(COMPLETE_SUFFIX)]
        phase_meta = phases.get(completed_phase) or {}
        next_command = phase_meta.get("auto_advance_to")
        if next_command:
            next_action = str(next_command).lstrip("/")
            display_name = phase_meta.get("display_name", completed_phase.replace("-", " ").title())
            return {
                "action": next_action,
                "command": str(next_command),
                "rationale": f"{display_name} is complete — continue with {next_command}",
                "gate_phase": next_action,
            }

    phase_meta = phases.get(phase) or {}
    if phase_meta:
        display_name = phase_meta.get("display_name", phase.replace("-", " ").title())
        return {
            "action": phase,
            "command": f"/{phase}",
            "rationale": f"Feature is in {display_name} — continue the {display_name} workflow",
            "gate_phase": phase,
        }

    if phase == "dev":
        return {
            "action": "dev",
            "command": "/dev",
            "rationale": "Feature is in dev execution — continue implementation and story flow",
            "gate_phase": "dev",
        }

    if phase == "complete":
        return {
            "action": "complete",
            "command": "/complete",
            "rationale": "Feature is at lifecycle closeout — finalize retrospective, documentation, and archival",
            "gate_phase": "complete",
        }

    if phase == "paused":
        paused_from = data.get("paused_from")
        from_text = f" from {paused_from}" if paused_from else ""
        return {
            "action": "pause-resume",
            "command": "/pause-resume",
            "rationale": f"Feature is paused{from_text} — resume when ready",
            "gate_phase": "pause-resume",
        }

    return {
        "action": "help",
        "command": "/help",
        "rationale": f"Feature is in {phase} phase — review the available commands for the current lifecycle state",
        "gate_phase": "help",
    }


def apply_entry_blockers(blockers: list[str], gate_phase: str, track_def: dict, milestones: dict) -> None:
    """Add hard gates for lifecycle entry when feature.yaml exposes the needed milestone."""
    rule = ENTRY_MILESTONE_RULES.get(gate_phase)
    if not rule:
        return

    milestone_key, message, required_track_phase = rule
    track_phases = track_def.get("phases") or []
    if required_track_phase and track_phases and required_track_phase not in track_phases:
        return

    if not milestones.get(milestone_key):
        blockers.append(message)


def validate_identifier(value: str, field_name: str) -> str | None:
    """Validate that a path-constructing identifier is safe. Returns error message or None."""
    if not SAFE_ID_PATTERN.match(value):
        return (
            f"Invalid {field_name}: '{value}'. "
            f"Must match [a-z0-9][a-z0-9._-]{{0,63}} (lowercase alphanumeric, dots, hyphens, underscores)."
        )
    return None


def find_feature(governance_repo: str, feature_id: str) -> Path | None:
    """Find a feature.yaml by featureId, scanning all domains/services."""
    features_dir = Path(governance_repo) / "features"
    if not features_dir.exists():
        return None
    for yaml_file in features_dir.rglob("feature.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if data and data.get("featureId") == feature_id:
                return yaml_file
        except (yaml.YAMLError, OSError):
            continue
    return None


def find_feature_via_index(governance_repo: str, feature_id: str) -> tuple[str, str] | None:
    """Look up domain/service from feature-index.yaml. Returns (domain, service) or None."""
    index_path = Path(governance_repo) / "feature-index.yaml"
    if not index_path.exists():
        return None
    try:
        with open(index_path) as f:
            index = yaml.safe_load(f)
        if not index or "features" not in index:
            return None
        for entry in index.get("features", []):
            if (entry.get("featureId") or entry.get("id")) == feature_id:
                domain = entry.get("domain", "")
                service = entry.get("service", "")
                if domain and service:
                    return domain, service
    except (yaml.YAMLError, OSError):
        return None
    return None


def build_recommendation(data: dict, lifecycle: dict) -> tuple[str, dict]:
    """Derive the next action recommendation from feature state."""
    phase = get_effective_phase(data, lifecycle)
    track_def = get_track_definition(str(data.get("track") or ""), lifecycle)
    milestones = data.get("milestones") or {}
    context = data.get("context") or {}
    links = data.get("links") or {}

    blockers: list[str] = []
    warnings: list[str] = []

    recommendation = build_phase_recommendation(data, phase, lifecycle)
    apply_entry_blockers(blockers, recommendation["gate_phase"], track_def, milestones)

    # Stale context warning
    if context.get("stale"):
        warnings.append("context.stale — consider fetching fresh context first")

    # Open issues warning
    issues = links.get("issues") or []
    if len(issues) > 3:
        warnings.append(f"{len(issues)} open issues — consider reviewing before proceeding")

    return phase, {
        "action": recommendation["action"],
        "rationale": recommendation["rationale"],
        "command": recommendation["command"],
        "blockers": blockers,
        "warnings": warnings,
    }


def resolve_feature_path(args: argparse.Namespace) -> Path | None:
    """Resolve the feature.yaml path via direct path, index, or full scan."""
    # Direct lookup when domain + service are provided
    if args.domain and args.service:
        candidate = (
            Path(args.governance_repo) / "features" / args.domain / args.service / args.feature_id / "feature.yaml"
        )
        if candidate.exists():
            return candidate

    # Feature index lookup
    loc = find_feature_via_index(args.governance_repo, args.feature_id)
    if loc:
        domain, service = loc
        candidate = (
            Path(args.governance_repo) / "features" / domain / service / args.feature_id / "feature.yaml"
        )
        if candidate.exists():
            return candidate

    # Full scan fallback
    return find_feature(args.governance_repo, args.feature_id)


def cmd_suggest(args: argparse.Namespace) -> dict:
    """Return the next recommended action for a feature."""
    try:
        lifecycle = load_lifecycle()
    except RuntimeError as exc:
        return {"status": "fail", "error": str(exc)}

    err = validate_identifier(args.feature_id, "feature-id")
    if err:
        return {"status": "fail", "error": err}

    if args.domain:
        err = validate_identifier(args.domain, "domain")
        if err:
            return {"status": "fail", "error": err}

    if args.service:
        err = validate_identifier(args.service, "service")
        if err:
            return {"status": "fail", "error": err}

    feature_path = resolve_feature_path(args)
    if not feature_path:
        return {"status": "fail", "error": f"Feature not found: {args.feature_id}"}

    try:
        with open(feature_path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "error": f"Failed to read feature.yaml: {e}"}

    phase, recommendation = build_recommendation(data, lifecycle)

    return {
        "status": "pass",
        "featureId": data.get("featureId", args.feature_id),
        "phase": phase,
        "track": data.get("track", "quickplan"),
        "path": str(feature_path),
        "recommendation": recommendation,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Next-action recommendations for Lens features.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s suggest --governance-repo /path/to/repo --feature-id auth-login
  %(prog)s suggest --governance-repo /path/to/repo --feature-id auth-login \\
    --domain platform --service identity
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    suggest_p = subparsers.add_parser("suggest", help="Return the next recommended action")
    suggest_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    suggest_p.add_argument("--feature-id", required=True, help="Feature identifier")
    suggest_p.add_argument("--domain", default="", help="Domain name (optional, accelerates lookup)")
    suggest_p.add_argument("--service", default="", help="Service name (optional, accelerates lookup)")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "suggest": cmd_suggest,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()

    exit_code = 0 if result.get("status") in ("pass", "warning") else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
