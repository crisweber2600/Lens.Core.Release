#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Help topic operations — contextual filtering, search, and full listing of Lens help topics."""

import argparse
import json
import sys
from pathlib import Path

import yaml


def load_topics(topics_file: str) -> list[dict]:
    """Load and return the topics list from the YAML registry."""
    path = Path(topics_file)
    if not path.exists():
        print(
            json.dumps({"status": "fail", "error": "topics_file_not_found", "detail": str(path)}),
            file=sys.stdout,
        )
        sys.exit(1)
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        return data.get("topics", [])
    except yaml.YAMLError as e:
        print(
            json.dumps({"status": "fail", "error": "invalid_topics_file", "detail": str(e)}),
            file=sys.stdout,
        )
        sys.exit(1)


def topic_matches_phase(topic: dict, phase: str) -> bool:
    """Return True if the topic applies to the given phase."""
    phases = topic.get("phases", [])
    return "all" in phases or phase in phases


def topic_matches_track(topic: dict, track: str) -> bool:
    """Return True if the topic applies to the given track."""
    tracks = topic.get("tracks", [])
    return "all" in tracks or track in tracks


def serialize_topic(topic: dict) -> dict:
    """Return the public-facing fields for a topic."""
    return {
        "id": topic["id"],
        "command": topic["command"],
        "description": topic["description"],
        "category": topic.get("category", ""),
    }


def cmd_contextual(args: argparse.Namespace) -> None:
    """Filter topics by phase and track, return the top N most relevant."""
    topics = load_topics(args.topics_file)
    phase = args.phase or "all"
    track = args.track or "all"

    matching = [t for t in topics if topic_matches_phase(t, phase) and topic_matches_track(t, track)]

    # Phase-specific topics (not tagged "all" in phases) sort before universal ones
    def sort_key(t: dict) -> int:
        phases = t.get("phases", [])
        return 0 if "all" not in phases else 1

    matching.sort(key=sort_key)

    total_available = len(matching)
    limited = matching[: args.limit]

    print(
        json.dumps(
            {
                "status": "pass",
                "phase": phase,
                "track": track,
                "topics": [serialize_topic(t) for t in limited],
                "total_available": total_available,
            }
        )
    )


def cmd_search(args: argparse.Namespace) -> None:
    """Case-insensitive text search across id, command, and description."""
    topics = load_topics(args.topics_file)
    query = args.query.lower()

    def match_rank(t: dict) -> int:
        if query in t.get("command", "").lower():
            return 0
        if query in t.get("id", "").lower():
            return 1
        if query in t.get("description", "").lower():
            return 2
        return 99

    matches = [t for t in topics if match_rank(t) < 99]
    matches.sort(key=match_rank)

    print(
        json.dumps(
            {
                "status": "pass",
                "query": args.query,
                "matches": [serialize_topic(t) for t in matches],
                "total": len(matches),
            }
        )
    )


def cmd_all(args: argparse.Namespace) -> None:
    """Return all topics, optionally filtered by category."""
    topics = load_topics(args.topics_file)

    if args.category:
        topics = [t for t in topics if t.get("category") == args.category]

    print(
        json.dumps(
            {
                "status": "pass",
                "topics": [serialize_topic(t) for t in topics],
                "total": len(topics),
            }
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lens help topic operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # contextual subcommand
    p_ctx = subparsers.add_parser("contextual", help="Get phase-relevant help topics")
    p_ctx.add_argument("--topics-file", required=True, help="Path to help-topics.yaml")
    p_ctx.add_argument("--phase", default="all", help="Current lifecycle phase")
    p_ctx.add_argument("--track", default="all", help="Current feature track")
    p_ctx.add_argument("--limit", type=int, default=5, help="Maximum topics to return")

    # search subcommand
    p_search = subparsers.add_parser("search", help="Text search across help topics")
    p_search.add_argument("--topics-file", required=True, help="Path to help-topics.yaml")
    p_search.add_argument("--query", required=True, help="Search query string")

    # all subcommand
    p_all = subparsers.add_parser("all", help="Return all topics")
    p_all.add_argument("--topics-file", required=True, help="Path to help-topics.yaml")
    p_all.add_argument("--category", default=None, help="Filter by category")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "contextual": cmd_contextual,
        "search": cmd_search,
        "all": cmd_all,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
