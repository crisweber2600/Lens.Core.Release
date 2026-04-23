#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""
light-preflight.py — Frozen stub-level workspace gate for Lens commands.

FROZEN INTERFACE — DO NOT ALTER exit codes, arguments, or output format.
Called identically in every .github/prompts/lens-*.prompt.md stub before redirect.

Exit 0 → workspace valid; stub continues to full prompt.
Exit 1 → validation failure; stub halts with no lifecycle change.

No arguments. No lifecycle mutations. No file writes.
"""

import sys
from pathlib import Path


def find_project_root() -> Path | None:
    """Walk up from CWD to find the project root (contains _bmad/config.yaml or _bmad/)."""
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "_bmad").is_dir():
            return candidate
    return None


def check_config_present(root: Path) -> tuple[bool, str]:
    """Verify at least one bmad config file exists."""
    if (root / "_bmad" / "config.yaml").exists():
        return True, "config.yaml present"
    if (root / "_bmad" / "config.user.yaml").exists():
        return True, "config.user.yaml present"
    return False, f"No config file found under {root / '_bmad'}"


def check_python_version() -> tuple[bool, str]:
    """Verify Python >= 3.12."""
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) >= (3, 12):
        return True, f"Python {major}.{minor}"
    return False, f"Python {major}.{minor} — requires >= 3.12"


def main() -> int:
    root = find_project_root()
    if root is None:
        print("[LENS:PREFLIGHT] FAIL — could not locate project root (_bmad/ directory not found)", file=sys.stderr)
        return 1

    ok_config, msg_config = check_config_present(root)
    ok_python, msg_python = check_python_version()

    if ok_config and ok_python:
        return 0

    if not ok_config:
        print(f"[LENS:PREFLIGHT] FAIL — {msg_config}", file=sys.stderr)
    if not ok_python:
        print(f"[LENS:PREFLIGHT] FAIL — {msg_python}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    sys.exit(main())
