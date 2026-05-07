#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
dev-session-compat.py — Read-time compatibility layer for dev-session.yaml.

Old format (pre-dogfood):
  - epic_number: int  (new: int or 'all')
  - started_at: ISO8601  (not in new schema; mapped to last_checkpoint if absent)
  - special_instructions: str  (extra; discarded on translate)
  - target_repo_name: str  (extra; discarded)
  - dev_branch_mode: str  (extra; discarded)
  - stories_completed: list of "sprint.epic.story" strings (new: list of "E{n}-S{n}" strings)
  - stories_failed: list (same)
  - validation: dict  (extra; discarded)
  - stories_blocked: absent  (new: required empty list if absent)

New format (dogfood / conductor):
  - feature_id, epic_number (int or 'all'), working_branch, base_branch
  - total_stories, stories_completed, stories_failed, stories_blocked
  - current_story_index, last_checkpoint, status
  - requires_final_pr, final_pr_url

Detection: if 'dev_branch_mode' in data OR story ids look like "n.n.n" → old format.

Contract:
- detect_format(data) → 'old' | 'new'
- translate_to_new(data) → new-format dict (in-memory only, never written)
- load(path) → new-format dict always
- save(path, data) → always writes new format

All writes go through save() and always emit the new schema.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_OLD_STORY_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def detect_format(data: dict[str, Any]) -> str:
    """Return 'old' or 'new' based on data content."""
    # Explicit old-only fields
    if "dev_branch_mode" in data:
        return "old"
    if "started_at" in data and "last_checkpoint" not in data:
        return "old"
    # Check story id format
    completed = data.get("stories_completed") or []
    if completed and _OLD_STORY_PATTERN.match(str(completed[0])):
        return "old"
    return "new"


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

def translate_to_new(data: dict[str, Any]) -> dict[str, Any]:
    """Translate an old-format dev-session dict to new format in-memory."""
    # Resolve last_checkpoint: prefer started_at when last_checkpoint absent
    last_checkpoint = (
        data.get("last_checkpoint")
        or data.get("started_at")
        or datetime.now(timezone.utc).isoformat()
    )

    result: dict[str, Any] = {
        "feature_id": data.get("feature_id", ""),
        "epic_number": data.get("epic_number", "all"),
        "working_branch": data.get("working_branch", ""),
        "base_branch": data.get("base_branch", "develop"),
        "total_stories": data.get("total_stories", 0),
        "stories_completed": list(data.get("stories_completed") or []),
        "stories_failed": list(data.get("stories_failed") or []),
        "stories_blocked": list(data.get("stories_blocked") or []),
        "current_story_index": data.get("current_story_index", 0),
        "last_checkpoint": last_checkpoint,
        "status": data.get("status", "in-progress"),
        "requires_final_pr": data.get("requires_final_pr", True),
        "final_pr_url": data.get("final_pr_url"),
    }

    # Preserve new-only review status fields if present
    for key in ("final_review_status", "final_party_mode_status"):
        if key in data:
            result[key] = data[key]

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load(path: str | Path) -> dict[str, Any]:
    """Load a dev-session.yaml, returning new-format dict regardless of on-disk format."""
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    fmt = detect_format(raw)
    if fmt == "old":
        return translate_to_new(raw)
    return raw


def save(path: str | Path, data: dict[str, Any]) -> None:
    """Write a dev-session.yaml in the new format. Always emits new schema."""
    p = Path(path)
    # Ensure status field is present
    if "status" not in data:
        data["status"] = "in-progress"
    p.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point (read-only diagnostic)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: dev-session-compat.py <path/to/dev-session.yaml>", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[1])
    if not target.exists():
        print(f"Error: file not found: {target}", file=sys.stderr)
        sys.exit(1)

    loaded = load(target)
    print(yaml.dump(loaded, default_flow_style=False, sort_keys=False))
