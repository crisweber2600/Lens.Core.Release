"""Config discovery and path normalization helpers for Lens Workbench scripts."""

from __future__ import annotations

import ntpath
import os
import platform
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REQUIRED_CONFIG_FIELDS = {
    "governance_repo_path",
    "control_topology",
    "target_projects_path",
    "default_git_remote",
    "lifecycle_contract",
}

USER_OVERRIDABLE_FIELDS = {
    "github_username",
    "default_branch",
    "target_branch_strategy",
    "governance_repo_path",
    "target_projects_path",
    "default_git_remote",
}

PATH_FIELDS = {
    "governance_repo_path",
    "target_projects_path",
    "lifecycle_contract",
    "planning_artifacts",
    "implementation_artifacts",
    "project_knowledge",
    "initiative_output_folder",
    "personal_output_folder",
}

_GIT_BASH_DRIVE_RE = re.compile(r"^/([A-Za-z])(?:/(.*))?$")
_NEXTLENS_DOCS_CONTEXT = Path("docs") / "nextlens" / "src"
_NEXTLENS_TOPDOWN_REFERENCE_DOCS = (
    (
        Path("nextlens-src-topdownlens") / "guides" / "bugfix-flow.md",
        "TopDownLens bugfix guide",
        (
            "implement only in approved target surfaces",
            "Governance repo: stay on `main`; no feature-branch governance topology.",
            "They must not hand-copy changes into governance or release as a fallback.",
        ),
    ),
    (
        Path("nextlens-src-topdownlens") / "examples" / "bugfix-example.md",
        "TopDownLens bugfix example",
        (
            "Target branch: prepared by `lens-git-orchestration` for the resolved target repo.",
            "It does not write directly to governance feature folders or release paths.",
        ),
    ),
)


class ConfigError(ValueError):
    """Raised when Lens config discovery or loading fails."""


@dataclass(frozen=True)
class LensConfig:
    data: dict[str, Any]
    config_path: Path
    user_config_path: Path | None
    project_root: Path
    module_root: Path


@dataclass(frozen=True)
class DesignConstraint:
    title: str
    source_path: Path
    excerpts: tuple[str, ...]


@dataclass(frozen=True)
class NextLensDesignContext:
    feature_id: str
    governance_repo_root: Path
    feature_yaml_path: Path
    control_repo_root: Path
    control_repo_path: Path
    docs_context_root: Path
    docs_context_path: Path
    feature_docs_root: Path
    skill_source_root: Path
    skill_source_path: Path
    runtime_target_root: Path
    runtime_target_path: Path
    constraints: tuple[DesignConstraint, ...]


def _windows_from_git_bash_drive(value: str) -> str:
    match = _GIT_BASH_DRIVE_RE.match(value)
    if not match:
        return value
    drive = match.group(1).upper()
    rest = (match.group(2) or "").replace("/", "\\")
    return f"{drive}:\\{rest}" if rest else f"{drive}:\\"


def normalize_path_text(
    value: str | os.PathLike[str],
    *,
    base: str | os.PathLike[str] | None = None,
    platform_system: str | None = None,
) -> str:
    """Return an absolute, normalized path string for the requested platform.

    On Windows this converts Git Bash drive paths such as `/d/repo` to
    `D:\\repo` before absolutizing, preventing `C:\\d\\repo` writes.
    """
    raw = os.path.expandvars(os.path.expanduser(os.fspath(value).strip()))
    system = (platform_system or platform.system()).lower()

    if system.startswith("win"):
        raw = _windows_from_git_bash_drive(raw)
        if ntpath.isabs(raw):
            return ntpath.normpath(raw)

        if base is None:
            base_text = os.getcwd()
        else:
            base_text = normalize_path_text(base, platform_system=platform_system)
        base_text = _windows_from_git_bash_drive(base_text)
        return ntpath.normpath(ntpath.join(base_text, raw))

    path = Path(raw)
    if not path.is_absolute():
        path = Path(base or os.getcwd()) / path
    return str(path.resolve(strict=False))


def normalize_absolute_path(
    value: str | os.PathLike[str],
    *,
    base: str | os.PathLike[str] | None = None,
) -> Path:
    """Return an absolute Path for the current OS, with Git Bash path repair."""
    return Path(normalize_path_text(value, base=base)).resolve(strict=False)


def project_root_for_config(config_path: Path) -> Path:
    """Return the target project root for `{project-root}/lens.core/_bmad/lens-work/bmadconfig.yaml`."""
    try:
        return config_path.resolve(strict=False).parents[2]
    except IndexError as exc:
        raise ConfigError(f"Cannot infer project root from {config_path}") from exc


