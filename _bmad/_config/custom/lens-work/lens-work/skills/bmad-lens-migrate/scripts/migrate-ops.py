#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Migration operations — scan legacy LENS v3 branches, check conflicts, migrate features.

Transitions features from the old domain-service-feature-milestone branch topology
to the Lens Next 2-branch model ({featureId} + {featureId}-plan).
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml

# Sanitization pattern for path-constructing identifiers
SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

SCRIPT_DIR = Path(__file__).resolve().parent
INIT_FEATURE_OPS_PATH = SCRIPT_DIR.parent.parent / "bmad-lens-init-feature" / "scripts" / "init-feature-ops.py"
PROBLEMS_TEMPLATE_PATH = SCRIPT_DIR.parent.parent.parent / "assets" / "templates" / "problems-template.md"
LEGACY_BRANCHES_DIR = "branches"
LEGACY_ARTIFACTS_DIR = Path("_bmad-output/lens-work/planning-artifacts")
MIGRATION_DOSSIER_ROOT = Path("docs/lens-work/migrations")
MIGRATION_RECORD_FILE = "migration-record.yaml"
CLEANUP_APPROVAL_FILE = "cleanup-approval.yaml"
CLEANUP_RECEIPT_FILE = "cleanup-receipt.yaml"

# Document source types for discovery
DOC_SOURCE_GOVERNANCE_LEGACY = "governance-legacy"
DOC_SOURCE_BRANCH_DOCS = "branch-docs"
DOC_SOURCE_REPO_DOCS = "source-docs"
DOC_SOURCE_BMAD_OUTPUT = "bmad-output"

DOC_LOCATION_BRANCH_DOCS_FLAT = "branch-docs-flat"
DOC_LOCATION_BRANCH_DOCS_COMPAT = "branch-docs-compat"
DOC_LOCATION_BRANCH_BMAD_OUTPUT = "branch-bmad-output"
DOC_LOCATION_WORKING_TREE_DOCS_FALLBACK = "working-tree-docs-fallback"
DOC_LOCATION_WORKING_TREE_BMAD_OUTPUT_FALLBACK = "working-tree-bmad-output-fallback"

# Priority order for conflict resolution (first wins)
DOC_SOURCE_PRIORITY = [DOC_SOURCE_GOVERNANCE_LEGACY, DOC_SOURCE_BRANCH_DOCS, DOC_SOURCE_REPO_DOCS, DOC_SOURCE_BMAD_OUTPUT]
DOC_CANONICAL_PRIORITY = {
    DOC_SOURCE_GOVERNANCE_LEGACY: 0,
    DOC_LOCATION_BRANCH_DOCS_FLAT: 1,
    DOC_LOCATION_BRANCH_DOCS_COMPAT: 2,
    DOC_LOCATION_WORKING_TREE_DOCS_FALLBACK: 3,
    DOC_LOCATION_BRANCH_BMAD_OUTPUT: 4,
    DOC_LOCATION_WORKING_TREE_BMAD_OUTPUT_FALLBACK: 5,
}

LEGACY_PHASE_MAP = {
    "planning": "preplan",
    "preplan": "preplan",
    "businessplan": "businessplan",
    "techplan": "techplan",
    "devproposal": "finalizeplan",
    "sprintplan": "finalizeplan",
    "dev": "dev",
    "dev-ready": "dev",
    "complete": "complete",
    "paused": "paused",
}

LEGACY_MILESTONE_MAP = {
    "businessplan": "businessplan",
    "techplan": "techplan",
    "devproposal": "finalizeplan",
    "sprintplan": "finalizeplan",
    "dev-ready": "dev-ready",
    "dev-complete": "dev-complete",
}

# Default legacy branch pattern
DEFAULT_BRANCH_PATTERN = r"^([a-z0-9-]+)-([a-z0-9-]+)-([a-z0-9-]+)(?:-([a-z0-9-]+))?$"

# Phase ordering for state derivation (earliest to latest)
PHASE_ORDER = ["planning", "businessplan", "techplan", "finalizeplan", "dev", "complete"]

KNOWN_LEGACY_MILESTONES = set(PHASE_ORDER) | set(LEGACY_PHASE_MAP) | set(LEGACY_MILESTONE_MAP)


def validate_identifier(value: str, field_name: str) -> str | None:
    """Validate that a path-constructing identifier is safe. Returns error message or None."""
    if not SAFE_ID_PATTERN.match(value):
        return (
            f"Invalid {field_name}: '{value}'. "
            f"Must match [a-z0-9][a-z0-9._-]{{0,63}} (lowercase alphanumeric, dots, hyphens, underscores)."
        )
    return None


def parse_legacy_identity(old_id: str) -> tuple[str, str, str] | None:
    """Split a legacy branch id into domain, service, and feature parts."""
    parts = old_id.split("-")
    if len(parts) < 3:
        return None
    return parts[0], parts[1], "-".join(parts[2:])


def is_legacy_milestone_suffix(value: str) -> bool:
    """Return True when *value* is a known legacy milestone suffix."""
    return value in KNOWN_LEGACY_MILESTONES


