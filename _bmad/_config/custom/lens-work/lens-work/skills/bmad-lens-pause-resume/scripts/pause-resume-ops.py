#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Pause/resume operations — pause and resume features with state preservation.

Pausing stores the current phase in paused_from and records a required reason.
Resuming restores the pre-pause phase and clears all pause state.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml


SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def validate_identifier(value: str, field_name: str) -> str | None:
    """Validate that a path-constructing identifier is safe. Returns error message or None."""
    if not SAFE_ID_PATTERN.match(value):
        return (
            f"Invalid {field_name}: '{value}'. "
            f"Must match [a-z0-9][a-z0-9._-]{{0,63}} (lowercase alphanumeric, dots, hyphens, underscores)."
        )
    return None


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_feature_path(governance_repo: str, domain: str, service: str, feature_id: str) -> Path:
    """Compute the feature.yaml file path."""
    return Path(governance_repo) / "features" / domain / service / feature_id / "feature.yaml"


def find_feature(governance_repo: str, feature_id: str, domain: str | None, service: str | None) -> Path | None:
    """Find a feature.yaml by featureId.

    If domain and service are provided, look up the direct path first.
    Falls back to a recursive search across all domains/services.
    """
    if domain and service:
        direct = get_feature_path(governance_repo, domain, service, feature_id)
        if direct.exists():
            return direct

    features_dir = Path(governance_repo) / "features"
    if not features_dir.exists():
        return None
    for yaml_file in features_dir.rglob("feature.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if data and data.get("featureId") == feature_id:
                return yaml_file
        except (yaml.YAMLError, OSError) as e:
            print(f"Warning: Cannot read {yaml_file}: {e}", file=sys.stderr)
            continue
    return None


def load_feature_yaml(path: Path) -> tuple[dict, str | None]:
    """Load and parse a feature.yaml. Returns (data, error_message)."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return {}, f"feature.yaml at {path} is not a YAML mapping"
        return data, None
    except (yaml.YAMLError, OSError) as e:
        return {}, f"Failed to read feature.yaml: {e}"


def atomic_write_yaml(path: Path, data: dict) -> None:
    """Write YAML atomically via temp file + rename to prevent corruption."""
    dir_path = path.parent
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        os.replace(tmp_path, str(path))
    except Exception:
        os.unlink(tmp_path)
        raise


def cmd_pause(args: argparse.Namespace) -> dict:
    """Mark a feature as paused, preserving its current phase."""
    for field_name, value in [("feature-id", args.feature_id), ("domain", args.domain), ("service", args.service)]:
        err = validate_identifier(value, field_name)
        if err:
            return {"status": "fail", "error": err}

    reason = (args.reason or "").strip()
    if not reason:
        return {"status": "fail", "error": "Pause reason is required"}

    feature_path = find_feature(args.governance_repo, args.feature_id, args.domain, args.service)
    if not feature_path:
        return {"status": "fail", "error": f"Feature not found: {args.feature_id}"}

    data, err = load_feature_yaml(feature_path)
    if err:
        return {"status": "fail", "error": err}

    current_phase = data.get("phase", "")
    if current_phase == "paused":
        return {"status": "fail", "error": "Feature is already paused"}

    timestamp = now_iso()
    paused_from = current_phase

    if not args.dry_run:
        data["phase"] = "paused"
        data["paused_from"] = paused_from
        data["pause_reason"] = reason
        data["paused_at"] = timestamp
        data["updated_at"] = timestamp
        try:
            atomic_write_yaml(feature_path, data)
        except OSError as e:
            return {"status": "fail", "error": f"Failed to write feature.yaml: {e}"}

    return {
        "status": "pass",
        "feature_id": args.feature_id,
        "paused_from": paused_from,
        "reason": reason,
        "paused_at": timestamp,
        "dry_run": args.dry_run,
    }


def cmd_resume(args: argparse.Namespace) -> dict:
    """Resume a paused feature, restoring its pre-pause phase."""
    for field_name, value in [("feature-id", args.feature_id), ("domain", args.domain), ("service", args.service)]:
        err = validate_identifier(value, field_name)
        if err:
            return {"status": "fail", "error": err}

    feature_path = find_feature(args.governance_repo, args.feature_id, args.domain, args.service)
    if not feature_path:
        return {"status": "fail", "error": f"Feature not found: {args.feature_id}"}

    data, err = load_feature_yaml(feature_path)
    if err:
        return {"status": "fail", "error": err}

    current_phase = data.get("phase", "")
    if current_phase != "paused":
        return {"status": "fail", "error": "Feature is not paused"}

    paused_from = data.get("paused_from", "")
    if not paused_from:
        return {"status": "fail", "error": "No paused_from phase to restore"}

    was_paused_since = data.get("paused_at", "")
    timestamp = now_iso()

    if not args.dry_run:
        data["phase"] = paused_from
        data.pop("paused_from", None)
        data.pop("pause_reason", None)
        data.pop("paused_at", None)
        data["updated_at"] = timestamp
        try:
            atomic_write_yaml(feature_path, data)
        except OSError as e:
            return {"status": "fail", "error": f"Failed to write feature.yaml: {e}"}

    return {
        "status": "pass",
        "feature_id": args.feature_id,
        "resumed_to_phase": paused_from,
        "was_paused_since": was_paused_since,
        "dry_run": args.dry_run,
    }


def cmd_status(args: argparse.Namespace) -> dict:
    """Get pause/resume status for a feature."""
    for field_name, value in [("feature-id", args.feature_id), ("domain", args.domain), ("service", args.service)]:
        err = validate_identifier(value, field_name)
        if err:
            return {"status": "fail", "error": err}

    feature_path = find_feature(args.governance_repo, args.feature_id, args.domain, args.service)
    if not feature_path:
        return {"status": "fail", "error": f"Feature not found: {args.feature_id}"}

    data, err = load_feature_yaml(feature_path)
    if err:
        return {"status": "fail", "error": err}

    phase = data.get("phase", "")
    is_paused = phase == "paused"

    return {
        "status": "pass",
        "feature_id": args.feature_id,
        "phase": phase,
        "paused": is_paused,
        "paused_from": data.get("paused_from", "") if is_paused else "",
        "pause_reason": data.get("pause_reason", "") if is_paused else "",
        "paused_at": data.get("paused_at", "") if is_paused else "",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pause/resume operations — pause and resume features with state preservation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s pause --governance-repo /path/to/repo --feature-id auth-login \\
    --domain platform --service identity --reason "Blocked on upstream API"

  %(prog)s resume --governance-repo /path/to/repo --feature-id auth-login \\
    --domain platform --service identity

  %(prog)s status --governance-repo /path/to/repo --feature-id auth-login \\
    --domain platform --service identity
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Pause
    pause_p = subparsers.add_parser("pause", help="Mark a feature as paused")
    pause_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    pause_p.add_argument("--feature-id", required=True, help="Feature identifier")
    pause_p.add_argument("--domain", required=True, help="Domain name")
    pause_p.add_argument("--service", required=True, help="Service name")
    pause_p.add_argument("--reason", required=True, help="Required reason for pausing")
    pause_p.add_argument("--dry-run", action="store_true", help="Preview without making changes")

    # Resume
    resume_p = subparsers.add_parser("resume", help="Resume a paused feature")
    resume_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    resume_p.add_argument("--feature-id", required=True, help="Feature identifier")
    resume_p.add_argument("--domain", required=True, help="Domain name")
    resume_p.add_argument("--service", required=True, help="Service name")
    resume_p.add_argument("--dry-run", action="store_true", help="Preview without making changes")

    # Status
    status_p = subparsers.add_parser("status", help="Get pause/resume status for a feature")
    status_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    status_p.add_argument("--feature-id", required=True, help="Feature identifier")
    status_p.add_argument("--domain", required=True, help="Domain name")
    status_p.add_argument("--service", required=True, help="Service name")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "pause": cmd_pause,
        "resume": cmd_resume,
        "status": cmd_status,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()

    status = result.get("status", "fail")
    exit_code = 0 if status in ("pass", "warning") else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
