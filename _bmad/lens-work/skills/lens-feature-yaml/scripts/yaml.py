"""Lens YAML shim loader for script-entrypoint imports."""

from __future__ import annotations

import importlib.util
import hashlib
import os
from pathlib import Path
import sys


def _resolve_repo_root() -> Path:
    """Resolve the repository root by finding the first parent that contains `_bmad/`."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "_bmad").exists():
            return parent
    raise ImportError("Unable to locate repository root for YAML shim resolution")


def _load_external_pyyaml(repo_root: Path):
    """
    Load installed PyYAML package when available.

    This avoids importing local shim files named `yaml.py` from the repository.
    """
    for entry in sys.path:
        base = Path(entry or ".").resolve()
        if base == repo_root or repo_root in base.parents:
            continue
        init_py = base / "yaml" / "__init__.py"
        if not init_py.exists():
            continue

        module_name = (
            "_lens_external_yaml_"
            + hashlib.sha256(str(Path(__file__).resolve()).encode("utf-8")).hexdigest()
        )
        spec = importlib.util.spec_from_file_location(
            module_name,
            init_py,
            submodule_search_locations=[str(init_py.parent)],
        )
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    return None


def _resolve_root_yaml(repo_root: Path) -> Path:
    """Resolve the repo-root `yaml.py` by finding the first parent that also contains `_bmad/`."""
    candidate = repo_root / "yaml.py"
    if candidate.exists():
        return candidate
    raise ImportError("Unable to locate repository root yaml.py shim")


_REPO_ROOT = _resolve_repo_root()
_MODULE = _load_external_pyyaml(_REPO_ROOT) if os.getenv("GITHUB_ACTIONS", "").lower() == "true" else None
if _MODULE is None:
    _ROOT_YAML = _resolve_root_yaml(_REPO_ROOT)
    _SPEC = importlib.util.spec_from_file_location("_lens_yaml_root", _ROOT_YAML)
    if _SPEC is None or _SPEC.loader is None:
        raise ImportError(f"Unable to load Lens YAML shim from {_ROOT_YAML}")
    _MODULE = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(_MODULE)

YAMLError = _MODULE.YAMLError
safe_load = _MODULE.safe_load
safe_load_all = _MODULE.safe_load_all
safe_dump = _MODULE.safe_dump
dump = _MODULE.dump
