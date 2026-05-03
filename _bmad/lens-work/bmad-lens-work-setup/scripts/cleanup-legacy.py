# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
cleanup-legacy.py — Remove legacy lens-work artifacts.

Cleans up:
- Old flat skill files at the module root level (skills/*.md)
- Legacy data/ directories that have been superseded
- Any other deprecated file patterns from older module versions
"""

import argparse
import sys
from pathlib import Path


LEGACY_PATTERNS = [
    # Flat skill files at module root (replaced by subdirectory structure)
    "*.skill.md",
    "*.agent.md",
]

LEGACY_DIRS = [
    # Legacy data/ dir (renamed to resources/ in newer versions)
    "data",
]


def cleanup_legacy(module_dir: Path, dry_run: bool = False) -> None:
    removed_files = []
    removed_dirs = []

    # Remove legacy flat files
    for pattern in LEGACY_PATTERNS:
        for path in module_dir.glob(pattern):
            if path.is_file():
                removed_files.append(path)
                if not dry_run:
                    path.unlink()

    # Remove empty legacy directories
    for dir_name in LEGACY_DIRS:
        dir_path = module_dir / dir_name
        if dir_path.is_dir():
            # Only remove if empty
            if not any(dir_path.iterdir()):
                removed_dirs.append(dir_path)
                if not dry_run:
                    dir_path.rmdir()
            else:
                print(f"⚠️  Skipping non-empty legacy dir: {dir_path}")

    prefix = "[DRY RUN] " if dry_run else ""
    for f in removed_files:
        print(f"{prefix}🗑️  Removed: {f}")
    for d in removed_dirs:
        print(f"{prefix}🗑️  Removed dir: {d}")

    if not removed_files and not removed_dirs:
        print("✅ No legacy artifacts found — nothing to remove.")
    else:
        total = len(removed_files) + len(removed_dirs)
        action = "Would remove" if dry_run else "Removed"
        print(f"✅ {action} {total} legacy artifact(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup legacy lens-work artifacts")
    parser.add_argument("--module-dir", required=True, help="Path to the lens-work module directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without removing")
    args = parser.parse_args()

    module_dir = Path(args.module_dir)
    if not module_dir.is_dir():
        print(f"❌ Module directory not found: {module_dir}", file=sys.stderr)
        sys.exit(1)

    cleanup_legacy(module_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
