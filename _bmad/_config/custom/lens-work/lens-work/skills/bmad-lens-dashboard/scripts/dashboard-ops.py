#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Dashboard operations — collect feature data and generate the Lens HTML dashboard.

Data sources:
  - feature-index.yaml on main (no branch switching)
  - plan/{feature-id} branches for problems.md, retrospective.md (graceful degradation)
  - features/{domain}/{service}/{id}/summary.md on main
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

STALE_DAYS = 14
ACTIVE_PHASES = {"dev", "finalizeplan", "businessplan", "techplan"}


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def git_show(governance_repo: str, ref: str, path: str) -> str | None:
    """Read a file from a git ref without switching branches. Returns None on failure."""
    result = subprocess.run(
        ["git", "-C", governance_repo, "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else None


# ---------------------------------------------------------------------------
# Feature index
# ---------------------------------------------------------------------------


def read_feature_index(governance_repo: str) -> list[dict]:
    """Read and parse feature-index.yaml from main. Returns empty list on any failure."""
    content = git_show(governance_repo, "main", "feature-index.yaml")
    if not content:
        return []
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []
    features = data.get("features", [])
    return features if isinstance(features, list) else []


# ---------------------------------------------------------------------------
# Staleness
# ---------------------------------------------------------------------------


def is_stale(feature: dict) -> bool:
    """Return True if an active-phase feature hasn't been updated in STALE_DAYS days."""
    if feature.get("phase") not in ACTIVE_PHASES:
        return False
    last_updated = feature.get("lastUpdated")
    if not last_updated:
        return True
    try:
        ts_str = str(last_updated).rstrip("Z")
        dt = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt) > timedelta(days=STALE_DAYS)
    except (ValueError, TypeError):
        return True


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def get_phase_status(phase: str) -> str:
    """Map a phase name to a CSS status class."""
    if phase in {"preplan", "businessplan", "techplan", "finalizeplan"}:
        return "planning"
    if phase == "dev":
        return "dev"
    if phase == "complete":
        return "complete"
    if phase in {"paused", "archived"}:
        return "archived"
    return "unknown"


def extract_dependency_edges(feature: dict) -> list[dict]:
    """Extract all dependency edges from a feature dict."""
    fid = feature.get("featureId", "")
    deps = feature.get("dependencies", {}) or {}
    edges: list[dict] = []
    for dep_id in deps.get("depends_on") or []:
        edges.append({"from": fid, "to": dep_id, "type": "depends_on"})
    for dep_id in deps.get("blocks") or []:
        edges.append({"from": fid, "to": dep_id, "type": "blocks"})
    for dep_id in deps.get("related") or []:
        edges.append({"from": fid, "to": dep_id, "type": "related"})
    return edges


# ---------------------------------------------------------------------------
# Core data collection
# ---------------------------------------------------------------------------


def collect_data(governance_repo: str) -> dict:
    """Collect all dashboard data. Core logic shared by collect and generate."""
    features = read_feature_index(governance_repo)

    enriched: list[dict] = []
    stale_count = 0
    domains: set[str] = set()
    problems_by_phase: dict[str, int] = {}
    dependency_edges: list[dict] = []

    for feature in features:
        fid = feature.get("featureId", "")
        phase = feature.get("phase", "")
        domain = feature.get("domain", "")
        service = feature.get("service", "")
        domains.add(domain)

        stale = is_stale(feature)
        if stale:
            stale_count += 1

        # Deep content from governance main (graceful degradation)
        feature_dir = f"features/{domain}/{service}/{fid}"
        problems_content = git_show(governance_repo, "main", f"{feature_dir}/problems.md")
        retro_content = git_show(governance_repo, "main", f"{feature_dir}/retrospective.md")
        summary_content = git_show(
            governance_repo, "main", f"{feature_dir}/summary.md"
        )

        if problems_content and phase:
            count = len(
                [line for line in problems_content.split("\n") if re.match(r"^#{1,3} |^- ", line)]
            )
            problems_by_phase[phase] = problems_by_phase.get(phase, 0) + max(1, count)

        enriched.append(
            {
                "featureId": fid,
                "name": feature.get("name", ""),
                "domain": domain,
                "service": service,
                "phase": phase,
                "track": feature.get("track", ""),
                "priority": feature.get("priority", ""),
                "stale": stale,
                "lastUpdated": str(feature.get("lastUpdated", "")) or None,
                "has_problems": problems_content is not None,
                "has_retro": retro_content is not None,
                "has_summary": summary_content is not None,
            }
        )
        dependency_edges.extend(extract_dependency_edges(feature))

    return {
        "status": "pass",
        "features": enriched,
        "stale_count": stale_count,
        "domain_count": len(domains),
        "problems_by_phase": problems_by_phase,
        "dependency_edges": dependency_edges,
    }


# ---------------------------------------------------------------------------
# HTML section builders
# ---------------------------------------------------------------------------


def build_feature_overview_table(features: list[dict]) -> str:
    """Generate the feature overview HTML table."""
    rows = []
    for f in features:
        status = get_phase_status(f.get("phase", ""))
        stale_badge = (
            ' <span class="badge-stale">STALE</span>' if f.get("stale") else ""
        )
        rows.append(
            f'<tr class="status-{status}">'
            f'<td><code>{f["featureId"]}</code>{stale_badge}</td>'
            f"<td>{f['name']}</td>"
            f"<td>{f['domain']}</td>"
            f"<td>{f['service']}</td>"
            f'<td><span class="phase">{f["phase"]}</span></td>'
            f"<td>{f['track']}</td>"
            f"<td>{f['priority']}</td>"
            f"</tr>"
        )
    if not rows:
        rows = ['<tr><td colspan="7" class="empty">No features found in feature-index.yaml</td></tr>']
    return (
        '<table class="data-table"><thead><tr>'
        "<th>Feature ID</th><th>Name</th><th>Domain</th><th>Service</th>"
        "<th>Phase</th><th>Track</th><th>Priority</th>"
        "</tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table>"
    )


def build_dependency_svg(nodes: list[dict], edges: list[dict]) -> str:
    """Generate an inline SVG dependency graph with grid layout."""
    if not nodes:
        return (
            '<svg width="400" height="60" xmlns="http://www.w3.org/2000/svg">'
            '<text x="20" y="35" fill="#475569" font-family="system-ui,sans-serif" font-size="13">'
            "No features to display</text></svg>"
        )

    width, height = 820, 400
    node_r = 30
    n = len(nodes)
    cols = max(1, min(6, n))
    rows_count = (n + cols - 1) // cols
    col_w = width / (cols + 1)
    row_h = height / (rows_count + 1)

    positions: dict[str, tuple[float, float]] = {}
    for i, node in enumerate(nodes):
        col = i % cols
        row = i // cols
        positions[node["id"]] = (col_w * (col + 1), row_h * (row + 1))

    status_colors = {
        "planning": "#3b82f6",
        "dev": "#f97316",
        "complete": "#22c55e",
        "archived": "#6b7280",
        "unknown": "#9ca3af",
    }
    edge_colors = {
        "depends_on": "#ef4444",
        "blocks": "#f97316",
        "related": "#6b7280",
    }

    svg: list[str] = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg">',
        '<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
        '<path d="M0,0 L0,6 L8,3 z" fill="#888"/></marker></defs>',
    ]

    for edge in edges:
        src = positions.get(edge["from"])
        dst = positions.get(edge["to"])
        if not src or not dst:
            continue
        color = edge_colors.get(edge["type"], "#6b7280")
        svg.append(
            f'<line x1="{src[0]:.1f}" y1="{src[1]:.1f}" '
            f'x2="{dst[0]:.1f}" y2="{dst[1]:.1f}" '
            f'stroke="{color}" stroke-width="1.5" '
            f'marker-end="url(#arr)" opacity="0.7"/>'
        )

    for node in nodes:
        pos = positions.get(node["id"])
        if not pos:
            continue
        x, y = pos
        color = status_colors.get(node["status"], "#9ca3af")
        label = node["id"][:12] + ("…" if len(node["id"]) > 12 else "")
        svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{node_r}" '
            f'fill="{color}" opacity="0.85" stroke="#1f2937" stroke-width="2"/>'
        )
        svg.append(
            f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" '
            f'font-size="9" fill="#fff" font-family="monospace">{label}</text>'
        )

    svg.append("</svg>")
    return "\n".join(svg)


