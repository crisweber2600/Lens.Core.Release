#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Init feature operations for Lens feature and container governance."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml

# source: old-codebase init-feature-ops.py SAFE_ID_PATTERN
SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
GOVERNANCE_AUTO_SYNC_COMMIT_MESSAGE = "chore(governance): auto-sync local changes"
LIFECYCLE_PATH = Path(__file__).resolve().parents[3] / "lifecycle.yaml"
CONTEXT_DOC_SUFFIXES = {".md", ".yaml", ".yml"}
AMBIGUOUS_SERVICE_NAMES = {"api", "auth", "common", "core", "data", "identity"}
CONTROL_TOPOLOGIES = ("3-branch", "flat")
DEFAULT_BRANCH_CANDIDATES = ("main", "master", "develop", "trunk")


@lru_cache(maxsize=1)
def load_lifecycle() -> dict:
    try:
        with LIFECYCLE_PATH.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"Failed to read lifecycle.yaml: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Failed to read lifecycle.yaml: expected a top-level mapping")
    return data


def lifecycle_track_names() -> list[str]:
    tracks = load_lifecycle().get("tracks") or {}
    if not isinstance(tracks, dict) or not tracks:
        raise RuntimeError("lifecycle.yaml must define a non-empty tracks mapping")
    return [str(track) for track in tracks.keys()]


def lifecycle_track_flow() -> str:
    return "[" + ", ".join(lifecycle_track_names()) + "]"


def lifecycle_track_markdown() -> str:
    return ", ".join(f"`{track}`" for track in lifecycle_track_names())


def _module_control_topology() -> str | None:
    for parent in Path(__file__).resolve().parents:
        config_path = parent / "bmadconfig.yaml"
        if not config_path.is_file():
            continue
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return None
        if isinstance(data, dict) and data.get("control_topology"):
            return str(data["control_topology"]).strip()
    return None


def resolve_control_topology(args: argparse.Namespace) -> str:
    topology = str(getattr(args, "control_topology", None) or _module_control_topology() or "3-branch").strip()
    if topology not in CONTROL_TOPOLOGIES:
        expected = ", ".join(CONTROL_TOPOLOGIES)
        raise ValueError(f"invalid control_topology '{topology}' — expected one of: {expected}")
    return topology


