#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Problem log operations — log, resolve, and list problems for a Lens feature.

Problems are append-only entries in a feature's problems.md file, tagged with
phase and category to enable retrospective pattern analysis.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

VALID_PHASES = [
    "preplan",
    "businessplan",
    "techplan",
    "finalizeplan",
    "dev",
    "complete",
]

VALID_CATEGORIES = [
    "requirements-gap",
    "execution-failure",
    "dependency-issue",
    "scope-creep",
    "tech-debt",
    "process-breakdown",
]

SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

PROBLEMS_HEADER = (
    "# Problems\n\n"
    "This file tracks problems encountered during feature development. "
    "Every entry is tagged with phase and category to enable retrospective analysis.\n\n"
)


def validate_identifier(value: str, field_name: str) -> str | None:
    """Validate a path-constructing identifier. Returns error message or None."""
    if not SAFE_ID_PATTERN.match(value):
        return (
            f"Invalid {field_name}: '{value}'. "
            f"Must match [a-z0-9][a-z0-9._-]{{0,63}} "
            f"(lowercase alphanumeric, dots, hyphens, underscores)."
        )
    return None


def get_problems_path(
    governance_repo: str, domain: str, service: str, feature_id: str
) -> Path:
    """Compute the problems.md file path."""
    return (
        Path(governance_repo)
        / "features"
        / domain
        / service
        / feature_id
        / "problems.md"
    )


def now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_compact() -> str:
    """Return current UTC time as a compact string for entry IDs (microsecond precision)."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def make_entry(
    entry_id: str,
    title: str,
    phase: str,
    category: str,
    description: str,
    logged: str,
) -> str:
    """Format a single problem entry for appending to problems.md."""
    return (
        f"## Problem: {title}\n"
        f"<!-- id: {entry_id} -->\n"
        f"- **Phase:** {phase}\n"
        f"- **Category:** {category}\n"
        f"- **Logged:** {logged}\n"
        f"- **Status:** open\n"
        f"- **Description:** {description}\n"
        f"- **Resolution:** —\n"
    )


def _parse_section(section: str) -> dict | None:
    """Parse a single ## Problem: section into a dict."""
    lines = section.split("\n")
    if not lines:
        return None

    title_match = re.match(r"^## Problem: (.+)$", lines[0])
    if not title_match:
        return None

    title = title_match.group(1).strip()
    entry_id: str | None = None
    fields: dict[str, str] = {}

    for line in lines[1:]:
        id_match = re.match(r"^<!-- id: (prob-\S+) -->$", line)
        if id_match:
            entry_id = id_match.group(1)
            continue

        field_match = re.match(r"^- \*\*([^:]+):\*\* (.*)$", line)
        if field_match:
            key = field_match.group(1).strip().lower()
            val = field_match.group(2).strip()
            fields[key] = val

    return {
        "entry_id": entry_id,
        "title": title,
        "phase": fields.get("phase"),
        "category": fields.get("category"),
        "logged": fields.get("logged"),
        "status": fields.get("status", "open"),
        "description": fields.get("description"),
        "resolution": fields.get("resolution"),
    }


def parse_problems(content: str) -> list[dict]:
    """Parse problems.md content into a list of problem dicts."""
    problems = []
    raw_sections = re.split(r"(?=^## Problem:)", content, flags=re.MULTILINE)
    for section in raw_sections:
        if not section.strip().startswith("## Problem:"):
            continue
        problem = _parse_section(section)
        if problem:
            problems.append(problem)
    return problems


