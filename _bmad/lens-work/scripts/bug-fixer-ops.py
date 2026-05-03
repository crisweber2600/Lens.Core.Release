#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
bug-fixer-ops.py — Bug discovery and status mutation operations for lens-bugbash.

Commands:
  discover-new        --governance-repo PATH
  move-to-inprogress  --governance-repo PATH --feature-id STR [--slugs STR ...]
  move-to-fixed       --governance-repo PATH [--slugs STR ...]
  resolve-bugs        --governance-repo PATH --feature-id STR

Exit codes: 0=success, 1=validation/not-found error, 2=scope violation, 3=write error
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bugbash_scope_guard import (
    ScopeViolationError,
    assert_governance_repo_exists,
    assert_path_in_scope,
)
from bugbash_schema import (
    InvalidTransitionError,
    SchemaValidationError,
    validate_frontmatter,
    validate_transition,
)

try:
    import yaml
except ImportError:
    print(
        "ERROR: pyyaml is required but not installed. "
        "Run via: uv run --script bug-fixer-ops.py",
        file=sys.stderr,
    )
    sys.exit(1)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from a markdown file content string."""
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = content[3:end]
    try:
        return yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return {}


def _update_frontmatter(content: str, updates: dict) -> str:
    """Return *content* with *updates* applied to the YAML frontmatter block."""
    if not content.startswith("---"):
        raise ValueError("Content does not start with a YAML frontmatter block")
    end = content.find("\n---", 3)
    if end == -1:
        raise ValueError("Frontmatter block is not properly closed")

    fm_text = content[3:end]
    body = content[end + 4:]  # skip the closing ---

    # Apply updates line-by-line (simple strategy for small frontmatter)
    lines = fm_text.splitlines()
    new_lines: list[str] = []
    applied: set[str] = set()

    for line in lines:
        if ":" in line:
            key = line.split(":", 1)[0].strip()
            if key in updates:
                val = updates[key]
                if isinstance(val, str):
                    new_lines.append(f'{key}: "{val}"')
                else:
                    new_lines.append(f"{key}: {val}")
                applied.add(key)
                continue
        new_lines.append(line)

    # Add any keys that were not in the original frontmatter
    for key, val in updates.items():
        if key not in applied:
            if isinstance(val, str):
                new_lines.append(f'{key}: "{val}"')
            else:
                new_lines.append(f"{key}: {val}")

    return "---\n" + "\n".join(new_lines) + "\n---" + body


def _atomic_move(src: Path, dest: Path, governance_repo: Path) -> None:
    """Atomically move src to dest (write-verify-delete) with scope checks."""
    assert_path_in_scope(dest, governance_repo)
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = src.read_text(encoding="utf-8")
    dest.write_text(content, encoding="utf-8")
    # Verify destination was written
    if not dest.exists():
        raise OSError(f"Destination file not written: {dest}")
    src.unlink()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_discover_new(args: argparse.Namespace) -> int:
    governance_repo = Path(args.governance_repo).resolve()
    assert_governance_repo_exists(governance_repo)

    bugs_new = governance_repo / "bugs" / "New"
    try:
        assert_path_in_scope(bugs_new, governance_repo)
    except ScopeViolationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not bugs_new.exists():
        print(json.dumps({"bugs": [], "count": 0}))
        return 0

    bugs: list[dict] = []
    for md_file in sorted(bugs_new.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)
        bugs.append({
            "slug": fm.get("slug", md_file.stem),
            "path": str(md_file),
            "title": fm.get("title", ""),
        })

    print(json.dumps({"bugs": bugs, "count": len(bugs)}))
    return 0


def cmd_move_to_inprogress(args: argparse.Namespace) -> int:
    governance_repo = Path(args.governance_repo).resolve()
    assert_governance_repo_exists(governance_repo)

    feature_id: str = args.feature_id
    if not feature_id.strip():
        print(
            "ERROR: --feature-id is required and must not be empty.",
            file=sys.stderr,
        )
        return 1

    slugs: list[str] = args.slugs or []

    moved: list[str] = []
    failed: list[dict] = []

    for slug in slugs:
        src = governance_repo / "bugs" / "New" / f"{slug}.md"
        dest = governance_repo / "bugs" / "Inprogress" / f"{slug}.md"

        try:
            assert_path_in_scope(src, governance_repo)
            assert_path_in_scope(dest, governance_repo)
        except ScopeViolationError as exc:
            failed.append({"slug": slug, "error": f"ScopeViolationError: {exc}"})
            continue

        if not src.exists():
            failed.append({"slug": slug, "error": f"Source not found: {src}"})
            continue

        try:
            content = src.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)
            validate_transition(fm.get("status", ""), "Inprogress")
            updated = _update_frontmatter(content, {
                "status": "Inprogress",
                "featureId": feature_id,
                "updated_at": _now_iso(),
            })
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(updated, encoding="utf-8")
            if not dest.exists():
                raise OSError(f"Destination not written: {dest}")
            src.unlink()
            moved.append(slug)
        except (InvalidTransitionError, SchemaValidationError) as exc:
            failed.append({"slug": slug, "error": f"{type(exc).__name__}: {exc}"})
        except OSError as exc:
            failed.append({"slug": slug, "error": f"OSError: {exc}"})

    print(json.dumps({"moved": moved, "failed": failed}))
    return 0


def cmd_move_to_fixed(args: argparse.Namespace) -> int:
    governance_repo = Path(args.governance_repo).resolve()
    assert_governance_repo_exists(governance_repo)

    slugs: list[str] = args.slugs or []

    moved: list[str] = []
    failed: list[dict] = []

    for slug in slugs:
        src = governance_repo / "bugs" / "Inprogress" / f"{slug}.md"
        dest = governance_repo / "bugs" / "Fixed" / f"{slug}.md"

        try:
            assert_path_in_scope(src, governance_repo)
            assert_path_in_scope(dest, governance_repo)
        except ScopeViolationError as exc:
            failed.append({"slug": slug, "error": f"ScopeViolationError: {exc}"})
            continue

        if not src.exists():
            failed.append({"slug": slug, "error": f"Source not found in Inprogress: {src}"})
            continue

        try:
            content = src.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)
            validate_transition(fm.get("status", ""), "Fixed")
            updated = _update_frontmatter(content, {
                "status": "Fixed",
                "updated_at": _now_iso(),
            })
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(updated, encoding="utf-8")
            if not dest.exists():
                raise OSError(f"Destination not written: {dest}")
            src.unlink()
            moved.append(slug)
        except (InvalidTransitionError, SchemaValidationError) as exc:
            failed.append({"slug": slug, "error": f"{type(exc).__name__}: {exc}"})
        except OSError as exc:
            failed.append({"slug": slug, "error": f"OSError: {exc}"})

    print(json.dumps({"moved": moved, "failed": failed}))
    return 0


def cmd_resolve_bugs(args: argparse.Namespace) -> int:
    governance_repo = Path(args.governance_repo).resolve()
    assert_governance_repo_exists(governance_repo)

    feature_id: str = args.feature_id
    inprogress_dir = governance_repo / "bugs" / "Inprogress"
    fixed_dir = governance_repo / "bugs" / "Fixed"

    resolved: list[str] = []
    not_found: list[str] = []
    already_fixed: list[str] = []

    # Check Fixed/ for already-done bugs
    if fixed_dir.exists():
        for md_file in fixed_dir.glob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)
            if fm.get("featureId", "").strip('"') == feature_id:
                already_fixed.append(md_file.stem)

    # Scan Inprogress/
    if inprogress_dir.exists():
        for md_file in sorted(inprogress_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)
            fid = fm.get("featureId", "").strip('"')
            if fid == feature_id:
                resolved.append(md_file.stem)

    if not resolved and not already_fixed:
        not_found.append(feature_id)
        print(
            f"ERROR: No Inprogress bugs found for featureId '{feature_id}'",
            file=sys.stderr,
        )
        print(json.dumps({"resolved": resolved, "not_found": not_found, "already_fixed": already_fixed}))
        return 1

    print(json.dumps({"resolved": resolved, "not_found": not_found, "already_fixed": already_fixed}))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bug-fixer-ops.py",
        description="Bug discovery and status mutation operations for lens-bugbash.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # discover-new
    dn = sub.add_parser("discover-new", help="List all New bugs.")
    dn.add_argument("--governance-repo", required=True)

    # move-to-inprogress
    mi = sub.add_parser("move-to-inprogress", help="Move bugs from New -> Inprogress.")
    mi.add_argument("--governance-repo", required=True)
    mi.add_argument("--feature-id", required=True)
    mi.add_argument("--slugs", nargs="+", default=[])

    # move-to-fixed
    mf = sub.add_parser("move-to-fixed", help="Move bugs from Inprogress -> Fixed.")
    mf.add_argument("--governance-repo", required=True)
    mf.add_argument("--slugs", nargs="+", default=[])

    # resolve-bugs
    rb = sub.add_parser("resolve-bugs", help="Find Inprogress bugs by featureId.")
    rb.add_argument("--governance-repo", required=True)
    rb.add_argument("--feature-id", required=True)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    dispatch = {
        "discover-new": cmd_discover_new,
        "move-to-inprogress": cmd_move_to_inprogress,
        "move-to-fixed": cmd_move_to_fixed,
        "resolve-bugs": cmd_resolve_bugs,
    }
    fn = dispatch.get(args.command)
    if fn:
        return fn(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