def build_problem_heatmap_table(problems_by_phase: dict) -> str:
    """Generate the problem heatmap HTML table."""
    if not problems_by_phase:
        return '<p class="empty">No problem data available.</p>'
    rows = []
    max_count = max(problems_by_phase.values(), default=1)
    for phase, count in sorted(problems_by_phase.items(), key=lambda x: -x[1]):
        bar_width = max(4, int(count / max_count * 100))
        rows.append(
            f"<tr><td>{phase}</td><td>{count}</td>"
            f'<td><div class="heat-bar" style="width:{bar_width}%"></div></td></tr>'
        )
    return (
        '<table class="data-table"><thead><tr>'
        "<th>Phase</th><th>Problem Count</th><th>Heatmap</th>"
        "</tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table>"
    )


def build_sprint_progress_table(features: list[dict]) -> str:
    """Generate the sprint progress table for active features."""
    active = [f for f in features if f.get("phase") in {"dev", "finalizeplan"}]
    if not active:
        return '<p class="empty">No active features in dev or finalizeplan phase.</p>'
    rows = []
    for f in active:
        summary_icon = "✓" if f.get("has_summary") else "—"
        problems_icon = "✓" if f.get("has_problems") else "—"
        stale_badge = ' <span class="badge-stale">STALE</span>' if f.get("stale") else ""
        rows.append(
            f'<tr><td><code>{f["featureId"]}</code>{stale_badge}</td>'
            f"<td>{f['name']}</td>"
            f"<td>{f['phase']}</td>"
            f"<td>{f['priority']}</td>"
            f"<td>{summary_icon}</td>"
            f"<td>{problems_icon}</td></tr>"
        )
    return (
        '<table class="data-table"><thead><tr>'
        "<th>Feature ID</th><th>Name</th><th>Phase</th>"
        "<th>Priority</th><th>Summary</th><th>Problems</th>"
        "</tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table>"
    )


