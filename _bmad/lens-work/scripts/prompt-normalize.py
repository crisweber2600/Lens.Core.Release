#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Normalize managed prompt files after accidental literal newline-token writes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


LITERAL_CRLF = "\\r\\n"


def iter_prompt_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path.is_dir():
            candidates = sorted(path.rglob("*.prompt.md"))
        else:
            candidates = [path] if path.name.endswith(".prompt.md") else []
        for candidate in candidates:
            resolved = candidate.resolve(strict=False)
            if resolved not in seen:
                files.append(candidate)
                seen.add(resolved)
    return files


def normalize_file(path: Path, *, check: bool, dry_run: bool) -> dict[str, object]:
    content = path.read_text(encoding="utf-8")
    normalized = content.replace(LITERAL_CRLF, "\n")
    changed = normalized != content
    if changed and not check and not dry_run:
        path.write_text(normalized, encoding="utf-8")
    return {"path": str(path), "changed": changed}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replace literal \\r\\n tokens in prompt files with real newlines."
    )
    parser.add_argument("paths", nargs="*", help="Prompt file or directory paths. Defaults to .github/prompts.")
    parser.add_argument("--check", action="store_true", help="Fail if any prompt would be changed.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    roots = [Path(path) for path in args.paths] or [Path(".github/prompts")]
    files = iter_prompt_files(roots)
    results = [normalize_file(path, check=args.check, dry_run=args.dry_run) for path in files]
    changed = [result for result in results if result["changed"]]
    payload = {
        "status": "fail" if args.check and changed else "pass",
        "checked_files": len(results),
        "changed_files": changed,
        "dry_run": args.dry_run,
        "check": args.check,
    }
    print(json.dumps(payload, indent=2))
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
