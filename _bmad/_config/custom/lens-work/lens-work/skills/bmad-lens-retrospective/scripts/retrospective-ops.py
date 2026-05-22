#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Retrospective operations — analyze problems, generate root cause reports, update insights.

Parses problems.md (append-only problem log), identifies patterns, generates
retrospective.md for the feature archive, and updates user-level insights.md
with cross-feature learning.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


VALID_PHASES = ["preplan", "businessplan", "techplan", "finalizeplan", "dev", "complete"]
VALID_CATEGORIES = [
    "requirements-gap",
    "execution-failure",
    "communication-breakdown",
    "technical-debt",
    "process-gap",
    "external-dependency",
    "scope-creep",
    "unknown",
]
VALID_STATUSES = ["open", "resolved"]
PATTERN_THRESHOLD = 3


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def parse_problems(content: str) -> list[dict]:
    """Parse problems.md content into a list of problem dicts."""
    problems = []
    # Split on ## Problem: headers
    sections = re.split(r"(?=^## Problem:)", content, flags=re.MULTILINE)
    for section in sections:
        section = section.strip()
        if not section.startswith("## Problem:"):
            continue
        problem: dict = {}

        # Title
        title_match = re.match(r"^## Problem:\s*(.+)$", section, re.MULTILINE)
        problem["title"] = title_match.group(1).strip() if title_match else "Untitled"

        # Metadata fields
        for field, key in [
            ("Phase", "phase"),
            ("Category", "category"),
            ("Status", "status"),
            ("Date", "date"),
            ("GitHub Issue", "github_issue"),
        ]:
            match = re.search(rf"^\s*[-*]\s*\*\*{field}:\*\*\s*(.+)$", section, re.MULTILINE | re.IGNORECASE)
            if match:
                problem[key] = match.group(1).strip()

        # Normalize and validate phase
        raw_phase = problem.get("phase", "").lower()
        problem["phase"] = raw_phase if raw_phase in VALID_PHASES else "unknown"

        # Normalize and validate category
        raw_cat = problem.get("category", "").lower()
        problem["category"] = raw_cat if raw_cat in VALID_CATEGORIES else "unknown"

        # Normalize status
        raw_status = problem.get("status", "").lower()
        problem["status"] = raw_status if raw_status in VALID_STATUSES else "open"

        problems.append(problem)
    return problems


def detect_patterns(by_category: dict[str, list[str]]) -> list[dict]:
    """Detect patterns: categories meeting the threshold (3+ occurrences)."""
    patterns = []
    for category, phases in by_category.items():
        count = len(phases)
        if count < PATTERN_THRESHOLD:
            continue
        unique_phases = sorted(set(phases))
        if len(unique_phases) == 1:
            phase_desc = f"concentrated in {unique_phases[0]}"
        elif len(unique_phases) == 2:
            phase_desc = f"repeated in {unique_phases[0]} and {unique_phases[1]}"
        else:
            phase_desc = f"spread across {len(unique_phases)} phases"
        patterns.append({
            "category": category,
            "count": count,
            "phases": unique_phases,
            "pattern": phase_desc,
        })
    # Sort by count descending for readability
    patterns.sort(key=lambda p: p["count"], reverse=True)
    return patterns


def cmd_analyze(args: argparse.Namespace) -> tuple[dict, int]:
    """Parse problems.md and return structured analysis."""
    problems_path = Path(args.problems_file)
    if not problems_path.exists():
        return {"status": "fail", "error": f"problems_file_not_found: {args.problems_file}"}, 1

    content = problems_path.read_text(encoding="utf-8")
    problems = parse_problems(content)

    total = len(problems)
    open_count = sum(1 for p in problems if p["status"] == "open")
    resolved_count = total - open_count

    # Tally by phase (count of problems per phase)
    by_phase: dict[str, int] = {}
    for p in problems:
        phase = p["phase"]
        by_phase[phase] = by_phase.get(phase, 0) + 1

    # Tally by category and track phases per category for pattern detection
    by_category_counts: dict[str, int] = {}
    by_category_phases: dict[str, list[str]] = {}
    for p in problems:
        cat = p["category"]
        by_category_counts[cat] = by_category_counts.get(cat, 0) + 1
        by_category_phases.setdefault(cat, []).append(p["phase"])

    patterns = detect_patterns(by_category_phases)

    return {
        "status": "pass",
        "total": total,
        "open": open_count,
        "resolved": resolved_count,
        "by_phase": by_phase,
        "by_category": by_category_counts,
        "patterns": patterns,
    }, 0