def build_team_view_table(_features: list[dict]) -> str:
    """Generate the team view section (requires user daily logs)."""
    return '<p class="empty">Team view requires user daily logs (unavailable in this run).</p>'


def build_retro_trends_table(features: list[dict]) -> str:
    """Generate the retrospective trends section."""
    with_retro = [f for f in features if f.get("has_retro")]
    without_retro = [f for f in features if not f.get("has_retro") and f.get("phase") not in {"preplan", "complete"}]
    if not with_retro:
        return '<p class="empty">No retrospective data available.</p>'
    rows = []
    for f in with_retro:
        rows.append(
            f'<tr><td><code>{f["featureId"]}</code></td>'
            f"<td>{f['domain']}</td>"
            f"<td>{f['phase']}</td>"
            f'<td><span style="color:#22c55e">✓ Available</span></td></tr>'
        )
    for f in without_retro:
        rows.append(
            f'<tr><td><code>{f["featureId"]}</code></td>'
            f"<td>{f['domain']}</td>"
            f"<td>{f['phase']}</td>"
            f'<td><span style="color:#64748b">— Unavailable</span></td></tr>'
        )
    return (
        '<table class="data-table"><thead><tr>'
        "<th>Feature ID</th><th>Domain</th><th>Phase</th><th>Retrospective</th>"
        "</tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table>"
    )


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def get_template(template_path: str | None) -> str | None:
    """Load the HTML template from a given path or the default bundled asset."""
    if template_path:
        p = Path(template_path)
        if p.exists():
            return p.read_text(encoding="utf-8")
        return None
    default = Path(__file__).parent.parent / "assets" / "dashboard-template.html"
    if default.exists():
        return default.read_text(encoding="utf-8")
    return None


def render_template(template: str, placeholders: dict[str, str]) -> str:
    """Replace all {{KEY}} placeholders in the template."""
    result = template
    for key, value in placeholders.items():
        result = result.replace("{{" + key + "}}", value)
    return result


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_collect(args: argparse.Namespace) -> dict:
    """Collect all dashboard data from the governance repo."""
    if not Path(args.governance_repo).exists():
        return {"status": "fail", "error": f"Governance repo not found: {args.governance_repo}"}

    result = collect_data(args.governance_repo)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        result["output_file"] = args.output

    return result


