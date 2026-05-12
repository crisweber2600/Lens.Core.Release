"""Lens YAML shim loader for script-entrypoint imports."""

from __future__ import annotations

import importlib.util
from pathlib import Path

def _resolve_root_yaml() -> Path:
    """Resolve the repo-root `yaml.py` by finding the first parent that also contains `_bmad/`."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "yaml.py"
        if candidate.exists() and (parent / "_bmad").exists():
            return candidate
    raise ImportError("Unable to locate repository root yaml.py shim")


_ROOT_YAML = _resolve_root_yaml()
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