def build_report(feature_id: str, problems: list[dict], analysis: dict) -> str:
    """Build retrospective.md markdown content from analysis."""
    date = now_iso()
    total = analysis["total"]
    open_count = analysis["open"]
    resolved = analysis["resolved"]
    patterns = analysis["patterns"]
    by_phase = analysis["by_phase"]

    # Summary sentence
    if patterns:
        dominant = patterns[0]
        summary = (
            f"{total} problems logged. "
            f"The dominant pattern is **{dominant['category']}** "
            f"({dominant['count']} occurrences, {dominant['pattern']}). "
            f"This suggests a systemic issue in the affected phases."
        )
    elif total == 0:
        summary = "No problems were logged for this feature."
    else:
        # Find top category
        by_cat = analysis["by_category"]
        top_cat = max(by_cat, key=lambda c: by_cat[c]) if by_cat else "unknown"
        summary = (
            f"{total} problems logged. "
            f"No single category reached pattern threshold. "
            f"Most common category: **{top_cat}** ({by_cat.get(top_cat, 0)} occurrences)."
        )

    lines: list[str] = [
        f"# Retrospective: {feature_id}",
        "",
        f"**Feature ID:** {feature_id}  ",
        f"**Date:** {date}  ",
        f"**Problems Logged:** {total} ({open_count} open, {resolved} resolved)",
        "",
        "## Summary",
        "",
        summary,
        "",
    ]

    # Findings section
    lines.append("## Findings")
    lines.append("")

    if patterns:
        for i, pat in enumerate(patterns, 1):
            phases_str = ", ".join(pat["phases"]) if pat["phases"] else "unknown"
            lines.append(f"### Finding {i}: {pat['category'].replace('-', ' ').title()} — {pat['count']} occurrences")
            lines.append("")
            lines.append(f"**Phases affected:** {phases_str}  ")
            lines.append(f"**Pattern:** {pat['pattern']}")
            lines.append("")
            lines.append(
                f"This category recurred {pat['count']} times across {len(pat['phases'])} phase(s), "
                f"indicating a systemic breakdown rather than a one-off incident. "
                f"Root cause investigation should focus on what made these phases susceptible to {pat['category']} problems."
            )
            lines.append("")
    else:
        lines.append("No patterns detected (no category reached the threshold of 3+ occurrences).")
        lines.append("")
        # Still report phase distribution if notable
        if by_phase:
            top_phase = max(by_phase, key=lambda ph: by_phase[ph])
            top_count = by_phase[top_phase]
            if total > 0 and top_count / total > 0.4:
                lines.append(
                    f"**Phase concentration:** {top_count} of {total} problems ({round(top_count/total*100)}%) "
                    f"occurred in **{top_phase}**. This phase warrants closer process review."
                )
                lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    rec_num = 1
    if patterns:
        for pat in patterns:
            cat = pat["category"]
            if cat == "requirements-gap":
                lines.append(
                    f"{rec_num}. **Define acceptance criteria before entering techplan** — "
                    "Requirements gaps concentrated in planning phases indicate specifications are finalized too late."
                )
            elif cat == "execution-failure":
                lines.append(
                    f"{rec_num}. **Add progress checkpoints during dev** — "
                    "Execution failures suggest implementation diverged from plan; mid-phase reviews catch drift early."
                )
            elif cat == "communication-breakdown":
                lines.append(
                    f"{rec_num}. **Establish explicit handoff artifacts between phases** — "
                    "Communication breakdowns indicate implicit context that fails to transfer across boundaries."
                )
            elif cat == "technical-debt":
                lines.append(
                    f"{rec_num}. **Schedule dedicated debt paydown sprints** — "
                    "Recurring technical debt indicates systemic underinvestment in code quality."
                )
            elif cat == "process-gap":
                lines.append(
                    f"{rec_num}. **Document and enforce the missing process step** — "
                    "Process gaps that recur are missing process definitions, not exceptions."
                )
            elif cat == "external-dependency":
                lines.append(
                    f"{rec_num}. **Identify and de-risk external dependencies during businessplan** — "
                    "External dependency problems are predictable; surface them before committing to a delivery date."
                )
            elif cat == "scope-creep":
                lines.append(
                    f"{rec_num}. **Require change requests for scope additions after techplan** — "
                    "Scope creep indicates scope is being added without formal impact assessment."
                )
            else:
                lines.append(
                    f"{rec_num}. **Investigate root cause of {cat} problems** — "
                    f"{pat['count']} occurrences warrant a dedicated root cause session."
                )
            rec_num += 1
    else:
        lines.append(
            f"{rec_num}. **Continue current practices** — "
            "No systemic patterns detected. Individual problems were isolated incidents."
        )
        rec_num += 1

    if open_count > 0 and total > 0 and open_count / total > 0.3:
        lines.append(
            f"{rec_num}. **Resolve or file GitHub Issues for all open problems before archiving** — "
            f"{open_count} of {total} problems remain open ({round(open_count/total*100)}%)."
        )
        rec_num += 1

    lines.append("")

    # Open problems table
    open_problems = [p for p in problems if p["status"] == "open"]
    if open_problems:
        lines.append("## Open Problems")
        lines.append("")
        lines.append("| Problem | Phase | Category | GitHub Issue |")
        lines.append("|---------|-------|----------|-------------|")
        for p in open_problems:
            issue = p.get("github_issue", "—") or "—"
            lines.append(f"| {p['title']} | {p['phase']} | {p['category']} | {issue} |")
        lines.append("")

    # Archive footer
    lines.append("## Archive")
    lines.append("")
    lines.append(f"Problems logged: {total}. Retrospective generated: {date}.")
    lines.append("")

    return "\n".join(lines)