def resolve_in_content(content: str, entry_id: str, resolution: str) -> str | None:
    """Find entry by ID and update its Status and Resolution lines.

    Returns updated content, or None if entry not found.
    """
    lines = content.split("\n")

    id_line_idx: int | None = None
    for i, line in enumerate(lines):
        if f"<!-- id: {entry_id} -->" in line:
            id_line_idx = i
            break

    if id_line_idx is None:
        return None

    section_start = id_line_idx
    while section_start > 0 and not lines[section_start].startswith("## Problem:"):
        section_start -= 1

    section_end = len(lines)
    for i in range(section_start + 1, len(lines)):
        if lines[i].startswith("## Problem:"):
            section_end = i
            break

    found_status = False
    for i in range(section_start, section_end):
        if re.match(r"^- \*\*Status:\*\* ", lines[i]):
            lines[i] = "- **Status:** resolved"
            found_status = True
        elif re.match(r"^- \*\*Resolution:\*\* ", lines[i]):
            lines[i] = f"- **Resolution:** {resolution}"

    if not found_status:
        return None

    return "\n".join(lines)


def _validate_path_args(feature_id: str, domain: str, service: str) -> str | None:
    """Validate path-constructing arguments. Returns error string or None."""
    for field_name, value in [
        ("feature-id", feature_id),
        ("domain", domain),
        ("service", service),
    ]:
        err = validate_identifier(value, field_name)
        if err:
            return err
    return None


def cmd_log(args: argparse.Namespace) -> dict:
    """Append a new problem entry to problems.md."""
    err = _validate_path_args(args.feature_id, args.domain, args.service)
    if err:
        return {"status": "fail", "error": err}

    if args.phase not in VALID_PHASES:
        return {
            "status": "fail",
            "error": (
                f"Invalid phase: '{args.phase}'. "
                f"Must be one of: {', '.join(VALID_PHASES)}"
            ),
        }

    if args.category not in VALID_CATEGORIES:
        return {
            "status": "fail",
            "error": (
                f"Invalid category: '{args.category}'. "
                f"Must be one of: {', '.join(VALID_CATEGORIES)}"
            ),
        }

    problems_path = get_problems_path(
        args.governance_repo, args.domain, args.service, args.feature_id
    )

    ts = datetime.now(timezone.utc)
    entry_id = f"prob-{ts.strftime('%Y%m%dT%H%M%S%fZ')}"
    logged = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = make_entry(entry_id, args.title, args.phase, args.category, args.description, logged)

    problem = {
        "entry_id": entry_id,
        "title": args.title,
        "phase": args.phase,
        "category": args.category,
        "description": args.description,
        "status": "open",
    }

    if args.dry_run:
        return {
            "status": "pass",
            "dry_run": True,
            "entry_id": entry_id,
            "problems_path": str(problems_path),
            "problem": problem,
        }

    try:
        problems_path.parent.mkdir(parents=True, exist_ok=True)
        if not problems_path.exists():
            problems_path.write_text(PROBLEMS_HEADER + entry)
        else:
            with open(problems_path, "a") as f:
                f.write("\n" + entry)
    except OSError as e:
        return {"status": "fail", "error": f"Failed to write problems.md: {e}"}

    return {
        "status": "pass",
        "entry_id": entry_id,
        "problems_path": str(problems_path),
        "problem": problem,
    }


def cmd_resolve(args: argparse.Namespace) -> dict:
    """Mark a problem as resolved."""
    err = _validate_path_args(args.feature_id, args.domain, args.service)
    if err:
        return {"status": "fail", "error": err}

    problems_path = get_problems_path(
        args.governance_repo, args.domain, args.service, args.feature_id
    )

    if not problems_path.exists():
        return {
            "status": "fail",
            "error": f"problems.md not found: {problems_path}",
        }

    try:
        content = problems_path.read_text()
    except OSError as e:
        return {"status": "fail", "error": f"Failed to read problems.md: {e}"}

    updated = resolve_in_content(content, args.entry_id, args.resolution)
    if updated is None:
        return {
            "status": "fail",
            "error": f"Entry not found: {args.entry_id}",
        }

    try:
        problems_path.write_text(updated)
    except OSError as e:
        return {"status": "fail", "error": f"Failed to write problems.md: {e}"}

    return {
        "status": "pass",
        "entry_id": args.entry_id,
        "resolution": args.resolution,
        "problems_path": str(problems_path),
    }


