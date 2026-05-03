#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
bugbash_schema.py — Bug artifact frontmatter schema + status state machine.

Shared by bug-reporter-ops.py (validate before write) and bug-fixer-ops.py
(validate before status mutations).

Allowed status values: New, Inprogress, Fixed
Allowed transitions:
  intake  → New              (new artifact; no prior state)
  New     → Inprogress       (requires featureId set first)
  Inprogress → Fixed         (completion)

Forbidden (hard-blocked):
  New → Fixed
  Fixed → any   (terminal)
  Inprogress → New
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ALLOWED_STATUSES: frozenset[str] = frozenset({"New", "Inprogress", "Fixed"})

REQUIRED_FIELDS: tuple[str, ...] = (
    "title",
    "description",
    "status",
    "featureId",
    "slug",
    "created_at",
    "updated_at",
)

# Maps (from_status, to_status) → allowed
_ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("New", "Inprogress"),
        ("Inprogress", "Fixed"),
    }
)


class SchemaValidationError(ValueError):
    """Raised when a bug artifact frontmatter fails schema validation."""


class InvalidTransitionError(ValueError):
    """Raised when a requested status transition is not allowed."""


@dataclass
class BugFrontmatter:
    """Validated, typed representation of a bug artifact's frontmatter."""

    title: str
    description: str
    status: str
    featureId: str
    slug: str
    created_at: str
    updated_at: str


def validate_frontmatter(data: dict[str, Any]) -> BugFrontmatter:
    """Validate *data* against the bug frontmatter schema.

    Args:
        data: Raw dict loaded from the YAML frontmatter block.

    Returns:
        A validated :class:`BugFrontmatter` instance.

    Raises:
        SchemaValidationError: On missing fields, wrong types, or invalid status.
    """
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    if errors:
        raise SchemaValidationError(
            "Bug frontmatter schema validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    # Type checks — title, description must be non-empty strings
    for str_field in ("title", "description"):
        val = data[str_field]
        if not isinstance(val, str) or not val.strip():
            errors.append(f"'{str_field}' must be a non-empty string; got: {val!r}")

    # Status enum
    status = data["status"]
    if status not in ALLOWED_STATUSES:
        errors.append(
            f"'status' must be one of {sorted(ALLOWED_STATUSES)}; got: {status!r}"
        )

    # featureId must be a string (may be empty at intake)
    if not isinstance(data["featureId"], str):
        errors.append(f"'featureId' must be a string; got: {data['featureId']!r}")

    if errors:
        raise SchemaValidationError(
            "Bug frontmatter schema validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return BugFrontmatter(
        title=data["title"],
        description=data["description"],
        status=data["status"],
        featureId=data["featureId"],
        slug=data["slug"],
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
    )


def validate_transition(current_status: str, target_status: str) -> None:
    """Validate that transitioning from *current_status* to *target_status* is allowed.

    Args:
        current_status: The bug's present status value.
        target_status: The desired next status value.

    Raises:
        SchemaValidationError: If *target_status* is not a known status.
        InvalidTransitionError: If the transition is not in the allowed set.
    """
    if target_status not in ALLOWED_STATUSES:
        raise SchemaValidationError(
            f"Invalid target status {target_status!r}; must be one of {sorted(ALLOWED_STATUSES)}"
        )

    if current_status == target_status:
        return  # no-op transition is always safe

    if (current_status, target_status) not in _ALLOWED_TRANSITIONS:
        raise InvalidTransitionError(
            f"Invalid status transition: {current_status!r} → {target_status!r}.\n"
            f"  Allowed transitions: {sorted(_ALLOWED_TRANSITIONS)}\n"
            "  Prior valid status is preserved; no file was modified."
        )


def validate_intake_fields(title: str, description: str, chat_log: str) -> None:
    """Validate the three required intake inputs before artifact creation.

    Args:
        title: Bug title (must be non-empty).
        description: Bug description (must be non-empty).
        chat_log: Chat log body (must be non-empty).

    Raises:
        SchemaValidationError: If any field is missing or empty.
    """
    errors: list[str] = []
    if not title or not title.strip():
        errors.append("'title' is required and must be non-empty")
    if not description or not description.strip():
        errors.append("'description' is required and must be non-empty")
    if not chat_log or not chat_log.strip():
        errors.append("'chat_log' is required and must be non-empty")
    if errors:
        raise SchemaValidationError(
            "Intake validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )
