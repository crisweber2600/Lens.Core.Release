#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Feature YAML state operations for Lens governance metadata."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

import yaml


MODULE_ROOT = Path(__file__).resolve().parents[3]
LENS_SCRIPTS_ROOT = MODULE_ROOT / "scripts"
if str(LENS_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(LENS_SCRIPTS_ROOT))

from lens_config import ConfigError, discover_feature_yaml, load_lens_config, normalize_absolute_path  # noqa: E402


DEFAULT_PHASE_ORDER = ["preplan", "businessplan", "techplan", "finalizeplan", "dev", "complete"]
TRACK_ALIASES = {
    "full": "standard",
    "tech-change": "standard",
    "quickplan": "express",
}


class FeatureYamlError(RuntimeError):
    def __init__(self, error: str, message: str, **extra: object) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.extra = extra


class GitCommandError(RuntimeError):
    def __init__(self, command: list[str], returncode: int, stdout: str, stderr: str) -> None:
        output = stderr.strip() or stdout.strip() or f"git command failed with exit code {returncode}"
        super().__init__(output)
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


Runner = Callable[..., subprocess.CompletedProcess[str]]


def fail(error: str, message: str, **extra: object) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "fail", "error": error, "message": message}
    payload.update(extra)
    return payload


def warning_payload(message: str, warnings: list[dict[str, str]], **extra: object) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "warning", "message": message, "warnings": warnings}
    payload.update(extra)
    return payload


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        raise FeatureYamlError("feature_yaml_malformed", f"Could not read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise FeatureYamlError("feature_yaml_malformed", f"{path} must contain a YAML mapping")
    return data


def atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".yaml.tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, default_flow_style=False, sort_keys=False, allow_unicode=True)
        os.replace(temp_path, str(path))
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def resolve_governance_repo(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "governance_repo", None)
    if explicit:
        return normalize_absolute_path(explicit)
    try:
        config = load_lens_config(
            getattr(args, "module_config", None),
            start=getattr(args, "workspace_root", None) or os.getcwd(),
        )
    except ConfigError as exc:
        raise FeatureYamlError("config_missing", str(exc)) from exc
    return Path(config.data["governance_repo_path"])


def resolve_feature_path(args: argparse.Namespace) -> Path:
    explicit_path = getattr(args, "feature_path", None)
    if explicit_path:
        feature_path = normalize_absolute_path(explicit_path)
        if not feature_path.exists():
            raise FeatureYamlError("feature_yaml_not_found", f"feature.yaml not found: {feature_path}")
        return feature_path

    feature_id = str(getattr(args, "feature_id", "") or "").strip()
    if not feature_id:
        raise FeatureYamlError("feature_id_missing", "Provide --feature-id or --feature-path")

    governance_repo = resolve_governance_repo(args)
    feature_path = discover_feature_yaml(governance_repo, feature_id)
    if feature_path is None:
        raise FeatureYamlError("feature_yaml_not_found", f"feature.yaml not found for '{feature_id}'")
    return feature_path


def load_lifecycle(args: argparse.Namespace | None = None) -> dict[str, Any]:
    lifecycle_path_text = getattr(args, "lifecycle_path", None) if args is not None else None
    lifecycle_path = normalize_absolute_path(lifecycle_path_text) if lifecycle_path_text else MODULE_ROOT / "lifecycle.yaml"
    if not lifecycle_path.exists():
        return {"phase_order": DEFAULT_PHASE_ORDER, "tracks": {}}
    try:
        with lifecycle_path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise FeatureYamlError("lifecycle_malformed", f"Could not read lifecycle contract: {exc}") from exc
    if not isinstance(data, dict):
        raise FeatureYamlError("lifecycle_malformed", "Lifecycle contract must contain a YAML mapping")
    return data


def canonical_track(track: object) -> str:
    text = str(track or "").strip()
    return TRACK_ALIASES.get(text, text)


def phases_for_track(lifecycle: dict[str, Any], track: object) -> list[str]:
    tracks = lifecycle.get("tracks") if isinstance(lifecycle.get("tracks"), dict) else {}
    track_key = canonical_track(track)
    track_data = tracks.get(track_key) if isinstance(tracks, dict) else None
    phases = track_data.get("phases") if isinstance(track_data, dict) else None
    if isinstance(phases, list) and all(isinstance(phase, str) for phase in phases):
        return phases

    phase_order = lifecycle.get("phase_order")
    if isinstance(phase_order, list) and all(isinstance(phase, str) for phase in phase_order):
        return phase_order
    return DEFAULT_PHASE_ORDER


def phase_state_sequence(lifecycle: dict[str, Any], track: object) -> list[str]:
    states: list[str] = []
    for phase in phases_for_track(lifecycle, track):
        if phase == "dev" and "dev-ready" not in states:
            states.append("dev-ready")
        states.append(phase)
        if phase != "complete":
            states.append(f"{phase}-complete")
    return list(dict.fromkeys(states))


def allowed_next_phases(current_phase: str, states: list[str]) -> list[str]:
    if current_phase not in states:
        return []
    current_index = states.index(current_phase)
    if current_index >= len(states) - 1:
        return []

    allowed = [states[current_index + 1]]
    next_phase = states[current_index + 1]
    if next_phase == "dev-ready" and current_index + 2 < len(states) and states[current_index + 2] == "dev":
        allowed.append("dev")
    if (
        not next_phase.endswith("-complete")
        and current_index + 2 < len(states)
        and states[current_index + 2] == f"{next_phase}-complete"
    ):
        allowed.append(states[current_index + 2])
    return list(dict.fromkeys(allowed))


def validate_phase_transition(
    feature_data: dict[str, Any],
    target_phase: str | None,
    lifecycle: dict[str, Any],
) -> dict[str, Any] | None:
    if not target_phase:
        return None

    current_phase = str(feature_data.get("phase") or "").strip()
    states = phase_state_sequence(lifecycle, feature_data.get("track"))
    if current_phase not in states:
        return fail(
            "invalid_current_phase",
            f"Current phase '{current_phase}' is not valid for track '{feature_data.get('track', '')}'",
            valid_phases=states,
        )
    if target_phase not in states:
        return fail(
            "invalid_target_phase",
            f"Target phase '{target_phase}' is not valid for track '{feature_data.get('track', '')}'",
            valid_phases=states,
        )
    if target_phase == current_phase:
        return None

    allowed = allowed_next_phases(current_phase, states)
    if target_phase not in allowed:
        return fail(
            "invalid_phase_transition",
            f"Cannot transition from '{current_phase}' to '{target_phase}'",
            current_phase=current_phase,
            target_phase=target_phase,
            allowed_next_phases=allowed,
        )
    return None


def implementation_impacts_target_repo(feature_data: dict[str, Any], lifecycle: dict[str, Any]) -> bool:
    track_key = canonical_track(feature_data.get("track"))
    if track_key == "spike":
        return False
    return "dev" in phases_for_track(lifecycle, feature_data.get("track"))


def validate_target_repos(feature_data: dict[str, Any], lifecycle: dict[str, Any]) -> list[dict[str, str]]:
    if not implementation_impacts_target_repo(feature_data, lifecycle):
        return []
    target_repos = feature_data.get("target_repos")
    if not isinstance(target_repos, list) or not target_repos:
        return [
            {
                "code": "missing_target_repos",
                "message": "Implementation-impacting feature has no target_repos entries.",
            }
        ]
    return []


def feature_identity(feature_data: dict[str, Any]) -> dict[str, Any]:
    feature_id = feature_data.get("featureId") or feature_data.get("feature_id") or feature_data.get("id")
    return {
        "featureId": feature_id,
        "feature_id": feature_data.get("feature_id") or feature_id,
        "id": feature_data.get("id") or feature_id,
        "featureSlug": feature_data.get("featureSlug") or feature_data.get("feature_slug"),
        "name": feature_data.get("name"),
        "domain": feature_data.get("domain"),
        "service": feature_data.get("service"),
        "status": feature_data.get("status"),
        "priority": feature_data.get("priority"),
    }


def build_read_payload(feature_path: Path, feature_data: dict[str, Any]) -> dict[str, Any]:
    docs = feature_data.get("docs") if isinstance(feature_data.get("docs"), dict) else {}
    transition_history = feature_data.get("transition_history") or feature_data.get("phase_transitions") or []
    return {
        "status": "pass",
        "feature_yaml_path": str(feature_path),
        "identity": feature_identity(feature_data),
        "featureId": feature_identity(feature_data)["featureId"],
        "phase": feature_data.get("phase"),
        "track": feature_data.get("track"),
        "docs": docs,
        "docs_path": docs.get("path"),
        "governance_docs_path": docs.get("governance_docs_path"),
        "target_repos": feature_data.get("target_repos") or [],
        "dependencies": feature_data.get("dependencies") or {},
        "milestones": feature_data.get("milestones") or {},
        "transition_history": transition_history,
        "phase_transitions": feature_data.get("phase_transitions") or [],
        "raw": feature_data,
    }


def parse_yaml_value(raw: str, field_name: str, expected_type: type) -> Any:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        try:
            value = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise FeatureYamlError("invalid_update_value", f"{field_name} is not valid JSON or YAML: {exc}") from exc
    if not isinstance(value, expected_type):
        raise FeatureYamlError("invalid_update_value", f"{field_name} must be a {expected_type.__name__}")
    return value


def resolve_feature_index_path(governance_repo: Path) -> Path:
    return governance_repo / "feature-index.yaml"


def sync_feature_index(governance_repo: Path, feature_data: dict[str, Any]) -> dict[str, Any]:
    feature_id = str(feature_data.get("featureId") or feature_data.get("feature_id") or feature_data.get("id") or "").strip()
    if not feature_id:
        raise FeatureYamlError("feature_id_missing", "feature.yaml is missing featureId/feature_id")

    index_path = resolve_feature_index_path(governance_repo)
    if index_path.exists():
        index_data = load_yaml_mapping(index_path)
    else:
        index_data = {"features": []}

    features = index_data.get("features")
    if not isinstance(features, list):
        raise FeatureYamlError("index_malformed", "feature-index.yaml must contain a features list")

    entry = {
        "id": feature_id,
        "domain": feature_data.get("domain"),
        "service": feature_data.get("service"),
        "phase": feature_data.get("phase"),
        "track": feature_data.get("track"),
        "status": feature_data.get("status"),
    }

    updated = False
    for idx, candidate in enumerate(features):
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("id") or candidate.get("featureId") or candidate.get("feature_id") or "").strip()
        if candidate_id == feature_id:
            features[idx] = {**candidate, **{k: v for k, v in entry.items() if v is not None}}
            updated = True
            break

    if not updated:
        features.append({k: v for k, v in entry.items() if v is not None})

    index_data["features"] = features
    atomic_write_yaml(index_path, index_data)
    return {
        "feature_index_path": str(index_path),
        "feature_id": feature_id,
        "updated_existing_entry": updated,
    }


