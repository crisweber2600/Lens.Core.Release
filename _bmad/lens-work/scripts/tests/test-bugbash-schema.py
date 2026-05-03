#!/usr/bin/env python3
"""
test-bugbash-schema.py — Unit tests for bugbash_schema.py

Covers regression category § 7.1 from tech-plan:
  - Intake with all required fields → artifact created; status=New; featureId=""
  - Intake missing title → rejected; no file written
  - Intake missing description → rejected; no file written
  - Status set to invalid value → operation rejected; prior state preserved
  - Invalid transition (New→Fixed) → blocked; explicit error
  - Invalid transition (Fixed→New) → blocked
  - Invalid transition (Inprogress→New) → blocked
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bugbash_schema import (
    ALLOWED_STATUSES,
    InvalidTransitionError,
    SchemaValidationError,
    validate_frontmatter,
    validate_intake_fields,
    validate_transition,
)

VALID_FRONTMATTER: dict = {
    "title": "Bug title",
    "description": "Bug description",
    "status": "New",
    "featureId": "",
    "slug": "bug-title-ab12cd34",
    "created_at": "2026-05-03T12:00:00Z",
    "updated_at": "2026-05-03T12:00:00Z",
}


class TestValidateFrontmatter(unittest.TestCase):
    def test_valid_frontmatter_passes(self) -> None:
        """All required fields present → validates cleanly; status=New; featureId=""."""
        fm = validate_frontmatter(VALID_FRONTMATTER)
        self.assertEqual(fm.status, "New")
        self.assertEqual(fm.featureId, "")

    def test_missing_title_raises(self) -> None:
        """Missing title → SchemaValidationError."""
        data = {**VALID_FRONTMATTER}
        del data["title"]
        with self.assertRaises(SchemaValidationError):
            validate_frontmatter(data)

    def test_missing_description_raises(self) -> None:
        """Missing description → SchemaValidationError."""
        data = {**VALID_FRONTMATTER}
        del data["description"]
        with self.assertRaises(SchemaValidationError):
            validate_frontmatter(data)

    def test_missing_status_raises(self) -> None:
        data = {**VALID_FRONTMATTER}
        del data["status"]
        with self.assertRaises(SchemaValidationError):
            validate_frontmatter(data)

    def test_missing_featureId_raises(self) -> None:
        data = {**VALID_FRONTMATTER}
        del data["featureId"]
        with self.assertRaises(SchemaValidationError):
            validate_frontmatter(data)

    def test_invalid_status_raises(self) -> None:
        """Status set to invalid value → operation rejected."""
        data = {**VALID_FRONTMATTER, "status": "Broken"}
        with self.assertRaises(SchemaValidationError) as ctx:
            validate_frontmatter(data)
        self.assertIn("status", str(ctx.exception))

    def test_empty_title_raises(self) -> None:
        data = {**VALID_FRONTMATTER, "title": "   "}
        with self.assertRaises(SchemaValidationError):
            validate_frontmatter(data)

    def test_all_valid_statuses_accepted(self) -> None:
        for status in ALLOWED_STATUSES:
            data = {**VALID_FRONTMATTER, "status": status}
            fm = validate_frontmatter(data)
            self.assertEqual(fm.status, status)


class TestValidateTransition(unittest.TestCase):
    def test_new_to_inprogress_allowed(self) -> None:
        validate_transition("New", "Inprogress")

    def test_inprogress_to_fixed_allowed(self) -> None:
        validate_transition("Inprogress", "Fixed")

    def test_new_to_fixed_blocked(self) -> None:
        """Invalid transition New→Fixed → blocked; explicit error."""
        with self.assertRaises(InvalidTransitionError) as ctx:
            validate_transition("New", "Fixed")
        msg = str(ctx.exception)
        self.assertIn("New", msg)
        self.assertIn("Fixed", msg)
        self.assertIn("Prior valid status is preserved", msg)

    def test_fixed_to_new_blocked(self) -> None:
        """Fixed is terminal; cannot go to New."""
        with self.assertRaises(InvalidTransitionError):
            validate_transition("Fixed", "New")

    def test_fixed_to_inprogress_blocked(self) -> None:
        with self.assertRaises(InvalidTransitionError):
            validate_transition("Fixed", "Inprogress")

    def test_inprogress_to_new_blocked(self) -> None:
        """No rollback from Inprogress to New."""
        with self.assertRaises(InvalidTransitionError):
            validate_transition("Inprogress", "New")

    def test_same_status_is_noop(self) -> None:
        validate_transition("New", "New")  # should not raise

    def test_invalid_target_status_raises_schema_error(self) -> None:
        with self.assertRaises(SchemaValidationError):
            validate_transition("New", "Unknown")


class TestValidateIntakeFields(unittest.TestCase):
    def test_valid_inputs_pass(self) -> None:
        validate_intake_fields("Title", "Desc", "Chat log")

    def test_empty_title_raises(self) -> None:
        with self.assertRaises(SchemaValidationError):
            validate_intake_fields("", "Desc", "Chat")

    def test_empty_description_raises(self) -> None:
        with self.assertRaises(SchemaValidationError):
            validate_intake_fields("Title", "", "Chat")

    def test_empty_chat_log_raises(self) -> None:
        with self.assertRaises(SchemaValidationError):
            validate_intake_fields("Title", "Desc", "")

    def test_whitespace_only_title_raises(self) -> None:
        with self.assertRaises(SchemaValidationError):
            validate_intake_fields("   ", "Desc", "Chat")


if __name__ == "__main__":
    unittest.main()
