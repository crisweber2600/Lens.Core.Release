#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Check that required lifecycle artifacts exist and are non-empty."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def get_required_artifacts(lifecycle_path: Path, phase: str, contract: str) -> list[str]:
    data = yaml.safe_load(lifecycle_path.read_text(encoding="utf-8"))
    phases = data.get("phases", {})
    phase_data = phases.get(phase, {})
    if contract == "phase-artifacts":
        return phase_data.get("artifacts", [])

    completion_review = phase_data.get("completion_review", {})
    if contract == "completion-review":
        return completion_review.get("reviewed_artifacts", [])
    if contract == "review-ready":
        return completion_review.get(
            "ready_when_artifacts",
            completion_review.get("reviewed_artifacts", []),
        )

    raise ValueError(f"Unsupported contract: {contract}")


def is_batch_input(candidate: Path) -> bool:
    return candidate.name.endswith("-batch-input.md")


def artifact_candidates(docs_root: Path, name: str) -> list[Path]:
    match name:
        case "product-brief":
            candidates = [docs_root / "product-brief.md"]
            candidates += list(docs_root.glob("product-brief-*.md"))
        case "research":
            candidates = [docs_root / "research.md"]
            candidates += list(docs_root.glob("research-*.md"))
            candidates += list((docs_root / "research").glob("*.md"))
        case "brainstorm":
            candidates = [docs_root / "brainstorm.md"]
        case "prd":
            candidates = [docs_root / "prd.md"]
        case "ux-design":
            candidates = [docs_root / "ux-design.md", docs_root / "ux-design-specification.md"]
        case "architecture":
            candidates = [docs_root / "architecture.md"]
            candidates += list(docs_root.glob("*architecture*.md"))
        case "epics":
            candidates = [docs_root / "epics.md"]
        case "stories":
            candidates = [docs_root / "stories.md"]
        case "implementation-readiness":
            candidates = [docs_root / "readiness-checklist.md", docs_root / "implementation-readiness.md"]
        case "sprint-status":
            candidates = [docs_root / "sprint-status.yaml", docs_root / "sprint-backlog.md"]
        case "story-files":
            candidates = story_file_candidates(docs_root)
        case "review-report":
            candidates = [
                docs_root / "review-report.md",
                docs_root / "adversarial-review.md",
                docs_root / "preplan-adversarial-review.md",
                docs_root / "businessplan-adversarial-review.md",
                docs_root / "techplan-adversarial-review.md",
                docs_root / "expressplan-adversarial-review.md",
                docs_root / "finalizeplan-review.md",
            ]
        case _:
            candidates = [docs_root / f"{name}.md"]
    return [candidate for candidate in candidates if not is_batch_input(candidate)]


def existing_artifact_files(docs_root: Path, name: str) -> list[Path]:
    return [candidate for candidate in artifact_candidates(docs_root, name) if candidate.exists() and candidate.stat().st_size > 0]


def story_file_candidates(docs_root: Path) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()

    for pattern in ("dev-story-*.md", "dev-story-*.yaml", "[0-9]*-[0-9]*-*.md", "[0-9]*-[0-9]*-*.yaml"):
        for candidate in docs_root.glob(pattern):
            if is_batch_input(candidate):
                continue
            if candidate not in seen:
                candidates.append(candidate)
                seen.add(candidate)

    stories_dir = docs_root / "stories"
    if stories_dir.exists():
        for pattern in ("*.md", "*.yaml"):
            for candidate in stories_dir.glob(pattern):
                if is_batch_input(candidate):
                    continue
                if candidate not in seen:
                    candidates.append(candidate)
                    seen.add(candidate)

    return candidates


def artifact_exists(docs_root: Path, name: str) -> bool:
    return bool(existing_artifact_files(docs_root, name))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that required lifecycle artifacts for a phase exist."
    )
    parser.add_argument("--phase", required=True, help="Phase name")
    parser.add_argument(
        "--contract",
        default="phase-artifacts",
        choices=("phase-artifacts", "completion-review", "review-ready"),
        help="Which lifecycle artifact contract to validate.",
    )
    parser.add_argument("--lifecycle-path", required=True, help="Path to lifecycle.yaml")
    parser.add_argument("--docs-root", required=True, help="Path to docs root")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    lifecycle_path = Path(args.lifecycle_path)
    docs_root = Path(args.docs_root)

    if not lifecycle_path.exists():
        print(f"ERROR: lifecycle.yaml not found: {lifecycle_path}", file=sys.stderr)
        return 1

    required = get_required_artifacts(lifecycle_path, args.phase, args.contract)

    if not required:
        if args.json:
            print(json.dumps({
                "phase": args.phase,
                "contract": args.contract,
                "required": 0,
                "found": 0,
                "missing": [],
                "status": "no_artifacts_defined",
            }))
        else:
            print(f"No artifacts defined for phase contract: {args.phase} [{args.contract}]")
        return 0

    found: list[str] = []
    missing: list[str] = []

    for artifact in required:
        if artifact_exists(docs_root, artifact):
            found.append(artifact)
        else:
            missing.append(artifact)

    passed = len(missing) == 0

    if args.json:
        print(json.dumps({
            "phase": args.phase,
            "contract": args.contract,
            "required": len(required),
            "found": len(found),
            "missing": missing,
            "found_list": found,
            "misplaced": {},
            "failure_reason": None if passed else "missing_artifacts",
            "status": "pass" if passed else "fail",
        }, indent=2))
    else:
        if passed:
            if args.contract == "phase-artifacts":
                print("Phase artifacts verified")
            elif args.contract == "completion-review":
                print("Completion review artifacts verified")
            else:
                print("Review-ready artifacts verified")
        else:
            if args.contract == "phase-artifacts":
                print("Phase incomplete")
            elif args.contract == "completion-review":
                print("Completion review incomplete")
            else:
                print("Review-ready contract incomplete")
        print(f"  Phase:    {args.phase}")
        print(f"  Contract: {args.contract}")
        print(f"  Required: {len(required)}")
        print(f"  Found:    {len(found)}")
        print(f"  Missing:  {', '.join(missing) if missing else 'none'}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