def apply_updates(feature_data: dict[str, Any], args: argparse.Namespace) -> list[str]:
    changed_fields: list[str] = []
    if args.phase is not None and feature_data.get("phase") != args.phase:
        feature_data["phase"] = args.phase
        changed_fields.append("phase")

    if args.docs_path is not None or args.governance_docs_path is not None:
        docs = feature_data.get("docs") if isinstance(feature_data.get("docs"), dict) else {}
        if args.docs_path is not None and docs.get("path") != args.docs_path:
            docs["path"] = args.docs_path
            changed_fields.append("docs.path")
        if args.governance_docs_path is not None and docs.get("governance_docs_path") != args.governance_docs_path:
            docs["governance_docs_path"] = args.governance_docs_path
            changed_fields.append("docs.governance_docs_path")
        feature_data["docs"] = docs

    if args.target_repos is not None:
        target_repos = parse_yaml_value(args.target_repos, "target_repos", list)
        if feature_data.get("target_repos") != target_repos:
            feature_data["target_repos"] = target_repos
            changed_fields.append("target_repos")

    if args.milestones is not None:
        milestones = parse_yaml_value(args.milestones, "milestones", dict)
        if feature_data.get("milestones") != milestones:
            feature_data["milestones"] = milestones
            changed_fields.append("milestones")

    return changed_fields


