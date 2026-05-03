#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Read-only git and governance state reporting for Lens features."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import yaml


MODULE_ROOT = Path(__file__).resolve().parents[3]
LENS_SCRIPTS_ROOT = MODULE_ROOT / "scripts"
if str(LENS_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(LENS_SCRIPTS_ROOT))

from lens_config import ConfigError, discover_feature_yaml, load_lens_config, normalize_absolute_path  # noqa: E402


Runner = Callable[..., subprocess.CompletedProcess[str]]

SAFE_FEATURE_ID = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")
DEV_BRANCH_RE = re.compile(r"^(?P<feature_id>.+)-dev(?:-.+)?$")

DEFAULT_BRANCHES = {"main", "master", "develop", "trunk"}
TERMINAL_STATUSES = {"archived", "complete", "completed", "abandoned", "superseded"}
TERMINAL_PHASES = TERMINAL_STATUSES | {"dev-complete"}
PLANNING_PHASES = {"preplan", "businessplan", "techplan", "finalizeplan", "expressplan"}

READ_ONLY_GIT_COMMANDS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("rev-parse", "--is-inside-work-tree"),
        ("rev-parse", "--show-toplevel"),
        ("branch", "--show-current"),
        ("branch", "--list", "--format=%(refname:short)"),
        ("branch", "--remotes", "--format=%(refname:short)"),
    }
)

MUTATING_GIT_SUBCOMMANDS = {
    "add",
    "am",
    "apply",
    "bisect",
    "branch-create",
    "checkout",
    "cherry-pick",
    "clean",
    "commit",
    "fetch",
    "gc",
    "init",
    "merge",
    "mv",
    "pull",
    "push",
    "rebase",
    "reset",
    "restore",
    "revert",
    "rm",
    "stash",
    "submodule",
    "switch",
    "tag",
    "worktree",
}


class GitStateError(RuntimeError):
    def __init__(self, error: str, message: str, **extra: object) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.extra = extra


def fail(error: str, message: str, **extra: object) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "fail", "error": error, "message": message, "read_only": True}
    payload.update(extra)
    return payload


def assert_git_args_read_only(args: list[str] | tuple[str, ...]) -> None:
    """Reject any git invocation outside the explicit read-only allowlist."""
    normalized = tuple(args)
    if not normalized:
        raise GitStateError("git_args_missing", "No git arguments supplied")
    if normalized[0] in MUTATING_GIT_SUBCOMMANDS:
        raise GitStateError(
            "git_write_rejected",
            f"git {normalized[0]} is not permitted in bmad-lens-git-state",
            git_args=list(normalized),
        )
    if normalized not in READ_ONLY_GIT_COMMANDS:
        raise GitStateError(
            "git_command_not_allowlisted",
            "Only explicit read-only git queries are permitted",
            git_args=list(normalized),
            allowed=[list(command) for command in sorted(READ_ONLY_GIT_COMMANDS)],
        )


