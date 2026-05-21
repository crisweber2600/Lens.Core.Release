#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Create the Auspex durable memory scaffold for one Lens unit of work."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SECTION_NAMES = [
    "Intent",
    "Decisions",
    "Open Loops",
    "Related Context",
    "Lifecycle Handoff",
    "Promotion Notes",
]


class MemoryError(ValueError):
    """Raised when a requested memory scaffold would violate its contract."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_safe_id(value: str, *, field: str) -> str:
    candidate = str(value or "").strip()
    if not SAFE_ID_PATTERN.fullmatch(candidate):
        raise MemoryError(f"{field} must be a safe id without path separators: {value!r}")
    return candidate


def normalize_related(values: Iterable[str]) -> list[str]:
    related: list[str] = []
    for value in values:
        safe = validate_safe_id(value, field="related")
        if safe not in related:
            related.append(safe)
    return related


def memory_path(project_root: Path, feature_id: str) -> Path:
    safe_feature_id = validate_safe_id(feature_id, field="feature_id")
    root = project_root.resolve()
    target = (root / "docs" / "features" / safe_feature_id / "memory.md").resolve()
    archive_root = (root / "docs" / "features" / safe_feature_id).resolve()
    if target.parent != archive_root or not target.is_relative_to(root / "docs" / "features"):
        raise MemoryError("memory path escapes docs/features")
    return target


def yaml_scalar(value: str | None) -> str:
    if value is None:
        return "null"
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def yaml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "\n".join(f"  - {yaml_scalar(value)}" for value in values)


def render_memory(
    *,
    feature_id: str,
    title: str,
    domain: str,
    service: str,
    track: str,
    docs_path: str,
    related: list[str],
    intent: str,
    memory_note: str,
    timestamp: str,
) -> str:
    frontmatter = [
        "---",
        f"featureId: {yaml_scalar(feature_id)}",
        "kind: auspex_unit_memory",
        "status: active",
        "belongs_to:",
        f"  service: {yaml_scalar(service)}",
        f"  domain: {yaml_scalar(domain)}",
        "  program: null",
        "related_units:" if related else "related_units: []",
    ]
    if related:
        frontmatter.append(yaml_list(related))
    frontmatter.extend(
        [
            f"docs_path: {yaml_scalar(docs_path)}",
            "promotion_status: pending",
            f"created_at: {yaml_scalar(timestamp)}",
            f"updated_at: {yaml_scalar(timestamp)}",
            "---",
            "",
        ]
    )

    intent_text = intent.strip() or "Capture the intent for this Auspex unit of work."
    note_text = memory_note.strip()
    related_text = "\n".join(f"- {value}" for value in related) if related else "- No related units recorded yet."

    body = [
        f"# {title.strip() or feature_id}",
        "",
        "## Intent",
        "",
        intent_text,
        "",
    ]
    if note_text:
        body.extend(["Initial memory note:", "", note_text, ""])
    body.extend(
        [
            "## Decisions",
            "",
            "- No durable decisions recorded yet.",
            "",
            "## Open Loops",
            "",
            "- Complete the Lens lifecycle handoff and record planning outcomes here as they become durable.",
            "",
            "## Related Context",
            "",
            related_text,
            "",
            "## Lifecycle Handoff",
            "",
            f"- Feature ID: `{feature_id}`",
            f"- Domain: `{domain}`",
            f"- Service: `{service}`",
            f"- Track: `{track}`",
            f"- Lens docs path: `{docs_path}`",
            "- Next Lens step: delegate to `lens-next` after memory bootstrap.",
            "",
            "## Promotion Notes",
            "",
            "- Promote durable lessons into living ledgers with `lens-auspex-ledger-promotion` after lifecycle work produces stable knowledge.",
            "",
        ]
    )
    return "\n".join(frontmatter + body)


def write_memory(args: argparse.Namespace) -> dict[str, object]:
    feature_id = validate_safe_id(args.feature_id, field="feature_id")
    domain = validate_safe_id(args.domain, field="domain")
    service = validate_safe_id(args.service, field="service")
    related = normalize_related(args.related or [])
    project_root = Path(args.project_root)
    target = memory_path(project_root, feature_id)
    timestamp = args.timestamp or utc_now()
    content = render_memory(
        feature_id=feature_id,
        title=args.title,
        domain=domain,
        service=service,
        track=args.track,
        docs_path=args.docs_path,
        related=related,
        intent=args.intent or "",
        memory_note=args.memory_note or "",
        timestamp=timestamp,
    )

    result: dict[str, object] = {
        "status": "dry-run" if args.dry_run else "created",
        "feature_id": feature_id,
        "memory_path": str(target),
        "relative_memory_path": str(target.relative_to(project_root.resolve())).replace("\\", "/"),
        "related_units": related,
        "sections": SECTION_NAMES,
    }

    if args.dry_run:
        result["content"] = content
        return result

    if target.exists():
        result["status"] = "exists"
        result["created"] = False
        return result

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    result["created"] = True
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--track", required=True)
    parser.add_argument("--docs-path", required=True)
    parser.add_argument("--related", action="append", default=[])
    parser.add_argument("--intent", default="")
    parser.add_argument("--memory-note", default="")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = write_memory(args)
    except MemoryError as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

