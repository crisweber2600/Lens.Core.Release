#!/usr/bin/env python3
"""NextLens clean-room lifecycle operations.

This script owns deterministic lifecycle checks for the local Two-Tree model.
It never imports or invokes lens.core. Authored feature state lives under
docs/features/<feature-id>/feature.yaml, with planning artifacts beside it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_CONTRACT = {
    "tracks": {
        "full": ["preplan", "businessplan", "techplan", "finalizeplan", "dev"],
        "express": ["expressplan", "finalizeplan", "dev"],
    },
    "phase_artifacts": {
        "preplan": {
            "required": [
                "brainstorm.md",
                "research.md",
                "product-brief.md",
                "preplan-adversarial-review.md",
            ],
            "required_globs": [],
        },
        "businessplan": {
            "required": ["prd.md", "ux-design.md", "businessplan-adversarial-review.md"],
            "required_globs": [],
        },
        "techplan": {
            "required": ["architecture.md", "techplan-adversarial-review.md"],
            "required_globs": [],
        },
        "expressplan": {
            "required": [
                "business-plan.md",
                "tech-plan.md",
                "sprint-plan.md",
                "expressplan-adversarial-review.md",
            ],
            "required_globs": [],
        },
        "finalizeplan": {
            "required": [
                "finalizeplan-review.md",
                "epics.md",
                "stories.md",
                "implementation-readiness.md",
                "sprint-status.yaml",
            ],
            "required_globs": ["stories/*.md"],
        },
        "dev": {
            "required": ["sprint-status.yaml"],
            "required_globs": ["stories/*.md"],
        },
    },
}

FEATURE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")
SCALAR_BOOL = {"true": True, "false": False}


def parse_scalar(raw_value: str):
    value = raw_value.strip()
    if not value:
        return ""
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part) for part in inner.split(",")]
    lowered = value.lower()
    if lowered in SCALAR_BOOL:
        return SCALAR_BOOL[lowered]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_simple_yaml(path: Path) -> dict:
    data: dict[str, object] = {}
    if not path.exists():
        raise FileNotFoundError(path)
    current_list_key = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if current_list_key and line.startswith(("  - ", "- ")):
            item = line.split("- ", 1)[1]
            list_value = data.setdefault(current_list_key, [])
            if isinstance(list_value, list):
                list_value.append(parse_scalar(item))
            continue
        current_list_key = None
        if ":" not in line or line.startswith(" "):
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if raw_value:
            data[key] = parse_scalar(raw_value)
            continue
        data[key] = []
        current_list_key = key
    return data


def dump_simple_yaml(data: dict) -> str:
    lines: list[str] = []

    def emit(key: str, value, indent: int) -> None:
        prefix = " " * indent
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            for child_key, child_value in value.items():
                emit(str(child_key), child_value, indent + 2)
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                lines.append(f"{prefix}  - {format_scalar(item)}")
        else:
            lines.append(f"{prefix}{key}: {format_scalar(value)}")

    for item_key, item_value in data.items():
        emit(str(item_key), item_value, 0)
    return "\n".join(lines) + "\n"


def format_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    text = str(value)
    if not text or any(char in text for char in [":", "#", "[", "]", "{", "}"]):
        escaped = text.replace('"', '\\"')
        return f'"{escaped}"'
    return text


def project_root_from_args(args: argparse.Namespace) -> Path:
    return Path(args.project_root).resolve()


def feature_path(root: Path, feature_id: str, explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    return root / "docs" / "features" / feature_id / "feature.yaml"


def docs_path_for(feature_yaml: Path, feature: dict, root: Path) -> Path:
    raw_docs_path = str(feature.get("docs_path") or feature.get("lens_docs_path") or "").strip()
    if raw_docs_path:
        path = Path(raw_docs_path.replace("{project-root}/", ""))
        return path if path.is_absolute() else root / path
    return feature_yaml.parent


def load_feature(args: argparse.Namespace) -> tuple[Path, dict, Path]:
    root = project_root_from_args(args)
    feature_id = args.feature_id
    if not feature_id and args.feature_path:
        feature_id = Path(args.feature_path).parent.name
    if not feature_id:
        raise ValueError("feature_id_required")
    if not FEATURE_ID_RE.match(feature_id):
        raise ValueError(f"feature_id_invalid: {feature_id}")
    path = feature_path(root, feature_id, args.feature_path)
    feature = parse_simple_yaml(path)
    feature.setdefault("feature_id", feature_id)
    feature.setdefault("stable_id", f"feature:{feature_id}")
    feature.setdefault("entity_type", "feature")
    feature.setdefault("track", "full")
    feature.setdefault("phase", "preplan")
    docs_path = docs_path_for(path, feature, root)
    return path, feature, docs_path


def normalize_phase(phase: str) -> tuple[str, bool]:
    clean_phase = str(phase or "").strip().lower()
    if clean_phase.endswith("-complete"):
        return clean_phase[: -len("-complete")], True
    return clean_phase, False


def artifact_requirements(phase: str) -> dict:
    return deepcopy(DEFAULT_CONTRACT["phase_artifacts"].get(phase, {"required": [], "required_globs": []}))


def validate_docs(phase: str, docs_path: Path) -> dict:
    requirements = artifact_requirements(phase)
    missing_files = [name for name in requirements["required"] if not (docs_path / name).is_file()]
    missing_globs = []
    for pattern in requirements["required_globs"]:
        if not list(docs_path.glob(pattern)):
            missing_globs.append(pattern)
    return {
        "phase": phase,
        "docs_path": docs_path.as_posix(),
        "status": "pass" if not missing_files and not missing_globs else "fail",
        "missing_files": missing_files,
        "missing_globs": missing_globs,
        "required_files": requirements["required"],
        "required_globs": requirements["required_globs"],
    }


def predecessor_ready(feature: dict, track: str, phase: str, docs_path: Path) -> dict:
    phases = DEFAULT_CONTRACT["tracks"].get(track)
    if not phases or phase not in phases:
        return {"status": "fail", "reason": f"phase_not_in_track: {phase} not in {track}"}
    position = phases.index(phase)
    if position == 0:
        return {"status": "pass", "reason": "first_phase"}
    previous = phases[position - 1]
    active_phase, is_complete = normalize_phase(str(feature.get("phase")))
    if active_phase == previous and is_complete:
        return {"status": "pass", "reason": "feature_phase_predecessor_complete"}
    if active_phase == phase:
        validation = validate_docs(previous, docs_path)
        if validation["status"] == "pass":
            return {"status": "pass", "reason": "predecessor_artifacts_present"}
    return {"status": "fail", "reason": f"requires_{previous}-complete"}


def suggest(feature: dict, docs_path: Path) -> dict:
    track = str(feature.get("track") or "full").strip().lower()
    phases = DEFAULT_CONTRACT["tracks"].get(track)
    if not phases:
        return {"status": "fail", "error": f"unknown_track: {track}"}
    raw_phase = str(feature.get("phase") or phases[0])
    phase, complete = normalize_phase(raw_phase)
    if phase in {"complete", "dev-complete"}:
        return {
            "status": "complete",
            "recommendation": "lens-doctor",
            "phase": raw_phase,
            "track": track,
            "reason": "feature lifecycle is complete; run topology/readiness workflows next",
        }
    if phase not in phases:
        phase = phases[0]
        complete = False
    if complete:
        index = phases.index(phase)
        if index + 1 >= len(phases):
            return {
                "status": "complete",
                "recommendation": "lens-doctor",
                "phase": raw_phase,
                "track": track,
                "reason": "all lifecycle phases complete",
            }
        next_phase = phases[index + 1]
    else:
        next_phase = phase
    validation = validate_docs(next_phase, docs_path)
    return {
        "status": "unblocked" if predecessor_ready(feature, track, next_phase, docs_path)["status"] == "pass" else "blocked",
        "recommendation": next_phase,
        "phase": raw_phase,
        "track": track,
        "docs_path": docs_path.as_posix(),
        "validation": validation,
        "predecessor": predecessor_ready(feature, track, next_phase, docs_path),
    }


def command_resolve(args: argparse.Namespace) -> tuple[int, dict]:
    path, feature, docs_path = load_feature(args)
    return 0, {
        "status": "pass",
        "feature_path": path.as_posix(),
        "docs_path": docs_path.as_posix(),
        "feature": feature,
    }


def command_validate(args: argparse.Namespace) -> tuple[int, dict]:
    _, feature, docs_path = load_feature(args)
    phase = args.phase or normalize_phase(str(feature.get("phase")))[0]
    result = validate_docs(phase, docs_path)
    result["feature_id"] = feature.get("feature_id")
    return (0 if result["status"] == "pass" else 2), result


def command_suggest(args: argparse.Namespace) -> tuple[int, dict]:
    _, feature, docs_path = load_feature(args)
    result = suggest(feature, docs_path)
    return (0 if result["status"] in {"unblocked", "complete"} else 2), result


def command_advance(args: argparse.Namespace) -> tuple[int, dict]:
    path, feature, docs_path = load_feature(args)
    phase = args.phase or normalize_phase(str(feature.get("phase")))[0]
    validation = validate_docs(phase, docs_path)
    if validation["status"] != "pass" and not args.force:
        return 2, {
            "status": "blocked",
            "reason": "phase_artifacts_missing",
            "validation": validation,
        }
    updated = deepcopy(feature)
    updated["phase"] = f"{phase}-complete"
    updated["lifecycle_stage"] = f"{phase}-complete"
    updated["updated_at"] = datetime.now(timezone.utc).isoformat()
    if args.dry_run:
        return 0, {"status": "dry-run", "feature_path": path.as_posix(), "feature": updated}
    path.write_text(dump_simple_yaml(updated), encoding="utf-8")
    return 0, {"status": "pass", "feature_path": path.as_posix(), "phase": updated["phase"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NextLens local lifecycle operations")
    parser.add_argument("--project-root", default=".")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("resolve-feature", "validate-phase", "suggest-next", "advance-phase"):
        subparser = subcommands.add_parser(name)
        subparser.add_argument("--feature-id")
        subparser.add_argument("--feature-path")
        if name in {"validate-phase", "advance-phase"}:
            subparser.add_argument("--phase")
        if name == "advance-phase":
            subparser.add_argument("--dry-run", action="store_true")
            subparser.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        handlers = {
            "resolve-feature": command_resolve,
            "validate-phase": command_validate,
            "suggest-next": command_suggest,
            "advance-phase": command_advance,
        }
        exit_code, result = handlers[args.command](args)
    except Exception as exc:  # noqa: BLE001 - command surface returns structured errors.
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())