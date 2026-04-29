#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Governance initialization operations for Lens features and containers.

The init-feature workflow creates the 2-branch topology ({featureId} and {featureId}-plan),
writes feature.yaml to the governance repo, registers the feature in feature-index.yaml on main,
and creates a summary.md stub. New features persist a canonical composite featureId and a short
featureSlug so control-repo branches stay globally unique while target-repo working branches can
remain concise. Domain and service container markers and constitutions are also created in the
governance repo. When --target-projects-root is provided, a .gitkeep scaffold file is created
inside the corresponding TargetProjects/{domain}/{service}/ folder. When --docs-root is provided,
a .gitkeep scaffold file is created inside docs/{domain}/{service}/ in the control repo.

Feature, domain, and service init can optionally execute the governance
checkout/pull/add/commit/push sequence directly when --execute-governance-git is provided.
Feature init still returns any remaining control-repo git commands and gh commands for the
caller to execute.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml


FEATURE_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
FEATURE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
VALID_TRACKS = [
    "quickplan",
    "full",
    "feature",
    "hotfix",
    "hotfix-express",
    "express",
    "spike",
    "tech-change",
]
CONTEXT_DOC_SUFFIXES = {".md", ".yaml", ".yml"}
AMBIGUOUS_SERVICE_NAMES = {"api", "auth", "common", "core", "data", "identity"}
LIFECYCLE_PATH = Path(__file__).resolve().parents[3] / "lifecycle.yaml"

# Legacy track names still appear in existing feature.yaml files.
LEGACY_TRACK_ALIASES: dict[str, str] = {
    "quickplan": "feature",
}


def validate_feature_slug(value: str) -> str | None:
    """Validate a local feature slug. Returns error message or None."""
    if not FEATURE_SLUG_PATTERN.match(value):
        return (
            f"Invalid featureId: '{value}'. "
            f"Must match ^[a-z0-9][a-z0-9-]{{0,63}}$ (lowercase alphanumeric and hyphens only)."
        )
    return None


def validate_feature_id(value: str) -> str | None:
    """Validate a canonical featureId. Returns error message or None."""
    if not FEATURE_ID_PATTERN.match(value):
        return (
            f"Invalid featureId: '{value}'. "
            "Must contain only lowercase alphanumeric characters and hyphens."
        )
    return None


def validate_safe_id(value: str, field_name: str) -> str | None:
    """Validate a path-constructing identifier is safe. Returns error message or None."""
    if not SAFE_ID_PATTERN.match(value):
        return (
            f"Invalid {field_name}: '{value}'. "
            f"Must match [a-z0-9][a-z0-9._-]{{0,63}} (lowercase alphanumeric, dots, hyphens, underscores)."
        )
    return None


def normalize_branch_component(value: str) -> str:
    """Normalize a governance-safe identifier into a branch-safe slug component."""
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    normalized = re.sub(r"-+", "-", normalized)
    return normalized


def canonical_feature_prefix(domain: str, service: str) -> str:
    """Return the normalized domain/service prefix used in canonical featureIds."""
    return f"{normalize_branch_component(domain)}-{normalize_branch_component(service)}"


def resolve_feature_identity(requested_feature_id: str, domain: str, service: str) -> tuple[str, str]:
    """Resolve a caller-supplied feature slug or canonical featureId to canonical fields."""
    prefix = canonical_feature_prefix(domain, service)
    canonical_prefix = f"{prefix}-"

    if requested_feature_id.startswith(canonical_prefix):
        feature_slug = requested_feature_id[len(canonical_prefix):]
        err = validate_feature_slug(feature_slug)
        if err is None:
            return requested_feature_id, feature_slug

    err = validate_feature_slug(requested_feature_id)
    if err is None:
        return f"{canonical_prefix}{requested_feature_id}", requested_feature_id

    raise ValueError(
        f"Invalid featureId: '{requested_feature_id}'. Pass either a local feature slug matching "
        "^[a-z0-9][a-z0-9-]{0,63}$ or the canonical featureId "
        f"'{canonical_prefix}<feature-slug>'."
    )


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_command_argv(repo: str, args: list[str]) -> list[str]:
    """Build a git command argv list scoped to a repository."""
    return ["git", "-C", repo, *args]


def git_command_text(repo: str, args: list[str]) -> str:
    """Build a shell-safe git command string scoped to a repository."""
    return shlex.join(git_command_argv(repo, args))


def uv_script_command_text(script_path: Path, args: list[str]) -> str:
    """Build a shell-safe uv command for a frontmatter script."""
    return shlex.join(["uv", "run", "--script", str(script_path), *args])


