#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Quickplan operations — validate frontmatter, extract summaries, check plan state.

Subcommands:
  validate-frontmatter  Validate required frontmatter in a planning document.
  extract-summary       Extract summary content from planning doc frontmatter.
  check-plan-state      Check which planning artifacts exist for a feature.
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import yaml


VALID_DOC_TYPES = ["business-plan", "tech-plan", "sprint-plan"]
VALID_STATUSES = ["draft", "in-review", "approved"]
REQUIRED_FRONTMATTER_FIELDS = [
    "feature",
    "doc_type",
    "status",
    "goal",
    "key_decisions",
    "open_questions",
    "depends_on",
    "blocks",
    "updated_at",
]

# Sanitization pattern for path-constructing identifiers
SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

# ISO 8601 date/datetime pattern (date-only or full datetime with optional timezone)
ISO_DATE_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$"
)


def validate_identifier(value: str, field_name: str) -> str | None:
    """Validate that a path-constructing identifier is safe. Returns error or None."""
    if not SAFE_ID_PATTERN.match(value):
        return (
            f"Invalid {field_name}: '{value}'. "
            f"Must match [a-z0-9][a-z0-9._-]{{0,63}} "
            "(lowercase alphanumeric, dots, hyphens, underscores)."
        )
    return None


def parse_frontmatter(file_path: Path) -> tuple[dict | None, str]:
    """Parse YAML frontmatter from a markdown file. Returns (data, error_message)."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as e:
        return None, f"Cannot read file: {e}"

    if not content.startswith("---"):
        return None, "No frontmatter found (file does not start with ---)"

    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        return None, "Frontmatter not closed (no closing ---)"

    frontmatter_str = content[3:end_idx].strip()
    try:
        data = yaml.safe_load(frontmatter_str)
        if not isinstance(data, dict):
            return None, "Frontmatter is not a YAML mapping"
        return data, ""
    except yaml.YAMLError as e:
        return None, f"YAML parse error in frontmatter: {e}"


def _validate_updated_at(val: object) -> str | None:
    """Return an issue string if val is not a valid ISO date, else None."""
    if isinstance(val, (datetime, date)):
        return None
    if not ISO_DATE_PATTERN.match(str(val)):
        return f"updated_at is not a valid ISO date: '{val}'."
    return None


def cmd_validate_frontmatter(args: argparse.Namespace) -> int:
    """Validate required frontmatter fields in a planning document."""
    file_path = Path(args.file)
    if not file_path.exists():
        print(json.dumps({"status": "fail", "issues": [f"File not found: {args.file}"]}))
        return 1

    data, err = parse_frontmatter(file_path)
    if err:
        print(json.dumps({"status": "fail", "issues": [err]}))
        return 1

    missing_fields = [f for f in REQUIRED_FRONTMATTER_FIELDS if f not in data]
    issues: list[str] = []

    if "doc_type" in data:
        doc_type_val = data["doc_type"]
        if doc_type_val not in VALID_DOC_TYPES:
            issues.append(
                f"Invalid doc_type: '{doc_type_val}'. Must be one of {VALID_DOC_TYPES}."
            )
        elif doc_type_val != args.doc_type:
            issues.append(
                f"doc_type mismatch: expected '{args.doc_type}', got '{doc_type_val}'."
            )

    if "updated_at" in data and data["updated_at"] is not None:
        date_issue = _validate_updated_at(data["updated_at"])
        if date_issue:
            issues.append(date_issue)

    doc_type = data.get("doc_type", args.doc_type)

    if missing_fields or issues:
        print(
            json.dumps(
                {
                    "status": "fail",
                    "doc_type": doc_type,
                    "missing_fields": missing_fields,
                    "issues": issues,
                }
            )
        )
        return 2

    print(
        json.dumps(
            {
                "status": "pass",
                "doc_type": doc_type,
                "missing_fields": [],
                "issues": [],
            }
        )
    )
    return 0


def cmd_extract_summary(args: argparse.Namespace) -> int:
    """Extract summary content from planning doc frontmatter."""
    file_path = Path(args.file)
    if not file_path.exists():
        print(json.dumps({"status": "fail", "issues": [f"File not found: {args.file}"]}))
        return 1

    data, err = parse_frontmatter(file_path)
    if err:
        print(json.dumps({"status": "fail", "issues": [err]}))
        return 1

    summary = {
        "feature": data.get("feature", args.feature_id),
        "doc_type": data.get("doc_type"),
        "status": data.get("status"),
        "goal": data.get("goal"),
        "key_decisions": data.get("key_decisions") or [],
        "open_questions": data.get("open_questions") or [],
    }

    print(json.dumps({"status": "pass", "summary": summary}))
    return 0


def _determine_phase(artifacts: dict[str, bool]) -> str:
    """Infer the current planning phase from which artifacts are present."""
    if artifacts.get("stories"):
        return "dev"
    if artifacts.get("sprint_plan"):
        return "finalizeplan"
    if artifacts.get("tech_plan"):
        return "techplan"
    if artifacts.get("business_plan"):
        return "businessplan"
    return "preplan"


def cmd_check_plan_state(args: argparse.Namespace) -> int:
    """Check which planning artifacts exist for a feature."""
    for field, value in [
        ("feature-id", args.feature_id),
        ("domain", args.domain),
        ("service", args.service),
    ]:
        err = validate_identifier(value, field)
        if err:
            print(json.dumps({"status": "fail", "issues": [err]}))
            return 1

    feature_dir = (
        Path(args.governance_repo)
        / "features"
        / args.domain
        / args.service
        / args.feature_id
    )

    artifacts: dict[str, bool] = {
        "business_plan": (feature_dir / "business-plan.md").exists(),
        "tech_plan": (feature_dir / "tech-plan.md").exists(),
        "sprint_plan": (feature_dir / "sprint-plan.md").exists(),
        "stories": (feature_dir / "stories").is_dir(),
    }

    print(
        json.dumps(
            {
                "status": "pass",
                "artifacts": artifacts,
                "phase": _determine_phase(artifacts),
            }
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Quickplan operations for the Lens planning pipeline."
    )
    subparsers = parser.add_subparsers(dest="command")

    p_val = subparsers.add_parser(
        "validate-frontmatter",
        help="Validate required frontmatter in a planning document.",
    )
    p_val.add_argument("--file", required=True, help="Path to the .md file to validate.")
    p_val.add_argument(
        "--doc-type",
        required=True,
        choices=VALID_DOC_TYPES,
        help="Expected doc_type value.",
    )

    p_ext = subparsers.add_parser(
        "extract-summary",
        help="Extract summary content from planning doc frontmatter.",
    )
    p_ext.add_argument("--file", required=True, help="Path to the .md file.")
    p_ext.add_argument("--feature-id", required=True, help="Feature ID for the summary.")

    p_chk = subparsers.add_parser(
        "check-plan-state",
        help="Check which planning artifacts exist for a feature.",
    )
    p_chk.add_argument("--governance-repo", required=True, help="Path to governance repo root.")
    p_chk.add_argument("--feature-id", required=True, help="Feature identifier.")
    p_chk.add_argument("--domain", required=True, help="Feature domain.")
    p_chk.add_argument("--service", required=True, help="Feature service.")

    args = parser.parse_args()

    if args.command == "validate-frontmatter":
        return cmd_validate_frontmatter(args)
    if args.command == "extract-summary":
        return cmd_extract_summary(args)
    if args.command == "check-plan-state":
        return cmd_check_plan_state(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
