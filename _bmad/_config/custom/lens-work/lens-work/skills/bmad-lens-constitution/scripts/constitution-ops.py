#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
constitution-ops.py — Resolve and evaluate governance constitutions.

Subcommands:
  resolve            Merge the 4-level constitution hierarchy for a scope
  check-compliance   Validate a feature against its resolved constitution
  progressive-display  Return context-filtered rules for current phase/track

All subcommands write JSON to stdout.
Exit codes: 0=success, 1=error, 2=compliance hard-gate failure.
"""

import argparse
import copy
import json
import re
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TRACKS = {"quickplan", "full", "hotfix", "tech-change"}
VALID_PHASES = {"planning", "dev", "complete"}
VALID_GATE_MODES = {"informational", "hard"}
KNOWN_CONSTITUTION_KEYS = frozenset({
    "permitted_tracks", "required_artifacts", "gate_mode",
    "additional_review_participants", "enforce_stories", "enforce_review",
})

# Slug: alphanumeric, hyphens, underscores; must start with alphanumeric
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

# Frontmatter delimiter — must be on its own line to avoid false splits on
# `---` embedded inside YAML values
_FM_DELIM = re.compile(r"^---\s*$", re.MULTILINE)

DEFAULTS: dict = {
    "permitted_tracks": ["quickplan", "full", "hotfix", "tech-change"],
    "required_artifacts": {
        "planning": ["business-plan", "tech-plan"],
        "dev": ["stories"],
    },
    "gate_mode": "informational",
    "additional_review_participants": [],
    "enforce_stories": False,
    "enforce_review": False,
}

# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------


def _validate_slug(value: str, name: str) -> tuple[dict | None, int]:
    """Validate a domain/service/repo slug.  Returns (error_dict, code) on failure, (None, 0) on ok."""
    if not value or not value.strip():
        return {"error": "invalid_slug", "field": name,
                "detail": f"'{name}' must not be empty"}, 1
    if not _SLUG_RE.match(value):
        return {"error": "invalid_slug", "field": name,
                "detail": f"'{name}' contains invalid characters — use only alphanumeric, hyphens, underscores",
                "value": value}, 1
    return None, 0


def _assert_within(candidate: Path, base: Path) -> bool:
    """Return True if candidate resolves to a path inside base (path traversal guard)."""
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Constitution loading & merging
# ---------------------------------------------------------------------------


def load_constitution(path: Path) -> dict:
    """Parse YAML frontmatter from a constitution.md file.

    Returns {} if the file does not exist or has no frontmatter.
    Returns {"_parse_error": str(path)} on YAML parse failure.
    Includes {"_unknown_keys": [...]} alongside parsed data when unknown keys are found.
    """
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    # Use regex split so `---` embedded in YAML values is not treated as a delimiter
    parts = _FM_DELIM.split(text, maxsplit=2)
    # Valid frontmatter: ["", yaml_body, markdown_body]  (first segment must be empty)
    if len(parts) < 3 or parts[0].strip():
        return {}

    try:
        data = yaml.safe_load(parts[1])
        if not isinstance(data, dict):
            return {}
    except yaml.YAMLError:
        return {"_parse_error": str(path)}

    unknown = set(data.keys()) - KNOWN_CONSTITUTION_KEYS
    if unknown:
        data["_unknown_keys"] = sorted(unknown)

    return data


def merge_constitutions(levels: list[dict]) -> tuple[dict, list[dict]]:
    """Merge a list of constitution dicts additively (org first, repo last).

    Returns (merged_result, warnings).

    Merge rules:
      permitted_tracks          — intersection (lower levels restrict)
      required_artifacts        — union per phase (lower levels add)
      gate_mode                 — strongest wins (hard beats informational)
      additional_review_participants — union
      enforce_stories / enforce_review — strongest wins (true beats false)
    """
    result = copy.deepcopy(DEFAULTS)
    warnings: list[dict] = []

    for level in levels:
        if not level:
            continue

        if "permitted_tracks" in level:
            incoming = level["permitted_tracks"]
            if isinstance(incoming, list):
                unknown_tracks = [t for t in incoming if t not in VALID_TRACKS]
                if unknown_tracks:
                    warnings.append({"type": "unknown_tracks",
                                     "detail": f"Unknown track values ignored: {unknown_tracks}"})
                result["permitted_tracks"] = [
                    t for t in result["permitted_tracks"] if t in incoming
                ]

        if "required_artifacts" in level:
            incoming = level["required_artifacts"]
            if isinstance(incoming, dict):
                for phase, artifacts in incoming.items():
                    if not isinstance(artifacts, list):
                        continue
                    if phase not in result["required_artifacts"]:
                        result["required_artifacts"][phase] = []
                    for artifact in artifacts:
                        if artifact not in result["required_artifacts"][phase]:
                            result["required_artifacts"][phase].append(artifact)

        if "gate_mode" in level:
            mode = level["gate_mode"]
            if mode == "hard":
                result["gate_mode"] = "hard"
            elif mode not in VALID_GATE_MODES:
                warnings.append({"type": "unknown_gate_mode",
                                  "detail": f"Unknown gate_mode '{mode}' ignored — must be 'informational' or 'hard'"})

        if "additional_review_participants" in level:
            incoming = level["additional_review_participants"]
            if isinstance(incoming, list):
                for participant in incoming:
                    if participant not in result["additional_review_participants"]:
                        result["additional_review_participants"].append(participant)

        # enforce_stories / enforce_review: strongest wins (true beats false)
        if "enforce_stories" in level:
            if bool(level["enforce_stories"]):
                result["enforce_stories"] = True

        if "enforce_review" in level:
            if bool(level["enforce_review"]):
                result["enforce_review"] = True

        # Report unknown keys found in this level
        if "_unknown_keys" in level:
            warnings.append({"type": "unknown_constitution_keys",
                              "detail": f"Unknown keys ignored: {level['_unknown_keys']}"})

    # Ensure enforce_stories is reflected in required_artifacts for dev
    if result["enforce_stories"]:
        if "dev" not in result["required_artifacts"]:
            result["required_artifacts"]["dev"] = []
        if "stories" not in result["required_artifacts"]["dev"]:
            result["required_artifacts"]["dev"].append("stories")

    # Warn on empty permitted_tracks intersection (governance misconfiguration)
    if not result["permitted_tracks"]:
        warnings.append({"type": "empty_permitted_tracks",
                          "detail": "No tracks remain after intersection — probable governance misconfiguration"})

    return result, warnings


# ---------------------------------------------------------------------------
# Subcommand: resolve
# ---------------------------------------------------------------------------


def cmd_resolve(args: argparse.Namespace) -> tuple[dict, int]:
    """Resolve the effective constitution for a domain/service scope."""
    # Validate slugs to prevent path traversal
    for slug_name, slug_val in [("domain", args.domain), ("service", args.service)]:
        err, code = _validate_slug(slug_val, slug_name)
        if err:
            return err, code
    if getattr(args, "repo", None):
        err, code = _validate_slug(args.repo, "repo")
        if err:
            return err, code

    gov_repo = Path(args.governance_repo)
    constitutions_path = gov_repo / "constitutions"

    if not constitutions_path.exists():
        return {
            "error": "constitutions_dir_not_found",
            "path": str(constitutions_path),
            "detail": "Governance repo does not contain a 'constitutions/' subdirectory",
        }, 1

    # Build the ordered level list (org first)
    level_specs: list[tuple[str, Path]] = [
        ("org", constitutions_path / "org" / "constitution.md"),
        ("domain", constitutions_path / args.domain / "constitution.md"),
        ("service", constitutions_path / args.domain / args.service / "constitution.md"),
    ]
    if getattr(args, "repo", None):
        level_specs.append((
            "repo",
            constitutions_path / args.domain / args.service / args.repo / "constitution.md",
        ))

    # Path traversal guard — validate each level path stays inside constitutions/
    for level_name, path in level_specs:
        if not _assert_within(path, constitutions_path):
            return {"error": "path_traversal_detected",
                    "level": level_name,
                    "detail": "Computed path escapes the constitutions/ directory"}, 1

    levels_loaded: list[str] = []
    level_data: list[dict] = []
    parse_errors: list[dict] = []

    for level_name, path in level_specs:
        data = load_constitution(path)
        if "_parse_error" in data:
            # Org parse error is fatal — governance cannot be resolved without it
            if level_name == "org":
                return {
                    "error": "org_constitution_parse_error",
                    "path": str(path),
                    "detail": "org/constitution.md has invalid YAML frontmatter — fix it to restore governance",
                }, 1
            parse_errors.append({"level": level_name, "path": str(path)})
            data = {}
        if path.exists():
            levels_loaded.append(level_name)
        level_data.append(data)

    if "org" not in levels_loaded:
        return {
            "error": "org_constitution_missing",
            "path": str(constitutions_path / "org" / "constitution.md"),
            "detail": "org/constitution.md is required — create it to define org-level defaults",
        }, 1

    merged, merge_warnings = merge_constitutions(level_data)

    all_warnings: list[dict] = []
    if parse_errors:
        all_warnings.extend({"type": "parse_error", **e} for e in parse_errors)
    all_warnings.extend(merge_warnings)

    result: dict = {
        "domain": args.domain,
        "service": args.service,
        "repo": getattr(args, "repo", None) or None,
        "levels_loaded": levels_loaded,
        "resolved_constitution": merged,
    }
    if all_warnings:
        result["warnings"] = all_warnings
    if getattr(args, "dry_run", False):
        result["dry_run"] = True

    return result, 0


# ---------------------------------------------------------------------------
# Subcommand: check-compliance
# ---------------------------------------------------------------------------


def cmd_check_compliance(args: argparse.Namespace) -> tuple[dict, int]:
    """Validate a feature against its resolved constitution."""
    feature_yaml_path = Path(args.feature_yaml)
    if not feature_yaml_path.exists():
        return {"error": "feature_yaml_not_found", "path": str(feature_yaml_path)}, 1

    try:
        with open(feature_yaml_path, encoding="utf-8") as fh:
            feature_data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        return {"error": "feature_yaml_parse_error", "detail": str(exc)}, 1

    domain = feature_data.get("domain")
    service = feature_data.get("service")
    track = feature_data.get("track", "quickplan")

    if not domain or not service:
        return {"error": "feature_yaml_missing_fields",
                "detail": "feature.yaml must have 'domain' and 'service' fields"}, 1

    # Validate domain/service from feature.yaml to prevent path traversal
    for slug_name, slug_val in [("domain", domain), ("service", service)]:
        err, code = _validate_slug(slug_val, slug_name)
        if err:
            return err, code

    # Resolve the constitution for this scope
    class _ResolveArgs:
        pass

    rargs = _ResolveArgs()
    rargs.governance_repo = args.governance_repo
    rargs.domain = domain
    rargs.service = service
    rargs.repo = getattr(args, "repo", None)
    rargs.dry_run = False

    resolved, code = cmd_resolve(rargs)
    if code != 0:
        return resolved, code

    constitution = resolved["resolved_constitution"]
    artifacts_path = Path(args.artifacts_path) if getattr(args, "artifacts_path", None) else None

    checks: list[dict] = []
    hard_failures: list[str] = []
    informational_failures: list[str] = []

    # ---- Check: track is permitted ----------------------------------------
    permitted = constitution.get("permitted_tracks", [])
    gate = constitution.get("gate_mode", "informational")
    req_label = f"Track '{track}' permitted"

    if track in permitted:
        checks.append({"requirement": req_label, "status": "PASS",
                        "detail": "Track permitted by constitution"})
    else:
        checks.append({"requirement": req_label, "status": "FAIL", "gate": gate,
                        "detail": f"Track '{track}' not in permitted_tracks: {permitted}"})
        (hard_failures if gate == "hard" else informational_failures).append(req_label)

    # ---- Check: required artifacts for phase --------------------------------
    phase = args.phase
    required_artifacts = constitution.get("required_artifacts", {}).get(phase, [])
    skipped_artifact_count = 0

    for artifact in required_artifacts:
        req_label = f"Artifact '{artifact}' present for phase '{phase}'"
        if artifacts_path is None:
            checks.append({"requirement": req_label, "status": "SKIP",
                            "detail": "No --artifacts-path provided — artifact check skipped"})
            skipped_artifact_count += 1
            continue

        candidate_paths = [
            artifacts_path / f"{artifact}.md",
            artifacts_path / f"{artifact}.yaml",
            artifacts_path / artifact,
        ]
        found = any(p.exists() for p in candidate_paths)
        status = "PASS" if found else "FAIL"
        check: dict = {
            "requirement": req_label,
            "status": status,
            "gate": gate,
            "detail": f"{'Found' if found else 'Missing'}: {artifacts_path / (artifact + '.md')}",
        }
        checks.append(check)
        if status == "FAIL":
            (hard_failures if gate == "hard" else informational_failures).append(req_label)

    # ---- Check: enforce_review (reviewers must be configured) ---------------
    if constitution.get("enforce_review"):
        participants = constitution.get("additional_review_participants", [])
        req_label = "Reviewers configured (enforce_review=true)"
        if participants:
            checks.append({"requirement": req_label, "status": "PASS",
                            "detail": f"Reviewers: {', '.join(str(p) for p in participants)}"})
        else:
            checks.append({"requirement": req_label, "status": "FAIL", "gate": gate,
                            "detail": "enforce_review=true but additional_review_participants is empty in constitution"})
            (hard_failures if gate == "hard" else informational_failures).append(req_label)

    # Determine overall status
    if skipped_artifact_count > 0 and not hard_failures:
        overall_status = "INCOMPLETE"
        exit_code = 0
    elif hard_failures:
        overall_status = "FAIL"
        exit_code = 2
    else:
        overall_status = "PASS"
        exit_code = 0

    result: dict = {
        "feature_id": args.feature_id,
        "domain": domain,
        "service": service,
        "track": track,
        "phase": phase,
        "status": overall_status,
        "checks": checks,
        "hard_gate_failures": hard_failures,
        "informational_failures": informational_failures,
    }
    if skipped_artifact_count:
        result["skipped_artifact_count"] = skipped_artifact_count

    # Warn when no completion criteria are defined for the complete phase
    if phase == "complete" and not required_artifacts:
        result.setdefault("warnings", []).append({
            "type": "no_complete_phase_requirements",
            "detail": "No required_artifacts defined for 'complete' phase — define them in a constitution to enable meaningful completion gates",
        })

    if getattr(args, "dry_run", False):
        result["dry_run"] = True

    return result, exit_code


# ---------------------------------------------------------------------------
# Subcommand: progressive-display
# ---------------------------------------------------------------------------


def cmd_progressive_display(args: argparse.Namespace) -> tuple[dict, int]:
    """Return a context-filtered view of the resolved constitution."""

    class _ResolveArgs:
        pass

    rargs = _ResolveArgs()
    rargs.governance_repo = args.governance_repo
    rargs.domain = args.domain
    rargs.service = args.service
    rargs.repo = getattr(args, "repo", None)
    rargs.dry_run = False

    resolved, code = cmd_resolve(rargs)
    if code != 0:
        return resolved, code

    constitution = resolved["resolved_constitution"]
    phase = getattr(args, "phase", None)
    track = getattr(args, "track", None)

    display: dict = {
        "domain": args.domain,
        "service": args.service,
        "levels_loaded": resolved["levels_loaded"],
        "gate_mode": constitution.get("gate_mode", "informational"),
        "additional_review_participants": constitution.get("additional_review_participants", []),
        "enforce_stories": constitution.get("enforce_stories", False),
        "enforce_review": constitution.get("enforce_review", False),
        # full_constitution_available: true only if org level was loaded successfully
        "full_constitution_available": "org" in resolved["levels_loaded"],
    }

    if phase:
        display["required_artifacts_for_phase"] = (
            constitution.get("required_artifacts", {}).get(phase, [])
        )

    if track:
        permitted = constitution.get("permitted_tracks", [])
        display["track_permitted"] = track in permitted
        display["permitted_tracks"] = permitted

    if "warnings" in resolved:
        display["warnings"] = resolved["warnings"]
    if getattr(args, "dry_run", False):
        display["dry_run"] = True

    return display, 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Governance constitution operations for Lens",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # ---- resolve ------------------------------------------------------------
    p_resolve = sub.add_parser("resolve", help="Resolve effective constitution for a scope")
    p_resolve.add_argument("--governance-repo", required=True, help="Path to governance repo")
    p_resolve.add_argument("--domain", required=True)
    p_resolve.add_argument("--service", required=True)
    p_resolve.add_argument("--repo", default=None)
    p_resolve.add_argument("--dry-run", action="store_true")

    # ---- check-compliance ---------------------------------------------------
    p_check = sub.add_parser("check-compliance", help="Validate a feature against its constitution")
    p_check.add_argument("--governance-repo", required=True)
    p_check.add_argument("--feature-id", required=True)
    p_check.add_argument("--feature-yaml", required=True, help="Path to feature.yaml (local)")
    p_check.add_argument("--artifacts-path", default=None,
                          help="Path to feature artifacts dir (local); omit to skip artifact checks")
    p_check.add_argument("--phase", required=True, choices=list(VALID_PHASES),
                          help="Phase to check artifacts for")
    p_check.add_argument("--repo", default=None)
    p_check.add_argument("--dry-run", action="store_true")

    # ---- progressive-display ------------------------------------------------
    p_display = sub.add_parser("progressive-display",
                                 help="Return context-filtered governance rules")
    p_display.add_argument("--governance-repo", required=True)
    p_display.add_argument("--domain", required=True)
    p_display.add_argument("--service", required=True)
    p_display.add_argument("--repo", default=None)
    p_display.add_argument("--phase", choices=list(VALID_PHASES), default=None)
    p_display.add_argument("--track", choices=list(VALID_TRACKS), default=None)
    p_display.add_argument("--dry-run", action="store_true")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "resolve": cmd_resolve,
        "check-compliance": cmd_check_compliance,
        "progressive-display": cmd_progressive_display,
    }

    handler = dispatch.get(args.subcommand)
    if handler is None:
        print(json.dumps({"error": "unknown_subcommand", "subcommand": args.subcommand}))
        return 1

    result, code = handler(args)
    print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