def cmd_list(args: argparse.Namespace) -> dict:
    """List problems for a feature with optional status and category filters."""
    err = _validate_path_args(args.feature_id, args.domain, args.service)
    if err:
        return {"status": "fail", "error": err}

    problems_path = get_problems_path(
        args.governance_repo, args.domain, args.service, args.feature_id
    )

    if not problems_path.exists():
        return {
            "status": "pass",
            "total": 0,
            "open": 0,
            "resolved": 0,
            "problems": [],
            "problems_path": str(problems_path),
        }

    try:
        content = problems_path.read_text()
    except OSError as e:
        return {"status": "fail", "error": f"Failed to read problems.md: {e}"}

    all_problems = parse_problems(content)

    open_count = sum(1 for p in all_problems if p.get("status") == "open")
    resolved_count = sum(1 for p in all_problems if p.get("status") == "resolved")

    filtered = all_problems
    if args.status != "all":
        filtered = [p for p in filtered if p.get("status") == args.status]
    if args.category:
        filtered = [p for p in filtered if p.get("category") == args.category]

    return {
        "status": "pass",
        "total": len(filtered),
        "open": open_count,
        "resolved": resolved_count,
        "problems": filtered,
        "problems_path": str(problems_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Problem log operations — log, resolve, and list problems for a Lens feature."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s log --governance-repo /path/to/repo --feature-id auth-login \\
    --domain platform --service identity \\
    --phase dev --category tech-debt \\
    --title "Missing index on users table" \\
    --description "Slow query due to missing index"

  %(prog)s resolve --governance-repo /path/to/repo --feature-id auth-login \\
    --domain platform --service identity \\
    --entry-id prob-20260406T020334Z \\
    --resolution "Added index in migration 042"

  %(prog)s list --governance-repo /path/to/repo --feature-id auth-login \\
    --domain platform --service identity --status open
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # log
    log_p = subparsers.add_parser("log", help="Append a problem entry to problems.md")
    log_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    log_p.add_argument("--feature-id", required=True, help="Feature identifier")
    log_p.add_argument("--domain", required=True, help="Domain name")
    log_p.add_argument("--service", required=True, help="Service name")
    log_p.add_argument(
        "--phase",
        required=True,
        help=f"Lifecycle phase. One of: {', '.join(VALID_PHASES)}",
    )
    log_p.add_argument(
        "--category",
        required=True,
        help=f"Problem category. One of: {', '.join(VALID_CATEGORIES)}",
    )
    log_p.add_argument("--title", required=True, help="Short problem title")
    log_p.add_argument("--description", required=True, help="Full problem description")
    log_p.add_argument(
        "--dry-run", action="store_true", help="Preview without writing to disk"
    )

    # resolve
    resolve_p = subparsers.add_parser("resolve", help="Mark a problem as resolved")
    resolve_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    resolve_p.add_argument("--feature-id", required=True, help="Feature identifier")
    resolve_p.add_argument("--domain", required=True, help="Domain name")
    resolve_p.add_argument("--service", required=True, help="Service name")
    resolve_p.add_argument("--entry-id", required=True, help="Problem entry ID (prob-...)")
    resolve_p.add_argument("--resolution", required=True, help="Resolution description")

    # list
    list_p = subparsers.add_parser("list", help="List problems for a feature")
    list_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    list_p.add_argument("--feature-id", required=True, help="Feature identifier")
    list_p.add_argument("--domain", required=True, help="Domain name")
    list_p.add_argument("--service", required=True, help="Service name")
    list_p.add_argument(
        "--status",
        default="all",
        choices=["open", "resolved", "all"],
        help="Filter by status (default: all)",
    )
    list_p.add_argument("--category", help="Filter by category")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "log": cmd_log,
        "resolve": cmd_resolve,
        "list": cmd_list,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()
    sys.exit(0 if result.get("status") == "pass" else 1)


if __name__ == "__main__":
    main()