def run_git(repo: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command and raise a clear error on failure."""
    result = subprocess.run(
        git_command_argv(repo, args),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f"{git_command_text(repo, args)} failed: {output or f'exit code {result.returncode}'}"
        )
    return result


def ensure_git_worktree(repo: str) -> None:
    """Ensure a path is a git worktree before write automation runs."""
    result = subprocess.run(
        git_command_argv(repo, ["rev-parse", "--is-inside-work-tree"]),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise RuntimeError(f"{repo} is not a git worktree")


def ensure_clean_worktree(repo: str) -> None:
    """Fail fast when automatic governance writes would touch a dirty repo."""
    result = subprocess.run(
        git_command_argv(repo, ["status", "--short"]),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f"{git_command_text(repo, ['status', '--short'])} failed: {output or f'exit code {result.returncode}'}"
        )
    if result.stdout.strip():
        raise RuntimeError(
            "Governance repo has local changes. Commit or stash them before using --execute-governance-git."
        )


def current_head_sha(repo: str, short: bool = True) -> str | None:
    """Return the current HEAD SHA, or None when git is unavailable."""
    args = ["rev-parse", "--short", "HEAD"] if short else ["rev-parse", "HEAD"]
    result = subprocess.run(
        git_command_argv(repo, args),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def sync_governance_main(governance_repo: str) -> None:
    """Sync governance main before container writes so duplicate checks see remote state."""
    ensure_git_worktree(governance_repo)
    ensure_clean_worktree(governance_repo)
    run_git(governance_repo, ["checkout", "main"])
    run_git(governance_repo, ["pull", "--rebase", "--autostash", "origin", "main"])


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


def resolve_start_phase(track: str) -> str:
    """Resolve the lifecycle start phase for a selected track."""
    lifecycle = load_lifecycle()
    tracks = lifecycle.get("tracks") or {}
    normalized_track = normalize_track(track, lifecycle)
    track_def = tracks.get(normalized_track)

    if not isinstance(track_def, dict):
        raise RuntimeError(f"Track '{track}' is not defined in lifecycle.yaml")

    start_phase = str(track_def.get("start_phase") or "").strip()
    if not start_phase:
        raise RuntimeError(f"Track '{track}' is missing start_phase in lifecycle.yaml")

    return start_phase


def read_feature_index(governance_repo: str) -> tuple[dict, bool]:
    """Read feature-index.yaml; return (data, exists). Creates empty structure if missing."""
    index_path = Path(governance_repo) / "feature-index.yaml"
    if not index_path.exists():
        return {"features": []}, False
    try:
        with open(index_path) as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        raise RuntimeError(f"Failed to read feature-index.yaml: {e}") from e
    if "features" not in data:
        data["features"] = []
    return data, True


def atomic_write_yaml(path: Path, data: dict) -> None:
    """Write YAML atomically via temp file + rename to prevent corruption."""
    dir_path = path.parent
    dir_path.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def write_context_yaml(personal_folder: str, domain: str, service: str | None, source: str) -> Path:
    """Write context.yaml to the personal folder with the current domain/service.

    This is a local-only file (not git-tracked); it persists the user's active domain/service
    context so that non-feature-branch commands can resolve it without a feature branch.
    """
    context_path = Path(personal_folder) / "context.yaml"
    context_data: dict = {
        "domain": domain,
        "service": service,
        "updated_at": now_iso(),
        "updated_by": source,
    }
    atomic_write_yaml(context_path, context_data)
    return context_path


def make_feature_yaml(
    feature_id: str,
    feature_slug: str,
    domain: str,
    service: str,
    name: str,
    track: str,
    phase: str,
    username: str,
    timestamp: str,
) -> dict:
    """Build the initial feature.yaml data structure."""
    return {
        "name": name,
        "description": "",
        "featureId": feature_id,
        "featureSlug": feature_slug,
        "domain": domain,
        "service": service,
        "phase": phase,
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
        "phase_transitions": [{"phase": phase, "timestamp": timestamp, "user": username}],
        "docs": {
            "path": f"docs/{domain}/{service}/{feature_id}",
            "governance_docs_path": f"features/{domain}/{service}/{feature_id}/docs",
        },
    }


def make_summary_md(
    feature_id: str,
    domain: str,
    service: str,
    name: str,
    phase: str,
    username: str,
    timestamp: str,
) -> str:
    """Build the initial summary.md stub content."""
    return (
        f"# {name}\n\n"
        f"> Status: {phase} | Feature ID: `{feature_id}`\n\n"
        f"Auto-generated stub. Update as planning progresses.\n\n"
        f"**Domain:** {domain}  \n"
        f"**Service:** {service}  \n"
        f"**Owner:** {username}  \n"
        f"**Initialized:** {timestamp}\n"
    )


def make_domain_yaml(domain: str, name: str, username: str, timestamp: str) -> dict:
    """Build the governance marker for a domain container."""
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
    """Build the initial domain-level constitution.md content."""
    display = name or domain
    return (
        "---\n"
        "permitted_tracks: [quickplan, full, hotfix, tech-change]\n"
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
        f"# {display} Domain Constitution\n"
        "\n"
        f"This constitution defines governance rules for the **{display}** domain.\n"
        "\n"
        "## Scope\n"
        "\n"
        f"Applies to all services and repositories within the `{domain}` domain.\n"
        "Lower-level constitutions (service, repo) may add constraints but may not remove those defined here.\n"
        "\n"
        "## Tracks\n"
        "\n"
        "All standard tracks are permitted: `quickplan`, `full`, `hotfix`, `tech-change`.\n"
        "Service-level constitutions may restrict this list further.\n"
        "\n"
        "## Artifacts\n"
        "\n"
        "- **Planning phase:** a `business-plan` is required before promotion to dev.\n"
        "- **Dev phase:** at least one story file must exist before dev work begins.\n"
        "\n"
        "## Review\n"
        "\n"
        "Peer review is enforced for all features in this domain.\n"
        "Additional participants may be named at the service or repo level.\n"
        "\n"
        "## Notes\n"
        "\n"
        "This constitution was initialized with domain defaults.\n"
        "Update it to reflect the specific governance needs of the "
        f"{display} domain.\n"
    )


def make_service_constitution_md(domain: str, service: str, name: str) -> str:
    """Build the initial service-level constitution.md content (inherits from domain)."""
    display = name or service
    return (
        "---\n"
        "permitted_tracks: [quickplan, full, hotfix, tech-change]\n"
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
        f"# {domain} / {display} Service Constitution\n"
        "\n"
        f"Inherits from the `{domain}` domain constitution.\n"
        "Lower-level constitutions (repo) may add constraints but may not remove those defined here.\n"
        "\n"
        "## Scope\n"
        "\n"
        f"Applies to all repositories within the `{service}` service of the `{domain}` domain.\n"
        "\n"
        "## Tracks\n"
        "\n"
        f"Inherits all permitted tracks from the domain: `quickplan`, `full`, `hotfix`, `tech-change`.\n"
        "Repo-level constitutions may restrict this list further.\n"
        "\n"
        "## Artifacts\n"
        "\n"
        "Inherits domain-level artifact requirements:\n"
        "- **Planning phase:** `business-plan`\n"
        "- **Dev phase:** `stories`\n"
        "\n"
        "Add service-specific artifact requirements below as needed.\n"
        "\n"
        "## Review\n"
        "\n"
        "Peer review is enforced. Additional participants may be named at the repo level.\n"
        "\n"
        "## Notes\n"
        "\n"
        "This constitution was initialized with service defaults inherited from the "
        f"`{domain}` domain.\n"
        f"Update it to reflect the specific governance needs of the `{service}` service.\n"
    )


def make_service_yaml(
    domain: str,
    service: str,
    name: str,
    username: str,
    timestamp: str,
) -> dict:
    """Build the governance marker for a service container."""
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


def get_domain_marker_path(governance_repo: str, domain: str) -> Path:
    """Return the canonical governance path for a domain marker."""
    return Path(governance_repo) / "features" / domain / "domain.yaml"


def get_service_marker_path(governance_repo: str, domain: str, service: str) -> Path:
    """Return the canonical governance path for a service marker."""
    return Path(governance_repo) / "features" / domain / service / "service.yaml"


def get_domain_constitution_path(governance_repo: str, domain: str) -> Path:
    """Return the canonical governance path for a domain constitution."""
    return Path(governance_repo) / "constitutions" / domain / "constitution.md"


def get_service_constitution_path(governance_repo: str, domain: str, service: str) -> Path:
    """Return the canonical governance path for a service constitution."""
    return Path(governance_repo) / "constitutions" / domain / service / "constitution.md"


def ensure_container_markers(
    governance_repo: str,
    domain: str,
    service: str,
    username: str,
    timestamp: str,
    dry_run: bool = False,
) -> list[str]:
    """Create missing domain/service governance markers and return created relative paths."""
    created: list[str] = []
    domain_path = get_domain_marker_path(governance_repo, domain)
    service_path = get_service_marker_path(governance_repo, domain, service)

    if not domain_path.exists():
        created.append(str(domain_path.relative_to(governance_repo)))
        if not dry_run:
            atomic_write_yaml(domain_path, make_domain_yaml(domain, domain, username, timestamp))

    if not service_path.exists():
        created.append(str(service_path.relative_to(governance_repo)))
        if not dry_run:
            atomic_write_yaml(
                service_path,
                make_service_yaml(domain, service, service, username, timestamp),
            )

    return created


def unique_paths(paths: list[str]) -> list[str]:
    """Return a stable, de-duplicated list of path strings."""
    seen: set[str] = set()
    ordered: list[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered


def feature_dir_from_entry(governance_repo: str, entry: dict) -> Path:
    """Return the feature directory for an index entry."""
    return Path(governance_repo) / "features" / entry.get("domain", "") / entry.get("service", "") / entry.get("id", "")


def collect_doc_files(root: Path) -> list[str]:
    """Collect supported doc files under a directory in stable order."""
    if not root.exists() or not root.is_dir():
        return []

    collected: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in CONTEXT_DOC_SUFFIXES:
            collected.append(str(path))
    return collected


def collect_feature_context_paths(governance_repo: str, entry: dict) -> list[str]:
    """Collect feature.yaml and any mirrored governance docs for a feature."""
    feature_dir = feature_dir_from_entry(governance_repo, entry)
    paths: list[str] = []

    feature_yaml = feature_dir / "feature.yaml"
    if feature_yaml.exists():
        paths.append(str(feature_yaml))

    docs_dir = feature_dir / "docs"
    paths.extend(collect_doc_files(docs_dir))
    return unique_paths(paths)


def collect_service_context_paths(
    governance_repo: str,
    service_name: str,
    exclude_feature_id: str,
    domain: str | None = None,
) -> list[str]:
    """Collect service-level governance files and child feature summaries for a named service."""
    features_root = Path(governance_repo) / "features"
    if not features_root.exists():
        return []

    matches: list[str] = []
    search_domains: list[str]
    if domain:
        search_domains = [domain]
    else:
        search_domains = [path.name for path in sorted(features_root.iterdir()) if path.is_dir()]

    for domain_name in search_domains:
        service_dir = features_root / domain_name / service_name
        if not service_dir.exists() or not service_dir.is_dir():
            continue

        service_yaml = service_dir / "service.yaml"
        if service_yaml.exists():
            matches.append(str(service_yaml))
        docs_dir = service_dir / "docs"
        matches.extend(collect_doc_files(docs_dir))

        for summary_path in sorted(service_dir.glob("*/summary.md")):
            if summary_path.parent.name != exclude_feature_id:
                matches.append(str(summary_path))

    return unique_paths(matches)


def normalize_lookup_text(value: str) -> str:
    """Normalize freeform text for identifier lookups."""
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return f" {normalized} " if normalized else ""


def available_service_names(governance_repo: str, features: list[dict], domain: str | None = None) -> list[str]:
    """Return known service names from governance markers and feature index entries."""
    names: set[str] = set()
    features_root = Path(governance_repo) / "features"

    if features_root.exists():
        pattern = f"{domain}/*/service.yaml" if domain else "*/*/service.yaml"
        for service_yaml in sorted(features_root.glob(pattern)):
            if service_yaml.is_file():
                names.add(service_yaml.parent.name.lower())

    for feature in features:
        feature_domain = str(feature.get("domain", "")).strip().lower()
        if domain and feature_domain != domain.lower():
            continue
        service_name = str(feature.get("service", "")).strip().lower()
        if service_name:
            names.add(service_name)

    return sorted(names)


def detect_service_refs_from_texts(texts: list[str], candidate_services: list[str]) -> list[str]:
    """Detect known governance service names mentioned in freeform text."""
    haystacks = [normalize_lookup_text(text) for text in texts if normalize_lookup_text(text)]
    if not haystacks:
        return []

    detected: list[str] = []
    for service_name in candidate_services:
        needle = normalize_lookup_text(service_name)
        if not needle:
            continue

        service_key = service_name.lower()
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


def build_control_repo_git_commands(governance_repo: str, control_repo: str | None, feature_id: str) -> list[str]:
    """Return control-repo commands that create the 2-branch topology from the repo default branch."""
    if not control_repo:
        return []

    git_orchestration_script = (
        Path(__file__).resolve().parents[2]
        / "bmad-lens-git-orchestration"
        / "scripts"
        / "git-orchestration-ops.py"
    )
    return [
        uv_script_command_text(
            git_orchestration_script,
            [
                "create-feature-branches",
                "--governance-repo",
                governance_repo,
                "--repo",
                control_repo,
                "--feature-id",
                feature_id,
            ],
        )
    ]


def build_control_repo_activation_commands(
    governance_repo: str,
    control_repo: str | None,
    feature_id: str,
    personal_folder: str | None = None,
) -> list[str]:
    """Return control-repo commands that activate the new feature context on the plan branch."""
    if not control_repo:
        return []

    switch_script = (
        Path(__file__).resolve().parents[2]
        / "bmad-lens-switch"
        / "scripts"
        / "switch-ops.py"
    )
    switch_args = [
        "switch",
        "--governance-repo",
        governance_repo,
        "--feature-id",
        feature_id,
        "--control-repo",
        control_repo,
    ]
    if personal_folder:
        switch_args.extend(["--personal-folder", personal_folder])

    return [uv_script_command_text(switch_script, switch_args)]


def build_feature_governance_rel_paths(
    feature_id: str,
    domain: str,
    service: str,
    container_rel_paths: list[str] | None = None,
) -> list[str]:
    """Return governance-relative paths staged for feature initialization."""
    feature_yaml_rel = f"features/{domain}/{service}/{feature_id}/feature.yaml"
    summary_rel = f"features/{domain}/{service}/{feature_id}/summary.md"
    return [feature_yaml_rel, "feature-index.yaml", summary_rel, *(container_rel_paths or [])]


def build_feature_governance_git_steps(
    feature_id: str,
    domain: str,
    service: str,
    container_rel_paths: list[str] | None = None,
) -> list[list[str]]:
    """Return ordered git argv steps for feature governance artifacts on main."""
    all_paths = build_feature_governance_rel_paths(feature_id, domain, service, container_rel_paths)
    commit_message = f"feat({domain}/{service}): init {feature_id}"
    return build_container_git_steps(all_paths, commit_message)


def build_feature_governance_git_commands(
    governance_repo: str,
    feature_id: str,
    domain: str,
    service: str,
    container_rel_paths: list[str] | None = None,
) -> list[str]:
    """Return ordered governance git commands for feature initialization on main."""
    return [
        git_command_text(governance_repo, step)
        for step in build_feature_governance_git_steps(feature_id, domain, service, container_rel_paths)
    ]


def build_git_commands(
    governance_repo: str,
    control_repo: str | None,
    feature_id: str,
    domain: str,
    service: str,
    container_rel_paths: list[str] | None = None,
) -> list[str]:
    """Return the ordered git commands needed to commit the initialized feature.

    Governance repo stays on main — all artifacts (feature.yaml, summary.md,
    feature-index.yaml, container markers) are committed directly to main.
    The 2-branch topology ({featureId} + {featureId}-plan) only exists in the
    control repo.
    """
    return build_control_repo_git_commands(governance_repo, control_repo, feature_id) + build_feature_governance_git_commands(
        governance_repo,
        feature_id,
        domain,
        service,
        container_rel_paths,
    )


def build_container_git_steps(rel_paths: list[str], commit_message: str) -> list[list[str]]:
    """Return the ordered git argv steps for domain/service markers on main."""
    return [
        ["checkout", "main"],
        ["pull", "--rebase", "--autostash", "origin", "main"],
        ["add", *rel_paths],
        ["commit", "-m", commit_message],
        ["push", "origin", "main"],
    ]


def build_container_git_commands(governance_repo: str, rel_paths: list[str], commit_message: str) -> list[str]:
    """Return the ordered git commands needed to commit domain/service markers on main."""
    return [
        git_command_text(governance_repo, step)
        for step in build_container_git_steps(rel_paths, commit_message)
    ]


def build_container_result_fields(
    governance_git_commands: list[str],
    workspace_git_commands: list[str],
    governance_git_executed: bool = False,
    governance_commit_sha: str | None = None,
) -> dict:
    """Return structured git result fields for container initialization flows."""
    all_git_commands = governance_git_commands + workspace_git_commands
    remaining_git_commands = workspace_git_commands if governance_git_executed else all_git_commands
    return {
        "git_commands": all_git_commands,
        "governance_git_commands": governance_git_commands,
        "workspace_git_commands": workspace_git_commands,
        "remaining_git_commands": remaining_git_commands,
        "governance_git_executed": governance_git_executed,
        "governance_commit_sha": governance_commit_sha,
    }


def build_feature_result_fields(
    governance_git_commands: list[str],
    control_repo_git_commands: list[str],
    control_repo_activation_commands: list[str] | None = None,
    governance_git_executed: bool = False,
    governance_commit_sha: str | None = None,
) -> dict:
    """Return structured git result fields for feature initialization flows."""
    activation_commands = list(control_repo_activation_commands or [])
    all_git_commands = control_repo_git_commands + governance_git_commands
    remaining_git_commands = control_repo_git_commands if governance_git_executed else all_git_commands
    remaining_commands = remaining_git_commands + activation_commands
    return {
        "git_commands": all_git_commands,
        "governance_git_commands": governance_git_commands,
        "control_repo_git_commands": control_repo_git_commands,
        "control_repo_activation_commands": activation_commands,
        "remaining_git_commands": remaining_git_commands,
        "remaining_commands": remaining_commands,
        "governance_git_executed": governance_git_executed,
        "governance_commit_sha": governance_commit_sha,
    }


def build_workspace_scaffold_commands(
    scaffold_entries: list[tuple[str, str]],
    scope: str,
    identifier: str,
) -> list[str]:
    """Return git commands for control-repo scaffold files grouped by workspace root."""
    grouped: dict[str, list[str]] = {}
    for workspace_root, rel_path in scaffold_entries:
        grouped.setdefault(workspace_root, []).append(rel_path)

    cmds: list[str] = []
    for workspace_root, rel_paths in grouped.items():
        unique_rel_paths = unique_paths(rel_paths)
        noun = "folder" if len(unique_rel_paths) == 1 else "folders"
        cmds.extend([
            f"git -C {workspace_root} add {' '.join(unique_rel_paths)}",
            f'git -C {workspace_root} commit -m "scaffold({scope}): add {identifier} {noun}"',
        ])
    return cmds


def build_gh_commands(control_repo: str, feature_id: str, name: str, track: str) -> list[str]:
    """Return the gh CLI commands for PR creation."""
    if track == "express":
        return []

    plan_branch = f"{feature_id}-plan"
    return [
        (
            f"gh pr create --repo {control_repo} "
            f"--head {plan_branch} --base {feature_id} "
            f'--title "Planning: {name}" '
            f'--body "Initialize planning artifacts for {name}"'
        ),
    ]


def cmd_create(args: argparse.Namespace) -> dict:
    """Create feature branches, feature.yaml, PR, feature-index entry, and summary stub."""
    for field_name, value in [("domain", args.domain), ("service", args.service)]:
        err = validate_safe_id(value, field_name)
        if err:
            return {"status": "fail", "error": err}

    try:
        feature_id, feature_slug = resolve_feature_identity(args.feature_id, args.domain, args.service)
    except ValueError as exc:
        return {"status": "fail", "error": str(exc)}

    governance_repo = args.governance_repo
    control_repo = args.control_repo
    domain = args.domain
    service = args.service
    name = args.name
    track = args.track
    username = args.username
    personal_folder = getattr(args, "personal_folder", None)
    execute_governance_git = bool(getattr(args, "execute_governance_git", False))

    if not track:
        return {
            "status": "fail",
            "error": "Track must be selected explicitly. Re-run with --track <track>.",
        }

    try:
        starting_phase = resolve_start_phase(track)
    except RuntimeError as e:
        return {"status": "fail", "error": str(e)}

    recommended_command = f"/{starting_phase}"

    if execute_governance_git and not args.dry_run:
        try:
            sync_governance_main(governance_repo)
        except RuntimeError as e:
            return {
                "status": "fail",
                "featureId": feature_id,
                "featureSlug": feature_slug,
                "starting_phase": starting_phase,
                "recommended_command": recommended_command,
                "router_command": "/next",
                "error": f"Governance git preflight failed: {e}",
            }

    try:
        index_data, _index_exists = read_feature_index(governance_repo)
    except RuntimeError as e:
        return {"status": "fail", "error": str(e)}

    existing_ids = [f.get("id") for f in index_data.get("features", [])]
    if feature_id in existing_ids:
        return {
            "status": "fail",
            "featureId": feature_id,
            "featureSlug": feature_slug,
            "error": f"Feature '{feature_id}' already exists in feature-index.yaml",
        }

    timestamp = now_iso()
    feature_yaml_path = (
        Path(governance_repo) / "features" / domain / service / feature_id / "feature.yaml"
    )
    summary_path = (
        Path(governance_repo) / "features" / domain / service / feature_id / "summary.md"
    )
    index_path = Path(governance_repo) / "feature-index.yaml"
    container_markers = ensure_container_markers(
        governance_repo,
        domain,
        service,
        username,
        timestamp,
        dry_run=args.dry_run,
    )

    # control_repo for git commands: use separately if provided, else None to skip ctrl-repo cmds
    ctrl_for_git = control_repo if (control_repo and control_repo != governance_repo) else None
    pr_repo = control_repo or governance_repo

    control_repo_git_commands = build_control_repo_git_commands(governance_repo, ctrl_for_git, feature_id)
    control_repo_activation_commands = build_control_repo_activation_commands(
        governance_repo,
        ctrl_for_git,
        feature_id,
        personal_folder=personal_folder,
    )
    governance_git_steps = build_feature_governance_git_steps(
        feature_id,
        domain,
        service,
        container_markers,
    )
    governance_git_commands = [git_command_text(governance_repo, step) for step in governance_git_steps]
    gh_cmds = build_gh_commands(pr_repo, feature_id, name, track)

    if args.dry_run:
        return {
            "status": "pass",
            "dry_run": True,
            "featureId": feature_id,
            "featureSlug": feature_slug,
            "starting_phase": starting_phase,
            "recommended_command": recommended_command,
            "router_command": "/next",
            "feature_yaml_path": str(feature_yaml_path),
            "index_updated": True,
            "summary_path": str(summary_path),
            "container_markers": container_markers,
            **build_feature_result_fields(
                governance_git_commands,
                control_repo_git_commands,
                control_repo_activation_commands=control_repo_activation_commands,
            ),
            "gh_commands": gh_cmds,
            "planning_pr_created": bool(gh_cmds),
        }

    feature_data = make_feature_yaml(
        feature_id,
        feature_slug,
        domain,
        service,
        name,
        track,
        starting_phase,
        username,
        timestamp,
    )
    try:
        atomic_write_yaml(feature_yaml_path, feature_data)
    except OSError as e:
        return {"status": "fail", "error": f"Failed to write feature.yaml: {e}"}

    new_entry = {
        "id": feature_id,
        "featureId": feature_id,
        "featureSlug": feature_slug,
        "domain": domain,
        "service": service,
        "status": starting_phase,
        "owner": username,
        # plan_branch refers to the control repo branch, not the governance repo.
        # Governance keeps all artifacts on main.
        "plan_branch": f"{feature_id}-plan",
        "related_features": {"depends_on": [], "blocks": [], "related": []},
        "updated_at": timestamp,
        "summary": "",
    }
    index_data["features"].append(new_entry)
    try:
        atomic_write_yaml(index_path, index_data)
    except OSError as e:
        return {"status": "fail", "error": f"Failed to write feature-index.yaml: {e}"}

    summary_content = make_summary_md(feature_id, domain, service, name, starting_phase, username, timestamp)
    try:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary_content, encoding="utf-8")
    except OSError as e:
        return {"status": "fail", "error": f"Failed to write summary.md: {e}"}

    governance_commit_sha: str | None = None
    governance_git_executed = False
    if execute_governance_git:
        try:
            for step in governance_git_steps[2:]:
                run_git(governance_repo, step)
            governance_commit_sha = current_head_sha(governance_repo)
            governance_git_executed = True
        except RuntimeError as e:
            return {
                "status": "fail",
                "featureId": feature_id,
                "featureSlug": feature_slug,
                "starting_phase": starting_phase,
                "recommended_command": recommended_command,
                "router_command": "/next",
                "feature_yaml_path": str(feature_yaml_path),
                "index_updated": True,
                "summary_path": str(summary_path),
                "container_markers": container_markers,
                "error": f"Governance git execution failed: {e}",
                **build_feature_result_fields(
                    governance_git_commands,
                    control_repo_git_commands,
                    control_repo_activation_commands=control_repo_activation_commands,
                    governance_commit_sha=current_head_sha(governance_repo),
                ),
                "gh_commands": gh_cmds,
                "planning_pr_created": bool(gh_cmds),
            }

    return {
        "status": "pass",
        "featureId": feature_id,
        "featureSlug": feature_slug,
        "starting_phase": starting_phase,
        "recommended_command": recommended_command,
        "router_command": "/next",
        "feature_yaml_path": str(feature_yaml_path),
        "index_updated": True,
        "summary_path": str(summary_path),
        "container_markers": container_markers,
        **build_feature_result_fields(
            governance_git_commands,
            control_repo_git_commands,
            control_repo_activation_commands=control_repo_activation_commands,
            governance_git_executed=governance_git_executed,
            governance_commit_sha=governance_commit_sha,
        ),
        "gh_commands": gh_cmds,
        "planning_pr_created": bool(gh_cmds),
    }


def cmd_create_domain(args: argparse.Namespace) -> dict:
    """Create a governance marker and constitution for a domain container."""
    err = validate_safe_id(args.domain, "domain")
    if err:
        return {"status": "fail", "error": err}

    governance_repo = args.governance_repo
    domain = args.domain
    name = args.name or domain
    username = args.username
    target_projects_root: str | None = getattr(args, "target_projects_root", None)
    docs_root: str | None = getattr(args, "docs_root", None)
    timestamp = now_iso()
    execute_governance_git = bool(getattr(args, "execute_governance_git", False))

    marker_path = get_domain_marker_path(governance_repo, domain)
    constitution_path = get_domain_constitution_path(governance_repo, domain)

    marker_rel = str(marker_path.relative_to(governance_repo))
    constitution_rel = str(constitution_path.relative_to(governance_repo))
    marker_paths = [marker_rel]
    constitution_paths = [constitution_rel]
    gov_paths = marker_paths + constitution_paths

    # Workspace .gitkeep paths when control-repo scaffolds are requested.
    tp_gitkeep_path: Path | None = None
    docs_gitkeep_path: Path | None = None
    workspace_scaffold_entries: list[tuple[str, str]] = []
    if target_projects_root:
        tp_gitkeep_path = Path(target_projects_root) / domain / ".gitkeep"
        workspace_root = str(Path(target_projects_root).parent)
        workspace_scaffold_entries.append((workspace_root, str(tp_gitkeep_path.relative_to(workspace_root))))
    if docs_root:
        docs_gitkeep_path = Path(docs_root) / domain / ".gitkeep"
        docs_workspace_root = str(Path(docs_root).parent)
        workspace_scaffold_entries.append((docs_workspace_root, str(docs_gitkeep_path.relative_to(docs_workspace_root))))

    commit_message = f"feat(domain): add {domain} container"
    governance_git_steps = build_container_git_steps(gov_paths, commit_message)
    governance_git_commands = [git_command_text(governance_repo, step) for step in governance_git_steps]
    workspace_git_commands = (
        build_workspace_scaffold_commands(workspace_scaffold_entries, "domain", domain)
        if workspace_scaffold_entries
        else []
    )

    if execute_governance_git and not args.dry_run:
        try:
            sync_governance_main(governance_repo)
        except RuntimeError as e:
            return {
                "status": "fail",
                "scope": "domain",
                "error": f"Governance git preflight failed: {e}",
                **build_container_result_fields(governance_git_commands, workspace_git_commands),
            }

    if marker_path.exists():
        return {
            "status": "fail",
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
            **build_container_result_fields(governance_git_commands, workspace_git_commands),
        }

    try:
        atomic_write_yaml(marker_path, make_domain_yaml(domain, name, username, timestamp))
    except OSError as e:
        return {"status": "fail", "error": f"Failed to write domain marker: {e}"}

    try:
        constitution_path.parent.mkdir(parents=True, exist_ok=True)
        constitution_path.write_text(make_domain_constitution_md(domain, name), encoding="utf-8")
    except OSError as e:
        return {"status": "fail", "error": f"Failed to write domain constitution: {e}"}

    if tp_gitkeep_path is not None:
        try:
            tp_gitkeep_path.parent.mkdir(parents=True, exist_ok=True)
            tp_gitkeep_path.touch()
        except OSError as e:
            return {"status": "fail", "error": f"Failed to scaffold TargetProjects domain folder: {e}"}

    if docs_gitkeep_path is not None:
        try:
            docs_gitkeep_path.parent.mkdir(parents=True, exist_ok=True)
            docs_gitkeep_path.touch()
        except OSError as e:
            return {"status": "fail", "error": f"Failed to scaffold docs domain folder: {e}"}

    personal_folder: str | None = getattr(args, "personal_folder", None)
    context_path: str | None = None
    if personal_folder:
        try:
            context_path = str(write_context_yaml(personal_folder, domain, None, "new-domain"))
        except OSError as e:
            return {"status": "fail", "error": f"Failed to write context.yaml: {e}"}

    governance_commit_sha: str | None = None
    governance_git_executed = False
    if execute_governance_git:
        try:
            for step in governance_git_steps[2:]:
                run_git(governance_repo, step)
            governance_commit_sha = current_head_sha(governance_repo)
            governance_git_executed = True
        except RuntimeError as e:
            return {
                "status": "fail",
                "scope": "domain",
                "path": str(marker_path),
                "constitution_path": str(constitution_path),
                "created_marker_paths": marker_paths,
                "created_constitution_paths": constitution_paths,
                "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
                "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
                "context_path": context_path,
                "error": f"Governance git execution failed: {e}",
                **build_container_result_fields(
                    governance_git_commands,
                    workspace_git_commands,
                    governance_commit_sha=current_head_sha(governance_repo),
                ),
            }

    result: dict = {
        "status": "pass",
        "scope": "domain",
        "path": str(marker_path),
        "constitution_path": str(constitution_path),
        "created_marker_paths": marker_paths,
        "created_constitution_paths": constitution_paths,
        "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
        "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
        **build_container_result_fields(
            governance_git_commands,
            workspace_git_commands,
            governance_git_executed=governance_git_executed,
            governance_commit_sha=governance_commit_sha,
        ),
    }
    if context_path is not None:
        result["context_path"] = context_path
    return result


def cmd_create_service(args: argparse.Namespace) -> dict:
    """Create governance markers and constitutions for a service container (and parent domain if absent)."""
    err = validate_safe_id(args.domain, "domain")
    if err:
        return {"status": "fail", "error": err}
    err = validate_safe_id(args.service, "service")
    if err:
        return {"status": "fail", "error": err}

    governance_repo = args.governance_repo
    domain = args.domain
    service = args.service
    name = args.name or service
    username = args.username
    target_projects_root: str | None = getattr(args, "target_projects_root", None)
    docs_root: str | None = getattr(args, "docs_root", None)
    timestamp = now_iso()
    execute_governance_git = bool(getattr(args, "execute_governance_git", False))

    service_path = get_service_marker_path(governance_repo, domain, service)
    service_constitution_path = get_service_constitution_path(governance_repo, domain, service)
    domain_constitution_path = get_domain_constitution_path(governance_repo, domain)

    predicted_marker_paths = unique_paths([
        str(get_domain_marker_path(governance_repo, domain).relative_to(governance_repo)),
        str(service_path.relative_to(governance_repo)),
    ])
    predicted_constitution_paths = unique_paths([
        str(domain_constitution_path.relative_to(governance_repo)),
        str(service_constitution_path.relative_to(governance_repo)),
    ])

    # Workspace .gitkeep paths when control-repo scaffolds are requested.
    tp_gitkeep_path: Path | None = None
    docs_gitkeep_path: Path | None = None
    workspace_scaffold_entries: list[tuple[str, str]] = []
    if target_projects_root:
        tp_gitkeep_path = Path(target_projects_root) / domain / service / ".gitkeep"
        workspace_root = str(Path(target_projects_root).parent)
        workspace_scaffold_entries.append((workspace_root, str(tp_gitkeep_path.relative_to(workspace_root))))
        if not args.dry_run:
            try:
                tp_gitkeep_path.parent.mkdir(parents=True, exist_ok=True)
                tp_gitkeep_path.touch()
            except OSError as e:
                return {"status": "fail", "error": f"Failed to scaffold TargetProjects service folder: {e}"}
    if docs_root:
        docs_gitkeep_path = Path(docs_root) / domain / service / ".gitkeep"
        docs_workspace_root = str(Path(docs_root).parent)
        workspace_scaffold_entries.append((docs_workspace_root, str(docs_gitkeep_path.relative_to(docs_workspace_root))))
        if not args.dry_run:
            try:
                docs_gitkeep_path.parent.mkdir(parents=True, exist_ok=True)
                docs_gitkeep_path.touch()
            except OSError as e:
                return {"status": "fail", "error": f"Failed to scaffold docs service folder: {e}"}

    all_gov_paths = unique_paths(predicted_marker_paths + predicted_constitution_paths)
    commit_message = f"feat(service): add {domain}/{service} container"
    governance_git_steps = build_container_git_steps(all_gov_paths, commit_message)
    governance_git_commands = [git_command_text(governance_repo, step) for step in governance_git_steps]
    workspace_git_commands = (
        build_workspace_scaffold_commands(workspace_scaffold_entries, "service", f"{domain}/{service}")
        if workspace_scaffold_entries
        else []
    )

    if execute_governance_git and not args.dry_run:
        try:
            sync_governance_main(governance_repo)
        except RuntimeError as e:
            return {
                "status": "fail",
                "scope": "service",
                "error": f"Governance git preflight failed: {e}",
                **build_container_result_fields(governance_git_commands, workspace_git_commands),
            }

    if service_path.exists():
        return {
            "status": "fail",
            "error": f"Service '{domain}/{service}' already exists at {service_path}",
        }

    # Marker paths (ensure_container_markers creates both domain and service markers).
    created_marker_paths = ensure_container_markers(
        governance_repo,
        domain,
        service,
        username,
        timestamp,
        dry_run=args.dry_run,
    )

    domain_name = domain  # display name falls back to id for auto-created domain
    created_constitution_paths: list[str] = []

    if not domain_constitution_path.exists():
        created_constitution_paths.append(str(domain_constitution_path.relative_to(governance_repo)))
        if not args.dry_run:
            try:
                domain_constitution_path.parent.mkdir(parents=True, exist_ok=True)
                domain_constitution_path.write_text(
                    make_domain_constitution_md(domain, domain_name), encoding="utf-8"
                )
            except OSError as e:
                return {"status": "fail", "error": f"Failed to write domain constitution: {e}"}

    created_constitution_paths.append(str(service_constitution_path.relative_to(governance_repo)))

    # Overwrite the auto-generated service marker with the requested display name.
    if not args.dry_run:
        try:
            atomic_write_yaml(
                service_path,
                make_service_yaml(domain, service, name, username, timestamp),
            )
        except OSError as e:
            return {"status": "fail", "error": f"Failed to write service marker: {e}"}

        try:
            service_constitution_path.parent.mkdir(parents=True, exist_ok=True)
            service_constitution_path.write_text(
                make_service_constitution_md(domain, service, name), encoding="utf-8"
            )
        except OSError as e:
            return {"status": "fail", "error": f"Failed to write service constitution: {e}"}

    personal_folder_svc: str | None = getattr(args, "personal_folder", None)
    context_path_svc: str | None = None
    if personal_folder_svc and not args.dry_run:
        try:
            context_path_svc = str(write_context_yaml(personal_folder_svc, domain, service, "new-service"))
        except OSError as e:
            return {"status": "fail", "error": f"Failed to write context.yaml: {e}"}

    all_gov_paths = unique_paths(created_marker_paths + created_constitution_paths)
    governance_git_steps = build_container_git_steps(all_gov_paths, commit_message)
    governance_git_commands = [git_command_text(governance_repo, step) for step in governance_git_steps]

    governance_commit_sha: str | None = None
    governance_git_executed = False
    if execute_governance_git and not args.dry_run:
        try:
            for step in governance_git_steps[2:]:
                run_git(governance_repo, step)
            governance_commit_sha = current_head_sha(governance_repo)
            governance_git_executed = True
        except RuntimeError as e:
            return {
                "status": "fail",
                "scope": "service",
                "path": str(service_path),
                "constitution_path": str(service_constitution_path),
                "created_domain_marker": any(path.endswith("/domain.yaml") for path in created_marker_paths),
                "created_domain_constitution": any("constitutions/" in path and path.endswith(f"{domain}/constitution.md") for path in created_constitution_paths),
                "created_marker_paths": created_marker_paths,
                "created_constitution_paths": created_constitution_paths,
                "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
                "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
                "context_path": context_path_svc,
                "error": f"Governance git execution failed: {e}",
                **build_container_result_fields(
                    governance_git_commands,
                    workspace_git_commands,
                    governance_commit_sha=current_head_sha(governance_repo),
                ),
            }

    svc_result: dict = {
        "status": "pass",
        "dry_run": bool(args.dry_run),
        "scope": "service",
        "path": str(service_path),
        "constitution_path": str(service_constitution_path),
        "created_domain_marker": any(path.endswith("/domain.yaml") for path in created_marker_paths),
        "created_domain_constitution": any("constitutions/" in path and path.endswith(f"{domain}/constitution.md") for path in created_constitution_paths),
        "created_marker_paths": created_marker_paths,
        "created_constitution_paths": created_constitution_paths,
        "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
        "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
        **build_container_result_fields(
            governance_git_commands,
            workspace_git_commands,
            governance_git_executed=governance_git_executed,
            governance_commit_sha=governance_commit_sha,
        ),
    }
    if context_path_svc is not None:
        svc_result["context_path"] = context_path_svc
    return svc_result


def cmd_fetch_context(args: argparse.Namespace) -> dict:
    """Fetch cross-feature context for a feature."""
    governance_repo = args.governance_repo
    feature_id = args.feature_id
    depth = args.depth
    explicit_service_refs = unique_paths([
        service.strip().lower() for service in getattr(args, "service_ref", []) if service.strip()
    ])
    service_ref_texts = [text.strip() for text in getattr(args, "service_ref_text", []) if text.strip()]

    try:
        index_data, index_exists = read_feature_index(governance_repo)
    except RuntimeError as e:
        return {"status": "fail", "error": str(e)}

    if not index_exists:
        return {"status": "fail", "error": "feature-index.yaml not found"}

    features = index_data.get("features", [])
    index_by_id = {feature.get("id"): feature for feature in features if feature.get("id")}

    target = index_by_id.get(feature_id)
    if target is None:
        return {
            "status": "fail",
            "error": f"Feature '{feature_id}' not found in feature-index.yaml",
        }

    target_feature_path = feature_dir_from_entry(governance_repo, target) / "feature.yaml"
    if not target_feature_path.exists():
        return {
            "status": "fail",
            "error": f"feature.yaml not found for '{feature_id}'",
        }

    try:
        feature_data = yaml.safe_load(target_feature_path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "error": f"Failed to read feature.yaml: {e}"}

    target_domain = target.get("domain", "")
    target_service = str(feature_data.get("service") or target.get("service") or "").strip().lower()
    dependencies = feature_data.get("dependencies") or {}
    depends_on_ids = list(dependencies.get("depends_on") or [])
    blocks_ids = list(dependencies.get("blocks") or [])

    related = [f for f in features if f.get("domain") == target_domain and f.get("id") != feature_id]
    depends_on = [index_by_id[dep_id] for dep_id in depends_on_ids if dep_id in index_by_id]
    blocks = [index_by_id[dep_id] for dep_id in blocks_ids if dep_id in index_by_id]
    candidate_services = [
        service_name
        for service_name in available_service_names(governance_repo, features, target_domain)
        if service_name != target_service
    ]
    detected_service_refs = detect_service_refs_from_texts(
        service_ref_texts,
        candidate_services,
    )
    service_refs = unique_paths(explicit_service_refs + detected_service_refs)
    context_paths: list[str] = []

    for f in related:
        fid = f.get("id", "")
        dom = f.get("domain", "")
        svc = f.get("service", "")
        if depth == "full":
            context_paths.extend(collect_feature_context_paths(governance_repo, f))
        else:
            context_paths.append(str(Path(governance_repo) / "features" / dom / svc / fid / "summary.md"))

    for f in depends_on + blocks:
        context_paths.extend(collect_feature_context_paths(governance_repo, f))

    service_context_paths: list[str] = []
    missing_service_refs: list[str] = []
    for service_name in service_refs:
        matched_paths = collect_service_context_paths(
            governance_repo,
            service_name,
            feature_id,
            target_domain,
        )
        if matched_paths:
            service_context_paths.extend(matched_paths)
        else:
            missing_service_refs.append(service_name)

    context_paths = unique_paths(context_paths + service_context_paths)

    return {
        "status": "pass",
        "related": [f.get("id") for f in related],
        "depends_on": [f.get("id") for f in depends_on],
        "blocks": [f.get("id") for f in blocks],
        "service_refs": service_refs,
        "detected_service_refs": detected_service_refs,
        "missing_service_refs": missing_service_refs,
        "context_paths": context_paths,
        "service_context_paths": unique_paths(service_context_paths),
    }


def cmd_read_context(args: argparse.Namespace) -> dict:
    """Read the active domain/service context from the personal folder context.yaml.

    Returns the last-written domain/service pair set by create-domain or create-service.
    When not on a feature branch, callers use this to resolve which domain/service to
    run commands against.
    """
    context_path = Path(args.personal_folder) / "context.yaml"
    if not context_path.exists():
        return {
            "status": "not-found",
            "error": (
                f"No context.yaml found at {context_path}. "
                "Run `lens-new-domain` or `lens-new-service` first to establish a context."
            ),
        }
    try:
        with open(context_path) as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "error": f"Failed to read context.yaml: {e}"}

    return {
        "status": "pass",
        "domain": data.get("domain"),
        "service": data.get("service"),
        "updated_at": data.get("updated_at"),
        "updated_by": data.get("updated_by"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
                description="Governance initialization operations for features and container scopes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create --governance-repo /path/to/repo --feature-id auth-refresh \\
    --domain platform --service identity --name "Auth Token Refresh" --username cweber

    %(prog)s create --governance-repo /path/to/repo --feature-id auth-refresh \
        --domain platform --service identity --name "Auth Token Refresh" --username cweber \
        --track quickplan --execute-governance-git

    %(prog)s create-domain --governance-repo /path/to/repo --domain platform \\
        --name "Platform" --username cweber


    %(prog)s create-domain --governance-repo /path/to/repo --domain platform \
        --name "Platform" --username cweber --execute-governance-git
    %(prog)s create-domain --governance-repo /path/to/repo --domain platform \\
        --name "Platform" --username cweber \\
        --target-projects-root /path/to/TargetProjects

    %(prog)s create-service --governance-repo /path/to/repo --domain platform \\
        --service identity --name "Identity" --username cweber


    %(prog)s create-service --governance-repo /path/to/repo --domain platform \
        --service identity --name "Identity" --username cweber \
        --execute-governance-git
    %(prog)s create-service --governance-repo /path/to/repo --domain platform \\
        --service identity --name "Identity" --username cweber \\
        --target-projects-root /path/to/TargetProjects

  %(prog)s create --governance-repo /path/to/gov --control-repo /path/to/src \\
    --feature-id payment-gateway --domain commerce --service payments \\
    --name "Payment Gateway" --username cweber --dry-run

  %(prog)s fetch-context --governance-repo /path/to/repo --feature-id auth-refresh

  %(prog)s fetch-context --governance-repo /path/to/repo --feature-id auth-refresh --depth full
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    create_domain_p = subparsers.add_parser(
        "create-domain",
        help="Create a governance marker and constitution for a domain container",
    )
    create_domain_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    create_domain_p.add_argument("--domain", required=True, help="Domain name")
    create_domain_p.add_argument("--name", default=None, help="Human-friendly domain name")
    create_domain_p.add_argument("--username", required=True, help="Username of the creator")
    create_domain_p.add_argument(
        "--target-projects-root",
        default=None,
        dest="target_projects_root",
        help="Path to TargetProjects folder; creates {domain}/.gitkeep scaffold if provided",
    )
    create_domain_p.add_argument(
        "--docs-root",
        default=None,
        dest="docs_root",
        help="Path to docs folder; creates {domain}/.gitkeep scaffold if provided",
    )
    create_domain_p.add_argument(
        "--personal-folder",
        default=None,
        dest="personal_folder",
        help="Path to personal folder; writes context.yaml with current domain when provided",
    )
    create_domain_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned operations without writing any files",
    )
    create_domain_p.add_argument(
        "--execute-governance-git",
        action="store_true",
        dest="execute_governance_git",
        help="Automatically run governance checkout/pull/add/commit/push after creating the container",
    )

    create_service_p = subparsers.add_parser(
        "create-service",
        help="Create a governance marker and constitution for a service container",
    )
    create_service_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    create_service_p.add_argument("--domain", required=True, help="Domain name")
    create_service_p.add_argument("--service", required=True, help="Service name")
    create_service_p.add_argument("--name", default=None, help="Human-friendly service name")
    create_service_p.add_argument("--username", required=True, help="Username of the creator")
    create_service_p.add_argument(
        "--target-projects-root",
        default=None,
        dest="target_projects_root",
        help="Path to TargetProjects folder; creates {domain}/{service}/.gitkeep scaffold if provided",
    )
    create_service_p.add_argument(
        "--docs-root",
        default=None,
        dest="docs_root",
        help="Path to docs folder; creates {domain}/{service}/.gitkeep scaffold if provided",
    )
    create_service_p.add_argument(
        "--personal-folder",
        default=None,
        dest="personal_folder",
        help="Path to personal folder; writes context.yaml with current domain and service when provided",
    )
    create_service_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned operations without writing any files",
    )
    create_service_p.add_argument(
        "--execute-governance-git",
        action="store_true",
        dest="execute_governance_git",
        help="Automatically run governance checkout/pull/add/commit/push after creating the container",
    )

    read_context_p = subparsers.add_parser(
        "read-context",
        help="Read the active domain/service context from the personal folder",
    )
    read_context_p.add_argument(
        "--personal-folder",
        required=True,
        dest="personal_folder",
        help="Path to personal folder containing context.yaml",
    )

    create_p = subparsers.add_parser("create", help="Create feature branches, YAML, PR, and index entry")
    create_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    create_p.add_argument(
        "--control-repo",
        default=None,
        help="Path to source control repo (defaults to governance-repo)",
    )
    create_p.add_argument(
        "--feature-id",
        required=True,
        help=(
            "Local feature slug or canonical featureId. New features are stored as "
            "{normalized-domain}-{normalized-service}-{feature-slug}."
        ),
    )
    create_p.add_argument("--domain", required=True, help="Domain name")
    create_p.add_argument("--service", required=True, help="Service name")
    create_p.add_argument("--name", required=True, help="Human-friendly feature name")
    create_p.add_argument(
        "--track",
        default=None,
        choices=VALID_TRACKS,
        help="Lifecycle track (must be selected explicitly)",
    )
    create_p.add_argument("--username", required=True, help="Username of the creator")
    create_p.add_argument(
        "--personal-folder",
        default=None,
        dest="personal_folder",
        help="Path to personal folder; forwarded to the activation step when provided",
    )
    create_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned operations without writing any files",
    )
    create_p.add_argument(
        "--execute-governance-git",
        action="store_true",
        dest="execute_governance_git",
        help="Automatically run governance checkout/pull/add/commit/push after creating the feature",
    )

    fetch_p = subparsers.add_parser("fetch-context", help="Fetch cross-feature context")
    fetch_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    fetch_p.add_argument("--feature-id", required=True, help="Feature identifier")
    fetch_p.add_argument(
        "--depth",
        default="summaries",
        choices=["summaries", "full"],
        help="Context depth: summaries (default) or full",
    )
    fetch_p.add_argument(
        "--service-ref",
        action="append",
        default=[],
        help="Named service reference to load governance context for (repeatable)",
    )
    fetch_p.add_argument(
        "--service-ref-text",
        action="append",
        default=[],
        help="Freeform conversation text used to detect named services implicitly (repeatable)",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "create-domain": cmd_create_domain,
        "create-service": cmd_create_service,
        "create": cmd_create,
        "fetch-context": cmd_fetch_context,
        "read-context": cmd_read_context,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()

    status = result.get("status", "fail")
    sys.exit(0 if status in ("pass", "warning") else 1)


if __name__ == "__main__":
    main()