def cmd_generate_report(args: argparse.Namespace) -> tuple[dict, int]:
    """Generate retrospective.md from problems.md analysis."""
    problems_path = Path(args.problems_file)
    if not problems_path.exists():
        return {"status": "fail", "error": f"problems_file_not_found: {args.problems_file}"}, 1

    content = problems_path.read_text(encoding="utf-8")
    problems = parse_problems(content)

    # Reuse analyze logic
    total = len(problems)
    open_count = sum(1 for p in problems if p["status"] == "open")
    resolved_count = total - open_count

    by_phase: dict[str, int] = {}
    by_category_counts: dict[str, int] = {}
    by_category_phases: dict[str, list[str]] = {}
    for p in problems:
        by_phase[p["phase"]] = by_phase.get(p["phase"], 0) + 1
        by_category_counts[p["category"]] = by_category_counts.get(p["category"], 0) + 1
        by_category_phases.setdefault(p["category"], []).append(p["phase"])

    patterns = detect_patterns(by_category_phases)
    analysis = {
        "total": total,
        "open": open_count,
        "resolved": resolved_count,
        "by_phase": by_phase,
        "by_category": by_category_counts,
        "patterns": patterns,
    }

    report_content = build_report(args.feature_id, problems, analysis)

    output_path = Path(args.output)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report_content, encoding="utf-8")
    except OSError as e:
        return {"status": "fail", "error": f"output_write_failed: {e}"}, 1

    # Count recommendations in output
    rec_count = report_content.count("\n1. ") + report_content.count("\n2. ") + report_content.count("\n3. ")
    # Simple count: number of numbered list items in Recommendations section
    rec_section = re.search(r"## Recommendations\n(.*?)(?=\n##|\Z)", report_content, re.DOTALL)
    if rec_section:
        rec_count = len(re.findall(r"^\d+\.", rec_section.group(1), re.MULTILINE))
    else:
        rec_count = 0

    return {
        "status": "pass",
        "report_path": str(output_path),
        "patterns_found": len(patterns),
        "recommendations": rec_count,
    }, 0