def derive_legacy_feature(old_id: str, domain: str, service: str) -> str:
    """Derive the legacy feature slug from *old_id* and validate its domain/service."""
    parsed = parse_legacy_identity(old_id)
    if parsed is None:
        raise ValueError(f"Legacy branch '{old_id}' must contain domain, service, and feature segments")

    derived_domain, derived_service, legacy_feature = parsed
    if derived_domain != domain or derived_service != service:
        raise ValueError(
            f"Legacy branch '{old_id}' derives domain/service '{derived_domain}/{derived_service}', "
            f"but migration requested '{domain}/{service}'"
        )

    return legacy_feature


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@lru_cache(maxsize=1)
def load_init_feature_ops():
    """Load the canonical init-feature helper module by file path."""
    spec = importlib.util.spec_from_file_location("lens_init_feature_ops", INIT_FEATURE_OPS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load init-feature helpers from {INIT_FEATURE_OPS_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def read_yaml_if_exists(path: Path) -> dict | None:
    """Return parsed YAML if the file exists and is valid, else None."""
    if not path.exists() or not path.is_file():
        return None
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return None
    return data if isinstance(data, dict) else None


def sha256_bytes(data: bytes) -> str:
    """Return the SHA256 hex digest for *data*."""
    return hashlib.sha256(data).hexdigest()


def safe_path_part(value: str | None) -> str:
    """Normalize free-form values so they are safe for nested dossier paths."""
    if not value:
        return "working-tree"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return cleaned or "working-tree"


def write_bytes_file(path: Path, data: bytes) -> None:
    """Write bytes to *path*, creating parent folders when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def relative_to_root(root: Path, path: Path) -> str:
    """Return *path* relative to *root* when possible, else a normalized string."""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def read_document_bytes(doc: dict) -> bytes | None:
    """Load a discovered document as bytes, regardless of source type."""
    if "git_ref" in doc:
        return _git_show_file(Path(doc["git_repo"]), doc["git_ref"], doc["git_path"])

    try:
        return Path(doc["source_path"]).read_bytes()
    except OSError:
        return None


def detect_git_user(repo_path: Path) -> str:
    """Return the local git user.name for *repo_path* or a safe fallback."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass

    return os.environ.get("GITHUB_ACTOR") or os.environ.get("USER") or "unknown"


def looks_like_control_repo(path: Path) -> bool:
    """Heuristic for detecting the control repo root from a filesystem path."""
    return path.is_dir() and (path / "lens.core").exists()


def looks_like_governance_repo(path: Path) -> bool:
    """Heuristic for detecting a governance repo root from a filesystem path."""
    return path.is_dir() and (
        path.name == "lens-governance"
        or (path / "repo-inventory.yaml").is_file()
        or (path / "feature-index.yaml").is_file()
        or (path / "features").is_dir()
    )


def find_control_repo_ancestor(path: Path) -> Path | None:
    """Return the nearest ancestor that looks like a control repo, if any."""
    for candidate in (path, *path.parents):
        if looks_like_control_repo(candidate):
            return candidate
    return None


def infer_governance_repo_from_control(control_root: Path) -> Path | None:
    """Infer the governance repo location from a control repo root."""
    direct_candidate = control_root / "TargetProjects" / "lens" / "lens-governance"
    if direct_candidate.is_dir():
        return direct_candidate.resolve()

    target_projects_dir = control_root / "TargetProjects"
    if target_projects_dir.is_dir():
        for candidate in sorted(target_projects_dir.glob("*/lens-governance")):
            if candidate.is_dir():
                return candidate.resolve()

    return None


def resolve_governance_repo(governance_repo_arg: str) -> tuple[Path, str | None]:
    """Resolve the governance repo root, correcting control-repo inputs when possible."""
    governance_repo = Path(governance_repo_arg).resolve()
    if not governance_repo.exists() or not governance_repo.is_dir():
        raise RuntimeError(f"Governance repo not found: {governance_repo}")

    control_root = find_control_repo_ancestor(governance_repo)
    if control_root is not None and not looks_like_governance_repo(governance_repo):
        inferred_repo = infer_governance_repo_from_control(control_root)
        if inferred_repo is None:
            raise RuntimeError(
                "Governance repo argument points inside the control repo "
                f"({governance_repo}) but no governance repo was found under {control_root / 'TargetProjects'}."
            )
        return inferred_repo, f"Resolved governance repo from control-repo path: {inferred_repo}"

    return governance_repo, None


def resolve_control_repo(
    control_repo_arg: str | None,
    governance_repo: Path,
    source_repo: Path | None,
) -> tuple[Path, str | None]:
    """Resolve the control repo root used for migration dossiers.

    If explicit `--control-repo` is not provided, try to infer it from the
    current working directory and the governance/source repo ancestry. When no
    control repo marker is found, fall back to the governance repo so tests and
    standalone executions remain usable.
    """
    if control_repo_arg:
        control_repo = Path(control_repo_arg).resolve()
        if not control_repo.exists() or not control_repo.is_dir():
            raise RuntimeError(f"Control repo not found: {control_repo}")
        return control_repo, None

    search_roots = [Path.cwd().resolve(), governance_repo.resolve()]
    if source_repo is not None:
        search_roots.append(source_repo.resolve())

    visited: set[Path] = set()
    for root in search_roots:
        for candidate in (root, *root.parents):
            if candidate in visited:
                continue
            visited.add(candidate)
            if looks_like_control_repo(candidate):
                return candidate, None

    governance_parts = governance_repo.resolve().parts
    if "TargetProjects" in governance_parts:
        idx = governance_parts.index("TargetProjects")
        if idx > 0:
            return Path(*governance_parts[:idx]), "Control repo inferred from TargetProjects ancestry."

    return governance_repo.resolve(), "Control repo could not be inferred; storing migration dossier in the governance repo root."


def migration_dossier_dir(control_repo: Path, domain: str, service: str, feature_id: str) -> Path:
    """Return the dossier root for a migrated feature inside the control repo."""
    return control_repo / MIGRATION_DOSSIER_ROOT / domain / service / feature_id


def migration_record_paths(control_repo: Path, domain: str, service: str, feature_id: str) -> tuple[Path, Path, Path, Path]:
    """Return dossier directory plus record, approval, and receipt paths."""
    dossier_dir = migration_dossier_dir(control_repo, domain, service, feature_id)
    return (
        dossier_dir,
        dossier_dir / MIGRATION_RECORD_FILE,
        dossier_dir / CLEANUP_APPROVAL_FILE,
        dossier_dir / CLEANUP_RECEIPT_FILE,
    )


def build_legacy_branch_variants(old_id: str, governance_repo: Path, source_repo: Path | None) -> list[str]:
    """Return the base legacy branch plus all detected milestone branch variants."""
    milestones = set(detect_legacy_milestones(governance_repo, old_id))
    if source_repo is not None:
        milestones.update(detect_legacy_milestones(source_repo, old_id))

    branch_names = [old_id]
    branch_names.extend(f"{old_id}-{milestone}" for milestone in sorted(milestones))
    return branch_names


def build_mirror_relative_path(doc: dict) -> Path:
    """Build the control-repo dossier path for a raw discovered document."""
    return Path("sources") / safe_path_part(doc["source_type"]) / safe_path_part(doc.get("source_branch")) / safe_path_part(
        doc.get("source_location")
    ) / doc["relative_path"]


def document_source_label(doc: dict) -> str:
    """Return the audit/reporting label for a discovered document."""
    source_type = doc.get("source_type")
    if source_type == DOC_SOURCE_GOVERNANCE_LEGACY:
        return DOC_SOURCE_GOVERNANCE_LEGACY
    return doc.get("source_location") or source_type or "unknown"


def document_canonical_priority(doc: dict) -> int:
    """Return the canonical precedence rank for a discovered document."""
    return DOC_CANONICAL_PRIORITY.get(document_source_label(doc), len(DOC_CANONICAL_PRIORITY) + 1)


def select_canonical_documents(docs: list[dict]) -> list[dict]:
    """Select the canonical governance document for each relative path."""
    canonical_docs: list[dict] = []
    seen_targets: set[str] = set()

    for doc in sorted(
        docs,
        key=lambda item: (
            document_canonical_priority(item),
            -(item.get("commit_ts") or 0),
            item.get("source_branch") or "working-tree",
            item["relative_path"],
            item["source_path"],
        ),
    ):
        rel = doc["relative_path"]
        if rel in seen_targets:
            continue
        seen_targets.add(rel)
        canonical_docs.append(doc)

    return canonical_docs


def build_document_audit(legacy_branches: list[str], control_entries: list[dict], governance_entries: list[dict]) -> dict:
    """Summarize per-branch mirrored control docs versus governance docs for a feature."""
    control_counts: Counter[str] = Counter()
    governance_counts: Counter[str] = Counter()
    control_by_source: dict[str, Counter[str]] = defaultdict(Counter)
    governance_by_source: dict[str, Counter[str]] = defaultdict(Counter)

    for entry in control_entries:
        branch = entry.get("source_branch") or "working-tree"
        source_type = document_source_label(entry)
        control_counts[branch] += 1
        control_by_source[branch][source_type] += 1

    for entry in governance_entries:
        branch = entry.get("source_branch") or "working-tree"
        source_type = document_source_label(entry)
        governance_counts[branch] += 1
        governance_by_source[branch][source_type] += 1

    ordered_branches: list[str] = []
    seen: set[str] = set()
    for branch in [*legacy_branches, *sorted(control_counts), *sorted(governance_counts)]:
        if branch in seen:
            continue
        seen.add(branch)
        ordered_branches.append(branch)

    return {
        "control_feature_documents": len(control_entries),
        "governance_feature_documents": len(governance_entries),
        "branches": [
            {
                "branch": branch,
                "control_repo_documents": control_counts.get(branch, 0),
                "governance_repo_documents": governance_counts.get(branch, 0),
                "control_repo_by_source": dict(sorted(control_by_source.get(branch, {}).items())),
                "governance_repo_by_source": dict(sorted(governance_by_source.get(branch, {}).items())),
            }
            for branch in ordered_branches
        ],
    }


def serialize_discovered_doc(doc: dict, mirror_rel_path: Path) -> dict:
    """Project an in-memory discovered document into the persisted dossier record shape."""
    record = {
        "source_type": doc["source_type"],
        "source_branch": doc.get("source_branch"),
        "source_location": doc.get("source_location"),
        "relative_path": doc["relative_path"],
        "filename": doc["filename"],
        "commit_ts": doc.get("commit_ts") or 0,
        "sha256": doc["sha256"],
        "mirror_path": str(mirror_rel_path),
        "repo_label": doc.get("repo_label"),
    }

    if "git_ref" in doc:
        record["git_ref"] = doc["git_ref"]
        record["git_path"] = doc["git_path"]
    elif doc.get("repo_relative_path"):
        record["source_path"] = doc["repo_relative_path"]

    return record


def load_migration_record(control_repo: Path, feature_id: str, domain: str, service: str) -> tuple[Path, dict | None]:
    """Load the persisted migration record for a feature dossier."""
    _, record_path, _, _ = migration_record_paths(control_repo, domain, service, feature_id)
    return record_path, read_yaml_if_exists(record_path)


def verify_recorded_files(root: Path, entries: list[dict], path_key: str) -> tuple[str, str]:
    """Verify a recorded file set exists under *root* and matches recorded hashes."""
    missing: list[str] = []
    mismatched: list[str] = []

    for entry in entries:
        rel_path = entry.get(path_key)
        if not rel_path:
            missing.append(f"<missing {path_key}>")
            continue

        target_path = root / rel_path
        if not target_path.is_file():
            missing.append(rel_path)
            continue

        try:
            actual_hash = sha256_bytes(target_path.read_bytes())
        except OSError:
            missing.append(rel_path)
            continue

        if entry.get("sha256") and actual_hash != entry["sha256"]:
            mismatched.append(rel_path)

    status = "pass" if not missing and not mismatched else "fail"
    details = [f"{len(entries) - len(missing) - len(mismatched)}/{len(entries)} verified"]
    if missing:
        details.append(f"missing: {', '.join(missing[:3])}{' ...' if len(missing) > 3 else ''}")
    if mismatched:
        details.append(f"hash mismatch: {', '.join(mismatched[:3])}{' ...' if len(mismatched) > 3 else ''}")
    return status, "; ".join(details)


# ---------------------------------------------------------------------------
# Git Utilities — read content from branches without checkout
# ---------------------------------------------------------------------------

def _git_ref_exists(repo_path: Path, ref: str) -> bool:
    """Check whether a git ref (branch, tag, commit) exists in the repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--verify", "--quiet", ref],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _git_ls_tree(repo_path: Path, ref: str, prefix: str = "") -> list[str]:
    """List file paths under *prefix* on *ref*. Returns relative paths (files only)."""
    cmd = ["git", "-C", str(repo_path), "ls-tree", "-r", "--name-only", ref]
    if prefix:
        cmd.extend(["--", prefix])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line]
    except (subprocess.TimeoutExpired, OSError):
        return []


def _git_show_file(repo_path: Path, ref: str, path: str) -> bytes | None:
    """Read raw bytes of a single file from *ref*. Returns None on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "show", f"{ref}:{path}"],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return None


def _git_file_commit_ts(repo_path: Path, ref: str, path: str) -> int | None:
    """Return the Unix epoch timestamp of the last commit that touched *path* on *ref*.

    Uses ``git log -1 --format=%ct`` so the value reflects actual commit history
    rather than filesystem mtime.  Returns *None* on any failure.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "log", "-1", "--format=%ct", ref, "--", path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return int(result.stdout.strip())
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def _git_list_remote_branches(repo_path: Path, pattern: str = "") -> list[str]:
    """List remote branch names. *pattern* filters with fnmatch-style glob."""
    cmd = ["git", "-C", str(repo_path), "branch", "-r", "--format=%(refname:short)"]
    if pattern:
        cmd.extend(["--list", pattern])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, OSError):
        return []


def group_legacy_branches(names: list[str]) -> dict[str, dict]:
    """Group branch names into base branches with their milestones.

    Uses prefix-matching: if name B starts with name A + "-", then B is a
    milestone branch of A, and B's suffix (after A + "-") is the milestone label.
    Names not identified as milestones of any other name are treated as base branches.
    """
    sorted_names = sorted(names)
    milestone_map: dict[str, list[str]] = {}
    is_milestone: set[str] = set()

    for name in sorted_names:
        for base in sorted_names:
            if base == name:
                continue
            prefix = base + "-"
            if name.startswith(prefix):
                milestone = name[len(prefix):]
                if not is_legacy_milestone_suffix(milestone):
                    continue
                if base not in milestone_map:
                    milestone_map[base] = []
                milestone_map[base].append(milestone)
                is_milestone.add(name)

    features = {}
    for name in sorted_names:
        if name in is_milestone:
            continue
        parsed = parse_legacy_identity(name)
        if parsed is None:
            continue
        domain, service, legacy_feature = parsed
        features[name] = {
            "old_id": name,
            "derived_domain": domain,
            "derived_service": service,
            "feature_id": legacy_feature,
            "legacy_feature": legacy_feature,
            "milestones": milestone_map.get(name, []),
        }

    return features


def derive_state(milestones: list[str]) -> str:
    """Derive current state from list of discovered milestone labels."""
    for phase in reversed(PHASE_ORDER):
        if phase in milestones:
            return phase
    return "preplan" if not milestones else "planning"


def normalize_phase(raw_phase: str | None) -> tuple[str, list[str]]:
    """Normalize a legacy phase into the current Lens phase set."""
    warnings: list[str] = []
    if not raw_phase:
        return "preplan", warnings

    phase = str(raw_phase).strip().lower()
    mapped = LEGACY_PHASE_MAP.get(phase)
    if mapped is None:
        warnings.append(f"Unknown legacy phase '{phase}' defaulted to 'preplan'")
        return "preplan", warnings
    if mapped != phase:
        warnings.append(f"Mapped legacy phase '{phase}' to '{mapped}'")
    return mapped, warnings


def normalize_milestone(raw_milestone: str | None) -> tuple[str | None, list[str]]:
    """Normalize a legacy milestone into the current Lens milestone set."""
    warnings: list[str] = []
    if not raw_milestone:
        return None, warnings

    milestone = str(raw_milestone).strip().lower()
    mapped = LEGACY_MILESTONE_MAP.get(milestone)
    if mapped is None:
        warnings.append(f"Ignored unmapped legacy milestone '{milestone}'")
        return None, warnings
    if mapped != milestone:
        warnings.append(f"Mapped legacy milestone '{milestone}' to '{mapped}'")
    return mapped, warnings


def normalize_phase_transitions(transitions: object, timestamp: str, username: str) -> tuple[list[dict], list[str]]:
    """Normalize legacy phase transition records to the current Lens shape."""
    warnings: list[str] = []
    normalized: list[dict] = []

    if isinstance(transitions, list):
        for entry in transitions:
            if not isinstance(entry, dict):
                continue
            phase, phase_warnings = normalize_phase(entry.get("phase"))
            warnings.extend(phase_warnings)
            normalized.append(
                {
                    "phase": phase,
                    "timestamp": entry.get("timestamp") or timestamp,
                    "user": entry.get("user") or username,
                }
            )

    if not normalized:
        normalized = [{"phase": "preplan", "timestamp": timestamp, "user": username}]

    return normalized, warnings


def detect_legacy_milestones(governance_repo: Path, old_id: str) -> list[str]:
    """Infer legacy milestone suffixes from sibling branch directories or git remote branches."""
    branches_dir = governance_repo / LEGACY_BRANCHES_DIR
    if branches_dir.exists():
        prefix = old_id + "-"
        milestones: list[str] = []
        for entry in sorted(branches_dir.iterdir()):
            if entry.is_dir() and entry.name.startswith(prefix):
                milestone = entry.name[len(prefix):]
                if is_legacy_milestone_suffix(milestone):
                    milestones.append(milestone)
        return milestones

    # Fall back: detect from remote branches
    remote_branches = _git_list_remote_branches(governance_repo, f"origin/{old_id}-*")
    if not remote_branches:
        return []

    prefix = f"origin/{old_id}-"
    milestones = []
    for branch in remote_branches:
        if branch.startswith(prefix):
            milestone = branch[len(prefix):]
            if is_legacy_milestone_suffix(milestone):
                milestones.append(milestone)
    return sorted(milestones)


def find_legacy_state(governance_repo: Path, old_id: str, domain: str, service: str, legacy_feature: str) -> tuple[dict | None, str | None]:
    """Locate a legacy initiative-state.yaml in known historical locations.

    Tries filesystem first, then falls back to git extraction from origin/{old_id}.
    """
    branch_dir = governance_repo / LEGACY_BRANCHES_DIR / old_id
    candidates = [
        branch_dir / "initiative-state.yaml",
        branch_dir / "_bmad-output" / "lens-work" / "initiative-state.yaml",
        branch_dir / "_bmad-output" / "lens-work" / "initiatives" / domain / service / legacy_feature / "initiative-state.yaml",
        branch_dir / "_bmad-output" / "lens-work" / "initiatives" / domain / service / "initiative-state.yaml",
    ]

    # Try filesystem first
    for path in candidates:
        data = read_yaml_if_exists(path)
        if data is not None:
            return data, str(path)

    # Fall back: try git extraction from governance repo branch
    ref = f"origin/{old_id}"
    if _git_ref_exists(governance_repo, ref):
        git_candidates = [
            "initiative-state.yaml",
            "_bmad-output/lens-work/initiative-state.yaml",
            f"_bmad-output/lens-work/initiatives/{domain}/{service}/{legacy_feature}/initiative-state.yaml",
            f"_bmad-output/lens-work/initiatives/{domain}/{service}/initiative-state.yaml",
        ]
        for git_path in git_candidates:
            content = _git_show_file(governance_repo, ref, git_path)
            if content is not None:
                try:
                    data = yaml.safe_load(content.decode("utf-8"))
                    if isinstance(data, dict):
                        return data, f"git:{ref}:{git_path}"
                except (yaml.YAMLError, UnicodeDecodeError):
                    continue

    return None, None


def render_problems_template(feature_id: str, domain: str, service: str, created_date: str) -> str:
    """Render the standard problems.md template with feature values."""
    if PROBLEMS_TEMPLATE_PATH.exists():
        template = PROBLEMS_TEMPLATE_PATH.read_text(encoding="utf-8")
    else:
        template = (
            "# Problems Log: {featureId}\n\n"
            "> Feature: {domain}/{service}/{featureId}\n"
            "> Created: {created_date}\n\n"
            "<!-- Entries appended by /log-problem. Consumed by /retrospective. -->\n\n"
            "---\n"
        )

    return (
        template.replace("{featureId}", feature_id)
        .replace("{domain}", domain)
        .replace("{service}", service)
        .replace("{created_date}", created_date)
    )


def create_problems_log(feature_dir: Path, feature_id: str, domain: str, service: str, created_date: str) -> bool:
    """Create a problems.md file if one is not already present."""
    problems_path = feature_dir / "problems.md"
    if problems_path.exists():
        return False
    problems_path.write_text(
        render_problems_template(feature_id, domain, service, created_date),
        encoding="utf-8",
    )
    return True


def copy_legacy_artifacts(governance_repo: Path, old_id: str, feature_dir: Path) -> list[str]:
    """Copy legacy planning artifacts from the old branch snapshot when present.

    Tries filesystem first (branches/{old_id}/...), then falls back to git
    extraction from origin/{old_id} in the governance repo.
    """
    source_root = governance_repo / LEGACY_BRANCHES_DIR / old_id / LEGACY_ARTIFACTS_DIR

    # Filesystem path exists — use direct copy
    if source_root.exists():
        copied: list[str] = []
        for source_path in sorted(source_root.rglob("*")):
            if not source_path.is_file():
                continue
            relative_path = source_path.relative_to(source_root)
            target_path = feature_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            copied.append(str(relative_path))
        return copied

    # Fall back: extract from git branch
    ref = f"origin/{old_id}"
    if not _git_ref_exists(governance_repo, ref):
        return []

    artifact_prefix = str(LEGACY_ARTIFACTS_DIR) + "/"
    paths = _git_ls_tree(governance_repo, ref, artifact_prefix)
    if not paths:
        return []

    copied = []
    for git_path in paths:
        rel = git_path[len(artifact_prefix):]
        if not rel:
            continue
        content = _git_show_file(governance_repo, ref, git_path)
        if content is None:
            continue
        target_path = feature_dir / rel
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
        copied.append(rel)
    return copied


# ---------------------------------------------------------------------------
# Document Discovery & Migration
# ---------------------------------------------------------------------------

def _find_docs_folder(repo_root: Path) -> Path | None:
    """Find a Docs or docs folder at the repo root (case-insensitive)."""
    for name in ("Docs", "docs", "DOCS"):
        candidate = repo_root / name
        if candidate.is_dir():
            return candidate
    return None


def _list_files_under(root: Path) -> list[Path]:
    """Return all files beneath *root* in stable order."""
    if not root.is_dir():
        return []
    return [path for path in sorted(root.rglob("*")) if path.is_file()]


def discover_documents(
    governance_repo: Path,
    old_id: str,
    domain: str,
    service: str,
    feature_id: str,
        legacy_feature: str,
    source_repo: Path | None,
) -> list[dict]:
    """Discover documents from all sources for a feature.

    Sources checked (in priority order):
      1. governance-legacy  — filesystem branches/{old_id}[-milestone]/... or git origin/{old_id}[-milestone] in governance repo
            2. branch-docs        — git origin/{old_id}[-milestone] docs/ tree in source repo using legacy feature paths
            3. source-docs        — fallback filesystem docs paths in source repo when branch docs are absent
            4. bmad-output        — feature-scoped branch or working-tree _bmad-output paths when docs are absent

    Returns list of dicts: {source_type, source_path, relative_path, filename, git_ref?, git_path?, source_branch, source_location}.
    """
    discovered: list[dict] = []
    governance_branches = build_legacy_branch_variants(old_id, governance_repo, None)

    # Source 1: Governance legacy artifacts
    for branch_name in governance_branches:
        legacy_root = governance_repo / LEGACY_BRANCHES_DIR / branch_name / LEGACY_ARTIFACTS_DIR
        if legacy_root.is_dir():
            for fpath in sorted(legacy_root.rglob("*")):
                if fpath.is_file():
                    rel_to_repo = str(fpath.relative_to(governance_repo))
                    ts = _git_file_commit_ts(governance_repo, "HEAD", rel_to_repo) or 0
                    discovered.append({
                        "source_type": DOC_SOURCE_GOVERNANCE_LEGACY,
                        "source_path": str(fpath),
                        "relative_path": str(fpath.relative_to(legacy_root)),
                        "filename": fpath.name,
                        "source_branch": branch_name,
                        "source_location": "planning-artifacts",
                        "repo_label": "governance",
                        "commit_ts": ts,
                    })
            continue

        ref = f"origin/{branch_name}"
        if _git_ref_exists(governance_repo, ref):
            artifact_prefix = str(LEGACY_ARTIFACTS_DIR) + "/"
            paths = _git_ls_tree(governance_repo, ref, artifact_prefix)
            for git_path in paths:
                rel = git_path[len(artifact_prefix):]
                if rel:
                    ts = _git_file_commit_ts(governance_repo, ref, git_path) or 0
                    discovered.append({
                        "source_type": DOC_SOURCE_GOVERNANCE_LEGACY,
                        "source_path": f"git:{ref}:{git_path}",
                        "relative_path": rel,
                        "filename": Path(rel).name,
                        "git_ref": ref,
                        "git_path": git_path,
                        "git_repo": str(governance_repo),
                        "source_branch": branch_name,
                        "source_location": "planning-artifacts",
                        "repo_label": "governance",
                        "commit_ts": ts,
                    })

    if source_repo is not None:
        # Source 2: Branch-docs — documents on the legacy branch family in the source repo
        source_branches = build_legacy_branch_variants(old_id, governance_repo, source_repo)
        branch_docs_found = False
        branch_bmad_found = False
        for branch_name in source_branches:
            ref = f"origin/{branch_name}"
            if not _git_ref_exists(source_repo, ref):
                continue

            flat_prefix = f"docs/{domain}/{service}/{legacy_feature}/"
            compat_prefix = f"docs/{domain}/{service}/feature/{legacy_feature}/"
            flat_paths = _git_ls_tree(source_repo, ref, flat_prefix)
            if flat_paths:
                branch_docs_found = True
                doc_paths = [(flat_paths, flat_prefix, DOC_LOCATION_BRANCH_DOCS_FLAT)]
            else:
                compat_paths = _git_ls_tree(source_repo, ref, compat_prefix)
                doc_paths = []
                if compat_paths:
                    branch_docs_found = True
                    doc_paths.append((compat_paths, compat_prefix, DOC_LOCATION_BRANCH_DOCS_COMPAT))

            for paths, prefix, location_name in doc_paths:
                for git_path in paths:
                    rel = git_path[len(prefix):]
                    if rel:
                        ts = _git_file_commit_ts(source_repo, ref, git_path) or 0
                        discovered.append({
                            "source_type": DOC_SOURCE_BRANCH_DOCS,
                            "source_path": f"git:{ref}:{git_path}",
                            "relative_path": rel,
                            "filename": Path(rel).name,
                            "git_ref": ref,
                            "git_path": git_path,
                            "git_repo": str(source_repo),
                            "source_branch": branch_name,
                            "source_location": location_name,
                            "repo_label": "source",
                            "commit_ts": ts,
                        })

            bmad_feature_file = f"_bmad-output/lens-work/initiatives/{domain}/{service}/{legacy_feature}.yaml"
            bmad_feature_prefix = f"_bmad-output/lens-work/initiatives/{domain}/{service}/{legacy_feature}/"
            for git_path in _git_ls_tree(source_repo, ref, bmad_feature_file):
                branch_bmad_found = True
                ts = _git_file_commit_ts(source_repo, ref, git_path) or 0
                rel = Path(git_path).name
                discovered.append({
                    "source_type": DOC_SOURCE_BMAD_OUTPUT,
                    "source_path": f"git:{ref}:{git_path}",
                    "relative_path": rel,
                    "filename": Path(rel).name,
                    "git_ref": ref,
                    "git_path": git_path,
                    "git_repo": str(source_repo),
                    "source_branch": branch_name,
                    "source_location": DOC_LOCATION_BRANCH_BMAD_OUTPUT,
                    "repo_label": "source",
                    "commit_ts": ts,
                })

            for git_path in _git_ls_tree(source_repo, ref, bmad_feature_prefix):
                rel = git_path[len(bmad_feature_prefix):]
                if rel:
                    branch_bmad_found = True
                    ts = _git_file_commit_ts(source_repo, ref, git_path) or 0
                    discovered.append({
                        "source_type": DOC_SOURCE_BMAD_OUTPUT,
                        "source_path": f"git:{ref}:{git_path}",
                        "relative_path": rel,
                        "filename": Path(rel).name,
                        "git_ref": ref,
                        "git_path": git_path,
                        "git_repo": str(source_repo),
                        "source_branch": branch_name,
                        "source_location": DOC_LOCATION_BRANCH_BMAD_OUTPUT,
                        "repo_label": "source",
                        "commit_ts": ts,
                    })

        # Source 3: Working-tree docs fallback when no branch docs exist for this feature.
        docs_folder = _find_docs_folder(source_repo)
        if not branch_docs_found and docs_folder is not None:
            flat_docs = docs_folder / domain / service / legacy_feature
            flat_files = _list_files_under(flat_docs)
            compat_docs = docs_folder / domain / service / "feature" / legacy_feature
            feature_docs = flat_docs if flat_files else compat_docs

            for fpath in (flat_files or _list_files_under(compat_docs)):
                rel_to_repo = str(fpath.relative_to(source_repo))
                ts = _git_file_commit_ts(source_repo, "HEAD", rel_to_repo) or 0
                discovered.append({
                    "source_type": DOC_SOURCE_REPO_DOCS,
                    "source_path": str(fpath),
                    "repo_relative_path": rel_to_repo,
                    "relative_path": str(fpath.relative_to(feature_docs)),
                    "filename": fpath.name,
                    "source_branch": "working-tree",
                    "source_location": DOC_LOCATION_WORKING_TREE_DOCS_FALLBACK,
                    "repo_label": "source",
                    "commit_ts": ts,
                })

        # Source 4: Working-tree feature-scoped _bmad-output fallback when branch entries are absent.
        if not branch_bmad_found:
            bmad_output = source_repo / "_bmad-output" / "lens-work" / "initiatives" / domain / service
            feature_yaml = bmad_output / f"{legacy_feature}.yaml"
            feature_dir = bmad_output / legacy_feature

            if feature_yaml.is_file():
                rel_to_repo = str(feature_yaml.relative_to(source_repo))
                ts = _git_file_commit_ts(source_repo, "HEAD", rel_to_repo) or 0
                discovered.append({
                    "source_type": DOC_SOURCE_BMAD_OUTPUT,
                    "source_path": str(feature_yaml),
                    "repo_relative_path": rel_to_repo,
                    "relative_path": feature_yaml.name,
                    "filename": feature_yaml.name,
                    "source_branch": "working-tree",
                    "source_location": DOC_LOCATION_WORKING_TREE_BMAD_OUTPUT_FALLBACK,
                    "repo_label": "source",
                    "commit_ts": ts,
                })

            for fpath in _list_files_under(feature_dir):
                rel_to_repo = str(fpath.relative_to(source_repo))
                ts = _git_file_commit_ts(source_repo, "HEAD", rel_to_repo) or 0
                discovered.append({
                    "source_type": DOC_SOURCE_BMAD_OUTPUT,
                    "source_path": str(fpath),
                    "repo_relative_path": rel_to_repo,
                    "relative_path": str(fpath.relative_to(feature_dir)),
                    "filename": fpath.name,
                    "source_branch": "working-tree",
                    "source_location": DOC_LOCATION_WORKING_TREE_BMAD_OUTPUT_FALLBACK,
                    "repo_label": "source",
                    "commit_ts": ts,
                })

    return discovered


def migrate_documents(
    governance_repo: Path,
    control_repo: Path,
    old_id: str,
    domain: str,
    service: str,
    feature_id: str,
    legacy_feature: str,
    source_repo: Path | None,
) -> dict:
    """Mirror discovered documents into the control repo dossier and migrate winners to governance docs.

    Conflict resolution: when the same relative_path appears in multiple sources,
    the most recently committed version wins.  Static source priority
    (DOC_SOURCE_PRIORITY) is the tiebreaker when timestamps are equal.
    All discovered source documents are mirrored into the dossier as proof before
    the canonical winners are written to governance docs.
    """
    legacy_branches = build_legacy_branch_variants(old_id, governance_repo, source_repo)
    docs = discover_documents(governance_repo, old_id, domain, service, feature_id, legacy_feature, source_repo)
    dossier_dir, _, _, _ = migration_record_paths(control_repo, domain, service, feature_id)
    target_dir = governance_repo / "features" / domain / service / feature_id / "docs"

    dossier_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    if not docs:
        return {
            "documents_migrated": [],
            "documents_source": {},
            "discovered_count": 0,
            "mirrored_count": 0,
            "canonical_count": 0,
            "discovered_records": [],
            "canonical_records": [],
            "document_audit": build_document_audit(legacy_branches, [], []),
            "dossier_dir": str(dossier_dir),
        }

    docs_with_content: list[dict] = []
    discovered_records: list[dict] = []
    errors: list[str] = []

    for doc in docs:
        content = read_document_bytes(doc)
        if content is None:
            errors.append(
                f"Failed to read discovered document {doc['relative_path']} from {doc['source_type']}:{doc.get('source_branch') or 'working-tree'}"
            )
            continue

        enriched_doc = dict(doc)
        enriched_doc["sha256"] = sha256_bytes(content)
        enriched_doc["_content"] = content

        mirror_rel_path = build_mirror_relative_path(enriched_doc)
        try:
            write_bytes_file(dossier_dir / mirror_rel_path, content)
        except OSError as exc:
            errors.append(f"Failed to mirror {doc['relative_path']} into dossier: {exc}")
            continue

        discovered_records.append(
            serialize_discovered_doc(
                enriched_doc,
                Path(relative_to_root(control_repo, dossier_dir / mirror_rel_path)),
            )
        )
        docs_with_content.append(enriched_doc)

    if errors:
        raise OSError("; ".join(errors))

    copied: list[str] = []
    source_counts: dict[str, int] = {}
    canonical_records: list[dict] = []
    canonical_docs = select_canonical_documents(docs_with_content)

    for doc in canonical_docs:
        rel = doc["relative_path"]
        target_path = target_dir / rel
        try:
            write_bytes_file(target_path, doc["_content"])
        except OSError as exc:
            raise OSError(f"Failed to write canonical document {rel}: {exc}") from exc

        copied.append(rel)
        source_label = document_source_label(doc)
        source_counts[source_label] = source_counts.get(source_label, 0) + 1
        canonical_records.append({
            "relative_path": rel,
            "source_type": doc["source_type"],
            "source_branch": doc.get("source_branch"),
            "source_location": doc.get("source_location"),
            "sha256": doc["sha256"],
            "governance_path": relative_to_root(governance_repo, target_path),
        })

    return {
        "documents_migrated": copied,
        "documents_source": source_counts,
        "discovered_count": len(docs),
        "mirrored_count": len(discovered_records),
        "canonical_count": len(canonical_records),
        "discovered_records": discovered_records,
        "canonical_records": canonical_records,
        "document_audit": build_document_audit(legacy_branches, discovered_records, canonical_records),
        "dossier_dir": str(dossier_dir),
    }


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_migration(
    governance_repo: Path,
    feature_id: str,
    domain: str,
    service: str,
    control_repo: Path,
) -> dict:
    """Verify governance artifacts plus the control-repo migration dossier."""
    checks: list[dict] = []
    feature_dir = governance_repo / "features" / domain / service / feature_id
    dossier_dir, record_path, approval_path, receipt_path = migration_record_paths(control_repo, domain, service, feature_id)

    # Check 1: feature.yaml exists and is valid
    feature_path = feature_dir / "feature.yaml"
    feature_data = read_yaml_if_exists(feature_path)
    checks.append({
        "name": "feature_yaml",
        "result": "pass" if feature_data else "fail",
        "details": str(feature_path),
    })

    # Check 2: feature-index.yaml entry exists
    index_path = governance_repo / "feature-index.yaml"
    index_data = read_yaml_if_exists(index_path)
    index_has_entry = False
    if index_data and isinstance(index_data.get("features"), list):
        index_has_entry = any(
            (e.get("id") == feature_id or e.get("featureId") == feature_id)
            for e in index_data["features"]
        )
    checks.append({
        "name": "feature_index_entry",
        "result": "pass" if index_has_entry else "fail",
        "details": str(index_path),
    })

    # Check 3: summary.md exists
    summary_path = feature_dir / "summary.md"
    checks.append({
        "name": "summary_md",
        "result": "pass" if summary_path.is_file() else "fail",
        "details": str(summary_path),
    })

    # Check 4: problems.md exists
    problems_path = feature_dir / "problems.md"
    checks.append({
        "name": "problems_md",
        "result": "pass" if problems_path.is_file() else "fail",
        "details": str(problems_path),
    })

    # Check 5: control-repo dossier exists
    checks.append({
        "name": "dossier_dir",
        "result": "pass" if dossier_dir.is_dir() else "fail",
        "details": relative_to_root(control_repo, dossier_dir),
    })

    # Check 6: migration record exists
    record = read_yaml_if_exists(record_path)
    checks.append({
        "name": "migration_record",
        "result": "pass" if record else "fail",
        "details": relative_to_root(control_repo, record_path),
    })

    discovered_entries = []
    canonical_entries = []
    document_audit = None
    if record:
        documents_block = record.get("documents") if isinstance(record, dict) else None
        if isinstance(documents_block, dict):
            discovered_entries = documents_block.get("discovered") or []
            canonical_entries = documents_block.get("canonical") or []
            document_audit = documents_block.get("document_audit")

    mirror_status, mirror_details = verify_recorded_files(control_repo, discovered_entries, "mirror_path")
    checks.append({
        "name": "mirrored_documents",
        "result": mirror_status if record else "fail",
        "details": mirror_details if record else "Migration record missing discovered document inventory",
    })

    governance_status, governance_details = verify_recorded_files(governance_repo, canonical_entries, "governance_path")
    checks.append({
        "name": "governance_docs",
        "result": governance_status if record else "fail",
        "details": governance_details if record else "Migration record missing governance document inventory",
    })

    overall = "pass" if all(c["result"] == "pass" for c in checks) else "fail"
    result = {
        "status": overall,
        "feature_id": feature_id,
        "domain": domain,
        "service": service,
        "checks": checks,
        "dossier_path": relative_to_root(control_repo, dossier_dir),
        "migration_record_path": relative_to_root(control_repo, record_path),
    }
    if document_audit is not None:
        result["document_audit"] = document_audit

    if record is not None:
        record["status"] = "verified" if overall == "pass" else "verification-failed"
        record["updated_at"] = now_iso()
        record["verification"] = {
            "status": overall,
            "verified_at": record["updated_at"],
            "checks": checks,
            "approval_path": relative_to_root(control_repo, approval_path) if approval_path.exists() else None,
            "cleanup_receipt_path": relative_to_root(control_repo, receipt_path) if receipt_path.exists() else None,
        }
        atomic_write_yaml(record_path, record)

    return result


def make_migration_summary(feature_id: str, domain: str, service: str, username: str, timestamp: str, old_id: str) -> str:
    """Build a summary stub compatible with the current Lens Next layout."""
    title = feature_id.replace("-", " ").title()
    return (
        f"# {title}\n\n"
        f"> Status: migrated | Feature ID: `{feature_id}`\n\n"
        f"Migrated from legacy branch `{old_id}`. Update as planning resumes.\n\n"
        f"**Domain:** {domain}  \n"
        f"**Service:** {service}  \n"
        f"**Owner:** {username}  \n"
        f"**Migrated:** {timestamp}\n"
    )


def build_index_entry(feature_data: dict, old_id: str, username: str) -> dict:
    """Build a compatibility index entry that works with both index readers in the repo."""
    feature_id = feature_data["featureId"]
    depends_on = feature_data.get("dependencies", {}).get("depends_on", [])
    updated_at = feature_data.get("updated") or now_iso()
    phase = feature_data.get("phase", "preplan")
    stale = bool(feature_data.get("context", {}).get("stale", False))
    return {
        "id": feature_id,
        "featureId": feature_id,
        "domain": feature_data.get("domain", ""),
        "service": feature_data.get("service", ""),
        "status": phase,
        "phase": phase,
        "owner": username,
        "plan_branch": f"{feature_id}-plan",
        "related_features": {
            "depends_on": depends_on,
            "blocks": [],
            "related": [],
        },
        "updated_at": updated_at,
        "summary": f"Migrated from legacy branch: {old_id}",
        "stale": stale,
        "migrated_from": old_id,
    }


def build_migrated_feature_data(
    governance_repo: Path,
    old_id: str,
    feature_id: str,
    domain: str,
    service: str,
    legacy_feature: str,
    username: str,
    timestamp: str,
    fallback_phase: str,
) -> tuple[dict, str | None, list[str]]:
    """Create a Lens Next feature.yaml payload, preserving legacy state where possible."""
    init_feature_ops = load_init_feature_ops()
    legacy_state, legacy_state_path = find_legacy_state(governance_repo, old_id, domain, service, legacy_feature)
    warnings: list[str] = []

    raw_track = None
    raw_name = None
    raw_description = None
    if legacy_state:
        raw_track = legacy_state.get("track")
        raw_name = legacy_state.get("name")
        raw_description = legacy_state.get("description")

    valid_tracks = getattr(init_feature_ops, "VALID_TRACKS", [])
    track = raw_track if raw_track in valid_tracks else "full"
    if raw_track and raw_track not in valid_tracks:
        warnings.append(f"Unsupported legacy track '{raw_track}' defaulted to 'full'")

    name = raw_name or feature_id.replace("-", " ").title()
    feature_data = init_feature_ops.make_feature_yaml(
        feature_id,
        feature_id,
        domain,
        service,
        name,
        track,
        fallback_phase,
        username,
        timestamp,
    )
    feature_data["description"] = raw_description or f"Migrated from legacy branch: {old_id}"
    feature_data["migrated_from"] = old_id

    if not legacy_state:
        phase, phase_warnings = normalize_phase(fallback_phase)
        warnings.extend(phase_warnings)
        feature_data["phase"] = phase
        return feature_data, legacy_state_path, warnings

    feature_data["created"] = legacy_state.get("created") or feature_data.get("created") or timestamp
    feature_data["updated"] = (
        legacy_state.get("updated")
        or legacy_state.get("updated_at")
        or legacy_state.get("last_updated")
        or timestamp
    )

    raw_phase = legacy_state.get("current_phase") or legacy_state.get("phase") or fallback_phase
    phase, phase_warnings = normalize_phase(raw_phase)
    warnings.extend(phase_warnings)
    feature_data["phase"] = phase

    transitions, transition_warnings = normalize_phase_transitions(
        legacy_state.get("phase_transitions"),
        feature_data["updated"],
        username,
    )
    warnings.extend(transition_warnings)
    if not transitions or transitions[-1].get("phase") != phase:
        transitions.append({"phase": phase, "timestamp": feature_data["updated"], "user": username})
    feature_data["phase_transitions"] = transitions

    legacy_milestones = legacy_state.get("milestones")
    if isinstance(legacy_milestones, dict):
        for milestone, value in legacy_milestones.items():
            if milestone in feature_data.get("milestones", {}):
                feature_data["milestones"][milestone] = value

    milestone, milestone_warnings = normalize_milestone(
        legacy_state.get("current_milestone") or legacy_state.get("milestone")
    )
    warnings.extend(milestone_warnings)
    if milestone and feature_data["milestones"].get(milestone) is None:
        feature_data["milestones"][milestone] = feature_data["updated"]

    dependencies = legacy_state.get("dependencies")
    if isinstance(dependencies, dict):
        feature_data.setdefault("dependencies", {})
        feature_data["dependencies"]["depends_on"] = list(dependencies.get("depends_on") or [])
        feature_data["dependencies"]["depended_by"] = list(dependencies.get("depended_by") or [])

    links = legacy_state.get("links")
    if isinstance(links, dict):
        feature_data.setdefault("links", {})
        feature_data["links"].update(links)

    context = legacy_state.get("context")
    if isinstance(context, dict):
        feature_data["context"] = {
            "last_pulled": context.get("last_pulled"),
            "stale": bool(context.get("stale", False)),
        }

    priority = legacy_state.get("priority")
    if isinstance(priority, str) and priority:
        feature_data["priority"] = priority

    return feature_data, legacy_state_path, warnings


def cmd_scan(args: argparse.Namespace) -> dict:
    """Detect legacy branches and build migration plan."""
    try:
        governance_repo, governance_warning = resolve_governance_repo(args.governance_repo)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    source_repo = Path(args.source_repo) if getattr(args, "source_repo", None) else None
    if source_repo and not source_repo.exists():
        print(f"Error: Source repo not found: {source_repo}", file=sys.stderr)
        sys.exit(1)

    try:
        control_repo, control_warning = resolve_control_repo(getattr(args, "control_repo", None), governance_repo, source_repo)
    except RuntimeError as exc:
        return {"status": "fail", "error": str(exc)}

    branches_dir = governance_repo / LEGACY_BRANCHES_DIR

    pattern_str = args.branch_pattern or DEFAULT_BRANCH_PATTERN
    try:
        pattern = re.compile(pattern_str)
    except re.error as e:
        return {"status": "fail", "error": f"Invalid branch pattern: {e}"}

    candidate_names = []

    # Try filesystem first
    if branches_dir.exists():
        for entry in branches_dir.iterdir():
            if entry.is_dir() and pattern.match(entry.name):
                candidate_names.append(entry.name)
    else:
        # Fall back: discover legacy branches from git remotes
        remote_branches = _git_list_remote_branches(governance_repo)
        for branch in remote_branches:
            # Strip 'origin/' prefix
            name = branch.split("/", 1)[1] if "/" in branch else branch
            if pattern.match(name):
                candidate_names.append(name)

    if not candidate_names:
        return {"status": "pass", "legacy_features": [], "total": 0, "conflicts": []}

    grouped = group_legacy_branches(candidate_names)

    legacy_features = []
    conflicts = []

    for base_name, info in sorted(grouped.items()):
        feature_id = info["feature_id"]
        domain = info["derived_domain"]
        service = info["derived_service"]
        legacy_feature = info["legacy_feature"]
        milestones = info["milestones"]
        state = derive_state(milestones)

        new_feature_path = governance_repo / "features" / domain / service / feature_id / "feature.yaml"
        if new_feature_path.exists():
            conflicts.append(
                {
                    "old_id": base_name,
                    "feature_id": feature_id,
                    "conflict_path": str(new_feature_path),
                }
            )

        docs = discover_documents(governance_repo, base_name, domain, service, feature_id, legacy_feature, source_repo)
        canonical_docs = select_canonical_documents(docs)

        legacy_features.append(
            {
                "old_id": base_name,
                "derived_domain": domain,
                "derived_service": service,
                "feature_id": feature_id,
                "legacy_feature": legacy_feature,
                "milestones": milestones,
                "proposed": {
                    "base_branch": feature_id,
                    "plan_branch": f"{feature_id}-plan",
                },
                "state": state,
                "dossier_path": relative_to_root(control_repo, migration_dossier_dir(control_repo, domain, service, feature_id)),
                "documents": docs,
                "document_audit": build_document_audit(
                    build_legacy_branch_variants(base_name, governance_repo, source_repo),
                    docs,
                    canonical_docs,
                ),
            }
        )

    result = {
        "status": "pass",
        "legacy_features": legacy_features,
        "total": len(legacy_features),
        "conflicts": conflicts,
        "governance_repo": str(governance_repo),
        "control_repo": str(control_repo),
    }
    if governance_warning:
        result.setdefault("warnings", []).append(governance_warning)
    if control_warning:
        result.setdefault("warnings", []).append(control_warning)
    return result


def cmd_migrate_feature(args: argparse.Namespace) -> dict:
    """Execute migration for a single feature."""
    try:
        governance_repo, governance_warning = resolve_governance_repo(args.governance_repo)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    init_feature_ops = load_init_feature_ops()

    err = init_feature_ops.validate_feature_id(args.feature_id)
    if err:
        return {"status": "fail", "error": err}

    for field_name, value in [("domain", args.domain), ("service", args.service)]:
        err = init_feature_ops.validate_safe_id(value, field_name)
        if err:
            return {"status": "fail", "error": err}

    dry_run = args.dry_run
    feature_id = args.feature_id
    domain = args.domain
    service = args.service
    old_id = args.old_id
    username = args.username or "unknown"
    timestamp = now_iso()
    source_repo = Path(args.source_repo) if getattr(args, "source_repo", None) else None
    try:
        control_repo, control_warning = resolve_control_repo(getattr(args, "control_repo", None), governance_repo, source_repo)
    except RuntimeError as exc:
        return {"status": "fail", "error": str(exc)}

    feature_dir = governance_repo / "features" / domain / service / feature_id
    feature_path = feature_dir / "feature.yaml"
    index_path = governance_repo / "feature-index.yaml"
    summary_path = feature_dir / "summary.md"
    problems_path = feature_dir / "problems.md"
    artifact_source = governance_repo / LEGACY_BRANCHES_DIR / old_id / LEGACY_ARTIFACTS_DIR
    dossier_dir, record_path, _, _ = migration_record_paths(control_repo, domain, service, feature_id)

    try:
        index_data, _index_exists = init_feature_ops.read_feature_index(str(governance_repo))
    except RuntimeError as e:
        return {"status": "fail", "error": str(e)}

    existing_ids = [entry.get("id") or entry.get("featureId") for entry in index_data.get("features", [])]
    if feature_id in existing_ids:
        return {
            "status": "fail",
            "error": f"Feature '{feature_id}' already exists in feature-index.yaml",
        }

    try:
        legacy_feature = derive_legacy_feature(old_id, domain, service)
    except ValueError as exc:
        return {"status": "fail", "error": str(exc)}

    milestones = detect_legacy_milestones(governance_repo, old_id)
    fallback_phase = derive_state(milestones)
    legacy_state, legacy_state_path = find_legacy_state(governance_repo, old_id, domain, service, legacy_feature)
    if legacy_state:
        raw_phase = legacy_state.get("current_phase") or legacy_state.get("phase")
        if isinstance(raw_phase, str) and raw_phase:
            fallback_phase = raw_phase

    warnings: list[str] = []
    if governance_warning:
        warnings.append(governance_warning)
    if control_warning:
        warnings.append(control_warning)

    if dry_run:
        planned_actions = [
            f"Create feature.yaml at {feature_path}",
            f"Update feature-index.yaml at {index_path}",
            f"Create summary stub at {summary_path}",
            f"Create problems log at {problems_path}",
            f"Write migration dossier at {dossier_dir}",
            f"Write migration record at {record_path}",
        ]
        if legacy_state_path:
            planned_actions.append(f"Preserve legacy state from {legacy_state_path}")
        if artifact_source.exists():
            planned_actions.append(f"Copy legacy artifacts from {artifact_source}")

        # Document discovery preview
        docs = discover_documents(governance_repo, old_id, domain, service, feature_id, legacy_feature, source_repo)
        canonical_docs = select_canonical_documents(docs)
        legacy_branches = build_legacy_branch_variants(old_id, governance_repo, source_repo)
        docs_target = governance_repo / "features" / domain / service / feature_id / "docs"
        for doc in docs:
            planned_actions.append(
                f"Mirror document [{document_source_label(doc)}:{doc.get('source_branch') or 'working-tree'}] {doc['relative_path']} → {dossier_dir / build_mirror_relative_path(doc)}"
            )
        for doc in canonical_docs:
            planned_actions.append(
                f"Migrate canonical document [{document_source_label(doc)}:{doc.get('source_branch') or 'working-tree'}] {doc['relative_path']} → {docs_target / doc['relative_path']}"
            )

        return {
            "status": "pass",
            "feature_id": feature_id,
            "legacy_feature": legacy_feature,
            "dry_run": True,
            "planned_actions": planned_actions,
            "feature_yaml_created": False,
            "index_updated": False,
            "legacy_state_path": legacy_state_path,
            "documents_discovered": docs,
            "documents_discovered_count": len(docs),
            "document_audit": build_document_audit(legacy_branches, docs, canonical_docs),
            "governance_repo": str(governance_repo),
            "dossier_path": str(dossier_dir),
            "migration_record_path": str(record_path),
            "warnings": warnings,
        }

    feature_data, legacy_state_path, feature_warnings = build_migrated_feature_data(
        governance_repo,
        old_id,
        feature_id,
        domain,
        service,
        legacy_feature,
        username,
        timestamp,
        fallback_phase,
    )
    warnings.extend(feature_warnings)

    feature_dir.mkdir(parents=True, exist_ok=True)

    feature_yaml_created = False
    if not feature_path.exists():
        try:
            init_feature_ops.atomic_write_yaml(feature_path, feature_data)
            feature_yaml_created = True
        except OSError as e:
            return {"status": "fail", "error": f"Failed to create feature.yaml: {e}"}

    index_updated = False
    try:
        if "features" not in index_data:
            index_data["features"] = []

        existing_ids = [entry.get("id") or entry.get("featureId") for entry in index_data["features"]]
        if feature_id not in existing_ids:
            index_data["features"].append(build_index_entry(feature_data, old_id, username))
            index_path.parent.mkdir(parents=True, exist_ok=True)
            init_feature_ops.atomic_write_yaml(index_path, index_data)
            index_updated = True
    except (OSError, yaml.YAMLError) as e:
        return {"status": "fail", "error": f"Failed to update feature-index.yaml: {e}"}

    summary_created = False
    try:
        if not summary_path.exists():
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                make_migration_summary(feature_id, domain, service, username, timestamp, old_id),
                encoding="utf-8",
            )
            summary_created = True
    except OSError as e:
        return {"status": "fail", "error": f"Failed to create summary.md: {e}"}

    try:
        problems_created = create_problems_log(feature_dir, feature_id, domain, service, timestamp)
    except OSError as e:
        return {"status": "fail", "error": f"Failed to create problems.md: {e}"}

    try:
        artifacts_copied = copy_legacy_artifacts(governance_repo, old_id, feature_dir)
    except OSError as e:
        return {"status": "fail", "error": f"Failed to copy legacy artifacts: {e}"}

    # Document migration
    try:
        documents_result = migrate_documents(
            governance_repo, control_repo, old_id, domain, service, feature_id, legacy_feature, source_repo,
        )
    except OSError as e:
        return {"status": "fail", "error": f"Failed to migrate documents: {e}"}

    migration_record = {
        "version": 1,
        "feature_id": feature_id,
        "legacy_feature": legacy_feature,
        "old_id": old_id,
        "domain": domain,
        "service": service,
        "status": "migrated",
        "migrated_at": timestamp,
        "updated_at": timestamp,
        "repos": {
            "governance": str(governance_repo),
            "source": str(source_repo) if source_repo else None,
            "control": str(control_repo),
        },
        "branch_refs": {
            "governance": build_legacy_branch_variants(old_id, governance_repo, None),
            "source": build_legacy_branch_variants(old_id, governance_repo, source_repo) if source_repo else [],
        },
        "documents": {
            "discovered_count": documents_result["discovered_count"],
            "mirrored_count": documents_result["mirrored_count"],
            "canonical_count": documents_result["canonical_count"],
            "discovered": documents_result["discovered_records"],
            "canonical": documents_result["canonical_records"],
            "document_audit": documents_result["document_audit"],
        },
        "verification": {
            "status": "pending",
            "verified_at": None,
            "checks": [],
            "approval_path": None,
            "cleanup_receipt_path": None,
        },
        "cleanup": {
            "status": "pending",
            "approval_path": None,
            "receipt_path": None,
            "approved_at": None,
            "approved_by": None,
            "executed_at": None,
        },
    }

    try:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_yaml(record_path, migration_record)
    except OSError as e:
        return {"status": "fail", "error": f"Failed to write migration record: {e}"}

    return {
        "status": "pass",
        "feature_id": feature_id,
        "legacy_feature": legacy_feature,
        "dry_run": False,
        "feature_yaml_created": feature_yaml_created,
        "index_updated": index_updated,
        "summary_created": summary_created,
        "problems_created": problems_created,
        "artifacts_copied": artifacts_copied,
        "documents_migrated": documents_result["documents_migrated"],
        "documents_source": documents_result["documents_source"],
        "documents_discovered_count": documents_result["discovered_count"],
        "documents_mirrored_count": documents_result["mirrored_count"],
        "canonical_documents_count": documents_result["canonical_count"],
        "document_audit": documents_result["document_audit"],
        "governance_repo": str(governance_repo),
        "dossier_path": documents_result["dossier_dir"],
        "migration_record_path": str(record_path),
        "legacy_state_path": legacy_state_path,
        "warnings": sorted(set(warnings)),
    }


def cmd_check_conflicts(args: argparse.Namespace) -> dict:
    """Check for naming conflicts before migration."""
    try:
        governance_repo, governance_warning = resolve_governance_repo(args.governance_repo)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    feature_id = args.feature_id
    domain = args.domain
    service = args.service

    target_path = governance_repo / "features" / domain / service / feature_id / "feature.yaml"

    if target_path.exists():
        result = {
            "status": "conflict",
            "conflict": True,
            "existing_path": str(target_path),
        }
        if governance_warning:
            result["warning"] = governance_warning
        return result

    result = {
        "status": "pass",
        "conflict": False,
        "existing_path": None,
    }
    if governance_warning:
        result["warning"] = governance_warning
    return result


def cmd_verify(args: argparse.Namespace) -> dict:
    """Verify a migrated feature has all expected artifacts."""
    try:
        governance_repo, governance_warning = resolve_governance_repo(args.governance_repo)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    init_feature_ops = load_init_feature_ops()

    err = init_feature_ops.validate_feature_id(args.feature_id)
    if err:
        return {"status": "fail", "error": err}

    for field_name, value in [("domain", args.domain), ("service", args.service)]:
        err = init_feature_ops.validate_safe_id(value, field_name)
        if err:
            return {"status": "fail", "error": err}

    source_repo = Path(args.source_repo) if getattr(args, "source_repo", None) else None
    try:
        control_repo, control_warning = resolve_control_repo(getattr(args, "control_repo", None), governance_repo, source_repo)
    except RuntimeError as exc:
        return {"status": "fail", "error": str(exc)}

    result = verify_migration(governance_repo, args.feature_id, args.domain, args.service, control_repo)
    if governance_warning:
        result.setdefault("warnings", []).append(governance_warning)
    if control_warning:
        result.setdefault("warnings", []).append(control_warning)
    return result


def cmd_cleanup(args: argparse.Namespace) -> dict:
    """Clean up legacy artifacts and source documents after verified migration."""
    try:
        governance_repo, governance_warning = resolve_governance_repo(args.governance_repo)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    init_feature_ops = load_init_feature_ops()

    err = init_feature_ops.validate_feature_id(args.feature_id)
    if err:
        return {"status": "fail", "error": err}

    for field_name, value in [("domain", args.domain), ("service", args.service)]:
        err = init_feature_ops.validate_safe_id(value, field_name)
        if err:
            return {"status": "fail", "error": err}

    feature_id = args.feature_id
    domain = args.domain
    service = args.service
    old_id = args.old_id
    dry_run = args.dry_run
    source_repo = Path(args.source_repo) if getattr(args, "source_repo", None) else None
    try:
        control_repo, control_warning = resolve_control_repo(getattr(args, "control_repo", None), governance_repo, source_repo)
    except RuntimeError as exc:
        return {"status": "fail", "error": str(exc)}

    try:
        legacy_feature = derive_legacy_feature(old_id, domain, service)
    except ValueError as exc:
        return {"status": "fail", "error": str(exc)}

    dossier_dir, record_path, approval_path, receipt_path = migration_record_paths(control_repo, domain, service, feature_id)
    record = read_yaml_if_exists(record_path)
    if record is None:
        return {
            "status": "fail",
            "error": "Cleanup blocked — migration record is missing. Re-run migrate before cleanup.",
            "migration_record_path": relative_to_root(control_repo, record_path),
        }

    # Gate: verify migration passed before allowing cleanup
    verification = verify_migration(governance_repo, feature_id, domain, service, control_repo)
    if verification["status"] != "pass":
        return {
            "status": "fail",
            "error": "Cleanup blocked — migration verification did not pass. Run 'verify' first.",
            "verification": verification,
        }

    planned_deletions: list[dict] = []
    planned_branch_deletions: list[dict] = []
    delete_remote = getattr(args, "delete_remote_branches", False)

    # 1. Governance legacy branch directory
    legacy_dir = governance_repo / LEGACY_BRANCHES_DIR / old_id
    if legacy_dir.is_dir():
        planned_deletions.append({
            "path": str(legacy_dir),
            "type": "directory",
            "source": "governance-legacy-branch",
        })

    # 2. Source repo Docs/{domain}/{service}/{featureId}/
    if source_repo:
        docs_folder = _find_docs_folder(source_repo)
        if docs_folder:
            source_docs = docs_folder / domain / service / legacy_feature
            if source_docs.is_dir():
                planned_deletions.append({
                    "path": str(source_docs),
                    "type": "directory",
                    "source": "source-repo-docs-flat",
                })

        # 3. Source repo feature-scoped _bmad-output artifacts
        bmad_output = source_repo / "_bmad-output" / "lens-work" / "initiatives" / domain / service
        feature_yaml = bmad_output / f"{legacy_feature}.yaml"
        feature_dir = bmad_output / legacy_feature
        if feature_yaml.is_file():
            planned_deletions.append({
                "path": str(feature_yaml),
                "type": "file",
                "source": "source-bmad-output-feature-file",
            })
        if feature_dir.is_dir():
            planned_deletions.append({
                "path": str(feature_dir),
                "type": "directory",
                "source": "source-bmad-output-feature-dir",
            })

    # 4. Remote branch cleanup (when --delete-remote-branches is set)
    if delete_remote:
        # Governance repo: base branch + milestone branches
        gov_base_ref = f"origin/{old_id}"
        if _git_ref_exists(governance_repo, gov_base_ref):
            planned_branch_deletions.append({
                "branch": old_id,
                "repo": str(governance_repo),
                "repo_label": "governance",
                "command": f"git -C {governance_repo} push origin --delete {old_id}",
            })
        milestones = detect_legacy_milestones(governance_repo, old_id)
        for ms in milestones:
            ms_branch = f"{old_id}-{ms}"
            planned_branch_deletions.append({
                "branch": ms_branch,
                "repo": str(governance_repo),
                "repo_label": "governance",
                "command": f"git -C {governance_repo} push origin --delete {ms_branch}",
            })

        # Source repo: base branch + milestone branches
        if source_repo:
            src_base_ref = f"origin/{old_id}"
            if _git_ref_exists(source_repo, src_base_ref):
                planned_branch_deletions.append({
                    "branch": old_id,
                    "repo": str(source_repo),
                    "repo_label": "source",
                    "command": f"git -C {source_repo} push origin --delete {old_id}",
                })
            src_ms_branches = _git_list_remote_branches(source_repo, f"origin/{old_id}-*")
            src_prefix = f"origin/{old_id}-"
            for branch in src_ms_branches:
                if branch.startswith(src_prefix):
                    branch_name = branch[len("origin/"):]
                    planned_branch_deletions.append({
                        "branch": branch_name,
                        "repo": str(source_repo),
                        "repo_label": "source",
                        "command": f"git -C {source_repo} push origin --delete {branch_name}",
                    })

    if dry_run:
        result: dict = {
            "status": "pass",
            "feature_id": feature_id,
            "legacy_feature": legacy_feature,
            "dry_run": True,
            "planned_deletions": planned_deletions,
            "approval_record_path": relative_to_root(control_repo, approval_path),
            "cleanup_receipt_path": relative_to_root(control_repo, receipt_path),
            "dossier_path": relative_to_root(control_repo, dossier_dir),
        }
        if planned_branch_deletions:
            result["planned_branch_deletions"] = planned_branch_deletions
        if control_warning:
            result["warning"] = control_warning
        return result

    actor = args.actor or detect_git_user(control_repo)
    approval_record = {
        "feature_id": feature_id,
        "legacy_feature": legacy_feature,
        "old_id": old_id,
        "domain": domain,
        "service": service,
        "approved_at": now_iso(),
        "approved_by": actor,
        "verification_status": verification["status"],
        "migration_record_path": relative_to_root(control_repo, record_path),
        "planned_deletions": planned_deletions,
        "planned_branch_deletions": planned_branch_deletions,
    }

    try:
        approval_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_yaml(approval_path, approval_record)
    except OSError as e:
        return {"status": "fail", "error": f"Failed to write cleanup approval artifact: {e}"}

    # Execute filesystem deletions
    cleaned: list[dict] = []
    errors: list[str] = []
    for deletion in planned_deletions:
        target = Path(deletion["path"])
        try:
            if target.is_dir():
                shutil.rmtree(target)
                cleaned.append(deletion)
            elif target.is_file():
                target.unlink()
                cleaned.append(deletion)
        except OSError as e:
            errors.append(f"Failed to delete {target}: {e}")

    # Execute remote branch deletions
    branches_deleted: list[dict] = []
    for bd in planned_branch_deletions:
        try:
            res = subprocess.run(
                ["git", "-C", bd["repo"], "push", "origin", "--delete", bd["branch"]],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode == 0:
                branches_deleted.append(bd)
            else:
                errors.append(f"Failed to delete remote branch {bd['branch']} in {bd['repo_label']}: {res.stderr.strip()}")
        except (subprocess.TimeoutExpired, OSError) as e:
            errors.append(f"Failed to delete remote branch {bd['branch']} in {bd['repo_label']}: {e}")

    result = {
        "status": "pass" if not errors else "partial",
        "feature_id": feature_id,
        "legacy_feature": legacy_feature,
        "dry_run": False,
        "cleaned": cleaned,
    }
    if branches_deleted:
        result["branches_deleted"] = branches_deleted
    if errors:
        result["errors"] = errors

    cleanup_receipt = {
        "feature_id": feature_id,
        "legacy_feature": legacy_feature,
        "old_id": old_id,
        "domain": domain,
        "service": service,
        "executed_at": now_iso(),
        "executed_by": actor,
        "approval_path": relative_to_root(control_repo, approval_path),
        "migration_record_path": relative_to_root(control_repo, record_path),
        "status": result["status"],
        "cleaned": cleaned,
        "branches_deleted": branches_deleted,
        "errors": errors,
    }

    try:
        atomic_write_yaml(receipt_path, cleanup_receipt)
    except OSError as e:
        return {"status": "fail", "error": f"Cleanup completed but receipt write failed: {e}", "partial_result": result}

    record = read_yaml_if_exists(record_path) or record
    record["status"] = "cleanup-complete" if result["status"] == "pass" else "cleanup-partial"
    record["updated_at"] = cleanup_receipt["executed_at"]
    record.setdefault("cleanup", {})
    record["cleanup"].update({
        "status": record["status"],
        "approval_path": relative_to_root(control_repo, approval_path),
        "receipt_path": relative_to_root(control_repo, receipt_path),
        "approved_at": approval_record["approved_at"],
        "approved_by": actor,
        "executed_at": cleanup_receipt["executed_at"],
    })
    record.setdefault("verification", {})
    record["verification"]["approval_path"] = relative_to_root(control_repo, approval_path)
    record["verification"]["cleanup_receipt_path"] = relative_to_root(control_repo, receipt_path)

    try:
        atomic_write_yaml(record_path, record)
    except OSError as e:
        return {"status": "fail", "error": f"Cleanup completed but migration record update failed: {e}", "partial_result": result}

    result["approval_record_path"] = relative_to_root(control_repo, approval_path)
    result["cleanup_receipt_path"] = relative_to_root(control_repo, receipt_path)
    result["migration_record_path"] = relative_to_root(control_repo, record_path)
    if governance_warning:
        result.setdefault("warnings", []).append(governance_warning)
    if control_warning:
        result.setdefault("warnings", []).append(control_warning)
    return result


def _scan_governance_features(governance_repo: Path) -> list[dict]:
    """Walk features/{domain}/{service}/{slug}/feature.yaml and return parsed metadata."""
    results = []
    features_root = governance_repo / "features"
    if not features_root.is_dir():
        return results
    for domain_dir in sorted(features_root.iterdir()):
        if not domain_dir.is_dir():
            continue
        domain = domain_dir.name
        for service_dir in sorted(domain_dir.iterdir()):
            if not service_dir.is_dir():
                continue
            service = service_dir.name
            for slug_dir in sorted(service_dir.iterdir()):
                if not slug_dir.is_dir():
                    continue
                feature_yaml_path = slug_dir / "feature.yaml"
                if not feature_yaml_path.is_file():
                    continue
                data = read_yaml_if_exists(feature_yaml_path)
                if data is None:
                    continue
                results.append({
                    "path": feature_yaml_path,
                    "dir_slug": slug_dir.name,
                    "domain": domain,
                    "service": service,
                    "data": data,
                })
    return results


def _is_short_feature_id(feature_id: str, domain: str, service: str) -> bool:
    """Return True when featureId does NOT already have the canonical {domain}-{service}- prefix."""
    init_feature_ops = load_init_feature_ops()
    prefix = init_feature_ops.canonical_feature_prefix(domain, service)
    return not feature_id.startswith(f"{prefix}-")


def _normalize_feature_index(
    governance_repo: Path,
    old_feature_id: str,
    canonical_feature_id: str,
    feature_slug: str,
    dry_run: bool,
) -> dict:
    """Update feature-index.yaml entry from short featureId to canonical form.

    Returns a dict with keys: ``status`` ('updated', 'not-found', 'skipped', 'error'), and
    optionally ``error`` or ``old``.
    """
    index_path = governance_repo / "feature-index.yaml"
    if not index_path.is_file():
        return {"status": "not-found"}
    index_data = read_yaml_if_exists(index_path)
    if index_data is None:
        return {"status": "not-found"}

    features = index_data.get("features", [])
    updated = False
    old_entry = None
    for entry in features:
        entry_id = entry.get("id") or entry.get("featureId")
        if entry_id == old_feature_id:
            old_entry = dict(entry)
            entry["id"] = canonical_feature_id
            entry["featureId"] = canonical_feature_id
            entry["featureSlug"] = feature_slug
            # Update plan_branch if it references the old id
            old_plan = entry.get("plan_branch", "")
            if old_plan == f"{old_feature_id}-plan":
                entry["plan_branch"] = f"{canonical_feature_id}-plan"
            updated = True
            break

    if not updated:
        return {"status": "not-found"}

    if not dry_run:
        try:
            atomic_write_yaml(index_path, index_data)
        except OSError as e:
            return {"status": "error", "error": str(e)}

    return {"status": "updated", "old": old_entry}


def _rename_control_repo_branches(
    control_repo: Path,
    old_feature_id: str,
    canonical_feature_id: str,
    dry_run: bool,
) -> list[dict]:
    """Rename {old_feature_id} and {old_feature_id}-plan branches in *control_repo*.

    Returns a list of rename records: {from, to, status}.
    """
    pairs = [
        (old_feature_id, canonical_feature_id),
        (f"{old_feature_id}-plan", f"{canonical_feature_id}-plan"),
    ]
    renames = []
    for old_branch, new_branch in pairs:
        # Check if old branch exists locally
        result = subprocess.run(
            ["git", "-C", str(control_repo), "branch", "--list", old_branch],
            capture_output=True, text=True,
        )
        exists = bool(result.stdout.strip())
        if not exists:
            renames.append({"from": old_branch, "to": new_branch, "status": "not-found"})
            continue

        # Check for conflict: new branch already exists
        result_new = subprocess.run(
            ["git", "-C", str(control_repo), "branch", "--list", new_branch],
            capture_output=True, text=True,
        )
        if result_new.stdout.strip():
            renames.append({"from": old_branch, "to": new_branch, "status": "conflict"})
            continue

        if dry_run:
            renames.append({"from": old_branch, "to": new_branch, "status": "would-rename"})
            continue

        mv = subprocess.run(
            ["git", "-C", str(control_repo), "branch", "-m", old_branch, new_branch],
            capture_output=True, text=True,
        )
        if mv.returncode == 0:
            renames.append({"from": old_branch, "to": new_branch, "status": "renamed"})
        else:
            renames.append({"from": old_branch, "to": new_branch, "status": "error", "error": mv.stderr.strip()})
    return renames


def cmd_normalize_feature_ids(args: argparse.Namespace) -> dict:
    """Scan governance features and normalize short featureIds to canonical {domain}-{service}-{slug} format.

    The governance directory name and docs paths use the featureSlug (short form).
    Only the featureId field and feature-index.yaml ids are upgraded to canonical form.
    Control-repo branches are renamed when --control-repo is supplied.
    """
    try:
        governance_repo, governance_warning = resolve_governance_repo(args.governance_repo)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    dry_run: bool = getattr(args, "dry_run", False)
    control_repo_arg: str | None = getattr(args, "control_repo", None)

    control_repo: Path | None = None
    control_warning: str | None = None
    if control_repo_arg:
        cr_path = Path(control_repo_arg)
        if not cr_path.exists():
            return {"status": "fail", "error": f"Control repo not found: {cr_path}"}
        control_repo = cr_path

    scanned = _scan_governance_features(governance_repo)

    needs_norm = [
        entry for entry in scanned
        if _is_short_feature_id(
            entry["data"].get("featureId", entry["dir_slug"]),
            entry["data"].get("domain", entry["domain"]),
            entry["data"].get("service", entry["service"]),
        )
    ]

    if not needs_norm:
        result: dict = {
            "status": "pass",
            "normalized": [],
            "total_scanned": len(scanned),
            "total_normalized": 0,
            "dry_run": dry_run,
        }
        if governance_warning:
            result.setdefault("warnings", []).append(governance_warning)
        return result

    init_feature_ops = load_init_feature_ops()

    normalized = []
    errors = []

    for entry in needs_norm:
        feature_yaml_path: Path = entry["path"]
        data: dict = entry["data"]
        domain: str = data.get("domain") or entry["domain"]
        service: str = data.get("service") or entry["service"]
        old_feature_id: str = data.get("featureId") or entry["dir_slug"]

        try:
            canonical_feature_id, feature_slug = init_feature_ops.resolve_feature_identity(
                old_feature_id, domain, service
            )
        except ValueError as exc:
            errors.append({"feature_yaml": str(feature_yaml_path), "error": str(exc)})
            continue

        # Determine correct docs paths (always use featureSlug / dir_slug, not featureId)
        slug_dir = entry["dir_slug"]
        expected_docs_path = f"docs/{domain}/{service}/{slug_dir}"
        expected_gov_docs_path = f"features/{domain}/{service}/{slug_dir}/docs"

        # Build updated feature.yaml data
        updated_data = dict(data)
        updated_data["featureId"] = canonical_feature_id
        updated_data["featureSlug"] = feature_slug

        # Fix docs block if present and pointing at old featureId
        if "docs" in updated_data and isinstance(updated_data["docs"], dict):
            docs_block = dict(updated_data["docs"])
            if docs_block.get("path", "").endswith(f"/{old_feature_id}"):
                docs_block["path"] = expected_docs_path
            if docs_block.get("governance_docs_path", "").endswith(f"/{old_feature_id}/docs"):
                docs_block["governance_docs_path"] = expected_gov_docs_path
            updated_data["docs"] = docs_block

        # Update feature-index.yaml
        index_result = _normalize_feature_index(
            governance_repo, old_feature_id, canonical_feature_id, feature_slug, dry_run
        )

        # Rename branches in control repo
        branch_renames: list[dict] = []
        if control_repo is not None:
            branch_renames = _rename_control_repo_branches(
                control_repo, old_feature_id, canonical_feature_id, dry_run
            )

        record: dict = {
            "feature_yaml": str(feature_yaml_path),
            "domain": domain,
            "service": service,
            "old_feature_id": old_feature_id,
            "canonical_feature_id": canonical_feature_id,
            "feature_slug": feature_slug,
            "index_update": index_result,
            "branch_renames": branch_renames,
        }

        if not dry_run:
            try:
                atomic_write_yaml(feature_yaml_path, updated_data)
                record["feature_yaml_status"] = "updated"
            except OSError as e:
                record["feature_yaml_status"] = "error"
                record["feature_yaml_error"] = str(e)
                errors.append(record)
                continue
        else:
            record["feature_yaml_status"] = "would-update"
            record["proposed_feature_yaml"] = {
                "featureId": canonical_feature_id,
                "featureSlug": feature_slug,
                "docs": updated_data.get("docs"),
            }

        normalized.append(record)

    result = {
        "status": "pass" if not errors else "partial",
        "normalized": normalized,
        "total_scanned": len(scanned),
        "total_normalized": len(normalized),
        "dry_run": dry_run,
    }
    if errors:
        result["errors"] = errors
    if governance_warning:
        result.setdefault("warnings", []).append(governance_warning)
    if control_warning:
        result.setdefault("warnings", []).append(control_warning)
    return result


def _fix_governance_feature_dir(
    governance_repo: Path,
    domain: str,
    service: str,
    old_dir_name: str,
    feature_slug: str,
    feature_yaml_data: dict,
    project_root: "Path | None",
    dry_run: bool,
) -> dict:
    """Rename a governance feature directory from featureId to featureSlug and fix docs paths.

    Returns a record dict with ``governance_dir``, ``docs_dir``, ``feature_yaml_status``,
    and optionally ``proposed_docs``.
    """
    old_dir = governance_repo / "features" / domain / service / old_dir_name
    new_dir = governance_repo / "features" / domain / service / feature_slug

    correct_docs_path = f"docs/{domain}/{service}/{feature_slug}"
    correct_gov_docs_path = f"features/{domain}/{service}/{feature_slug}/docs"

    updated_data = dict(feature_yaml_data)
    if "docs" in updated_data and isinstance(updated_data["docs"], dict):
        docs_block = dict(updated_data["docs"])
        docs_block["path"] = correct_docs_path
        docs_block["governance_docs_path"] = correct_gov_docs_path
        updated_data["docs"] = docs_block

    docs_dir_result: "dict | None" = None
    if project_root is not None:
        old_docs_dir = project_root / "docs" / domain / service / old_dir_name
        new_docs_dir = project_root / "docs" / domain / service / feature_slug
        if old_docs_dir.exists():
            if dry_run:
                docs_dir_result = {"from": str(old_docs_dir), "to": str(new_docs_dir), "status": "would-rename"}
            else:
                old_docs_dir.rename(new_docs_dir)
                docs_dir_result = {"from": str(old_docs_dir), "to": str(new_docs_dir), "status": "renamed"}
        else:
            docs_dir_result = {"from": str(old_docs_dir), "to": str(new_docs_dir), "status": "not-found"}

    if dry_run:
        return {
            "governance_dir": {"from": str(old_dir), "to": str(new_dir), "status": "would-rename"},
            "docs_dir": docs_dir_result,
            "feature_yaml_status": "would-update",
            "proposed_docs": updated_data.get("docs"),
        }

    old_dir.rename(new_dir)
    feature_yaml_path = new_dir / "feature.yaml"
    atomic_write_yaml(feature_yaml_path, updated_data)

    return {
        "governance_dir": {"from": str(old_dir), "to": str(new_dir), "status": "renamed"},
        "docs_dir": docs_dir_result,
        "feature_yaml_status": "updated",
    }


def cmd_fix_feature_dirs(args: argparse.Namespace) -> dict:
    """Rename governance feature directories that use featureId instead of featureSlug.

    Governance feature directories must always use the featureSlug (short form), never the
    canonical featureId (``{domain}-{service}-{slug}``).  This command scans all
    ``features/{domain}/{service}/{dir}/feature.yaml`` files, detects misnamed directories
    (where the directory name equals featureId rather than featureSlug), renames them, and
    updates the ``docs.path`` / ``docs.governance_docs_path`` fields in each affected
    feature.yaml.

    When ``--project-root`` is provided the corresponding
    ``docs/{domain}/{service}/{old_dir}`` directory is also renamed.
    """
    try:
        governance_repo, governance_warning = resolve_governance_repo(args.governance_repo)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    dry_run: bool = getattr(args, "dry_run", False)
    project_root_arg: "str | None" = getattr(args, "project_root", None)

    project_root: "Path | None" = None
    if project_root_arg:
        pr_path = Path(project_root_arg)
        if not pr_path.exists():
            return {"status": "fail", "error": f"Project root not found: {pr_path}"}
        project_root = pr_path

    scanned = _scan_governance_features(governance_repo)

    needs_fix = [
        entry for entry in scanned
        if entry["data"].get("featureSlug") and entry["dir_slug"] != entry["data"]["featureSlug"]
    ]

    if not needs_fix:
        result: dict = {
            "status": "pass",
            "fixed": [],
            "total_scanned": len(scanned),
            "total_fixed": 0,
            "dry_run": dry_run,
        }
        if governance_warning:
            result.setdefault("warnings", []).append(governance_warning)
        return result

    fixed: list[dict] = []
    errors: list[dict] = []

    for entry in needs_fix:
        data = entry["data"]
        domain: str = data.get("domain") or entry["domain"]
        service: str = data.get("service") or entry["service"]
        feature_slug: str = data["featureSlug"]
        dir_name: str = entry["dir_slug"]
        canonical_feature_id: str = data.get("featureId", dir_name)

        record: dict = {
            "domain": domain,
            "service": service,
            "old_dir_name": dir_name,
            "feature_slug": feature_slug,
            "canonical_feature_id": canonical_feature_id,
        }

        try:
            fix_result = _fix_governance_feature_dir(
                governance_repo=governance_repo,
                domain=domain,
                service=service,
                old_dir_name=dir_name,
                feature_slug=feature_slug,
                feature_yaml_data=data,
                project_root=project_root,
                dry_run=dry_run,
            )
            record.update(fix_result)
            fixed.append(record)
        except OSError as e:
            record["status_error"] = str(e)
            errors.append(record)

    result = {
        "status": "pass" if not errors else "partial",
        "fixed": fixed,
        "total_scanned": len(scanned),
        "total_fixed": len(fixed),
        "dry_run": dry_run,
    }
    if errors:
        result["errors"] = errors
    if governance_warning:
        result.setdefault("warnings", []).append(governance_warning)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migration operations — scan legacy LENS v3 branches and migrate to Lens Next model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scan --governance-repo /path/to/repo
  %(prog)s scan --governance-repo /path/to/repo --branch-pattern "^custom-.*$"

  %(prog)s scan --governance-repo /path/to/repo --source-repo /path/to/source

  %(prog)s check-conflicts --governance-repo /path/to/repo \\
    --feature-id auth-login --domain platform --service identity

  %(prog)s migrate-feature --governance-repo /path/to/repo \\
    --old-id platform-identity-auth-login --feature-id auth-login \\
    --domain platform --service identity --username cweber --dry-run

  %(prog)s migrate-feature --governance-repo /path/to/repo \\
    --old-id platform-identity-auth-login --feature-id auth-login \\
    --domain platform --service identity --username cweber \\
    --source-repo /path/to/source

  %(prog)s verify --governance-repo /path/to/repo \\
    --feature-id auth-login --domain platform --service identity

  %(prog)s cleanup --governance-repo /path/to/repo \\
    --old-id platform-identity-auth-login --feature-id auth-login \\
    --domain platform --service identity --dry-run

  %(prog)s cleanup --governance-repo /path/to/repo \\
    --old-id platform-identity-auth-login --feature-id auth-login \\
    --domain platform --service identity --source-repo /path/to/source

  %(prog)s normalize-feature-ids --governance-repo /path/to/repo --dry-run

  %(prog)s normalize-feature-ids --governance-repo /path/to/repo \\
    --control-repo /path/to/control-repo

  %(prog)s fix-feature-dirs --governance-repo /path/to/repo --dry-run

  %(prog)s fix-feature-dirs --governance-repo /path/to/repo \\
    --project-root /path/to/project-root
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_p = subparsers.add_parser("scan", help="Detect legacy branches and build migration plan")
    scan_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    scan_p.add_argument("--branch-pattern", help="Optional regex override for branch pattern detection")
    scan_p.add_argument("--source-repo", help="Path to source repo for document discovery")
    scan_p.add_argument("--control-repo", help="Optional control repo root for migration dossier preview")

    mig_p = subparsers.add_parser("migrate-feature", help="Execute migration for a single feature")
    mig_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    mig_p.add_argument("--old-id", required=True, help="Old branch name (legacy ID)")
    mig_p.add_argument("--feature-id", required=True, help="New feature ID (kebab-case)")
    mig_p.add_argument("--domain", required=True, help="Domain name")
    mig_p.add_argument("--service", required=True, help="Service name")
    mig_p.add_argument("--username", default="unknown", help="Username performing the migration")
    mig_p.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    mig_p.add_argument("--source-repo", help="Path to source repo for document migration")
    mig_p.add_argument("--control-repo", help="Optional control repo root for dossier storage")

    cc_p = subparsers.add_parser("check-conflicts", help="Check for naming conflicts before migration")
    cc_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    cc_p.add_argument("--feature-id", required=True, help="Target feature ID")
    cc_p.add_argument("--domain", required=True, help="Domain name")
    cc_p.add_argument("--service", required=True, help="Service name")

    ver_p = subparsers.add_parser("verify", help="Verify a migrated feature has all expected artifacts")
    ver_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    ver_p.add_argument("--feature-id", required=True, help="Feature ID to verify")
    ver_p.add_argument("--domain", required=True, help="Domain name")
    ver_p.add_argument("--service", required=True, help="Service name")
    ver_p.add_argument("--source-repo", help="Optional source repo used to help infer control repo")
    ver_p.add_argument("--control-repo", help="Optional control repo root for dossier verification")

    cl_p = subparsers.add_parser("cleanup", help="Remove legacy branches and source docs after verified migration")
    cl_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    cl_p.add_argument("--old-id", required=True, help="Old branch name (legacy ID)")
    cl_p.add_argument("--feature-id", required=True, help="Feature ID to clean up")
    cl_p.add_argument("--domain", required=True, help="Domain name")
    cl_p.add_argument("--service", required=True, help="Service name")
    cl_p.add_argument("--source-repo", help="Path to source repo (for Docs/ and _bmad-output cleanup)")
    cl_p.add_argument("--control-repo", help="Optional control repo root for dossier records")
    cl_p.add_argument("--actor", help="Actor recorded in cleanup approval and receipt artifacts")
    cl_p.add_argument("--delete-remote-branches", action="store_true",
                       help="Also delete legacy remote branches (governance + source repo)")
    cl_p.add_argument("--dry-run", action="store_true", help="Preview deletions without executing")

    norm_p = subparsers.add_parser(
        "normalize-feature-ids",
        help="Normalize short featureIds to canonical {domain}-{service}-{slug} format in all governance feature.yaml files",
    )
    norm_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    norm_p.add_argument("--control-repo", help="Optional path to control repo for branch renaming")
    norm_p.add_argument("--dry-run", action="store_true", help="Preview changes without writing")

    fix_p = subparsers.add_parser(
        "fix-feature-dirs",
        help="Rename governance feature directories that use featureId instead of featureSlug",
    )
    fix_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    fix_p.add_argument(
        "--project-root",
        help="Optional path to project root for renaming docs/{domain}/{service}/{dir} directories",
    )
    fix_p.add_argument("--dry-run", action="store_true", help="Preview changes without writing")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "scan": cmd_scan,
        "migrate-feature": cmd_migrate_feature,
        "check-conflicts": cmd_check_conflicts,
        "verify": cmd_verify,
        "cleanup": cmd_cleanup,
        "normalize-feature-ids": cmd_normalize_feature_ids,
        "fix-feature-dirs": cmd_fix_feature_dirs,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()

    status = result.get("status", "fail")
    sys.exit(0 if status in ("pass", "conflict") else 1)


if __name__ == "__main__":
    main()