def run_git(
    repo: Path,
    git_args: list[str],
    *,
    runner: Runner = subprocess.run,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(repo), *git_args]
    result = runner(command, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise GitCommandError(command, result.returncode, result.stdout or "", result.stderr or "")
    return result


def handle_dirty_state(
    governance_repo: Path,
    paths: list[str],
    message: str,
    *,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    status_args = ["status", "--porcelain"]
    if paths:
        status_args.extend(["--", *paths])
    status_result = run_git(governance_repo, status_args, runner=runner)
    dirty_entries = [line for line in status_result.stdout.splitlines() if line.strip()]

    if not dirty_entries:
        run_git(governance_repo, ["pull"], runner=runner)
        return {
            "status": "pass",
            "dirty": False,
            "committed": False,
            "sha": None,
            "message": "No relevant governance changes to commit.",
        }

    run_git(governance_repo, ["pull", "--rebase", "--autostash"], runner=runner)
    add_args = ["add", "--", *paths] if paths else ["add", "-A"]
    run_git(governance_repo, add_args, runner=runner)

    diff_result = run_git(governance_repo, ["diff", "--cached", "--quiet"], runner=runner, check=False)
    if diff_result.returncode == 0:
        return {
            "status": "pass",
            "dirty": True,
            "committed": False,
            "sha": None,
            "message": "Dirty entries were present, but no staged changes remained after pull/add.",
        }
    if diff_result.returncode != 1:
        raise GitCommandError(
            ["git", "-C", str(governance_repo), "diff", "--cached", "--quiet"],
            diff_result.returncode,
            diff_result.stdout or "",
            diff_result.stderr or "",
        )

    run_git(governance_repo, ["commit", "-m", message], runner=runner)
    sha_result = run_git(governance_repo, ["rev-parse", "HEAD"], runner=runner)
    sha = sha_result.stdout.strip()
    run_git(governance_repo, ["push"], runner=runner)
    return {
        "status": "pass",
        "dirty": True,
        "committed": True,
        "sha": sha,
        "staged_paths": paths or ["-A"],
        "message": "Committed and pushed relevant governance changes.",
    }


def cmd_read(args: argparse.Namespace) -> dict[str, Any]:
    feature_path = resolve_feature_path(args)
    return build_read_payload(feature_path, load_yaml_mapping(feature_path))


def cmd_validate(args: argparse.Namespace) -> dict[str, Any]:
    feature_path = resolve_feature_path(args)
    feature_data = load_yaml_mapping(feature_path)
    lifecycle = load_lifecycle(args)

    phase_error = validate_phase_transition(feature_data, args.to_phase, lifecycle)
    warnings = validate_target_repos(feature_data, lifecycle)
    states = phase_state_sequence(lifecycle, feature_data.get("track"))
    current_phase = str(feature_data.get("phase") or "")
    base_payload = {
        "feature_yaml_path": str(feature_path),
        "feature_id": feature_identity(feature_data)["featureId"],
        "current_phase": current_phase,
        "target_phase": args.to_phase,
        "allowed_next_phases": allowed_next_phases(current_phase, states),
    }

    if phase_error:
        phase_error["warnings"] = warnings
        phase_error.update(base_payload)
        return phase_error
    if warnings:
        return warning_payload("Feature YAML validation passed with warnings.", warnings, **base_payload)
    return {"status": "pass", "message": "Feature YAML validation passed.", "warnings": [], **base_payload}


def cmd_update(args: argparse.Namespace) -> dict[str, Any]:
    feature_path = resolve_feature_path(args)
    feature_data = load_yaml_mapping(feature_path)
    lifecycle = load_lifecycle(args)

    phase_error = validate_phase_transition(feature_data, args.phase, lifecycle)
    if phase_error:
        phase_error["feature_yaml_path"] = str(feature_path)
        return phase_error

    changed_fields = apply_updates(feature_data, args)
    sync_result: dict[str, Any] | None = None
    if changed_fields:
        atomic_write_yaml(feature_path, feature_data)
        if "phase" in changed_fields:
            governance_repo = resolve_governance_repo(args)
            sync_result = sync_feature_index(governance_repo, feature_data)
    return {
        "status": "pass",
        "feature_yaml_path": str(feature_path),
        "changed_fields": changed_fields,
        "feature_index_sync": sync_result,
        "feature": build_read_payload(feature_path, feature_data),
    }


def cmd_sync_feature_index(args: argparse.Namespace) -> dict[str, Any]:
    feature_path = resolve_feature_path(args)
    governance_repo = resolve_governance_repo(args)
    feature_data = load_yaml_mapping(feature_path)
    result = sync_feature_index(governance_repo, feature_data)
    return {"status": "pass", **result}


def cmd_commit_dirty(args: argparse.Namespace) -> dict[str, Any]:
    governance_repo = resolve_governance_repo(args)
    paths = list(args.paths or [])
    if not paths and getattr(args, "feature_id", None):
        feature_path = resolve_feature_path(args)
        try:
            paths = [str(feature_path.relative_to(governance_repo))]
        except ValueError:
            paths = [str(feature_path)]
    message = args.message or f"[STATE] {args.feature_id or 'governance'} - persist feature yaml state"
    return handle_dirty_state(governance_repo, paths, message)


def add_feature_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--feature-id", required=False, help="Feature identifier to discover in governance features/")
    parser.add_argument("--feature-path", required=False, help="Direct path to feature.yaml")
    parser.add_argument("--governance-repo", required=False, help="Governance repo root path")
    parser.add_argument("--workspace-root", required=False, help="Workspace/project root for config discovery")
    parser.add_argument("--module-config", required=False, help="Explicit _bmad/lens-work/bmadconfig.yaml path")
    parser.add_argument("--lifecycle-path", required=False, help="Explicit lifecycle.yaml path")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read, validate, update, and persist Lens feature.yaml state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    read_parser = subparsers.add_parser("read", help="Read feature.yaml state")
    add_feature_args(read_parser)

    validate_parser = subparsers.add_parser("validate", help="Validate feature.yaml state and phase transition")
    add_feature_args(validate_parser)
    validate_parser.add_argument("--to-phase", required=False, help="Target phase for transition validation")

    update_parser = subparsers.add_parser("update", help="Surgically update supported feature.yaml fields")
    add_feature_args(update_parser)
    update_parser.add_argument("--phase", required=False, help="New phase value")
    update_parser.add_argument("--docs-path", required=False, help="New docs.path value")
    update_parser.add_argument("--governance-docs-path", required=False, help="New docs.governance_docs_path value")
    update_parser.add_argument("--target-repos", required=False, help="JSON or YAML list for target_repos")
    update_parser.add_argument("--milestones", required=False, help="JSON or YAML mapping for milestones")

    sync_parser = subparsers.add_parser("sync-feature-index", help="Synchronize feature-index.yaml from feature.yaml")
    add_feature_args(sync_parser)

    commit_parser = subparsers.add_parser("commit-dirty", help="Commit and push relevant dirty governance changes")
    commit_parser.add_argument("--governance-repo", required=False, help="Governance repo root path")
    commit_parser.add_argument("--workspace-root", required=False, help="Workspace/project root for config discovery")
    commit_parser.add_argument("--module-config", required=False, help="Explicit _bmad/lens-work/bmadconfig.yaml path")
    commit_parser.add_argument("--feature-id", required=False, help="Feature id whose feature.yaml should be staged")
    commit_parser.add_argument("--path", action="append", dest="paths", default=[], help="Relevant path to stage; repeatable")
    commit_parser.add_argument("--message", required=False, help="Commit message")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    commands = {
        "read": cmd_read,
        "validate": cmd_validate,
        "update": cmd_update,
        "sync-feature-index": cmd_sync_feature_index,
        "commit-dirty": cmd_commit_dirty,
    }
    try:
        payload = commands[args.command](args)
    except FeatureYamlError as exc:
        payload = fail(exc.error, exc.message, **exc.extra)
    except GitCommandError as exc:
        payload = fail(
            "git_failed",
            str(exc),
            command=exc.command,
            returncode=exc.returncode,
            stdout=exc.stdout,
            stderr=exc.stderr,
        )
    json.dump(payload, sys.stdout, indent=2, default=str)
    print()
    raise SystemExit(0 if payload.get("status") in {"pass", "warning"} else 1)


if __name__ == "__main__":
    main()