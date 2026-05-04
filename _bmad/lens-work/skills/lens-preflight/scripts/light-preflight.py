#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""Frozen preflight gate for prompt stubs.

Exit 0 -> proceed.
Exit 1 -> halt.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def find_project_root() -> Path | None:
    current = Path.cwd().resolve()
    candidates = [current, *current.parents]

    for candidate in candidates:
        if (candidate / "lens.core" / "_bmad" / "lens-work" / "lifecycle.yaml").is_file():
            return candidate

    for candidate in candidates:
        if (candidate / "_bmad" / "lens-work" / "lifecycle.yaml").is_file():
            return candidate
    return None


def check_python_version() -> tuple[bool, str]:
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) >= (3, 12):
        return True, f"Python {major}.{minor}"
    return False, f"Python {major}.{minor} — requires >= 3.12"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prompt-start preflight wrapper for Lens workflows.")
    parser.add_argument("--skip-constitution", action="store_true")
    parser.add_argument("--caller", default="")
    parser.add_argument("--governance-path", default="")
    return parser


def delegate_preflight(args: argparse.Namespace, project_root: Path) -> int:
    # Option B: light-preflight is the prompt-start wrapper; preflight.py owns full sync behavior.
    script = Path(__file__).resolve().with_name("preflight.py")
    command = [sys.executable, str(script)]
    if args.skip_constitution:
        command.append("--skip-constitution")
    if args.caller:
        command.extend(["--caller", args.caller])
    if args.governance_path:
        command.extend(["--governance-path", args.governance_path])

    result = subprocess.run(command, cwd=project_root)
    return result.returncode


def main() -> int:
    args = build_parser().parse_args()
    root = find_project_root()
    if root is None:
        print(
            "[LENS:PREFLIGHT] FAIL — could not locate project root "
            "(lens.core/_bmad/lens-work or _bmad/lens-work not found)",
            file=sys.stderr,
        )
        return 1

    ok_python, msg = check_python_version()
    if not ok_python:
        print(f"[LENS:PREFLIGHT] FAIL — {msg}", file=sys.stderr)
        return 1

    return delegate_preflight(args, root)


if __name__ == "__main__":
    raise SystemExit(main())
