#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Feature YAML operations — create, read, update, validate, list feature.yaml files.

The feature.yaml is the single source of truth for feature identity, lifecycle
state, organizational hierarchy, and metadata within the Lens governance repo.
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


BASE_PHASES = ["preplan", "businessplan", "techplan", "finalizeplan", "expressplan", "dev", "complete", "paused"]
COMPLETABLE_PHASES = ["preplan", "businessplan", "techplan", "finalizeplan", "expressplan"]
VALID_PHASES = BASE_PHASES + [f"{phase}-complete" for phase in COMPLETABLE_PHASES]
VALID_TRACKS = ["quickplan", "full", "feature", "hotfix", "hotfix-express", "express", "spike", "tech-change"]
VALID_PRIORITIES = ["critical", "high", "medium", "low"]
VALID_ROLES = ["lead", "contributor", "reviewer"]
VALID_VISIBILITIES = ["public", "private", "internal"]

# Sanitization pattern for path-constructing identifiers
SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

# Phase transition rules per track: from_phase -> allowed next phases
TRACK_TRANSITIONS = {
    "full": {
        "preplan": ["businessplan", "paused"],
        "businessplan": ["techplan", "paused"],
        "techplan": ["finalizeplan", "paused"],
        "finalizeplan": ["dev", "paused"],
        "dev": ["complete", "paused"],
        "paused": BASE_PHASES,
        "complete": [],
    },
    "quickplan": {
        "preplan": ["businessplan", "techplan", "finalizeplan", "dev", "paused"],
        "businessplan": ["techplan", "finalizeplan", "dev", "paused"],
        "techplan": ["finalizeplan", "dev", "paused"],
        "finalizeplan": ["dev", "paused"],
        "dev": ["complete", "paused"],
        "paused": BASE_PHASES,
        "complete": [],
    },
    "feature": {
        "preplan": ["businessplan", "paused"],
        "businessplan": ["techplan", "paused"],
        "techplan": ["finalizeplan", "paused"],
        "finalizeplan": ["dev", "paused"],
        "dev": ["complete", "paused"],
        "paused": BASE_PHASES,
        "complete": [],
    },
    "hotfix": {
        "preplan": ["dev", "paused"],
        "dev": ["complete", "paused"],
        "paused": BASE_PHASES,
        "complete": [],
    },
    "hotfix-express": {
        "preplan": ["dev", "paused"],
        "dev": ["complete", "paused"],
        "paused": BASE_PHASES,
        "complete": [],
    },
    "express": {
        "preplan": ["expressplan", "dev", "paused"],
        "expressplan": ["dev", "paused"],
        "dev": ["complete", "paused"],
        "paused": BASE_PHASES,
        "complete": [],
    },
    "spike": {
        "preplan": ["dev", "paused"],
        "dev": ["complete", "paused"],
        "paused": BASE_PHASES,
        "complete": [],
    },
    "tech-change": {
        "preplan": ["techplan", "dev", "paused"],
        "techplan": ["finalizeplan", "dev", "paused"],
        "finalizeplan": ["dev", "paused"],
        "dev": ["complete", "paused"],
        "paused": BASE_PHASES,
        "complete": [],
    },
}

# Backwards-compat aliases
PHASE_TRANSITIONS = TRACK_TRANSITIONS["full"]
QUICKPLAN_TRANSITIONS = TRACK_TRANSITIONS["quickplan"]


def validate_identifier(value: str, field_name: str) -> str | None:
    """Validate that a path-constructing identifier is safe. Returns error message or None."""
    if not SAFE_ID_PATTERN.match(value):
        return (
            f"Invalid {field_name}: '{value}'. "
            f"Must match [a-z0-9][a-z0-9._-]{{0,63}} (lowercase alphanumeric, dots, hyphens, underscores)."
        )
    return None


def get_template_path() -> Path:
    """Return path to the feature template YAML."""
    return Path(__file__).parent.parent / "assets" / "feature-template.yaml"


def get_feature_dir(governance_repo: str, domain: str, service: str, feature_id: str) -> Path:
    """Compute the feature directory path."""
    return Path(governance_repo) / "features" / domain / service / feature_id


def get_feature_path(governance_repo: str, domain: str, service: str, feature_id: str) -> Path:
    """Compute the feature.yaml file path."""
    return get_feature_dir(governance_repo, domain, service, feature_id) / "feature.yaml"