def cmd_dependency_data(args: argparse.Namespace) -> dict:
    """Extract dependency graph data from feature-index.yaml on main."""
    if not Path(args.governance_repo).exists():
        return {"status": "fail", "error": f"Governance repo not found: {args.governance_repo}"}

    features = read_feature_index(args.governance_repo)
    nodes: list[dict] = []
    edges: list[dict] = []

    for feature in features:
        nodes.append(
            {
                "id": feature.get("featureId", ""),
                "name": feature.get("name", ""),
                "domain": feature.get("domain", ""),
                "status": get_phase_status(feature.get("phase", "")),
            }
        )
        edges.extend(extract_dependency_edges(feature))

    return {"status": "pass", "nodes": nodes, "edges": edges}


def cmd_generate(args: argparse.Namespace) -> dict:
    """Generate the HTML dashboard file."""
    if not Path(args.governance_repo).exists():
        return {"status": "fail", "error": f"Governance repo not found: {args.governance_repo}"}

    template = get_template(getattr(args, "template", None))
    if template is None:
        return {"status": "fail", "error": "Dashboard template not found"}

    data = collect_data(args.governance_repo)
    features = data.get("features", [])

    dep_nodes = [
        {
            "id": f["featureId"],
            "name": f["name"],
            "domain": f["domain"],
            "status": get_phase_status(f["phase"]),
        }
        for f in features
    ]
    dep_edges = data.get("dependency_edges", [])

    stale_count = data.get("stale_count", 0)
    stale_alerts = ""
    if stale_count:
        stale_items = "".join(
            f'<li><code>{f["featureId"]}</code> ({f["phase"]})</li>'
            for f in features
            if f.get("stale")
        )
        stale_alerts = (
            f'<div class="stale-alert">'
            f"<strong>⚠ {stale_count} stale feature(s) — no updates in {STALE_DAYS}+ days:</strong>"
            f"<ul>{stale_items}</ul></div>"
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    placeholders: dict[str, str] = {
        "TITLE": "Lens Dashboard",
        "GENERATED_AT": now,
        "STALE_ALERTS": stale_alerts,
        "FEATURE_OVERVIEW_TABLE": build_feature_overview_table(features),
        "DEPENDENCY_GRAPH_SVG": build_dependency_svg(dep_nodes, dep_edges),
        "PROBLEM_HEATMAP_TABLE": build_problem_heatmap_table(data.get("problems_by_phase", {})),
        "SPRINT_PROGRESS_TABLE": build_sprint_progress_table(features),
        "TEAM_VIEW_TABLE": build_team_view_table(features),
        "RETRO_TRENDS_TABLE": build_retro_trends_table(features),
    }

    html = render_template(template, placeholders)
    output_path = getattr(args, "output", None) or "./lens-dashboard.html"
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    return {
        "status": "pass",
        "output_path": str(out.resolve()),
        "features_included": len(features),
        "generated_at": now,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dashboard operations — collect feature data and generate the Lens HTML dashboard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s collect --governance-repo /path/to/repo
  %(prog)s collect --governance-repo /path/to/repo --output ./data.json
  %(prog)s dependency-data --governance-repo /path/to/repo
  %(prog)s generate --governance-repo /path/to/repo
  %(prog)s generate --governance-repo /path/to/repo --output ./dashboard.html
""",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # collect
    collect_p = subparsers.add_parser("collect", help="Collect all dashboard data")
    collect_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    collect_p.add_argument("--output", default=None, help="Optional JSON output file path")

    # dependency-data
    dep_p = subparsers.add_parser("dependency-data", help="Extract dependency graph data")
    dep_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")

    # generate
    gen_p = subparsers.add_parser("generate", help="Generate HTML dashboard")
    gen_p.add_argument("--governance-repo", required=True, help="Path to governance repo root")
    gen_p.add_argument(
        "--output", default="./lens-dashboard.html", help="Output HTML file path"
    )
    gen_p.add_argument(
        "--template", default=None, help="Path to HTML template (default: bundled template)"
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "collect": cmd_collect,
        "dependency-data": cmd_dependency_data,
        "generate": cmd_generate,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()

    sys.exit(0 if result.get("status") == "pass" else 1)


if __name__ == "__main__":
    main()