def resolve_default_branch(repo: str | None) -> str:
    """Resolve a repo's default branch, falling back to known/current branches."""
    if not repo:
        return "main"
    try:
        result = subprocess.run(
            ["git", "-C", repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result and result.returncode == 0:
        remote_ref = result.stdout.strip()
        if remote_ref.startswith("origin/"):
            return remote_ref.removeprefix("origin/")
    for candidate in DEFAULT_BRANCH_CANDIDATES:
        if git_branch_exists(repo, candidate, include_remote=True):
            return candidate
    try:
        return git_current_branch(repo) or "main"
    except RuntimeError:
        return "main"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_safe_id(domain: str) -> None:
    if not SAFE_ID_PATTERN.match(domain) or domain.endswith("-"):
        raise ValueError(
            f"Invalid domain: '{domain}'. "
            "Must match [a-z0-9][a-z0-9._-]{0,63} "
            "(lowercase alphanumeric, dots, hyphens, underscores)."
        )


def validate_safe_id_field(value: str, field_name: str) -> str | None:
    if not SAFE_ID_PATTERN.match(value) or value.endswith("-"):
        return (
            f"Invalid {field_name}: '{value}'. "
            "Must match [a-z0-9][a-z0-9._-]{0,63} "
            "(lowercase alphanumeric, dots, hyphens, underscores)."
        )
    return None


def git_command_argv(repo: str, args: list[str]) -> list[str]:
    return ["git", "-C", repo, *args]


def git_command_text(repo: str, args: list[str]) -> str:
    return shlex.join(git_command_argv(repo, args))


def run_git(repo: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(git_command_argv(repo, args), capture_output=True, text=True)
    if result.returncode != 0:
        msg = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"{git_command_text(repo, args)} failed: {msg}")
    return result


def unique_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered


def feature_entry_id(entry: dict) -> str:
    return str(entry.get("featureId") or entry.get("feature_id") or entry.get("id") or "").strip()


def feature_dir_from_entry(governance_repo: str, entry: dict) -> Path:
    explicit_dir = entry.get("_feature_dir")
    if explicit_dir:
        return Path(str(explicit_dir))
    explicit_path = entry.get("_feature_yaml_path")
    if explicit_path:
        return Path(str(explicit_path)).parent
    return (
        Path(governance_repo)
        / "features"
        / str(entry.get("domain") or "")
        / str(entry.get("service") or "")
        / feature_entry_id(entry)
    )


def feature_entry_from_yaml(feature_path: Path, feature_data: dict) -> dict:
    feature_id = str(feature_data.get("featureId") or feature_data.get("feature_id") or feature_data.get("id") or "").strip()
    entry = {
        "id": feature_id,
        "featureId": feature_id,
        "feature_id": feature_id,
        "domain": feature_data.get("domain"),
        "service": feature_data.get("service"),
        "status": feature_data.get("status"),
        "phase": feature_data.get("phase"),
        "track": feature_data.get("track"),
        "related_features": feature_data.get("related_features") or {},
        "_feature_yaml_path": str(feature_path),
        "_feature_dir": str(feature_path.parent),
    }
    if feature_data.get("docs_path"):
        entry["docs_path"] = feature_data.get("docs_path")
    return entry


def discover_feature_yaml_by_id(root: Path, feature_id: str) -> Path | None:
    search_roots = [root / "features", root / "docs" / "features"]
    for features_root in search_roots:
        if not features_root.exists():
            continue
        for feature_path in sorted(features_root.rglob("feature.yaml")):
            try:
                data = yaml.safe_load(feature_path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(data, dict):
                continue
            current_id = str(data.get("featureId") or data.get("feature_id") or data.get("id") or "").strip()
            if current_id == feature_id:
                return feature_path.resolve(strict=False)
    return None


def discover_feature_entries(root: Path) -> list[dict]:
    entries: list[dict] = []
    for features_root in [root / "features", root / "docs" / "features"]:
        if not features_root.exists():
            continue
        for feature_path in sorted(features_root.rglob("feature.yaml")):
            try:
                data = yaml.safe_load(feature_path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            if isinstance(data, dict) and (data.get("featureId") or data.get("feature_id") or data.get("id")):
                entries.append(feature_entry_from_yaml(feature_path.resolve(strict=False), data))
    return entries


def discover_feature_yaml_across_roots(governance_repo: Path, feature_id: str, workspace_root: str | None = None) -> Path | None:
    candidate_roots = [governance_repo]
    if workspace_root:
        candidate_roots.append(Path(workspace_root))
    candidate_roots.append(Path.cwd())

    seen: set[str] = set()
    for root in candidate_roots:
        resolved_root = root.resolve(strict=False)
        key = str(resolved_root)
        if key in seen:
            continue
        seen.add(key)
        found = discover_feature_yaml_by_id(resolved_root, feature_id)
        if found is not None:
            return found
    return None


def collect_doc_files(root: Path) -> list[str]:
    if not root.exists() or not root.is_dir():
        return []
    return [
        str(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in CONTEXT_DOC_SUFFIXES
    ]


def collect_feature_context_paths(governance_repo: str, entry: dict, depth: str) -> list[str]:
    feature_dir = feature_dir_from_entry(governance_repo, entry)
    summary = feature_dir / "summary.md"
    if depth in {"summary", "summaries"}:
        return [str(summary)] if summary.exists() else []

    paths: list[str] = []
    feature_yaml = feature_dir / "feature.yaml"
    if feature_yaml.exists():
        paths.append(str(feature_yaml))
    paths.extend(collect_doc_files(feature_dir / "docs"))
    return unique_paths(paths)


def collect_service_context_paths(
    governance_repo: str,
    service_name: str,
    exclude_feature_id: str,
    domain: str | None = None,
) -> list[str]:
    features_root = Path(governance_repo) / "features"
    if not features_root.exists():
        return []

    search_domains = [domain] if domain else [path.name for path in sorted(features_root.iterdir()) if path.is_dir()]
    matches: list[str] = []
    for domain_name in search_domains:
        if not domain_name:
            continue
        service_dir = features_root / domain_name / service_name
        if not service_dir.is_dir():
            continue

        service_yaml = service_dir / "service.yaml"
        if service_yaml.exists():
            matches.append(str(service_yaml))
        matches.extend(collect_doc_files(service_dir / "docs"))

        for summary_path in sorted(service_dir.glob("*/summary.md")):
            if summary_path.parent.name != exclude_feature_id:
                matches.append(str(summary_path))

    return unique_paths(matches)


def normalize_lookup_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return f" {normalized} " if normalized else ""


def available_service_names(governance_repo: str, features: list[dict], domain: str | None = None) -> list[str]:
    names: set[str] = set()
    features_root = Path(governance_repo) / "features"

    if features_root.exists():
        pattern = f"{domain}/*/service.yaml" if domain else "*/*/service.yaml"
        for service_yaml in sorted(features_root.glob(pattern)):
            if service_yaml.is_file():
                names.add(service_yaml.parent.name.lower())

    for feature in features:
        feature_domain = str(feature.get("domain") or "").strip().lower()
        if domain and feature_domain != domain.lower():
            continue
        service_name = str(feature.get("service") or "").strip().lower()
        if service_name:
            names.add(service_name)

    return sorted(names)


def detect_service_refs_from_texts(texts: list[str], candidate_services: list[str]) -> list[str]:
    haystacks = [normalize_lookup_text(text) for text in texts]
    haystacks = [text for text in haystacks if text]
    if not haystacks:
        return []

    detected: list[str] = []
    for service_name in candidate_services:
        service_key = service_name.lower()
        needle = normalize_lookup_text(service_key)
        if not needle:
            continue

        cue_matches = [
            f" {service_key} service ",
            f" service {service_key} ",
            f" {service_key} svc ",
            f" svc {service_key} ",
            f" {service_key} api ",
            f" api {service_key} ",
        ]
        has_cue_match = any(any(cue in haystack for cue in cue_matches) for haystack in haystacks)
        has_bare_match = any(needle in haystack for haystack in haystacks)

        if has_cue_match or (has_bare_match and service_key not in AMBIGUOUS_SERVICE_NAMES):
            detected.append(service_name)

    return unique_paths(detected)


def is_same_path(first: str, second: str) -> bool:
    try:
        return Path(first).resolve() == Path(second).resolve()
    except OSError:
        return os.path.abspath(first) == os.path.abspath(second)


def resolve_control_repo_for_feature(control_repo: str | None, governance_repo: str) -> str | None:
    if not control_repo:
        return None
    if is_same_path(control_repo, governance_repo):
        return None
    return control_repo


def ensure_git_worktree(repo: str) -> None:
    result = subprocess.run(
        git_command_argv(repo, ["rev-parse", "--is-inside-work-tree"]),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise RuntimeError(f"{repo} is not a git worktree")


def git_current_branch(repo: str) -> str:
    result = subprocess.run(
        git_command_argv(repo, ["rev-parse", "--abbrev-ref", "HEAD"]),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        msg = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"{git_command_text(repo, ['rev-parse', '--abbrev-ref', 'HEAD'])} failed: {msg}")
    return result.stdout.strip() or "HEAD"


def git_branch_exists(repo: str, branch: str, *, include_remote: bool = False) -> bool:
    result = subprocess.run(
        git_command_argv(repo, ["branch", "--list", branch]),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    if result.stdout.strip():
        return True
    if not include_remote:
        return False
    result = subprocess.run(
        git_command_argv(repo, ["branch", "-r", "--list", f"origin/{branch}"]),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def worktree_has_local_changes(repo: str) -> bool:
    result = subprocess.run(git_command_argv(repo, ["status", "--short"]), capture_output=True, text=True)
    if result.returncode != 0:
        msg = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"{git_command_text(repo, ['status', '--short'])} failed: {msg}")
    return bool(result.stdout.strip())


def ensure_clean_worktree(repo: str) -> None:
    if worktree_has_local_changes(repo):
        raise RuntimeError("Governance repo has local changes. Commit or stash before --execute-governance-git.")


def auto_commit_local_changes(repo: str) -> None:
    run_git(repo, ["add", "-A"])
    diff_result = subprocess.run(
        git_command_argv(repo, ["diff", "--cached", "--quiet"]),
        capture_output=True,
        text=True,
    )
    if diff_result.returncode == 0:
        raise RuntimeError("Governance repo has local changes, but none could be staged for commit.")
    if diff_result.returncode != 1:
        output = (diff_result.stderr or diff_result.stdout).strip() or f"exit code {diff_result.returncode}"
        raise RuntimeError(f"{git_command_text(repo, ['diff', '--cached', '--quiet'])} failed: {output}")
    run_git(repo, ["commit", "-m", GOVERNANCE_AUTO_SYNC_COMMIT_MESSAGE])


def current_head_sha(repo: str) -> str | None:
    result = subprocess.run(git_command_argv(repo, ["rev-parse", "HEAD"]), capture_output=True, text=True)
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha if sha else None


def sync_governance_main(governance_repo: str) -> None:
    ensure_git_worktree(governance_repo)
    active_branch = git_current_branch(governance_repo)
    has_local_changes = worktree_has_local_changes(governance_repo)

    if has_local_changes and active_branch != "main":
        raise RuntimeError(
            f"Governance repo has local changes on branch '{active_branch}'. "
            "Switch to main or clean the repo before --execute-governance-git."
        )

    if active_branch != "main":
        run_git(governance_repo, ["checkout", "main"])

    if has_local_changes:
        auto_commit_local_changes(governance_repo)

    run_git(governance_repo, ["pull", "--rebase", "--autostash", "origin", "main"])


def atomic_write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.dump(data, handle, default_flow_style=False, sort_keys=False, allow_unicode=True)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def write_context_yaml(personal_folder: str, domain: str, source: str, service: str | None = None) -> Path:
    context_path = Path(personal_folder) / "context.yaml"
    context_data = {
        "domain": domain,
        "service": service,
        "updated_at": now_iso(),
        "updated_by": source,
    }
    atomic_write_yaml(context_path, context_data)
    return context_path


def make_domain_yaml(domain: str, name: str, username: str, timestamp: str) -> dict:
    return {
        "kind": "domain",
        "id": domain,
        "name": name,
        "domain": domain,
        "status": "active",
        "owner": username,
        "created": timestamp,
        "updated": timestamp,
    }


def make_domain_constitution_md(domain: str, name: str) -> str:
    return (
        "---\n"
        f"permitted_tracks: {lifecycle_track_flow()}\n"
        "required_artifacts:\n"
        "  planning:\n"
        "    - business-plan\n"
        "  dev:\n"
        "    - stories\n"
        "gate_mode: informational\n"
        "sensing_gate_mode: informational\n"
        "additional_review_participants: []\n"
        "enforce_stories: true\n"
        "enforce_review: true\n"
        "---\n"
        "\n"
        f"# {domain} Domain Constitution\n"
        "\n"
        "## Scope\n"
        "\n"
        f"This constitution governs all features under the `{domain}` domain.\n"
        "\n"
        "## Tracks\n"
        "\n"
        "All tracks listed in `permitted_tracks` are available for features in this domain.\n"
        "\n"
        "## Artifacts\n"
        "\n"
        "Planning artifacts and development artifacts listed in `required_artifacts` are required for features in this domain.\n"
        "\n"
        "## Review\n"
        "\n"
        "Reviews are `informational`. Sensing is `informational`.\n"
        "\n"
        "## Notes\n"
        "\n"
        "This is an auto-generated default constitution. Edit this file to add domain-specific governance rules.\n"
    )


def build_container_git_steps(paths: list[str], commit_message: str) -> list[list[str]]:
    add_args = ["add", *paths]
    return [
        ["checkout", "main"],
        ["pull", "--rebase", "--autostash", "origin", "main"],
        add_args,
        ["commit", "-m", commit_message],
        ["push", "origin", "main"],
    ]


def build_container_result_fields(
    governance_git_commands: list[str],
    workspace_git_commands: list[str],
    governance_git_executed: bool = False,
    governance_commit_sha: str | None = None,
    workspace_git_executed: bool = False,
) -> dict:
    all_git_commands = [*governance_git_commands, *workspace_git_commands]
    if governance_git_executed and workspace_git_executed:
        remaining_git_commands: list[str] = []
    else:
        remaining_git_commands = workspace_git_commands if governance_git_executed else all_git_commands
    return {
        "git_commands": all_git_commands,
        "governance_git_commands": governance_git_commands,
        "workspace_git_commands": workspace_git_commands,
        "remaining_git_commands": remaining_git_commands,
        "governance_git_executed": governance_git_executed,
        "governance_commit_sha": governance_commit_sha,
        "workspace_git_executed": workspace_git_executed,
    }


def related_service_clone_container_path(domain: str, service: str) -> str:
    return f"TargetProjects/{domain}/{service}"


def related_service_clone_path(domain: str, service: str) -> str:
    return f"{related_service_clone_container_path(domain, service)}/<repo-name>"


def related_service_clone_guidance(domain: str, service: str) -> str:
    container_path = related_service_clone_container_path(domain, service)
    example_path = related_service_clone_path(domain, service)
    return (
        "Before running /new-feature, clone each related service repository into its own "
        f"repo-named subfolder under {container_path} (for example {example_path})."
    )


def build_workspace_scaffold_batches(
    scaffold_entries: list[tuple[str, str]],
    scope: str,
    identifier: str,
) -> list[tuple[str, list[list[str]]]]:
    grouped: dict[str, list[str]] = {}
    for workspace_root, rel_path in scaffold_entries:
        grouped.setdefault(workspace_root, []).append(rel_path)

    batches: list[tuple[str, list[list[str]]]] = []
    for workspace_root, rel_paths in grouped.items():
        unique_rel_paths = unique_paths(rel_paths)
        noun = "folder" if len(unique_rel_paths) == 1 else "folders"
        add_args = ["add"]
        if any(Path(rel_path).parts[:1] == ("TargetProjects",) for rel_path in unique_rel_paths):
            add_args.append("--force")
        add_args.extend(unique_rel_paths)
        batches.append(
            (
                workspace_root,
                [
                    add_args,
                    ["commit", "-m", f"scaffold({scope}): add {identifier} {noun}", "--only", "--", *unique_rel_paths],
                    ["push"],
                ],
            )
        )
    return batches


def build_workspace_scaffold_commands(
    scaffold_entries: list[tuple[str, str]],
    scope: str,
    identifier: str,
) -> list[str]:
    commands: list[str] = []
    for workspace_root, steps in build_workspace_scaffold_batches(scaffold_entries, scope, identifier):
        commands.extend(git_command_text(workspace_root, step) for step in steps)
    return commands


def execute_workspace_scaffold_git(
    scaffold_entries: list[tuple[str, str]],
    scope: str,
    identifier: str,
) -> None:
    for workspace_root, steps in build_workspace_scaffold_batches(scaffold_entries, scope, identifier):
        ensure_git_worktree(workspace_root)
        for step in steps:
            run_git(workspace_root, step)


def resolve_personal_folder(args: argparse.Namespace) -> Path:
    if args.personal_folder:
        return Path(args.personal_folder).expanduser().resolve()
    env_value = os.environ.get("LENS_PERSONAL_FOLDER")
    if env_value:
        return Path(env_value).expanduser().resolve()
    return (Path.cwd() / ".lens" / "personal").resolve()


def cmd_create_domain(args: argparse.Namespace) -> dict:
    domain = args.domain
    name = args.name if args.name else domain
    username = args.username if args.username else ""
    governance_repo = args.governance_repo

    try:
        validate_safe_id(domain)
    except ValueError as exc:
        return {"status": "fail", "scope": "domain", "dry_run": bool(args.dry_run), "error": str(exc)}

    gov_path = Path(governance_repo)
    if not gov_path.is_dir():
        return {
            "status": "fail",
            "scope": "domain",
            "dry_run": bool(args.dry_run),
            "error": f"Governance repo not found: {governance_repo}",
        }

    marker_path = gov_path / "features" / domain / "domain.yaml"
    constitution_path = gov_path / "constitutions" / domain / "constitution.md"
    marker_paths = [marker_path.relative_to(gov_path).as_posix()]
    constitution_paths = [constitution_path.relative_to(gov_path).as_posix()]

    tp_gitkeep_path: Path | None = None
    workspace_scaffold_entries: list[tuple[str, str]] = []
    if args.target_projects_root:
        target_projects_root = Path(args.target_projects_root)
        tp_gitkeep_path = target_projects_root / domain / ".gitkeep"
        workspace_scaffold_entries.append(
            (str(target_projects_root.parent), (Path(target_projects_root.name) / domain / ".gitkeep").as_posix())
        )

    docs_gitkeep_path: Path | None = None
    if args.docs_root:
        docs_root = Path(args.docs_root)
        docs_gitkeep_path = docs_root / domain / ".gitkeep"
        workspace_scaffold_entries.append(
            (str(docs_root.parent), (Path(docs_root.name) / domain / ".gitkeep").as_posix())
        )

    personal_folder = resolve_personal_folder(args)
    context_path = str((personal_folder / "context.yaml"))

    gov_paths = marker_paths + constitution_paths
    gov_steps = build_container_git_steps(gov_paths, f"feat(domain): add {domain} container")
    governance_git_commands = [git_command_text(governance_repo, step) for step in gov_steps]
    workspace_git_commands = build_workspace_scaffold_commands(workspace_scaffold_entries, "domain", domain)

    if args.execute_governance_git and not args.dry_run:
        try:
            sync_governance_main(governance_repo)
        except RuntimeError as exc:
            return {
                "status": "fail",
                "scope": "domain",
                "dry_run": False,
                "error": f"Governance git preflight failed: {exc}",
                **build_container_result_fields(governance_git_commands, workspace_git_commands),
            }

    if marker_path.exists():
        return {
            "status": "fail",
            "scope": "domain",
            "dry_run": bool(args.dry_run),
            "error": f"Domain '{domain}' already exists at {marker_path}",
        }

    if args.dry_run:
        return {
            "status": "pass",
            "dry_run": True,
            "scope": "domain",
            "path": str(marker_path),
            "constitution_path": str(constitution_path),
            "created_marker_paths": marker_paths,
            "created_constitution_paths": constitution_paths,
            "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
            "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
            "context_path": context_path,
            "related_service_clone_path": None,
            "related_service_clone_guidance": None,
            "error": None,
            **build_container_result_fields(governance_git_commands, workspace_git_commands),
        }

    timestamp = now_iso()

    try:
        atomic_write_yaml(marker_path, make_domain_yaml(domain, name, username, timestamp))
    except OSError as exc:
        return {"status": "fail", "scope": "domain", "dry_run": False, "error": f"Failed to write domain marker: {exc}"}

    try:
        constitution_path.parent.mkdir(parents=True, exist_ok=True)
        constitution_path.write_text(make_domain_constitution_md(domain, name), encoding="utf-8")
    except (OSError, RuntimeError) as exc:
        return {
            "status": "fail",
            "scope": "domain",
            "dry_run": False,
            "error": f"Failed to write domain constitution: {exc}",
        }

    if tp_gitkeep_path is not None:
        try:
            tp_gitkeep_path.parent.mkdir(parents=True, exist_ok=True)
            tp_gitkeep_path.touch()
        except OSError as exc:
            return {
                "status": "fail",
                "scope": "domain",
                "dry_run": False,
                "error": f"Failed to scaffold TargetProjects domain folder: {exc}",
            }

    if docs_gitkeep_path is not None:
        try:
            docs_gitkeep_path.parent.mkdir(parents=True, exist_ok=True)
            docs_gitkeep_path.touch()
        except OSError as exc:
            return {
                "status": "fail",
                "scope": "domain",
                "dry_run": False,
                "error": f"Failed to scaffold docs domain folder: {exc}",
            }

    try:
        written_context_path = str(write_context_yaml(str(personal_folder), domain, "new-domain"))
    except OSError as exc:
        return {"status": "fail", "scope": "domain", "dry_run": False, "error": f"Failed to write context.yaml: {exc}"}

    governance_commit_sha: str | None = None
    governance_git_executed = False
    workspace_git_executed = False
    if args.execute_governance_git:
        try:
            for step in gov_steps[2:]:
                run_git(governance_repo, step)
            governance_commit_sha = current_head_sha(governance_repo)
            governance_git_executed = True
            if workspace_scaffold_entries:
                execute_workspace_scaffold_git(workspace_scaffold_entries, "domain", domain)
                workspace_git_executed = True
        except RuntimeError as exc:
            return {
                "status": "fail",
                "scope": "domain",
                "dry_run": False,
                "path": str(marker_path),
                "constitution_path": str(constitution_path),
                "created_marker_paths": marker_paths,
                "created_constitution_paths": constitution_paths,
                "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
                "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
                "context_path": written_context_path,
                "error": f"Governance git execution failed: {exc}",
                **build_container_result_fields(
                    governance_git_commands,
                    workspace_git_commands,
                    governance_commit_sha=current_head_sha(governance_repo),
                    governance_git_executed=governance_git_executed,
                    workspace_git_executed=workspace_git_executed,
                ),
            }

    return {
        "status": "pass",
        "dry_run": False,
        "scope": "domain",
        "path": str(marker_path),
        "constitution_path": str(constitution_path),
        "created_marker_paths": marker_paths,
        "created_constitution_paths": constitution_paths,
        "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
        "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
        "context_path": written_context_path,
        "related_service_clone_path": None,
        "related_service_clone_guidance": None,
        "error": None,
        **build_container_result_fields(
            governance_git_commands,
            workspace_git_commands,
            governance_git_executed=governance_git_executed,
            governance_commit_sha=governance_commit_sha,
            workspace_git_executed=workspace_git_executed,
        ),
    }


# ---------------------------------------------------------------------------
# NS-4: Service marker and constitution builders
# ADR-3 delegation boundary: create-service calls create-domain helpers
# (make_domain_yaml, make_domain_constitution_md) for parent domain creation.
# There is exactly one code path that writes domain.yaml — owned by those helpers.
# ---------------------------------------------------------------------------


def get_service_marker_path(gov_path: Path, domain: str, service: str) -> Path:
    return gov_path / "features" / domain / service / "service.yaml"


def get_service_constitution_path(gov_path: Path, domain: str, service: str) -> Path:
    return gov_path / "constitutions" / domain / service / "constitution.md"


def make_service_yaml(domain: str, service: str, name: str, username: str, timestamp: str) -> dict:
    return {
        "kind": "service",
        "id": f"{domain}-{service}",
        "name": name,
        "domain": domain,
        "service": service,
        "status": "active",
        "owner": username,
        "created": timestamp,
        "updated": timestamp,
    }


def make_service_constitution_md(domain: str, service: str, name: str) -> str:
    display = name or service
    return (
        "---\n"
        f"permitted_tracks: {lifecycle_track_flow()}\n"
        "required_artifacts:\n"
        "  planning:\n"
        "    - business-plan\n"
        "  dev:\n"
        "    - stories\n"
        "gate_mode: informational\n"
        "sensing_gate_mode: informational\n"
        "additional_review_participants: []\n"
        "enforce_stories: true\n"
        "enforce_review: true\n"
        "---\n"
        "\n"
        f"# {display} Service Constitution\n"
        "\n"
        f"This constitution defines governance rules for the **{display}** service "
        f"within the `{domain}` domain.\n"
        "\n"
        "## Scope\n"
        "\n"
        f"Applies to all repositories within the `{domain}/{service}` service.\n"
        "Inherits domain-level constraints and may add further restrictions.\n"
        "\n"
        "## Tracks\n"
        "\n"
        f"All lifecycle tracks are permitted: {lifecycle_track_markdown()}.\n"
        "\n"
        "## Artifacts\n"
        "\n"
        "- **Planning phase:** a `business-plan` is required before promotion to dev.\n"
        "- **Dev phase:** at least one story file must exist before dev work begins.\n"
        "\n"
        "## Review\n"
        "\n"
        "Peer review is enforced for all features in this service.\n"
        "Additional participants may be named at the repo level.\n"
        "\n"
        "## Notes\n"
        "\n"
        "This constitution was initialized with service defaults.\n"
        f"Update it to reflect the specific governance needs of the {display} service.\n"
    )


# ---------------------------------------------------------------------------
# NS-5: create-service command handler
# NS-6: Context writer extended (service param added to write_context_yaml above)
# NS-7: Governance git behavior follows the same create-domain pattern
# ---------------------------------------------------------------------------


def cmd_create_service(args: argparse.Namespace) -> dict:
    # NS-5 AC-4: mutual exclusion guard — no file writes before this check
    if args.dry_run and args.execute_governance_git:
        return {
            "status": "fail",
            "scope": "service",
            "dry_run": True,
            "error": "--dry-run and --execute-governance-git are mutually exclusive.",
        }

    domain = args.domain
    service = args.service
    name = args.name if args.name else service
    username = args.username if args.username else ""
    governance_repo = args.governance_repo

    err = validate_safe_id_field(domain, "domain")
    if err:
        return {"status": "fail", "scope": "service", "dry_run": bool(args.dry_run), "error": err}

    err = validate_safe_id_field(service, "service")
    if err:
        return {"status": "fail", "scope": "service", "dry_run": bool(args.dry_run), "error": err}

    gov_path = Path(governance_repo)
    if not gov_path.is_dir():
        return {
            "status": "fail",
            "scope": "service",
            "dry_run": bool(args.dry_run),
            "error": f"Governance repo not found: {governance_repo}",
        }

    # Service marker and constitution paths
    service_marker_path = get_service_marker_path(gov_path, domain, service)
    service_const_path = get_service_constitution_path(gov_path, domain, service)
    service_marker_paths = [service_marker_path.relative_to(gov_path).as_posix()]
    service_const_paths = [service_const_path.relative_to(gov_path).as_posix()]

    # Domain marker and constitution paths (ADR-3 delegation)
    domain_marker_path = gov_path / "features" / domain / "domain.yaml"
    domain_const_path = gov_path / "constitutions" / domain / "constitution.md"
    domain_marker_rel = domain_marker_path.relative_to(gov_path).as_posix()
    domain_const_rel = domain_const_path.relative_to(gov_path).as_posix()

    parent_domain_absent = not domain_marker_path.exists()
    created_domain_marker = False
    created_domain_constitution = False

    # Scaffold paths
    target_projects_path: Path | None = None
    workspace_scaffold_entries: list[tuple[str, str]] = []
    if args.target_projects_root:
        tp_root = Path(args.target_projects_root)
        target_projects_path = tp_root / domain / service

    docs_gitkeep_path: Path | None = None
    if args.docs_root:
        docs_root = Path(args.docs_root)
        docs_gitkeep_path = docs_root / domain / service / ".gitkeep"
        workspace_scaffold_entries.append(
            (str(docs_root.parent), (Path(docs_root.name) / domain / service / ".gitkeep").as_posix())
        )

    personal_folder = resolve_personal_folder(args)
    context_path = str(personal_folder / "context.yaml")

    # Build governance git paths: domain artifacts first if absent, then service artifacts
    gov_marker_paths = []
    if parent_domain_absent:
        gov_marker_paths.extend([domain_marker_rel, domain_const_rel])
    gov_marker_paths.extend(service_marker_paths + service_const_paths)

    gov_steps = build_container_git_steps(
        gov_marker_paths, f"feat(service): add {domain}/{service} container"
    )
    governance_git_commands = [git_command_text(governance_repo, step) for step in gov_steps]
    workspace_git_commands = build_workspace_scaffold_commands(
        workspace_scaffold_entries, "service", f"{domain}-{service}"
    )

    # NS-7: governance git preflight (validate -> sync -> duplicate check -> write)
    if args.execute_governance_git and not args.dry_run:
        try:
            sync_governance_main(governance_repo)
        except RuntimeError as exc:
            return {
                "status": "fail",
                "scope": "service",
                "dry_run": False,
                "error": f"Governance git preflight failed: {exc}",
                **build_container_result_fields(governance_git_commands, workspace_git_commands),
            }

    if service_marker_path.exists():
        return {
            "status": "fail",
            "scope": "service",
            "dry_run": bool(args.dry_run),
            "error": f"Service '{domain}/{service}' already exists at {service_marker_path}",
        }

    if args.dry_run:
        return {
            "status": "pass",
            "dry_run": True,
            "scope": "service",
            "path": str(service_marker_path),
            "constitution_path": str(service_const_path),
            "created_marker_paths": service_marker_paths,
            "created_constitution_paths": service_const_paths,
            "created_domain_marker": parent_domain_absent,
            "created_domain_constitution": parent_domain_absent,
            "target_projects_path": str(target_projects_path) if target_projects_path else None,
            "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
            "context_path": context_path,
            "related_service_clone_path": related_service_clone_path(domain, service),
            "related_service_clone_guidance": related_service_clone_guidance(domain, service),
            "error": None,
            **build_container_result_fields(governance_git_commands, workspace_git_commands),
        }

    timestamp = now_iso()

    # ADR-3: Auto-establish missing parent domain using create-domain helpers
    if parent_domain_absent:
        domain_name = domain
        try:
            atomic_write_yaml(domain_marker_path, make_domain_yaml(domain, domain_name, username, timestamp))
            created_domain_marker = True
        except OSError as exc:
            return {"status": "fail", "scope": "service", "dry_run": False,
                    "error": f"Failed to write parent domain marker: {exc}"}
        try:
            domain_const_path.parent.mkdir(parents=True, exist_ok=True)
            domain_const_path.write_text(make_domain_constitution_md(domain, domain_name), encoding="utf-8")
            created_domain_constitution = True
        except (OSError, RuntimeError) as exc:
            return {"status": "fail", "scope": "service", "dry_run": False,
                    "error": f"Failed to write parent domain constitution: {exc}"}

    # Write service marker
    try:
        atomic_write_yaml(service_marker_path, make_service_yaml(domain, service, name, username, timestamp))
    except OSError as exc:
        return {"status": "fail", "scope": "service", "dry_run": False,
                "error": f"Failed to write service marker: {exc}"}

    # Write service constitution
    try:
        service_const_path.parent.mkdir(parents=True, exist_ok=True)
        service_const_path.write_text(make_service_constitution_md(domain, service, name), encoding="utf-8")
    except (OSError, RuntimeError) as exc:
        return {"status": "fail", "scope": "service", "dry_run": False,
                "error": f"Failed to write service constitution: {exc}"}

    # Create the service container folder without a tracked placeholder.
    if target_projects_path is not None:
        try:
            target_projects_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"status": "fail", "scope": "service", "dry_run": False,
                    "error": f"Failed to scaffold TargetProjects service folder: {exc}"}

    if docs_gitkeep_path is not None:
        try:
            docs_gitkeep_path.parent.mkdir(parents=True, exist_ok=True)
            docs_gitkeep_path.touch()
        except OSError as exc:
            return {"status": "fail", "scope": "service", "dry_run": False,
                    "error": f"Failed to scaffold docs service folder: {exc}"}

    # NS-6: Write context with service value
    try:
        written_context_path = str(write_context_yaml(str(personal_folder), domain, "new-service", service))
    except OSError as exc:
        return {"status": "fail", "scope": "service", "dry_run": False,
                "error": f"Failed to write context.yaml: {exc}"}

    # NS-7: Execute governance git if requested
    governance_commit_sha: str | None = None
    governance_git_executed = False
    if args.execute_governance_git:
        try:
            for step in gov_steps[2:]:
                run_git(governance_repo, step)
            governance_commit_sha = current_head_sha(governance_repo)
            governance_git_executed = True
        except RuntimeError as exc:
            return {
                "status": "fail",
                "scope": "service",
                "dry_run": False,
                "path": str(service_marker_path),
                "constitution_path": str(service_const_path),
                "created_marker_paths": service_marker_paths,
                "created_constitution_paths": service_const_paths,
                "created_domain_marker": created_domain_marker,
                "created_domain_constitution": created_domain_constitution,
                "target_projects_path": str(target_projects_path) if target_projects_path else None,
                "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
                "context_path": written_context_path,
                "related_service_clone_path": related_service_clone_path(domain, service),
                "related_service_clone_guidance": related_service_clone_guidance(domain, service),
                "error": f"Governance git execution failed: {exc}",
                **build_container_result_fields(
                    governance_git_commands,
                    workspace_git_commands,
                    governance_commit_sha=current_head_sha(governance_repo),
                ),
            }

    return {
        "status": "pass",
        "dry_run": False,
        "scope": "service",
        "path": str(service_marker_path),
        "constitution_path": str(service_const_path),
        "created_marker_paths": service_marker_paths,
        "created_constitution_paths": service_const_paths,
        "created_domain_marker": created_domain_marker,
        "created_domain_constitution": created_domain_constitution,
        "target_projects_path": str(target_projects_path) if target_projects_path else None,
        "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
        "context_path": written_context_path,
        "related_service_clone_path": related_service_clone_path(domain, service),
        "related_service_clone_guidance": related_service_clone_guidance(domain, service),
        "error": None,
        **build_container_result_fields(
            governance_git_commands,
            workspace_git_commands,
            governance_git_executed=governance_git_executed,
            governance_commit_sha=governance_commit_sha,
        ),
    }


def _starting_phase_for_track(track: str) -> str:
    tracks = load_lifecycle().get("tracks") or {}
    track_def = tracks.get(track)
    if not isinstance(track_def, dict):
        raise RuntimeError(
            f"Invalid track: '{track}'. Must be one of: {', '.join(lifecycle_track_names())}."
        )
    start_phase = str(track_def.get("start_phase") or "").strip()
    if not start_phase:
        raise RuntimeError(f"Track '{track}' is missing start_phase in lifecycle.yaml.")
    return start_phase


def make_feature_yaml(
    feature_id: str,
    feature_slug: str,
    domain: str,
    service: str,
    name: str,
    track: str,
    username: str,
    timestamp: str,
    description: str = "",
) -> dict:
    starting_phase = _starting_phase_for_track(track)
    return {
        "name": name,
        "description": description,
        "featureId": feature_id,
        "featureSlug": feature_slug,
        "domain": domain,
        "service": service,
        "phase": starting_phase,
        "track": track,
        "milestones": {
            "businessplan": None,
            "techplan": None,
            "finalizeplan": None,
            "dev-ready": None,
            "dev-complete": None,
        },
        "team": [{"username": username, "role": "lead"}],
        "dependencies": {"depends_on": [], "depended_by": []},
        "target_repos": [],
        "links": {"retrospective": None, "issues": [], "pull_request": None},
        "priority": "medium",
        "created": timestamp,
        "updated": timestamp,
        "phase_transitions": [{"phase": starting_phase, "timestamp": timestamp, "user": username}],
        "docs": {
            "path": f"docs/{domain}/{service}/{feature_id}",
            "governance_docs_path": f"features/{domain}/{service}/{feature_id}/docs",
        },
    }


def make_summary_md(feature_id: str, name: str, starting_phase: str, track: str, timestamp: str) -> str:
    return (
        "---\n"
        f"featureId: {feature_id}\n"
        f"name: {name}\n"
        f"status: {starting_phase}\n"
        f"track: {track}\n"
        f"updated_at: {timestamp}\n"
        "---\n"
        "\n"
        f"# {name}\n"
        "\n"
        "<!-- Auto-generated summary stub. Update when planning begins. -->\n"
    )


def _load_feature_index(gov_path: Path) -> dict:
    index_path = gov_path / "feature-index.yaml"
    if not index_path.exists():
        return {"features": []}
    with index_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if "features" not in data:
        data["features"] = []
    return data


def load_existing_feature_index(gov_path: Path) -> tuple[dict, bool]:
    index_path = gov_path / "feature-index.yaml"
    if not index_path.exists():
        return {"features": []}, False
    return _load_feature_index(gov_path), True


def feature_index_by_id(features: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for feature in features:
        for key in (feature.get("featureId"), feature.get("id")):
            feature_id = str(key or "").strip()
            if feature_id:
                index[feature_id] = feature
    return index


def _feature_index_has_id(index_data: dict, feature_id: str) -> bool:
    for entry in index_data.get("features", []):
        if entry.get("featureId") == feature_id or entry.get("id") == feature_id:
            return True
    return False


def _make_index_entry(
    feature_id: str,
    feature_slug: str,
    domain: str,
    service: str,
    name: str,
    track: str,
    username: str,
    starting_phase: str,
    timestamp: str,
    plan_branch: str,
) -> dict:
    return {
        "featureId": feature_id,
        "id": feature_id,
        "name": name,
        "featureSlug": feature_slug,
        "domain": domain,
        "service": service,
        "status": starting_phase,
        "track": track,
        "owner": username,
        "plan_branch": plan_branch,
        "related_features": {"depends_on": [], "blocks": [], "related": []},
        "created": timestamp,
        "updated_at": timestamp,
        "summary": "",
    }


# ---------------------------------------------------------------------------
# CF-2: create subcommand — initialize a new feature
# ---------------------------------------------------------------------------
def cmd_create(args: argparse.Namespace) -> dict:
    feature_id = args.feature_id
    domain = args.domain
    service = args.service
    name = args.name if args.name else feature_id
    track = args.track
    username = args.username if args.username else ""
    governance_repo = args.governance_repo
    control_repo = resolve_control_repo_for_feature(args.control_repo, governance_repo)
    description = args.description if args.description else ""
    try:
        control_topology = resolve_control_topology(args)
    except ValueError as exc:
        return {"status": "fail", "scope": "feature", "dry_run": bool(args.dry_run), "error": str(exc)}
    control_default_branch = resolve_default_branch(control_repo) if control_repo else "main"
    plan_branch = control_default_branch if control_topology == "flat" else f"{feature_id}-plan"

    if not track:
        try:
            available = ", ".join(lifecycle_track_names())
            track_msg = f"Available tracks from lifecycle.yaml: {available}."
        except RuntimeError as exc:
            track_msg = f"Could not read available tracks from lifecycle.yaml: {exc}"
        return {
            "status": "fail",
            "scope": "feature",
            "dry_run": bool(args.dry_run),
            "error": f"Track must be selected explicitly. {track_msg}",
        }

    try:
        starting_phase = _starting_phase_for_track(track)
    except RuntimeError as exc:
        return {
            "status": "fail",
            "scope": "feature",
            "dry_run": bool(args.dry_run),
            "error": str(exc),
        }

    err = validate_safe_id_field(domain, "domain")
    if err:
        return {"status": "fail", "scope": "feature", "dry_run": bool(args.dry_run), "error": err}

    err = validate_safe_id_field(service, "service")
    if err:
        return {"status": "fail", "scope": "feature", "dry_run": bool(args.dry_run), "error": err}

    err = validate_safe_id_field(feature_id, "feature-id")
    if err:
        return {"status": "fail", "scope": "feature", "dry_run": bool(args.dry_run), "error": err}

    gov_path = Path(governance_repo)
    if not gov_path.is_dir():
        return {
            "status": "fail",
            "scope": "feature",
            "dry_run": bool(args.dry_run),
            "error": f"Governance repo not found: {governance_repo}",
        }

    # Derive feature slug: strip "{domain}-{service}-" prefix if present
    prefix = f"{domain}-{service}-"
    feature_slug = feature_id[len(prefix):] if feature_id.startswith(prefix) else feature_id

    feature_dir = gov_path / "features" / domain / service / feature_id
    feature_yaml_path = feature_dir / "feature.yaml"
    summary_md_path = feature_dir / "summary.md"
    index_path = gov_path / "feature-index.yaml"
    domain_marker_path = gov_path / "features" / domain / "domain.yaml"
    service_marker_path = gov_path / "features" / domain / service / "service.yaml"
    domain_const_path = gov_path / "constitutions" / domain / "constitution.md"
    service_const_path = gov_path / "constitutions" / domain / service / "constitution.md"

    # Build governance git path list (include parent markers if absent)
    gov_rel_paths: list[str] = []
    if not domain_marker_path.exists():
        gov_rel_paths.append(domain_marker_path.relative_to(gov_path).as_posix())
        gov_rel_paths.append(domain_const_path.relative_to(gov_path).as_posix())
    if not service_marker_path.exists():
        gov_rel_paths.append(service_marker_path.relative_to(gov_path).as_posix())
        gov_rel_paths.append(service_const_path.relative_to(gov_path).as_posix())
    gov_rel_paths.extend([
        feature_yaml_path.relative_to(gov_path).as_posix(),
        summary_md_path.relative_to(gov_path).as_posix(),
        index_path.relative_to(gov_path).as_posix(),
    ])

    gov_steps = build_container_git_steps(
        gov_rel_paths, f"feat(feature): add {domain}/{service}/{feature_id}"
    )
    governance_git_commands = [git_command_text(governance_repo, step) for step in gov_steps]

    remaining_commands: list[str] = []
    if control_repo:
        remaining_commands = [
            (
                f"uv run --script {{project-root}}/lens.core/_bmad/lens-work/skills/lens-git-orchestration/"
                f"scripts/git-orchestration-ops.py create-feature-branches "
                f"--governance-repo {shlex.quote(governance_repo)} --repo {shlex.quote(control_repo)} "
                f"--feature-id {shlex.quote(feature_id)} --control-topology {shlex.quote(control_topology)}"
            ),
            (
                f"uv run --script {{project-root}}/lens.core/_bmad/lens-work/skills/lens-switch/"
                f"scripts/switch-ops.py switch "
                f"--governance-repo {shlex.quote(governance_repo)} --feature-id {shlex.quote(feature_id)} --control-repo {shlex.quote(control_repo)}"
            ),
        ]

    # Duplicate detection
    index_data = _load_feature_index(gov_path)
    if _feature_index_has_id(index_data, feature_id):
        return {
            "status": "fail",
            "scope": "feature",
            "dry_run": bool(args.dry_run),
            "error": f"Feature '{feature_id}' already exists in feature-index.yaml.",
        }

    if feature_yaml_path.exists():
        return {
            "status": "exists",
            "scope": "feature",
            "dry_run": bool(args.dry_run),
            "feature_id": feature_id,
            "feature_slug": feature_slug,
            "path": str(feature_yaml_path),
            "error": None,
        }

    if args.dry_run:
        return {
            "status": "pass",
            "dry_run": True,
            "scope": "feature",
            "feature_id": feature_id,
            "feature_slug": feature_slug,
            "control_topology": control_topology,
            "control_default_branch": control_default_branch,
            "plan_branch": plan_branch,
            "domain": domain,
            "service": service,
            "track": track,
            "starting_phase": starting_phase,
            "path": str(feature_yaml_path),
            "summary_path": str(summary_md_path),
            "index_path": str(index_path),
            "error": None,
            **build_container_result_fields(governance_git_commands, []),
            "remaining_commands": remaining_commands,
        }

    if args.execute_governance_git and not args.dry_run:
        try:
            sync_governance_main(governance_repo)
        except RuntimeError as exc:
            return {
                "status": "fail",
                "scope": "feature",
                "dry_run": False,
                "error": f"Governance git preflight failed: {exc}",
                **build_container_result_fields(governance_git_commands, []),
            }

    timestamp = now_iso()

    if not domain_marker_path.exists():
        try:
            atomic_write_yaml(domain_marker_path, make_domain_yaml(domain, domain, username, timestamp))
            domain_const_path.parent.mkdir(parents=True, exist_ok=True)
            domain_const_path.write_text(make_domain_constitution_md(domain, domain), encoding="utf-8")
        except OSError as exc:
            return {"status": "fail", "scope": "feature", "dry_run": False,
                    "error": f"Failed to create domain marker: {exc}"}

    if not service_marker_path.exists():
        try:
            atomic_write_yaml(service_marker_path, make_service_yaml(domain, service, service, username, timestamp))
            service_const_path.parent.mkdir(parents=True, exist_ok=True)
            service_const_path.write_text(make_service_constitution_md(domain, service, service), encoding="utf-8")
        except OSError as exc:
            return {"status": "fail", "scope": "feature", "dry_run": False,
                    "error": f"Failed to create service marker: {exc}"}

    files_written: list[Path] = []

    try:
        atomic_write_yaml(
            feature_yaml_path,
            make_feature_yaml(feature_id, feature_slug, domain, service, name, track, username, timestamp, description),
        )
        files_written.append(feature_yaml_path)
    except OSError as exc:
        return {"status": "fail", "scope": "feature", "dry_run": False,
                "error": f"Failed to write feature.yaml: {exc}"}

    try:
        summary_md_path.parent.mkdir(parents=True, exist_ok=True)
        summary_md_path.write_text(
            make_summary_md(feature_id, name, starting_phase, track, timestamp), encoding="utf-8"
        )
        files_written.append(summary_md_path)
    except OSError as exc:
        return {"status": "fail", "scope": "feature", "dry_run": False,
                "error": f"Failed to write summary.md: {exc}"}

    # Re-read index (timestamp may differ) and append entry
    index_data = _load_feature_index(gov_path)
    new_entry = _make_index_entry(
        feature_id, feature_slug, domain, service, name, track, username, starting_phase, timestamp, plan_branch
    )
    index_data["features"].append(new_entry)
    try:
        atomic_write_yaml(index_path, index_data)
    except OSError as exc:
        # Rollback: remove already-written feature files to avoid partial state
        for written_path in files_written:
            try:
                written_path.unlink()
            except OSError:
                pass
        return {"status": "fail", "scope": "feature", "dry_run": False,
                "error": f"Failed to update feature-index.yaml: {exc}"}

    governance_commit_sha: str | None = None
    governance_git_executed = False
    if args.execute_governance_git and not args.dry_run:
        try:
            for step in gov_steps[2:]:
                run_git(governance_repo, step)
            governance_commit_sha = current_head_sha(governance_repo)
            governance_git_executed = True
        except RuntimeError as exc:
            return {
                "status": "fail",
                "scope": "feature",
                "dry_run": False,
                "feature_id": feature_id,
                "path": str(feature_yaml_path),
                "error": f"Governance git execution failed: {exc}",
                **build_container_result_fields(
                    governance_git_commands, [],
                    governance_commit_sha=current_head_sha(governance_repo),
                ),
            }

    gh_commands: list[str] = []
    planning_pr_followup_commands: list[str] = []
    planning_pr_deferred_reason: str | None = None
    if control_repo:
        if control_topology == "flat":
            planning_pr_deferred_reason = "Planning PR creation is not required for flat control topology."
        else:
            planning_pr_followup_commands = [
                (
                    f"gh pr create --repo {shlex.quote(control_repo)} "
                    f"--head {shlex.quote(f'{feature_id}-plan')} --base {shlex.quote(feature_id)} "
                    f"--title {shlex.quote(f'[plan] {feature_id} — planning artifacts')} "
                    f"--body {shlex.quote('Auto-created by lens-init-feature')}"
                )
            ]
            planning_pr_deferred_reason = (
                "Planning PR creation is deferred until the plan branch contains planning commits."
            )

    return {
        "status": "pass",
        "dry_run": False,
        "scope": "feature",
        "feature_id": feature_id,
        "feature_slug": feature_slug,
        "control_topology": control_topology,
        "control_default_branch": control_default_branch,
        "plan_branch": plan_branch,
        "domain": domain,
        "service": service,
        "track": track,
        "starting_phase": starting_phase,
        "recommended_command": "/next",
        "router_command": "/next",
        "planning_pr_created": False,
        "gh_commands": gh_commands,
        "planning_pr_followup_commands": planning_pr_followup_commands,
        "planning_pr_deferred_reason": planning_pr_deferred_reason,
        "path": str(feature_yaml_path),
        "summary_path": str(summary_md_path),
        "index_path": str(index_path),
        "index_updated": True,
        "error": None,
        **build_container_result_fields(
            governance_git_commands, [],
            governance_git_executed=governance_git_executed,
            governance_commit_sha=governance_commit_sha,
        ),
        "remaining_commands": remaining_commands,
    }


def cmd_read_context(args: argparse.Namespace) -> dict:
    context_path = Path(args.personal_folder) / "context.yaml"
    if not context_path.exists():
        return {
            "status": "fail",
            "error": "context_missing",
            "path": str(context_path),
        }

    try:
        data = yaml.safe_load(context_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return {"status": "fail", "error": f"Failed to read context.yaml: {exc}", "path": str(context_path)}

    return {
        "status": "pass",
        "domain": data.get("domain"),
        "service": data.get("service"),
        "updated_at": data.get("updated_at"),
        "updated_by": data.get("updated_by"),
        "path": str(context_path),
    }


def cmd_fetch_context(args: argparse.Namespace) -> dict:
    gov_path = Path(args.governance_repo)
    if not gov_path.is_dir():
        return {"status": "fail", "error": f"Governance repo not found: {args.governance_repo}"}

    target_feature_path = discover_feature_yaml_across_roots(
        gov_path,
        args.feature_id,
        getattr(args, "workspace_root", None),
    )
    if target_feature_path is None:
        return {"status": "fail", "error": f"Feature '{args.feature_id}' feature.yaml not found"}

    try:
        feature_data = yaml.safe_load(target_feature_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return {"status": "fail", "error": f"Failed to read feature.yaml: {exc}"}
    if not isinstance(feature_data, dict):
        return {"status": "fail", "error": f"feature.yaml for '{args.feature_id}' must contain a YAML mapping"}

    try:
        index_data, index_exists = load_existing_feature_index(gov_path)
    except (OSError, yaml.YAMLError) as exc:
        return {"status": "fail", "error": f"Failed to read feature-index.yaml: {exc}"}

    indexed_features = index_data.get("features") or [] if index_exists else []
    if not isinstance(indexed_features, list):
        return {"status": "fail", "error": "feature-index.yaml features must be a list"}

    discovered_features = discover_feature_entries(gov_path)
    workspace_root = getattr(args, "workspace_root", None)
    if workspace_root:
        discovered_features.extend(discover_feature_entries(Path(workspace_root)))
    discovered_features.extend(discover_feature_entries(Path.cwd()))

    features_by_id = feature_index_by_id(indexed_features)
    for feature in discovered_features:
        current_id = feature_entry_id(feature)
        if current_id and current_id not in features_by_id:
            features_by_id[current_id] = feature
    target = features_by_id.get(args.feature_id) or feature_entry_from_yaml(target_feature_path, feature_data)
    features = list(features_by_id.values())

    depth = "summaries" if args.depth == "summary" else args.depth
    target_domain = str(feature_data.get("domain") or target.get("domain") or "").strip().lower()
    target_service = str(feature_data.get("service") or target.get("service") or "").strip().lower()
    target_id = feature_entry_id(target)

    dependencies = feature_data.get("dependencies") or {}
    related_features = feature_data.get("related_features") or target.get("related_features") or {}
    depends_on_ids = list(dependencies.get("depends_on") or related_features.get("depends_on") or feature_data.get("depends_on") or [])
    blocks_ids = list(dependencies.get("blocks") or related_features.get("blocks") or feature_data.get("blocks") or [])
    related_ids = list(related_features.get("related") or feature_data.get("related_to") or [])

    if target_domain:
        related = [
            feature
            for feature in features
            if str(feature.get("domain") or "").strip().lower() == target_domain
            and feature_entry_id(feature) != target_id
        ]
    else:
        related = [features_by_id[feature_id] for feature_id in related_ids if feature_id in features_by_id]
    depends_on = [features_by_id[feature_id] for feature_id in depends_on_ids if feature_id in features_by_id]
    blocks = [features_by_id[feature_id] for feature_id in blocks_ids if feature_id in features_by_id]

    explicit_service_refs = unique_paths([
        service.strip().lower()
        for service in getattr(args, "service_ref", [])
        if service.strip()
    ])
    service_ref_texts = [text.strip() for text in getattr(args, "service_ref_text", []) if text.strip()]
    candidate_services = [
        service_name
        for service_name in available_service_names(str(gov_path), features, target_domain)
        if service_name != target_service
    ]
    detected_service_refs = detect_service_refs_from_texts(service_ref_texts, candidate_services)
    service_refs = unique_paths(explicit_service_refs + detected_service_refs)

    related_paths: list[str] = []
    dependency_paths: list[str] = []
    blocking_paths: list[str] = []
    for feature in related:
        related_paths.extend(collect_feature_context_paths(str(gov_path), feature, "summaries"))
    for feature in depends_on:
        dependency_paths.extend(collect_feature_context_paths(str(gov_path), feature, "full"))
    for feature in blocks:
        blocking_paths.extend(collect_feature_context_paths(str(gov_path), feature, "full"))

    if depth == "full":
        for feature in related:
            related_paths.extend(collect_feature_context_paths(str(gov_path), feature, "full"))

    service_context_paths: list[str] = []
    missing_service_refs: list[str] = []
    for service_name in service_refs:
        matched_paths = collect_service_context_paths(str(gov_path), service_name, target_id, target_domain)
        if matched_paths:
            service_context_paths.extend(matched_paths)
        else:
            missing_service_refs.append(service_name)

    summaries = unique_paths(related_paths)
    full_docs = unique_paths(dependency_paths + blocking_paths + service_context_paths)
    flat_context_paths = unique_paths(summaries + full_docs)

    return {
        "status": "pass",
        "feature_id": args.feature_id,
        "depth": depth,
        "related": [feature_entry_id(feature) for feature in related],
        "depends_on": [feature_entry_id(feature) for feature in depends_on],
        "blocks": [feature_entry_id(feature) for feature in blocks],
        "service_refs": service_refs,
        "detected_service_refs": detected_service_refs,
        "missing_service_refs": missing_service_refs,
        "summaries": summaries,
        "full_docs": full_docs,
        "context_paths": flat_context_paths,
        "relationship_context_paths": {
            "related": unique_paths(related_paths),
            "depends_on": unique_paths(dependency_paths),
            "blocks": unique_paths(blocking_paths),
            "services": unique_paths(service_context_paths),
        },
        "service_context_paths": unique_paths(service_context_paths),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lens init-feature ops")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_domain = subparsers.add_parser("create-domain", help="Create a governance domain")
    create_domain.add_argument("--governance-repo", required=True)
    create_domain.add_argument("--domain", required=True)
    create_domain.add_argument("--name")
    create_domain.add_argument("--username", default="")
    create_domain.add_argument("--target-projects-root")
    create_domain.add_argument("--docs-root")
    create_domain.add_argument("--personal-folder")
    create_domain.add_argument("--execute-governance-git", action="store_true")
    create_domain.add_argument("--dry-run", action="store_true")

    create_service = subparsers.add_parser("create-service", help="Create a governance service container")
    create_service.add_argument("--governance-repo", required=True)
    create_service.add_argument("--domain", required=True)
    create_service.add_argument("--service", required=True)
    create_service.add_argument("--name")
    create_service.add_argument("--username", default="")
    create_service.add_argument("--target-projects-root")
    create_service.add_argument("--docs-root")
    create_service.add_argument("--personal-folder")
    create_service.add_argument("--execute-governance-git", action="store_true")
    create_service.add_argument("--dry-run", action="store_true")

    create = subparsers.add_parser("create", help="Initialize a new feature")
    create.add_argument("--governance-repo", required=True)
    create.add_argument(
        "--control-repo",
        help="Separate control repo for feature branches; omitted or governance-equivalent values skip branch activation commands.",
    )
    create.add_argument("--feature-id", required=True)
    create.add_argument("--domain", required=True)
    create.add_argument("--service", required=True)
    create.add_argument("--name")
    create.add_argument("--description", default="")
    create.add_argument("--track")
    create.add_argument("--username", default="")
    create.add_argument("--control-topology", choices=CONTROL_TOPOLOGIES, default=None)
    create.add_argument("--execute-governance-git", action="store_true")
    create.add_argument("--dry-run", action="store_true")

    read_context = subparsers.add_parser("read-context", help="Read active domain/service context")
    read_context.add_argument("--personal-folder", required=True)

    fetch_context = subparsers.add_parser("fetch-context", help="Fetch cross-feature context")
    fetch_context.add_argument("--governance-repo", required=True)
    fetch_context.add_argument("--workspace-root", help="Control/workspace root for docs/features discovery")
    fetch_context.add_argument("--feature-id", required=True)
    fetch_context.add_argument(
        "--depth",
        default="summaries",
        choices=("summary", "summaries", "full"),
        help="Context depth: summaries (default) or full",
    )
    fetch_context.add_argument("--service-ref", action="append", default=[])
    fetch_context.add_argument("--service-ref-text", action="append", default=[])

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "create":
        result = cmd_create(args)
    elif args.command == "create-domain":
        result = cmd_create_domain(args)
    elif args.command == "create-service":
        result = cmd_create_service(args)
    elif args.command == "read-context":
        result = cmd_read_context(args)
    elif args.command == "fetch-context":
        result = cmd_fetch_context(args)
    else:
        result = {"status": "fail", "error": f"Unsupported command: {args.command}"}

    print(json.dumps(result, indent=2, sort_keys=False))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