def find_feature(governance_repo: str, feature_id: str) -> Path | None:
    """Find a feature.yaml by featureId, searching all domains/services."""
    features_dir = Path(governance_repo) / "features"
    if not features_dir.exists():
        return None
    for yaml_file in features_dir.rglob("feature.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if data and data.get("featureId") == feature_id:
                return yaml_file
        except yaml.YAMLError as e:
            print(f"Warning: Unparseable YAML at {yaml_file}: {e}", file=sys.stderr)
            continue
        except OSError as e:
            print(f"Warning: Cannot read {yaml_file}: {e}", file=sys.stderr)
            continue
    return None


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


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def derive_repo_name(value: str) -> str:
    """Derive a repository name from a URL or filesystem path."""
    stripped = str(value or "").strip().rstrip("/")
    if not stripped:
        return ""
    name = stripped.rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def normalize_target_repo_entry(entry: dict | str) -> dict:
    """Normalize target repo metadata while keeping backward compatibility."""
    if isinstance(entry, str):
        entry = {"url": entry}
    if not isinstance(entry, dict):
        raise ValueError(f"target_repos entries must be mappings or strings, got {type(entry).__name__}")

    remote_url = str(entry.get("remote_url") or entry.get("url") or "").strip()
    url = str(entry.get("url") or remote_url).strip()
    local_path = str(entry.get("local_path") or entry.get("path") or "").strip()
    name = str(entry.get("name") or "").strip() or derive_repo_name(url or local_path)
    branch = str(entry.get("branch") or "").strip()
    default_branch = str(entry.get("default_branch") or "").strip()
    visibility = str(entry.get("visibility") or "").strip().lower()

    normalized: dict = {}
    if name:
        normalized["name"] = name
    if url:
        normalized["url"] = url
    if remote_url:
        normalized["remote_url"] = remote_url
    elif url:
        normalized["remote_url"] = url
    if local_path:
        normalized["local_path"] = local_path
    if branch:
        normalized["branch"] = branch
    elif "branch" in entry:
        normalized["branch"] = ""
    if default_branch:
        normalized["default_branch"] = default_branch
    if visibility:
        normalized["visibility"] = visibility
    return normalized


def normalize_target_repos(entries: list | None) -> list[dict]:
    """Normalize a target repo list, preserving list order."""
    if not entries:
        return []
    return [normalize_target_repo_entry(entry) for entry in entries]


def parse_target_repos_arg(value: str) -> list[dict]:
    """Parse the legacy comma-separated --target-repos argument into normalized entries."""
    urls = [url.strip() for url in value.split(",") if url.strip()]
    return normalize_target_repos(urls)


def get_transitions_for_track(track: str) -> dict:
    """Get the phase transition map for a given track."""
    return TRACK_TRANSITIONS.get(track, TRACK_TRANSITIONS["full"])


def normalize_phase(phase: str) -> str:
    """Strip a trailing -complete suffix when present."""
    if phase.endswith("-complete"):
        return phase[: -len("-complete")]
    return phase


def is_completion_phase(phase: str) -> bool:
    """Return True when the phase token is a supported *-complete state."""
    return phase.endswith("-complete") and normalize_phase(phase) in COMPLETABLE_PHASES


def cmd_create(args: argparse.Namespace) -> dict:
    """Create a new feature.yaml from the template."""
    # Sanitize path-constructing inputs
    for field_name, value in [("feature-id", args.feature_id), ("domain", args.domain), ("service", args.service)]:
        err = validate_identifier(value, field_name)
        if err:
            return {"status": "fail", "error": err}

    template_path = get_template_path()
    if not template_path.exists():
        return {"status": "fail", "error": f"Template not found: {template_path}"}

    feature_dir = get_feature_dir(args.governance_repo, args.domain, args.service, args.feature_id)
    feature_path = feature_dir / "feature.yaml"

    if feature_path.exists():
        return {"status": "fail", "error": f"Feature already exists: {feature_path}"}

    try:
        with open(template_path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "error": f"Failed to read template: {e}"}

    timestamp = now_iso()

    data["name"] = args.name
    data["description"] = args.description or ""
    data["featureId"] = args.feature_id
    data["domain"] = args.domain
    data["service"] = args.service
    data["track"] = args.track
    data["priority"] = args.priority
    data["created"] = timestamp
    data["updated"] = timestamp
    data["team"] = [{"username": args.username, "role": "lead"}]
    data["phase_transitions"] = [{"phase": "preplan", "timestamp": timestamp, "user": args.username}]
    data["docs"] = {
        "path": f"docs/{args.domain}/{args.service}/{args.feature_id}",
        "governance_docs_path": f"features/{args.domain}/{args.service}/{args.feature_id}/docs",
    }

    if args.target_repos:
        data["target_repos"] = parse_target_repos_arg(args.target_repos)

    try:
        feature_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_yaml(feature_path, data)
    except OSError as e:
        return {"status": "fail", "error": f"Failed to write feature.yaml: {e}"}

    return {
        "status": "pass",
        "path": str(feature_path),
        "featureId": args.feature_id,
        "data": data,
    }


def cmd_read(args: argparse.Namespace) -> dict:
    """Read and return feature state."""
    feature_path = find_feature(args.governance_repo, args.feature_id)
    if not feature_path:
        return {"status": "fail", "error": f"Feature not found: {args.feature_id}"}

    try:
        with open(feature_path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "error": f"Failed to read feature.yaml: {e}"}

    if args.field:
        value = data
        for key in args.field.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return {"status": "fail", "error": f"Field not found: {args.field}"}
        return {"status": "pass", "field": args.field, "value": value, "path": str(feature_path)}

    return {"status": "pass", "path": str(feature_path), "data": data}


def sync_dependency(governance_repo: str, target_feature_id: str, source_feature_id: str, action: str) -> dict | None:
    """Sync bidirectional dependency. Returns error dict on failure, None on success."""
    dep_path = find_feature(governance_repo, target_feature_id)
    if not dep_path:
        return {"warning": f"Dependency target '{target_feature_id}' not found — skipping bidirectional sync"}

    try:
        with open(dep_path) as f:
            dep_data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {"warning": f"Cannot read dependency '{target_feature_id}': {e}"}

    if "dependencies" not in dep_data:
        dep_data["dependencies"] = {"depends_on": [], "depended_by": []}
    if "depended_by" not in dep_data["dependencies"]:
        dep_data["dependencies"]["depended_by"] = []

    depended_by = dep_data["dependencies"]["depended_by"]

    if action == "add" and source_feature_id not in depended_by:
        depended_by.append(source_feature_id)
    elif action == "remove" and source_feature_id in depended_by:
        depended_by.remove(source_feature_id)
    else:
        return None  # no change needed

    dep_data["updated"] = now_iso()

    try:
        atomic_write_yaml(dep_path, dep_data)
    except OSError as e:
        return {"warning": f"Failed to update dependency '{target_feature_id}': {e}"}

    return None


def cmd_update(args: argparse.Namespace) -> dict:
    """Update fields in a feature.yaml."""
    feature_path = find_feature(args.governance_repo, args.feature_id)
    if not feature_path:
        return {"status": "fail", "error": f"Feature not found: {args.feature_id}"}

    try:
        with open(feature_path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "error": f"Failed to read feature.yaml: {e}"}

    changes = []
    sync_warnings = []

    for field_spec in args.set:
        if "=" not in field_spec:
            return {"status": "fail", "error": f"Invalid --set format: {field_spec}. Use key=value"}
        key, value = field_spec.split("=", 1)

        # Handle phase transitions specially
        if key == "phase":
            current_phase = data.get("phase", "preplan")
            track = data.get("track", "full")
            transitions = get_transitions_for_track(track)
            allowed = transitions.get(normalize_phase(current_phase), [])
            completing_current_phase = value == f"{normalize_phase(current_phase)}-complete"
            if not completing_current_phase and value not in allowed:
                return {
                    "status": "fail",
                    "error": f"Invalid phase transition: {current_phase} -> {value} on track '{track}'. "
                    f"Allowed: {allowed}",
                }
            data["phase"] = value
            if not data.get("phase_transitions"):
                data["phase_transitions"] = []
            data["phase_transitions"].append({
                "phase": value,
                "timestamp": now_iso(),
                "user": args.username or "unknown",
            })
            # Update milestone if applicable
            if value in data.get("milestones", {}):
                data["milestones"][value] = now_iso()
            elif is_completion_phase(value):
                completed_phase = normalize_phase(value)
                if completed_phase in data.get("milestones", {}):
                    data["milestones"][completed_phase] = now_iso()
            changes.append({"field": "phase", "old": current_phase, "new": value})

        # Handle dependency updates with bidirectional sync
        elif key == "dependencies.depends_on":
            old_deps = data.get("dependencies", {}).get("depends_on", [])
            new_deps = [d.strip() for d in value.split(",") if d.strip()]

            # Determine adds and removes
            added = set(new_deps) - set(old_deps)
            removed = set(old_deps) - set(new_deps)

            # Sync bidirectional references
            for dep_id in added:
                warn = sync_dependency(args.governance_repo, dep_id, args.feature_id, "add")
                if warn:
                    sync_warnings.append(warn["warning"])
            for dep_id in removed:
                warn = sync_dependency(args.governance_repo, dep_id, args.feature_id, "remove")
                if warn:
                    sync_warnings.append(warn["warning"])

            if "dependencies" not in data:
                data["dependencies"] = {"depends_on": [], "depended_by": []}
            data["dependencies"]["depends_on"] = new_deps
            changes.append({"field": key, "old": old_deps, "new": new_deps})
        elif key == "target_repos":
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                return {
                    "status": "fail",
                    "error": f"Invalid JSON for target_repos: {exc.msg}",
                }
            if not isinstance(parsed, list):
                return {
                    "status": "fail",
                    "error": "target_repos must be a JSON array",
                }
            old_repos = normalize_target_repos(data.get("target_repos", []))
            try:
                new_repos = normalize_target_repos(parsed)
            except ValueError as exc:
                return {"status": "fail", "error": str(exc)}
            data["target_repos"] = new_repos
            changes.append({"field": key, "old": old_repos, "new": new_repos})
        else:
            # Dot-notation path traversal
            keys = key.split(".")
            target = data
            for k in keys[:-1]:
                if isinstance(target, dict) and k in target:
                    target = target[k]
                else:
                    return {"status": "fail", "error": f"Path not found: {key}"}

            final_key = keys[-1]
            old_value = target.get(final_key) if isinstance(target, dict) else None

            # Type coercion for known fields
            if value.lower() == "null":
                value = None
            elif value.lower() in ("true", "false"):
                value = value.lower() == "true"

            target[final_key] = value
            changes.append({"field": key, "old": old_value, "new": value})

    data["updated"] = now_iso()

    try:
        atomic_write_yaml(feature_path, data)
    except OSError as e:
        return {"status": "fail", "error": f"Failed to write feature.yaml: {e}"}

    result = {"status": "pass", "path": str(feature_path), "changes": changes}
    if sync_warnings:
        result["warnings"] = sync_warnings
    return result


def cmd_validate(args: argparse.Namespace) -> dict:
    """Validate feature.yaml against schema and state."""
    feature_path = find_feature(args.governance_repo, args.feature_id)
    if not feature_path:
        return {"status": "fail", "error": f"Feature not found: {args.feature_id}"}

    try:
        with open(feature_path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "error": f"Failed to read feature.yaml: {e}"}

    findings = []

    # Schema compliance
    required_fields = ["name", "featureId", "domain", "service", "phase", "track"]
    for field in required_fields:
        if not data.get(field):
            findings.append({
                "severity": "critical",
                "category": "schema",
                "issue": f"Required field missing or empty: {field}",
                "fix": f"Set {field} in feature.yaml",
            })

    if data.get("phase") and data["phase"] not in VALID_PHASES:
        findings.append({
            "severity": "critical",
            "category": "schema",
            "issue": f"Invalid phase: {data['phase']}",
            "fix": f"Must be one of: {VALID_PHASES}",
        })

    if data.get("track") and data["track"] not in VALID_TRACKS:
        findings.append({
            "severity": "critical",
            "category": "schema",
            "issue": f"Invalid track: {data['track']}",
            "fix": f"Must be one of: {VALID_TRACKS}",
        })

    if data.get("priority") and data["priority"] not in VALID_PRIORITIES:
        findings.append({
            "severity": "high",
            "category": "schema",
            "issue": f"Invalid priority: {data['priority']}",
            "fix": f"Must be one of: {VALID_PRIORITIES}",
        })

    # Identifier sanitization check
    for field_name in ["featureId", "domain", "service"]:
        val = data.get(field_name, "")
        if val and not SAFE_ID_PATTERN.match(val):
            findings.append({
                "severity": "high",
                "category": "schema",
                "issue": f"Unsafe identifier in '{field_name}': '{val}'",
                "fix": "Must match [a-z0-9][a-z0-9._-]{0,63}",
            })

    # Directory consistency
    expected_dir = get_feature_dir(
        args.governance_repo,
        data.get("domain", ""),
        data.get("service", ""),
        data.get("featureId", ""),
    )
    actual_dir = feature_path.parent
    if expected_dir.resolve() != actual_dir.resolve():
        findings.append({
            "severity": "high",
            "category": "consistency",
            "issue": f"Feature directory mismatch: expected {expected_dir}, found {actual_dir}",
            "fix": "Move feature directory or update domain/service fields",
        })

    # Phase/milestone coherence
    milestones = data.get("milestones", {})
    phase = data.get("phase", "preplan")
    phase_index = VALID_PHASES.index(phase) if phase in VALID_PHASES else 0
    for milestone_name, milestone_time in milestones.items():
        if milestone_time and milestone_name in VALID_PHASES:
            ms_index = VALID_PHASES.index(milestone_name)
            if ms_index > phase_index:
                findings.append({
                    "severity": "high",
                    "category": "coherence",
                    "issue": f"Milestone '{milestone_name}' completed but phase is '{phase}'",
                    "fix": "Update phase to reflect actual progress",
                })

    # Team validation
    team = data.get("team", [])
    if not team:
        findings.append({
            "severity": "warning",
            "category": "team",
            "issue": "No team members assigned",
            "fix": "Add at least one team member with 'lead' role",
        })
    elif not any(m.get("role") == "lead" for m in team):
        findings.append({
            "severity": "warning",
            "category": "team",
            "issue": "No team member with 'lead' role",
            "fix": "Assign a team lead",
        })

    # Dependency integrity
    depends_on = data.get("dependencies", {}).get("depends_on", [])
    for dep_id in depends_on:
        dep_path = find_feature(args.governance_repo, dep_id)
        if not dep_path:
            findings.append({
                "severity": "high",
                "category": "dependencies",
                "issue": f"Dependency '{dep_id}' not found in governance repo",
                "fix": f"Create feature '{dep_id}' or remove from depends_on",
            })
        else:
            try:
                with open(dep_path) as f:
                    dep_data = yaml.safe_load(f)
                dep_by = dep_data.get("dependencies", {}).get("depended_by", [])
                if data.get("featureId") not in dep_by:
                    findings.append({
                        "severity": "medium",
                        "category": "dependencies",
                        "issue": f"Dependency '{dep_id}' doesn't list this feature in depended_by",
                        "fix": f"Add '{data.get('featureId')}' to {dep_id}'s depended_by list",
                    })
            except (yaml.YAMLError, OSError) as e:
                findings.append({
                    "severity": "high",
                    "category": "dependencies",
                    "issue": f"Cannot read dependency '{dep_id}': {e}",
                    "fix": "Check the dependency feature.yaml for corruption",
                })

    # Target repo integrity
    target_repos = data.get("target_repos", [])
    if target_repos and not isinstance(target_repos, list):
        findings.append({
            "severity": "high",
            "category": "target_repos",
            "issue": "target_repos must be a list",
            "fix": "Rewrite target_repos as a YAML sequence of repo objects",
        })
    else:
        for index, repo in enumerate(target_repos):
            if not isinstance(repo, dict):
                findings.append({
                    "severity": "high",
                    "category": "target_repos",
                    "issue": f"target_repos[{index}] is not a mapping",
                    "fix": "Convert each target repo entry into a YAML mapping",
                })
                continue

            remote_url = repo.get("remote_url") or repo.get("url")
            local_path = repo.get("local_path")
            visibility = repo.get("visibility")

            if not remote_url:
                findings.append({
                    "severity": "medium",
                    "category": "target_repos",
                    "issue": f"target_repos[{index}] is missing url/remote_url",
                    "fix": "Add a reachable repository URL so downstream tooling can target the repo",
                })
            if local_path and not str(local_path).startswith("TargetProjects/"):
                findings.append({
                    "severity": "medium",
                    "category": "target_repos",
                    "issue": f"target_repos[{index}].local_path should be project-root-relative and start with TargetProjects/",
                    "fix": "Rewrite local_path using the canonical TargetProjects/{domain}/{service}/{repo} form",
                })
            if visibility and str(visibility).lower() not in VALID_VISIBILITIES:
                findings.append({
                    "severity": "warning",
                    "category": "target_repos",
                    "issue": f"target_repos[{index}].visibility '{visibility}' is not recognized",
                    "fix": "Use one of: public, private, internal",
                })

    # Determine overall status
    severities = [f["severity"] for f in findings]
    if "critical" in severities:
        status = "fail"
    elif "high" in severities or "medium" in severities:
        status = "warning"
    else:
        status = "pass"

    return {
        "status": status,
        "path": str(feature_path),
        "findings": findings,
        "summary": {
            "total": len(findings),
            "critical": severities.count("critical"),
            "high": severities.count("high"),
            "medium": severities.count("medium"),
            "warning": severities.count("warning"),
        },
    }


def cmd_list(args: argparse.Namespace) -> dict:
    """List all features in the governance repo."""
    features_dir = Path(args.governance_repo) / "features"
    if not features_dir.exists():
        return {"status": "pass", "features": [], "total": 0}

    features = []
    parse_errors = []
    for yaml_file in sorted(features_dir.rglob("feature.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if data:
                entry = {
                    "featureId": data.get("featureId", ""),
                    "name": data.get("name", ""),
                    "domain": data.get("domain", ""),
                    "service": data.get("service", ""),
                    "phase": data.get("phase", ""),
                    "track": data.get("track", ""),
                    "priority": data.get("priority", ""),
                    "path": str(yaml_file),
                }
                # Apply filters
                if hasattr(args, "phase") and args.phase and entry["phase"] != args.phase:
                    continue
                if hasattr(args, "domain") and args.domain and entry["domain"] != args.domain:
                    continue
                if hasattr(args, "track") and args.track and entry["track"] != args.track:
                    continue
                features.append(entry)
        except yaml.YAMLError as e:
            parse_errors.append({"path": str(yaml_file), "error": str(e)})
            print(f"Warning: Unparseable YAML at {yaml_file}: {e}", file=sys.stderr)
            continue
        except OSError as e:
            parse_errors.append({"path": str(yaml_file), "error": str(e)})
            print(f"Warning: Cannot read {yaml_file}: {e}", file=sys.stderr)
            continue

    result = {"status": "pass", "features": features, "total": len(features)}
    if parse_errors:
        result["parse_errors"] = parse_errors
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Feature YAML operations — create, read, update, validate, list feature.yaml files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create --governance-repo /path/to/repo --feature-id auth-login \\
    --domain platform --service identity --name "User Auth" --track quickplan --username cweber

  %(prog)s read --governance-repo /path/to/repo --feature-id auth-login
  %(prog)s read --governance-repo /path/to/repo --feature-id auth-login --field phase

  %(prog)s update --governance-repo /path/to/repo --feature-id auth-login \\
    --set phase=techplan --username cweber

  %(prog)s validate --governance-repo /path/to/repo --feature-id auth-login

  %(prog)s list --governance-repo /path/to/repo
  %(prog)s list --governance-repo /path/to/repo --phase dev --domain platform
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create
    create_p = subparsers.add_parser("create", help="Create a new feature.yaml")
    create_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    create_p.add_argument("--feature-id", required=True, help="Unique feature identifier")
    create_p.add_argument("--domain", required=True, help="Domain name")
    create_p.add_argument("--service", required=True, help="Service name")
    create_p.add_argument("--name", required=True, help="Human-friendly feature name")
    create_p.add_argument("--description", default="", help="Feature description")
    create_p.add_argument("--track", default="quickplan", choices=VALID_TRACKS, help="Lifecycle track")
    create_p.add_argument("--priority", default="medium", choices=VALID_PRIORITIES, help="Feature priority")
    create_p.add_argument("--username", required=True, help="Username of the creator")
    create_p.add_argument("--target-repos", default="", help="Comma-separated target repo URLs")

    # Read
    read_p = subparsers.add_parser("read", help="Read feature state")
    read_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    read_p.add_argument("--feature-id", required=True, help="Feature identifier")
    read_p.add_argument("--field", help="Dot-notation path to specific field")

    # Update
    update_p = subparsers.add_parser("update", help="Update feature fields")
    update_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    update_p.add_argument("--feature-id", required=True, help="Feature identifier")
    update_p.add_argument("--set", action="append", required=True, help="Field=value (dot-notation, repeatable)")
    update_p.add_argument("--username", help="Username performing the update")

    # Validate
    validate_p = subparsers.add_parser("validate", help="Validate feature.yaml")
    validate_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    validate_p.add_argument("--feature-id", required=True, help="Feature identifier")

    # List
    list_p = subparsers.add_parser("list", help="List all features")
    list_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    list_p.add_argument("--phase", help="Filter by phase")
    list_p.add_argument("--domain", help="Filter by domain")
    list_p.add_argument("--track", help="Filter by track")

    # Global
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "create": cmd_create,
        "read": cmd_read,
        "update": cmd_update,
        "validate": cmd_validate,
        "list": cmd_list,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()  # trailing newline

    status = result.get("status", "fail")
    exit_code = 0 if status in ("pass", "warning") else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