def _candidate_config_paths(start: Path) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    current = start if start.is_dir() else start.parent

    for parent in [current, *current.parents]:
        for candidate in (
            parent / "bmadconfig.yaml",
            parent / "_bmad" / "lens-work" / "bmadconfig.yaml",
            parent / "TargetProjects" / "lens-dev" / "new-codebase" / "lens.core.src" / "_bmad" / "lens-work" / "bmadconfig.yaml",
            parent / "lens.core" / "_bmad" / "lens-work" / "bmadconfig.yaml",
        ):
            normalized = candidate.resolve(strict=False)
            if normalized not in seen:
                candidates.append(normalized)
                seen.add(normalized)
    return candidates


def find_module_config(
    start: str | os.PathLike[str] | None = None,
    *,
    explicit_config: str | os.PathLike[str] | None = None,
) -> Path:
    """Find the Lens module config by walking parent directories.

    This uses only Python filesystem APIs. It does not shell out to `rg`, git,
    or any editor search provider.
    """
    base = normalize_absolute_path(start or os.getcwd())
    if explicit_config:
        explicit = normalize_absolute_path(explicit_config, base=base)
        if explicit.exists():
            return explicit
        raise ConfigError(f"Lens module config not found: {explicit}")

    for candidate in _candidate_config_paths(base):
        if candidate.exists():
            return candidate

    raise ConfigError(f"Lens module config not found from {base}")


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Could not read {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping")
    return data


def _expand_placeholders(value: str, *, project_root: Path, module_root: Path) -> str:
    return (
        value.replace("{project-root}", str(project_root))
        .replace("{module-root}", str(module_root))
        .replace("{config-dir}", str(module_root))
    )


def normalize_config_path_value(value: Any, *, project_root: Path, module_root: Path) -> str:
    expanded = _expand_placeholders(str(value), project_root=project_root, module_root=module_root)
    return str(normalize_absolute_path(expanded, base=project_root))


def _merge_user_config(base: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in user.items():
        if key in USER_OVERRIDABLE_FIELDS:
            merged[key] = value
    return merged


def load_lens_config(
    config_path: str | os.PathLike[str] | None = None,
    *,
    start: str | os.PathLike[str] | None = None,
    user_config_path: str | os.PathLike[str] | None = None,
    validate_required: bool = True,
) -> LensConfig:
    """Load committed Lens config and optional user overrides."""
    config = find_module_config(start=start, explicit_config=config_path)
    module_root = config.parent.resolve(strict=False)
    project_root = project_root_for_config(config)
    data = _read_yaml_mapping(config)

    user_path = normalize_absolute_path(user_config_path, base=module_root) if user_config_path else module_root / "config.user.yaml"
    loaded_user_path: Path | None = None
    if user_path.exists():
        data = _merge_user_config(data, _read_yaml_mapping(user_path))
        loaded_user_path = user_path

    if validate_required:
        missing = sorted(field for field in REQUIRED_CONFIG_FIELDS if not data.get(field))
        if missing:
            raise ConfigError(f"Missing required Lens config field(s): {', '.join(missing)}")
        if str(data.get("control_topology")) != "3-branch":
            raise ConfigError("control_topology must be 3-branch")

    normalized = dict(data)
    for field in PATH_FIELDS:
        if normalized.get(field):
            normalized[field] = normalize_config_path_value(
                normalized[field],
                project_root=project_root,
                module_root=module_root,
            )

    return LensConfig(
        data=normalized,
        config_path=config,
        user_config_path=loaded_user_path,
        project_root=project_root,
        module_root=module_root,
    )


def discover_feature_yaml(governance_repo: str | os.PathLike[str], feature_id: str) -> Path | None:
    """Find a feature.yaml by deterministic filesystem traversal."""
    features_dir = normalize_absolute_path(governance_repo) / "features"
    if not features_dir.exists():
        return None

    for yaml_file in sorted(features_dir.rglob("feature.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(data, dict) and (data.get("featureId") == feature_id or data.get("feature_id") == feature_id):
            return yaml_file.resolve(strict=False)
    return None


def _fold_path(path: Path) -> Path:
    return Path(os.path.normcase(str(path)))


def _resolve_boundary_path(
    value: str | os.PathLike[str],
    *,
    base: str | os.PathLike[str] | None = None,
    require_exists: bool = True,
) -> Path:
    path = normalize_absolute_path(value, base=base)
    if require_exists:
        try:
            return path.resolve(strict=True)
        except OSError as exc:
            raise ConfigError(f"Path not found: {path}") from exc

    missing_parts: list[str] = []
    existing = path
    while not existing.exists():
        parent = existing.parent
        if parent == existing:
            break
        missing_parts.append(existing.name)
        existing = parent

    resolved = existing.resolve(strict=True) if existing.exists() else existing.resolve(strict=False)
    for name in reversed(missing_parts):
        resolved /= name
    return resolved


def _path_is_within_root(candidate: Path, root: Path) -> bool:
    try:
        _fold_path(candidate).relative_to(_fold_path(root))
        return True
    except ValueError:
        return False


def ensure_within_root(
    value: str | os.PathLike[str],
    *,
    approved_root: str | os.PathLike[str],
    label: str,
    base: str | os.PathLike[str] | None = None,
    require_exists: bool = True,
) -> Path:
    root = _resolve_boundary_path(approved_root, require_exists=True)
    candidate = _resolve_boundary_path(value, base=base, require_exists=require_exists)
    if not _path_is_within_root(candidate, root):
        raise ConfigError(f"{label} escapes approved root: {candidate} is outside {root}")
    return candidate


def _feature_repo_entries(feature_data: dict[str, Any]) -> list[dict[str, Any]]:
    target_repos = feature_data.get("target_repos") or []
    if not isinstance(target_repos, list):
        raise ConfigError("feature.yaml target_repos must be a list")
    entries = [entry for entry in target_repos if isinstance(entry, dict)]
    if not entries:
        raise ConfigError("feature.yaml target_repos must include mapping entries")
    return entries


def _resolve_control_repo_root(config: LensConfig) -> Path:
    target_projects_root = _resolve_boundary_path(config.data["target_projects_path"], require_exists=True)
    if _fold_path(config.project_root) == _fold_path(target_projects_root):
        raise ConfigError("target_projects_path must resolve to the TargetProjects root, not the skill source root")
    if not _path_is_within_root(config.project_root, target_projects_root):
        raise ConfigError(
            f"Configured skill source root {config.project_root} is outside target_projects_path {target_projects_root}"
        )
    return target_projects_root.parent.resolve(strict=True)


def _resolve_feature_yaml_for_context(
    *,
    feature_id: str,
    feature_path: str | os.PathLike[str] | None,
    governance_repo_root: Path,
) -> Path:
    if feature_path:
        path = _resolve_boundary_path(feature_path, require_exists=True)
        if not path.is_file():
            raise ConfigError(f"feature.yaml not found: {path}")
        return path

    path = discover_feature_yaml(governance_repo_root, feature_id)
    if path is None:
        raise ConfigError(f"feature.yaml not found for '{feature_id}'")
    return path


def _resolve_named_target_repo(
    entries: list[dict[str, Any]],
    *,
    name: str,
    control_repo_root: Path,
    target_projects_root: Path,
) -> Path:
    matches: list[Path] = []
    for entry in entries:
        if str(entry.get("name") or "").strip().lower() != name.lower():
            continue
        local_path = str(entry.get("local_path") or "").strip()
        if not local_path:
            raise ConfigError(f"feature.yaml target_repos entry '{name}' is missing local_path")
        matches.append(
            ensure_within_root(
                local_path,
                approved_root=target_projects_root,
                label=f"target repo '{name}' local_path",
                base=control_repo_root,
            )
        )

    if not matches:
        raise ConfigError(f"feature.yaml target_repos does not include '{name}'")
    if len(matches) > 1:
        raise ConfigError(f"feature.yaml target_repos includes multiple '{name}' entries")
    return matches[0]


def _load_topdown_constraints(docs_context_root: Path) -> tuple[DesignConstraint, ...]:
    constraints: list[DesignConstraint] = []
    missing: list[str] = []
    mismatched: list[str] = []

    for relative_path, title, excerpts in _NEXTLENS_TOPDOWN_REFERENCE_DOCS:
        source_path = docs_context_root / relative_path
        if not source_path.is_file():
            missing.append(str(source_path))
            continue

        text = source_path.read_text(encoding="utf-8")
        missing_excerpts = tuple(excerpt for excerpt in excerpts if excerpt not in text)
        if missing_excerpts:
            mismatched.append(f"{source_path}: missing excerpt(s): {', '.join(missing_excerpts)}")
            continue
        constraints.append(DesignConstraint(title=title, source_path=source_path, excerpts=tuple(excerpts)))

    if missing or mismatched:
        details = []
        if missing:
            details.append(f"missing docs: {', '.join(missing)}")
        if mismatched:
            details.append("; ".join(mismatched))
        raise ConfigError(f"NextLens docs context is incomplete or conflicting: {'; '.join(details)}")

    return tuple(constraints)


def resolve_nextlens_design_context(
    feature_id: str,
    *,
    start: str | os.PathLike[str] | None = None,
    config_path: str | os.PathLike[str] | None = None,
    user_config_path: str | os.PathLike[str] | None = None,
    governance_repo: str | os.PathLike[str] | None = None,
    feature_path: str | os.PathLike[str] | None = None,
    control_repo_override: str | os.PathLike[str] | None = None,
    docs_path_override: str | os.PathLike[str] | None = None,
    skill_source_override: str | os.PathLike[str] | None = None,
    runtime_target_override: str | os.PathLike[str] | None = None,
) -> NextLensDesignContext:
    invocation_root = normalize_absolute_path(start or os.getcwd())
    config = load_lens_config(config_path, start=invocation_root, user_config_path=user_config_path)
    governance_repo_root = _resolve_boundary_path(governance_repo or config.data["governance_repo_path"], require_exists=True)
    control_repo_root = _resolve_control_repo_root(config)
    control_repo_path = (
        ensure_within_root(
            control_repo_override,
            approved_root=control_repo_root,
            label="control repo override",
            base=invocation_root,
        )
        if control_repo_override
        else control_repo_root
    )
    feature_yaml_path = _resolve_feature_yaml_for_context(
        feature_id=feature_id,
        feature_path=feature_path,
        governance_repo_root=governance_repo_root,
    )
    feature_data = _read_yaml_mapping(feature_yaml_path)

    docs = feature_data.get("docs")
    if not isinstance(docs, dict) or not str(docs.get("path") or "").strip():
        raise ConfigError(f"feature.yaml missing docs.path for '{feature_id}'")

    target_projects_root = _resolve_boundary_path(config.data["target_projects_path"], require_exists=True)
    skill_source_root = ensure_within_root(
        config.project_root,
        approved_root=target_projects_root,
        label="skill source root",
    )
    feature_docs_root = ensure_within_root(
        str(docs["path"]),
        approved_root=control_repo_root,
        label="feature docs path",
        base=control_repo_root,
    )
    docs_context_root = ensure_within_root(
        _NEXTLENS_DOCS_CONTEXT,
        approved_root=control_repo_root,
        label="NextLens docs context root",
        base=control_repo_root,
    )
    if not _path_is_within_root(feature_docs_root, docs_context_root):
        raise ConfigError(
            f"feature docs path {feature_docs_root} conflicts with required NextLens docs root {docs_context_root}"
        )

    entries = _feature_repo_entries(feature_data)
    feature_skill_source_root = _resolve_named_target_repo(
        entries,
        name="lens.core.src",
        control_repo_root=control_repo_root,
        target_projects_root=target_projects_root,
    )
    if _fold_path(feature_skill_source_root) != _fold_path(skill_source_root):
        raise ConfigError(
            f"feature.yaml lens.core.src path {feature_skill_source_root} conflicts with configured skill root {skill_source_root}"
        )

    runtime_target_root = _resolve_named_target_repo(
        entries,
        name="NextLens",
        control_repo_root=control_repo_root,
        target_projects_root=target_projects_root,
    )

    docs_context_path = (
        ensure_within_root(
            docs_path_override,
            approved_root=docs_context_root,
            label="docs context override",
            base=invocation_root,
        )
        if docs_path_override
        else docs_context_root
    )
    skill_source_path = (
        ensure_within_root(
            skill_source_override,
            approved_root=skill_source_root,
            label="skill source override",
            base=invocation_root,
        )
        if skill_source_override
        else skill_source_root
    )
    runtime_target_path = (
        ensure_within_root(
            runtime_target_override,
            approved_root=runtime_target_root,
            label="runtime target override",
            base=invocation_root,
        )
        if runtime_target_override
        else runtime_target_root
    )

    return NextLensDesignContext(
        feature_id=feature_id,
        governance_repo_root=governance_repo_root,
        feature_yaml_path=feature_yaml_path,
        control_repo_root=control_repo_root,
        control_repo_path=control_repo_path,
        docs_context_root=docs_context_root,
        docs_context_path=docs_context_path,
        feature_docs_root=feature_docs_root,
        skill_source_root=skill_source_root,
        skill_source_path=skill_source_path,
        runtime_target_root=runtime_target_root,
        runtime_target_path=runtime_target_path,
        constraints=_load_topdown_constraints(docs_context_root),
    )