def build_insights_section(feature_id: str, patterns: list[dict]) -> str:
    """Build a markdown section to append to insights.md."""
    date = now_iso()
    count = len(patterns)
    lines = [
        f"## {feature_id} — {date}",
        "",
        f"{count} pattern{'s' if count != 1 else ''} identified.",
        "",
    ]
    if patterns:
        lines.append("| Category | Count | Phases | Pattern |")
        lines.append("|----------|-------|--------|---------|")
        for pat in patterns:
            phases_str = ", ".join(pat.get("phases", []))
            lines.append(
                f"| {pat['category']} | {pat['count']} | {phases_str} | {pat['pattern']} |"
            )
        lines.append("")
        dominant = patterns[0]
        lines.append(
            f"**Key Takeaway:** **{dominant['category']}** was the primary failure mode "
            f"({dominant['count']} occurrences, {dominant['pattern']}). "
            "Watch for this in future features during planning."
        )
    else:
        lines.append("No patterns met the recurrence threshold.")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


INSIGHTS_HEADER = """# Lens Insights

Cross-feature patterns and lessons learned. Updated automatically by the retrospective skill.

---

"""


def cmd_update_insights(args: argparse.Namespace) -> tuple[dict, int]:
    """Append new patterns to user insights.md."""
    try:
        patterns = json.loads(args.patterns)
    except json.JSONDecodeError as e:
        return {"status": "fail", "error": f"invalid_patterns_json: {e}"}, 1

    insights_path = Path(args.insights_file)
    parent = insights_path.parent

    if not parent.exists():
        return {"status": "fail", "error": f"insights_dir_not_found: {parent}"}, 1

    if args.dry_run:
        section = build_insights_section(args.feature_id, patterns)
        return {
            "status": "pass",
            "insights_path": str(insights_path),
            "new_patterns": len(patterns),
            "dry_run": True,
            "preview": section,
        }, 0

    if insights_path.exists():
        existing = insights_path.read_text(encoding="utf-8")
    else:
        existing = INSIGHTS_HEADER

    section = build_insights_section(args.feature_id, patterns)

    try:
        insights_path.write_text(existing.rstrip() + "\n\n" + section, encoding="utf-8")
    except OSError as e:
        return {"status": "fail", "error": f"insights_write_failed: {e}"}, 1

    return {
        "status": "pass",
        "insights_path": str(insights_path),
        "new_patterns": len(patterns),
        "dry_run": False,
    }, 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="retrospective-ops",
        description="Retrospective operations for Lens features",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # analyze
    p_analyze = sub.add_parser("analyze", help="Analyze problems.md and return structured analysis")
    p_analyze.add_argument("--problems-file", required=True, help="Path to problems.md")

    # generate-report
    p_report = sub.add_parser("generate-report", help="Generate retrospective.md from analysis")
    p_report.add_argument("--problems-file", required=True, help="Path to problems.md")
    p_report.add_argument("--feature-id", required=True, help="Feature identifier")
    p_report.add_argument("--output", required=True, help="Path to write retrospective.md")

    # update-insights
    p_insights = sub.add_parser("update-insights", help="Append new patterns to user insights.md")
    p_insights.add_argument("--insights-file", required=True, help="Path to insights.md")
    p_insights.add_argument("--patterns", required=True, help="JSON array of pattern objects")
    p_insights.add_argument("--feature-id", required=True, help="Feature identifier")
    p_insights.add_argument("--dry-run", action="store_true", help="Preview without writing")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "analyze": cmd_analyze,
        "generate-report": cmd_generate_report,
        "update-insights": cmd_update_insights,
    }

    result, exit_code = handlers[args.command](args)
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
