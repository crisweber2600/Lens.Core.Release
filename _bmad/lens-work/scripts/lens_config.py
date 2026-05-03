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


class ConfigError(ValueError):
    """Raised when Lens config discovery or loading fails."""


@dataclass(frozen=True)
class LensConfig:
    data: dict[str, Any]
    config_path: Path
    user_config_path: Path | None
    project_root: Path
    module_root: Path


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