def run_git_read_only(
    repo: Path,
    args: list[str],
    *,
    runner: Runner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    assert_git_args_read_only(args)
    try:
        result = runner(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except OSError as exc:
        raise GitStateError("git_unavailable", f"Could not execute git: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitStateError("git_timeout", f"git {' '.join(args)} timed out after 30s") from exc
    if result.returncode != 0:
        if result.stderr.strip():
            message = f"git {' '.join(args)} failed"
        else:
            message = result.stdout.strip() or f"git {' '.join(args)} failed"
        raise GitStateError("git_query_failed", message, git_args=args, repo=str(repo))
    return result


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def remote_branch_short_name(branch: str) -> tuple[str, str | None]:
    if " -> " in branch:
        return "", None
    if "/" not in branch:
        return branch, None
    remote, short_name = branch.split("/", 1)
    return short_name, remote


def parse_branch_role(short_name: str) -> tuple[str, str] | None:
    if not short_name or short_name in DEFAULT_BRANCHES or "/" in short_name:
        return None

    if short_name.endswith("-plan"):
        feature_id = short_name[: -len("-plan")]
        if SAFE_FEATURE_ID.fullmatch(feature_id):
            return feature_id, "plan"
        return None

    dev_match = DEV_BRANCH_RE.fullmatch(short_name)
    if dev_match:
        feature_id = dev_match.group("feature_id")
        if SAFE_FEATURE_ID.fullmatch(feature_id):
            return feature_id, "dev"
        return None

    if SAFE_FEATURE_ID.fullmatch(short_name):
        return short_name, "base"

    return None


def add_branch_entry(entries: list[dict[str, Any]], name: str, scope: str, remote: str | None = None) -> None:
    short_name = name if scope == "local" else remote_branch_short_name(name)[0]
    role_data = parse_branch_role(short_name)
    if not role_data:
        return
    feature_id, role = role_data
    entries.append(
        {
            "name": name,
            "short_name": short_name,
            "feature_id": feature_id,
            "role": role,
            "scope": scope,
            "remote": remote,
        }
    )


def summarize_feature_branches(branch_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_feature: dict[str, dict[str, Any]] = {}
    for entry in branch_entries:
        feature_id = str(entry["feature_id"])
        summary = by_feature.setdefault(
            feature_id,
            {
                "feature_id": feature_id,
                "base_branches": [],
                "plan_branches": [],
                "dev_branches": [],
                "branches": [],
            },
        )
        summary["branches"].append(entry)
        match entry["role"]:
            case "base":
                summary["base_branches"].append(entry["name"])
            case "plan":
                summary["plan_branches"].append(entry["name"])
            case "dev":
                summary["dev_branches"].append(entry["name"])

    results: list[dict[str, Any]] = []
    for feature_id in sorted(by_feature):
        summary = by_feature[feature_id]
        summary["has_base_branch"] = bool(summary["base_branches"])
        summary["has_plan_branch"] = bool(summary["plan_branches"])
        summary["has_dev_branch"] = bool(summary["dev_branches"])
        results.append(summary)
    return results


def collect_branch_state(repo: str | os.PathLike[str], *, runner: Runner = subprocess.run) -> dict[str, Any]:
    repo_path = normalize_absolute_path(repo)
    inside = run_git_read_only(repo_path, ["rev-parse", "--is-inside-work-tree"], runner=runner).stdout.strip()
    if inside != "true":
        raise GitStateError("not_git_repo", f"Not a git work tree: {repo_path}")

    repo_root = run_git_read_only(repo_path, ["rev-parse", "--show-toplevel"], runner=runner).stdout.strip()
    current_branch = run_git_read_only(repo_path, ["branch", "--show-current"], runner=runner).stdout.strip()
    local_branches = split_lines(
        run_git_read_only(repo_path, ["branch", "--list", "--format=%(refname:short)"], runner=runner).stdout
    )
    remote_branches = split_lines(
        run_git_read_only(repo_path, ["branch", "--remotes", "--format=%(refname:short)"], runner=runner).stdout
    )

    feature_branch_entries: list[dict[str, Any]] = []
    for branch in local_branches:
        add_branch_entry(feature_branch_entries, branch, "local")
    for branch in remote_branches:
        short_name, remote = remote_branch_short_name(branch)
        if short_name:
            add_branch_entry(feature_branch_entries, branch, "remote", remote)

    feature_branches = summarize_feature_branches(feature_branch_entries)

    return {
        "repo": str(repo_path),
        "repo_root": repo_root,
        "current_branch": current_branch,
        "local_branches": local_branches,
        "remote_branches": remote_branches,
        "all_feature_branches": feature_branch_entries,
        "feature_branches": feature_branches,
        "features_with_plan_branches": [item["feature_id"] for item in feature_branches if item["has_plan_branch"]],
        "features_with_dev_branches": [item["feature_id"] for item in feature_branches if item["has_dev_branch"]],
    }


def read_yaml_mapping(path: Path) -> dict[str, Any]:
    MAX_YAML_SIZE = 10_000_000  # 10MB
    
    try:
        data_bytes = path.read_bytes()
    except OSError as exc:
        raise GitStateError("yaml_read_failed", f"Could not read {path}: {exc}") from exc
    
    if len(data_bytes) > MAX_YAML_SIZE:
        raise GitStateError("yaml_too_large", f"{path} exceeds {MAX_YAML_SIZE} bytes")
    
    try:
        data = yaml.safe_load(data_bytes.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise GitStateError("yaml_parse_failed", f"Could not decode {path} as UTF-8: {exc}") from exc
    except yaml.YAMLError as exc:
        raise GitStateError("yaml_parse_failed", f"Could not parse {path}: {exc}") from exc
    
    if not isinstance(data, dict):
        raise GitStateError("yaml_malformed", f"{path} must contain a YAML mapping")
    return data


def resolve_governance_repo(args: argparse.Namespace) -> Path:
    if getattr(args, "governance_repo", None):
        return normalize_absolute_path(args.governance_repo)
    try:
        config = load_lens_config(
            getattr(args, "module_config", None),
            start=getattr(args, "workspace_root", None) or getattr(args, "repo", None) or os.getcwd(),
        )
    except ConfigError as exc:
        raise GitStateError("config_missing", str(exc)) from exc
    return Path(config.data["governance_repo_path"])


def resolve_feature_yaml_path(governance_repo: Path, entry: dict[str, Any], feature_id: str) -> Path | None:
    domain = str(entry.get("domain") or "").strip()
    service = str(entry.get("service") or "").strip()
    if domain and service:
        direct = governance_repo / "features" / domain / service / feature_id / "feature.yaml"
        if direct.exists():
            return direct.resolve(strict=False)
    return discover_feature_yaml(governance_repo, feature_id)


def feature_identity(entry: dict[str, Any]) -> str:
    return str(entry.get("featureId") or entry.get("feature_id") or entry.get("id") or "").strip()


def is_active_index_entry(entry: dict[str, Any]) -> bool:
    status = str(entry.get("status") or entry.get("phase") or "").strip().lower()
    return status not in TERMINAL_STATUSES


def collect_active_features(
    governance_repo: str | os.PathLike[str],
    *,
    feature_id_filter: str | None = None,
) -> dict[str, Any]:
    governance_path = normalize_absolute_path(governance_repo)
    index_path = governance_path / "feature-index.yaml"
    if not index_path.exists():
        raise GitStateError("index_not_found", f"feature-index.yaml not found at {index_path}")

    index_data = read_yaml_mapping(index_path)
    raw_features = index_data.get("features")
    if not isinstance(raw_features, list):
        raise GitStateError("index_malformed", "feature-index.yaml must contain a features list")

    active_features: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for position, entry in enumerate(raw_features):
        if not isinstance(entry, dict):
            warnings.append({"code": "index_entry_malformed", "index": position, "message": "feature entry is not a mapping"})
            continue
        feature_id = feature_identity(entry)
        if not feature_id:
            warnings.append({"code": "feature_id_missing", "index": position, "message": "feature entry has no id"})
            continue
        if feature_id_filter and feature_id != feature_id_filter:
            continue
        if not is_active_index_entry(entry):
            continue

        feature_yaml_path = resolve_feature_yaml_path(governance_path, entry, feature_id)
        feature_yaml_data: dict[str, Any] = {}
        phase_source = "feature-index"
        if feature_yaml_path:
            try:
                feature_yaml_data = read_yaml_mapping(feature_yaml_path)
                phase_source = "feature.yaml"
            except GitStateError as exc:
                warnings.append(
                    {
                        "code": exc.error,
                        "feature_id": feature_id,
                        "path": str(feature_yaml_path),
                        "message": exc.message,
                    }
                )

        phase = str(
            feature_yaml_data.get("phase")
            or entry.get("phase")
            or entry.get("status")
            or ""
        ).strip()

        active_features.append(
            {
                "feature_id": feature_id,
                "id": str(entry.get("id") or feature_id),
                "featureSlug": feature_yaml_data.get("featureSlug") or entry.get("featureSlug"),
                "name": feature_yaml_data.get("name") or entry.get("name", ""),
                "domain": feature_yaml_data.get("domain") or entry.get("domain", ""),
                "service": feature_yaml_data.get("service") or entry.get("service", ""),
                "phase": phase,
                "phase_source": phase_source,
                "index_status": entry.get("status", ""),
                "track": feature_yaml_data.get("track") or entry.get("track", ""),
                "owner": entry.get("owner", ""),
                "plan_branch": entry.get("plan_branch", f"{feature_id}-plan"),
                "feature_yaml_path": str(feature_yaml_path) if feature_yaml_path else None,
                "feature_yaml": feature_yaml_data,
            }
        )

    return {
        "governance_repo": str(governance_path),
        "feature_index": str(index_path),
        "active_features": active_features,
        "warnings": warnings,
    }


def branch_summary_by_feature(branch_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["feature_id"]: item for item in branch_state.get("feature_branches", [])}


def phase_root(phase: str) -> str:
    return phase[: -len("-complete")] if phase.endswith("-complete") else phase


def discrepancy(
    feature_id: str,
    field: str,
    yaml_value: object,
    branch_state_field: str,
    branch_state_value: object,
    expected_state: str,
    message: str,
) -> dict[str, Any]:
    return {
        "feature_id": feature_id,
        "field": field,
        "yaml_value": yaml_value,
        "branch_state_field": branch_state_field,
        "branch_state_value": branch_state_value,
        "expected_state": expected_state,
        "message": message,
    }


def compare_features_to_branches(
    active_features: list[dict[str, Any]],
    branch_state: dict[str, Any],
) -> list[dict[str, Any]]:
    by_feature = branch_summary_by_feature(branch_state)
    discrepancies: list[dict[str, Any]] = []

    for feature in active_features:
        feature_id = str(feature["feature_id"])
        phase = str(feature.get("phase") or "").strip()
        root = phase_root(phase)
        branches = by_feature.get(
            feature_id,
            {
                "base_branches": [],
                "plan_branches": [],
                "dev_branches": [],
                "has_base_branch": False,
                "has_plan_branch": False,
                "has_dev_branch": False,
            },
        )

        if not phase:
            discrepancies.append(
                discrepancy(
                    feature_id,
                    "feature.yaml.phase",
                    phase,
                    "branch_state.feature_branches",
                    branches.get("branches", []),
                    "feature.yaml.phase is set before branch-state comparison",
                    f"{feature_id} has no feature.yaml.phase value to compare with branch state.",
                )
            )
            continue

        if root in PLANNING_PHASES and not branches.get("has_plan_branch"):
            discrepancies.append(
                discrepancy(
                    feature_id,
                    "feature.yaml.phase",
                    phase,
                    "branch_state.plan_branches",
                    branches.get("plan_branches", []),
                    f"one of {feature_id}-plan or a remote {feature_id}-plan exists",
                    f"feature.yaml.phase={phase} indicates planning, but no plan branch is present.",
                )
            )

        if phase == "dev" and not branches.get("has_dev_branch"):
            discrepancies.append(
                discrepancy(
                    feature_id,
                    "feature.yaml.phase",
                    phase,
                    "branch_state.dev_branches",
                    branches.get("dev_branches", []),
                    f"one of {feature_id}-dev or {feature_id}-dev-* exists",
                    f"feature.yaml.phase=dev but no {feature_id}-dev branch is present.",
                )
            )

        if phase == "dev" and branches.get("has_plan_branch"):
            discrepancies.append(
                discrepancy(
                    feature_id,
                    "feature.yaml.phase",
                    phase,
                    "branch_state.plan_branches",
                    branches.get("plan_branches", []),
                    "plan branch is merged or closed before dev starts",
                    f"feature.yaml.phase=dev but plan branch state is still open for {feature_id}.",
                )
            )

        if phase != "dev" and branches.get("has_dev_branch"):
            discrepancies.append(
                discrepancy(
                    feature_id,
                    "feature.yaml.phase",
                    phase,
                    "branch_state.dev_branches",
                    branches.get("dev_branches", []),
                    "phase must be 'dev' if dev branch exists",
                    f"feature.yaml.phase={phase} but {feature_id}-dev branch exists.",
                )
            )

        if phase in TERMINAL_PHASES and (branches.get("has_plan_branch") or branches.get("has_dev_branch")):
            discrepancies.append(
                discrepancy(
                    feature_id,
                    "feature.yaml.phase",
                    phase,
                    "branch_state.plan_branches/dev_branches",
                    {
                        "plan_branches": branches.get("plan_branches", []),
                        "dev_branches": branches.get("dev_branches", []),
                    },
                    "no open plan or dev branches remain for terminal features",
                    f"feature.yaml.phase={phase} is terminal, but plan or dev branches are still present.",
                )
            )

    return discrepancies


def command_branch_state(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    branch_state = collect_branch_state(args.repo or os.getcwd())
    return {"status": "pass", "read_only": True, "branch_state": branch_state}, 0


def command_active_features(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    governance_repo = resolve_governance_repo(args)
    features = collect_active_features(governance_repo, feature_id_filter=args.feature_id)
    return {
        "status": "pass",
        "read_only": True,
        "governance_repo": features["governance_repo"],
        "feature_index": features["feature_index"],
        "active_features": features["active_features"],
        "warnings": features["warnings"],
    }, 0


def command_discrepancies(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    branch_state = collect_branch_state(args.repo or os.getcwd())
    governance_repo = resolve_governance_repo(args)
    features = collect_active_features(governance_repo, feature_id_filter=args.feature_id)
    discrepancies = compare_features_to_branches(features["active_features"], branch_state)
    return {
        "status": "pass",
        "read_only": True,
        "branch_state": branch_state,
        "active_features": features["active_features"],
        "discrepancies": discrepancies,
        "warnings": features["warnings"],
    }, 0


def command_feature_state(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    branch_state = collect_branch_state(args.repo or os.getcwd())
    governance_repo = resolve_governance_repo(args)
    features = collect_active_features(governance_repo, feature_id_filter=args.feature_id)
    discrepancies = compare_features_to_branches(features["active_features"], branch_state)
    return {
        "status": "pass",
        "read_only": True,
        "repo": branch_state["repo"],
        "governance_repo": features["governance_repo"],
        "feature_index": features["feature_index"],
        "branch_state": branch_state,
        "active_features": features["active_features"],
        "discrepancies": discrepancies,
        "warnings": features["warnings"],
    }, 0


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", help="Git repo to inspect. Defaults to the current working directory.")
    parser.add_argument("--governance-repo", help="Governance repo containing feature-index.yaml.")
    parser.add_argument("--feature-id", help="Limit feature reporting to one feature ID.")
    parser.add_argument("--workspace-root", help="Workspace root used for config discovery.")
    parser.add_argument("--module-config", help="Explicit _bmad/lens-work/bmadconfig.yaml path.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Lens git state reporting")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler, help_text in (
        ("branch-state", command_branch_state, "Report current branch and Lens feature branch topology"),
        ("active-features", command_active_features, "Report active features and phase from governance"),
        ("discrepancies", command_discrepancies, "Report git-vs-yaml discrepancies"),
        ("feature-state", command_feature_state, "Report branch state, active features, and discrepancies"),
    ):
        subparser = subparsers.add_parser(name, help=help_text)
        add_common_args(subparser)
        subparser.set_defaults(func=handler)

    return parser


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload, code = args.func(args)
    except GitStateError as exc:
        payload, code = fail(exc.error, exc.message, **exc.extra), 1
    except Exception as exc:  # pragma: no cover - defensive JSON boundary
        payload, code = fail("unexpected_error", str(exc)), 1
    emit(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())