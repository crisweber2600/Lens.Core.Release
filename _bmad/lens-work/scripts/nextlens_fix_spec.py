#!/usr/bin/env python3
"""
Build deterministic NextLens implementation handoff data from normalized intake,
namespaced bug state, and resolved design context.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).parent))

from lens_config import ConfigError, NextLensDesignContext, normalize_path_text, resolve_nextlens_design_context
from nextlens_bugfix_parser import NextLensBugfixReport, parse_nextlens_bugfix_intake


NEXTLENS_NAMESPACE = "nextlens"
_ALLOWED_WRITE_ROOT_DISPLAY = r"TargetProjects\nextlens\src\NextLens"
_BUGFIX_FEATURE_PREFIX = "nextlens-bugfix-"
_SALMON_ACTIONS = {
    "low": "local_note",
    "medium": "landscape_update",
    "high": "bmad_correct_course",
    "blocking": "block_promotion",
}


@dataclass(frozen=True)
class NextLensBugState:
    slug: str
    status: str
    namespace: str
    artifact_path: Path


@lru_cache(maxsize=1)
def _load_bug_reporter_ops():
    script_path = Path(__file__).with_name("bug-reporter-ops.py")
    spec = importlib.util.spec_from_file_location("nextlens_bug_reporter_ops", script_path)
    module = importlib.util.module_from_spec(spec)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load bug reporter helpers from {script_path}")
    spec.loader.exec_module(module)
    return module


def _as_report(intake: Mapping[str, Any] | NextLensBugfixReport) -> NextLensBugfixReport:
    if isinstance(intake, NextLensBugfixReport):
        return intake
    return parse_nextlens_bugfix_intake(intake)


def _normalize_bug_state(
    bug_state: Mapping[str, Any],
    *,
    report: NextLensBugfixReport,
    governance_repo: str | Path | None = None,
) -> NextLensBugState:
    ops = _load_bug_reporter_ops()
    namespace = ops._normalize_namespace(str(bug_state.get("namespace") or NEXTLENS_NAMESPACE))
    if namespace != NEXTLENS_NAMESPACE:
        raise ValueError("NextLens fix specs require a namespaced bug state with namespace 'nextlens'")

    slug = str(bug_state.get("slug") or "").strip() or ops._make_slug(report.title, report.description)
    slug_error = ops._validate_slug(slug)
    if slug_error:
        raise ValueError(slug_error)

    status = str(bug_state.get("status") or "QuickDev").strip() or "QuickDev"
    if status not in ops.BUG_STATUS_FOLDERS:
        raise ValueError(f"Unsupported bug status '{status}'")

    governance_repo_root = bug_state.get("governance_repo_root") or bug_state.get("governance_repo") or governance_repo
    artifact_value = bug_state.get("artifact_path") or bug_state.get("path")
    if artifact_value:
        artifact_path = Path(str(artifact_value))
        if not artifact_path.is_absolute() and governance_repo_root:
            artifact_path = Path(str(governance_repo_root)) / artifact_path
        artifact_path = artifact_path.resolve(strict=False)
    else:
        if not governance_repo_root:
            raise ValueError("bug state must include artifact_path/path or governance_repo_root")
        artifact_path = ops._artifact_path(Path(str(governance_repo_root)).resolve(strict=False), status, slug, namespace)

    if governance_repo_root:
        expected_path = ops._artifact_path(Path(str(governance_repo_root)).resolve(strict=False), status, slug, namespace)
        if artifact_path.resolve(strict=False) != expected_path.resolve(strict=False):
            raise ValueError(
                f"bug artifact path {artifact_path} does not match the namespaced bug path {expected_path}"
            )

    return NextLensBugState(
        slug=slug,
        status=status,
        namespace=namespace,
        artifact_path=artifact_path.resolve(strict=False),
    )


def _display_path(path: Path, *, root: Path | None = None) -> str:
    if root is not None:
        try:
            path = path.resolve(strict=False).relative_to(root.resolve(strict=False))
        except ValueError:
            path = path.resolve(strict=False)
    return str(path).replace("/", "\\")


def _build_design_context_references(context: NextLensDesignContext) -> list[dict[str, Any]]:
    return [
        {
            "title": constraint.title,
            "source_path": _display_path(constraint.source_path, root=context.control_repo_root),
            "excerpts": list(constraint.excerpts),
        }
        for constraint in context.constraints
    ]


def _normalize_suspected_surface(surface: str, context: NextLensDesignContext) -> str:
    try:
        normalized = normalize_path_text(surface, base=context.control_repo_root)
    except Exception:
        return surface
    return str(Path(normalized)).replace("/", "\\")


def _build_suspected_target_surfaces(
    report: NextLensBugfixReport,
    context: NextLensDesignContext | None,
) -> list[str]:
    candidates: list[str] = []
    if report.suspected_target_surface:
        candidates.append(
            _normalize_suspected_surface(report.suspected_target_surface, context)
            if context is not None
            else report.suspected_target_surface
        )
    elif context is not None:
        candidates.append(str(context.runtime_target_path).replace("/", "\\"))

    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            ordered.append(candidate)
            seen.add(candidate)
    return ordered


def _build_validation_expectations(
    report: NextLensBugfixReport,
    *,
    allowed_write_root_display: str,
) -> list[str]:
    expectations = []
    if report.validation_request:
        expectations.append(report.validation_request)
    expectations.extend(
        [
            f"Run focused validation against the touched NextLens surface(s) under {allowed_write_root_display}.",
            "Capture validation evidence for the bug artifact, PR recording, and later review attachment.",
            "Reference NextLens Doctor outputs when they apply instead of reimplementing Doctor logic.",
        ]
    )
    seen: set[str] = set()
    ordered: list[str] = []
    for expectation in expectations:
        if expectation not in seen:
            ordered.append(expectation)
            seen.add(expectation)
    return ordered


def _build_salmon_linkage(report: NextLensBugfixReport) -> dict[str, Any] | None:
    if not report.salmon_signal_id:
        return None

    recommended_action = _SALMON_ACTIONS.get(report.severity or "", "bmad_correct_course")
    closure_expectations = [
        "Record validation evidence and any PR linkage before marking the originating signal resolved.",
        "If a newer signal replaces this bug, mark the originating signal superseded with a pointer to the replacement.",
    ]
    if report.severity in {"high", "blocking"}:
        closure_expectations.insert(
            0,
            "Treat the signal as an immediate bugfix path before more dependent work or promotion proceeds.",
        )

    return {
        "signal_id": report.salmon_signal_id,
        "severity": report.severity,
        "recommended_action": recommended_action,
        "evidence_refs": list(report.evidence_refs),
        "closure_expectations": closure_expectations,
    }


def _build_prohibited_write_roots(context: NextLensDesignContext) -> list[dict[str, str]]:
    return [
        {
            "label": "governance_repo",
            "path": str(context.governance_repo_root).replace("/", "\\"),
            "reason": "Governance updates must flow through approved orchestration instead of direct bugfix edits.",
        },
        {
            "label": "release_clone_paths",
            "path": "release clone paths",
            "reason": "Release clones are read-only local surfaces and must not be edited directly.",
        },
        {
            "label": "unrelated_control_paths",
            "path": str(context.control_repo_root).replace("/", "\\"),
            "reason": f"Only {_ALLOWED_WRITE_ROOT_DISPLAY} is approved for runtime fixes; other control-repo paths stay out of scope.",
        },
    ]


def _build_bugfix_branch_identity(slug: str) -> dict[str, str]:
    bugfix_feature_id = f"{_BUGFIX_FEATURE_PREFIX}{slug}"
    return {
        "bugfix_feature_id": bugfix_feature_id,
        "bugfix_feature_slug": bugfix_feature_id,
        "bugfix_working_branch": f"feature/{bugfix_feature_id}",
    }


def _build_spec_payload(
    *,
    feature_id: str,
    report: NextLensBugfixReport,
    bug: NextLensBugState,
    context: NextLensDesignContext | None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    blocked = bool(blockers)
    allowed_write_root = str(context.runtime_target_root) if context is not None else None
    branch_identity = _build_bugfix_branch_identity(bug.slug)
    bug_reporter_fields = report.to_bug_reporter_fields()
    payload = {
        "status": "blocked" if blocked else "ready",
        "feature_id": feature_id,
        "bugfix_feature_id": branch_identity["bugfix_feature_id"],
        "bugfix_feature_slug": branch_identity["bugfix_feature_slug"],
        "bugfix_working_branch": branch_identity["bugfix_working_branch"],
        "bug_slug": bug.slug,
        "bug_status": bug.status,
        "bug_artifact_path": str(bug.artifact_path).replace("/", "\\"),
        "bug_reporter_fields": bug_reporter_fields,
        "actual_behavior": report.actual_behavior,
        "expected_behavior": report.expected_behavior,
        "evidence_summary": report.evidence_summary,
        "design_context_references": _build_design_context_references(context) if context is not None else [],
        "skill_source_root": str(context.skill_source_root).replace("/", "\\") if context is not None else None,
        "allowed_write_root": allowed_write_root,
        "allowed_write_root_display": _ALLOWED_WRITE_ROOT_DISPLAY if context is not None else None,
        "prohibited_write_roots": _build_prohibited_write_roots(context) if context is not None else [],
        "suspected_target_surfaces": _build_suspected_target_surfaces(report, context),
        "validation_expectations": _build_validation_expectations(
            report,
            allowed_write_root_display=_ALLOWED_WRITE_ROOT_DISPLAY,
        ),
        "salmon_linkage": _build_salmon_linkage(report),
        "delegation_blocked": blocked,
        "delegation_blockers": blockers or [],
        "handoff_storage": "in-memory",
    }
    return payload


def build_nextlens_fix_spec(
    report: Mapping[str, Any] | NextLensBugfixReport,
    *,
    feature_id: str,
    bug_state: Mapping[str, Any],
    design_context: NextLensDesignContext,
) -> dict[str, Any]:
    normalized_report = _as_report(report)
    normalized_bug_state = _normalize_bug_state(
        bug_state,
        report=normalized_report,
        governance_repo=design_context.governance_repo_root,
    )
    return _build_spec_payload(
        feature_id=feature_id,
        report=normalized_report,
        bug=normalized_bug_state,
        context=design_context,
    )


def _parse_json_mapping(value: str, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must decode to a JSON object")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic NextLens bugfix handoff data.")
    parser.add_argument("--feature-id", required=True, help="Active NextLens feature identifier.")
    parser.add_argument("--intake-json", required=True, help="Raw NextLens intake JSON object.")
    parser.add_argument(
        "--bug-state-json",
        required=True,
        help="Bug state JSON object (for example namespace/status/governance_repo_root).",
    )
    parser.add_argument("--start", default=None)
    parser.add_argument("--config-path", default=None)
    parser.add_argument("--user-config-path", default=None)
    parser.add_argument("--governance-repo", default=None)
    parser.add_argument("--feature-path", default=None)
    parser.add_argument("--control-repo-override", default=None)
    parser.add_argument("--docs-path-override", default=None)
    parser.add_argument("--skill-source-override", default=None)
    parser.add_argument("--runtime-target-override", default=None)
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation level.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        spec = generate_nextlens_fix_spec(
            args.feature_id,
            _parse_json_mapping(args.intake_json, label="--intake-json"),
            bug_state=_parse_json_mapping(args.bug_state_json, label="--bug-state-json"),
            start=args.start,
            config_path=args.config_path,
            user_config_path=args.user_config_path,
            governance_repo=args.governance_repo,
            feature_path=args.feature_path,
            control_repo_override=args.control_repo_override,
            docs_path_override=args.docs_path_override,
            skill_source_override=args.skill_source_override,
            runtime_target_override=args.runtime_target_override,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(spec, indent=args.indent))
    return 0


def generate_nextlens_fix_spec(
    feature_id: str,
    intake: Mapping[str, Any] | NextLensBugfixReport,
    *,
    bug_state: Mapping[str, Any],
    start: str | None = None,
    config_path: str | None = None,
    user_config_path: str | None = None,
    governance_repo: str | None = None,
    feature_path: str | None = None,
    control_repo_override: str | None = None,
    docs_path_override: str | None = None,
    skill_source_override: str | None = None,
    runtime_target_override: str | None = None,
) -> dict[str, Any]:
    normalized_report = _as_report(intake)
    normalized_bug_state = _normalize_bug_state(
        bug_state,
        report=normalized_report,
        governance_repo=governance_repo,
    )

    try:
        context = resolve_nextlens_design_context(
            feature_id,
            start=start,
            config_path=config_path,
            user_config_path=user_config_path,
            governance_repo=governance_repo,
            feature_path=feature_path,
            control_repo_override=control_repo_override,
            docs_path_override=docs_path_override,
            skill_source_override=skill_source_override,
            runtime_target_override=runtime_target_override,
        )
    except ConfigError as exc:
        return _build_spec_payload(
            feature_id=feature_id,
            report=normalized_report,
            bug=normalized_bug_state,
            context=None,
            blockers=[str(exc)],
        )

    return _build_spec_payload(
        feature_id=feature_id,
        report=normalized_report,
        bug=normalized_bug_state,
        context=context,
    )


if __name__ == "__main__":
    raise SystemExit(main())
