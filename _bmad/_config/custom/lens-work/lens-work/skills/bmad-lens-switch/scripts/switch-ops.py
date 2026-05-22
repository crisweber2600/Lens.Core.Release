#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Switch operations — manage active feature context for Lens agent sessions.

Reads feature-index.yaml (always from main) and feature.yaml files to validate
targets, load cross-feature context paths, and confirm feature switches.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml


SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
MAX_INDEX_BYTES = 1_000_000  # 1 MB sanity cap on feature-index.yaml
STALE_DAYS = 30


def normalize_target_repo_state(feature_data: dict) -> dict | None:
    """Return the primary target repo dev state summary from feature metadata."""
    target_repos = feature_data.get("target_repos") or []
    if not isinstance(target_repos, list):
        return None

    primary = next((entry for entry in target_repos if isinstance(entry, dict)), None)
    if not primary:
        return None

    dev_branch_mode = str(primary.get("dev_branch_mode") or "").strip() or None
    working_branch = (
        str(primary.get("dev_branch_name") or primary.get("working_branch") or primary.get("branch") or "").strip() or None
    )
    base_branch = str(primary.get("dev_base_branch") or primary.get("default_branch") or "").strip() or None
    final_pr_url = str(primary.get("final_pr_url") or "").strip() or None
    final_review_report = str(primary.get("final_review_report") or "").strip() or None
    final_party_mode_report = str(primary.get("final_party_mode_report") or "").strip() or None

    if dev_branch_mode == "direct-default":
        final_pr_state = "not-required"
    elif final_pr_url:
        final_pr_state = "created"
    elif dev_branch_mode:
        final_pr_state = "pending"
    else:
        final_pr_state = "unknown"

    return {
        "name": primary.get("name", ""),
        "local_path": primary.get("local_path", ""),
        "remote_url": primary.get("remote_url") or primary.get("url", ""),
        "dev_branch_mode": dev_branch_mode,
        "working_branch": working_branch,
        "base_branch": base_branch,
        "final_pr_state": final_pr_state,
        "final_pr_url": final_pr_url,
        "final_review_report": final_review_report,
        "final_party_mode_report": final_party_mode_report,
    }


def load_feature_yaml_for_index_entry(governance_repo: str, entry: dict) -> dict | None:
    """Load feature.yaml for an index entry when available."""
    feature_path = feature_yaml_path_for_index_entry(governance_repo, entry)
    if feature_path is None:
        return None

    try:
        with open(feature_path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return None
    return data if isinstance(data, dict) else None


def feature_yaml_path_for_index_entry(governance_repo: str, entry: dict) -> Path | None:
    """Return the direct feature.yaml path for an index entry when available."""
    feature_id = str(entry.get("id") or entry.get("featureId") or "").strip()
    domain = str(entry.get("domain") or "").strip()
    service = str(entry.get("service") or "").strip()
    if not feature_id or not domain or not service:
        return None

    feature_path = Path(governance_repo) / "features" / domain / service / feature_id / "feature.yaml"
    return feature_path if feature_path.exists() else None


def validate_identifier(value: str, field_name: str) -> str | None:
    """Validate that a path-constructing identifier is safe. Returns error message or None."""
    if not SAFE_ID_PATTERN.match(value):
        return (
            f"Invalid {field_name}: '{value}'. "
            f"Must match [a-z0-9][a-z0-9._-]{{0,63}} "
            f"(lowercase alphanumeric, dots, hyphens, underscores)."
        )
    return None


def load_feature_index(governance_repo: str) -> tuple[dict | None, str | None]:
    """Load feature-index.yaml from the governance repo root.

    Returns (data, error). On success error is None; on failure data is None.
    """
    index_path = Path(governance_repo) / "feature-index.yaml"
    if not index_path.exists():
        return None, f"feature-index.yaml not found at {index_path}"

    if index_path.stat().st_size > MAX_INDEX_BYTES:
        return None, f"feature-index.yaml exceeds size limit ({MAX_INDEX_BYTES} bytes)"

    try:
        with open(index_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return None, f"Failed to parse feature-index.yaml: {e}"
    except OSError as e:
        return None, f"Failed to read feature-index.yaml: {e}"

    if not isinstance(data, dict):
        return None, "feature-index.yaml must be a YAML mapping"

    return data, None


def find_feature_yaml(governance_repo: str, feature_id: str) -> Path | None:
    """Find feature.yaml by scanning all domains/services under features/."""
    features_dir = Path(governance_repo) / "features"
    if not features_dir.exists():
        return None
    for yaml_file in sorted(features_dir.rglob("feature.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if data and data.get("featureId") == feature_id:
                return yaml_file
        except (yaml.YAMLError, OSError):
            continue
    return None


def write_context_yaml(personal_folder: str, domain: str, service: str, source: str) -> Path:
    """Write context.yaml to the personal folder with current domain/service context."""
    context_path = Path(personal_folder) / "context.yaml"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_data = {
        "domain": domain,
        "service": service,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "updated_by": source,
    }

    fd, tmp_path = tempfile.mkstemp(dir=str(context_path.parent), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(context_data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, str(context_path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return context_path


def find_service_by_id(governance_repo: str, service_id: str) -> dict | None:
    """Find service metadata by service id from service.yaml files under features/."""
    features_dir = Path(governance_repo) / "features"
    if not features_dir.exists():
        return None

    for yaml_file in sorted(features_dir.rglob("service.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("id") == service_id:
            return {
                "id": data.get("id", ""),
                "name": data.get("name", ""),
                "domain": data.get("domain", ""),
                "service": data.get("service", ""),
                "status": data.get("status", "active"),
                "owner": data.get("owner", ""),
            }
    return None


def load_service_by_path(governance_repo: str, domain: str, service: str) -> dict | None:
    """Load service metadata using an explicit domain/service path."""
    service_yaml = Path(governance_repo) / "features" / domain / service / "service.yaml"
    if not service_yaml.exists():
        return None
    try:
        with open(service_yaml) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return {
        "id": data.get("id", f"{domain}-{service}"),
        "name": data.get("name", ""),
        "domain": data.get("domain", domain),
        "service": data.get("service", service),
        "status": data.get("status", "active"),
        "owner": data.get("owner", ""),
    }


def resolve_service_context(
    governance_repo: str,
    selector_id: str,
    domain: str | None,
    service: str | None,
) -> tuple[dict | None, str | None]:
    """Resolve a service context from explicit domain/service or service id."""
    if domain and service:
        service_meta = load_service_by_path(governance_repo, domain, service)
        if not service_meta:
            return None, f"Service '{domain}/{service}' not found in governance repo"
        return service_meta, None

    service_meta = find_service_by_id(governance_repo, selector_id)
    if service_meta:
        return service_meta, None

    return None, (
        "feature-index.yaml not found and no matching service context found. "
        f"Expected service id '{selector_id}' from domain inventory, or provide --domain and --service."
    )


def resolve_personal_folder(
    governance_repo: str,
    personal_folder: str | None,
    control_repo: str | None = None,
) -> str:
    """Resolve the personal folder used for context.yaml persistence.

    If not provided explicitly and a control repo is set, default to:
    <control_repo>/.lens/personal

    Otherwise default to sibling of governance repo root:
    <governance_repo_parent>/.lens/personal
    """
    if personal_folder:
        return personal_folder
    if control_repo:
        return str(Path(control_repo) / ".lens" / "personal")
    return str(Path(governance_repo).parent / ".lens" / "personal")


def is_stale(feature_data: dict) -> bool:
    """Return True if the feature has not been updated in STALE_DAYS days."""
    updated = feature_data.get("updated", "")
    if not updated or not isinstance(updated, str):
        return False
    try:
        dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days > STALE_DAYS
    except ValueError:
        return False


def build_context_paths(
    feature_data: dict,
    index_by_id: dict[str, dict],
) -> tuple[list[str], list[str]]:
    """Derive cross-feature context paths from dependencies.

    Returns (summaries, full_docs):
      - summaries: summary.md paths for 'related' features
      - full_docs: tech-plan.md paths for 'depends_on' and 'blocks' features
    """
    deps = feature_data.get("dependencies") or {}
    depends_on: list[str] = deps.get("depends_on") or []
    related: list[str] = deps.get("related") or []
    blocks: list[str] = deps.get("blocks") or []

    full_doc_ids = list(dict.fromkeys(depends_on + blocks))
    # related features not already in full_doc_ids get summaries only
    summary_ids = [fid for fid in related if fid not in full_doc_ids]

    summaries: list[str] = []
    for fid in summary_ids:
        entry = index_by_id.get(fid)
        if entry:
            d = entry.get("domain", "")
            s = entry.get("service", "")
            summaries.append(f"features/{d}/{s}/{fid}/summary.md")

    full_docs: list[str] = []
    for fid in full_doc_ids:
        entry = index_by_id.get(fid)
        if entry:
            d = entry.get("domain", "")
            s = entry.get("service", "")
            full_docs.append(f"features/{d}/{s}/{fid}/tech-plan.md")

    return summaries, full_docs


def scan_domain_inventory(governance_repo: str) -> dict:
    """Scan features/ for domain.yaml and service.yaml files.

    Fallback used when feature-index.yaml does not yet exist. Returns domain/service
    inventory so the agent can orient the user without requiring feature initialization.
    """
    features_dir = Path(governance_repo) / "features"
    domains: list[dict] = []

    if features_dir.exists():
        for domain_dir in sorted(d for d in features_dir.iterdir() if d.is_dir()):
            domain_yaml = domain_dir / "domain.yaml"
            if not domain_yaml.exists():
                continue
            try:
                with open(domain_yaml) as f:
                    domain_data = yaml.safe_load(f)
            except (yaml.YAMLError, OSError):
                continue
            if not isinstance(domain_data, dict):
                continue

            services: list[dict] = []
            for service_dir in sorted(d for d in domain_dir.iterdir() if d.is_dir()):
                service_yaml = service_dir / "service.yaml"
                if not service_yaml.exists():
                    continue
                try:
                    with open(service_yaml) as f:
                        service_data = yaml.safe_load(f)
                except (yaml.YAMLError, OSError):
                    continue
                if not isinstance(service_data, dict):
                    continue
                services.append(
                    {
                        "id": service_data.get("id", ""),
                        "name": service_data.get("name", ""),
                        "service": service_data.get("service", ""),
                        "status": service_data.get("status", "active"),
                        "owner": service_data.get("owner", ""),
                    }
                )

            domains.append(
                {
                    "id": domain_data.get("id", ""),
                    "name": domain_data.get("name", ""),
                    "domain": domain_data.get("domain", ""),
                    "status": domain_data.get("status", "active"),
                    "owner": domain_data.get("owner", ""),
                    "services": services,
                }
            )

    total_services = sum(len(d["services"]) for d in domains)
    if domains:
        message = "No features initialized yet. Showing domain/service inventory from governance repo."
    else:
        message = "No features initialized and no domains registered. Run /lens-init-feature to begin."
    return {
        "status": "pass",
        "mode": "domains",
        "domains": domains,
        "total_domains": len(domains),
        "total_services": total_services,
        "message": message,
    }


def cmd_list(args: argparse.Namespace) -> dict:
    """List features from feature-index.yaml with optional status filter.

    Falls back to domain/service inventory (scan_domain_inventory) when
    feature-index.yaml does not yet exist in the governance repo.
    """
    index_data, err = load_feature_index(args.governance_repo)
    if err:
        if "not found" in err:
            return scan_domain_inventory(args.governance_repo)
        return {"status": "fail", "error": err}

    raw_features: list[dict] = index_data.get("features") or []

    status_filter: str = args.status_filter
    if status_filter == "archived":
        raw_features = [f for f in raw_features if f.get("status") == "archived"]
    elif status_filter != "all":
        raw_features = [f for f in raw_features if f.get("status") != "archived"]

    features = []
    for i, f in enumerate(raw_features):
        feature_data = load_feature_yaml_for_index_entry(args.governance_repo, f)
        features.append(
            {
                "num": i + 1,
                "id": f.get("id", ""),
                "domain": f.get("domain", ""),
                "service": f.get("service", ""),
                "status": f.get("status", "active"),
                "owner": f.get("owner", ""),
                "summary": f.get("summary", ""),
                "target_repo": normalize_target_repo_state(feature_data or {}),
            }
        )

    return {"status": "pass", "mode": "features", "features": features, "total": len(features)}


def try_git_checkout(control_repo: str, branch: str) -> tuple[bool, str | None]:
    """Attempt git checkout of branch in control_repo. Returns (switched, error_msg)."""
    try:
        result = subprocess.run(
            ["git", "-C", control_repo, "checkout", branch],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True, None
        return False, result.stderr.strip() or result.stdout.strip() or f"git checkout {branch} failed"
    except OSError as e:
        return False, f"git not available: {e}"


def cmd_switch(args: argparse.Namespace) -> dict:
    """Validate and prepare context for switching to a feature."""
    err = validate_identifier(args.feature_id, "feature-id")
    if err:
        return {"status": "fail", "error": err}

    if args.domain:
        err = validate_identifier(args.domain, "domain")
        if err:
            return {"status": "fail", "error": err}
    if args.service:
        err = validate_identifier(args.service, "service")
        if err:
            return {"status": "fail", "error": err}

    explicit_control_repo = getattr(args, "control_repo", None)
    personal_folder = resolve_personal_folder(args.governance_repo, args.personal_folder, explicit_control_repo)
    plan_branch = f"{args.feature_id}-plan"
    control_repo = explicit_control_repo or "."

    index_data, err = load_feature_index(args.governance_repo)
    if err:
        if "not found" not in err:
            return {"status": "fail", "error": err}

        service_meta, service_err = resolve_service_context(
            args.governance_repo,
            args.feature_id,
            args.domain,
            args.service,
        )
        if service_err:
            return {"status": "fail", "error": service_err}

        try:
            context_path = str(
                write_context_yaml(
                    personal_folder,
                    service_meta["domain"],
                    service_meta["service"],
                    "lens-switch",
                )
            )
        except OSError as e:
            return {"status": "fail", "error": f"Failed to write context.yaml: {e}"}

        branch_switched: bool | None = None
        branch_error: str | None = None
        if control_repo:
            branch_switched, branch_error = try_git_checkout(control_repo, plan_branch)

        result: dict = {
            "status": "pass",
            "mode": "service-context",
            "plan_branch": plan_branch,
            "service_context": {
                "id": service_meta["id"],
                "name": service_meta["name"],
                "domain": service_meta["domain"],
                "service": service_meta["service"],
                "status": service_meta["status"],
                "owner": service_meta["owner"],
                "context_path": context_path,
            },
            "context_to_load": {
                "summaries": [],
                "full_docs": [],
            },
            "message": "feature-index.yaml missing; switched to service context fallback.",
        }
        if control_repo is not None:
            result["branch_switched"] = branch_switched
            if branch_error:
                result["branch_error"] = branch_error
        return result

    raw_features: list[dict] = index_data.get("features") or []
    index_by_id = {f.get("id"): f for f in raw_features if f.get("id")}

    index_entry = index_by_id.get(args.feature_id)
    if not index_entry:
        return {
            "status": "fail",
            "error": f"Feature '{args.feature_id}' not found in feature-index.yaml",
        }

    feature_path = feature_yaml_path_for_index_entry(args.governance_repo, index_entry)
    if feature_path is None:
        feature_path = find_feature_yaml(args.governance_repo, args.feature_id)
    if not feature_path:
        return {
            "status": "fail",
            "error": f"feature.yaml not found for '{args.feature_id}'",
        }

    try:
        with open(feature_path) as f:
            feature_data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "error": f"Failed to read feature.yaml: {e}"}

    if not isinstance(feature_data, dict):
        return {"status": "fail", "error": "feature.yaml is not a valid YAML mapping"}

    summaries, full_docs = build_context_paths(feature_data, index_by_id)

    try:
        context_path = str(
            write_context_yaml(
                personal_folder,
                str(feature_data.get("domain", "")),
                str(feature_data.get("service", "")),
                "lens-switch",
            )
        )
    except OSError as e:
        return {"status": "fail", "error": f"Failed to write context.yaml: {e}"}

    branch_switched2: bool | None = None
    branch_error2: str | None = None
    if control_repo:
        branch_switched2, branch_error2 = try_git_checkout(control_repo, plan_branch)

    out: dict = {
        "status": "pass",
        "plan_branch": plan_branch,
        "feature": {
            "id": args.feature_id,
            "name": feature_data.get("name", ""),
            "domain": feature_data.get("domain", ""),
            "service": feature_data.get("service", ""),
            "phase": feature_data.get("phase", ""),
            "track": feature_data.get("track", ""),
            "priority": feature_data.get("priority", ""),
            "status": index_entry.get("status", "active"),
            "owner": index_entry.get("owner", ""),
            "stale": is_stale(feature_data),
            "updated": str(feature_data.get("updated", "")),
            "context_path": context_path,
            "target_repo": normalize_target_repo_state(feature_data),
        },
        "context_to_load": {
            "summaries": summaries,
            "full_docs": full_docs,
        },
    }
    if control_repo is not None:
        out["branch_switched"] = branch_switched2
        if branch_error2:
            out["branch_error"] = branch_error2
    return out


def cmd_context_paths(args: argparse.Namespace) -> dict:
    """Get file paths needed for cross-feature context for a given feature."""
    err = validate_identifier(args.feature_id, "feature-id")
    if err:
        return {"status": "fail", "error": err}

    # Prefer direct path using provided domain/service; fall back to scan
    direct_path = (
        Path(args.governance_repo)
        / "features"
        / args.domain
        / args.service
        / args.feature_id
        / "feature.yaml"
    )
    if direct_path.exists():
        feature_path: Path | None = direct_path
    else:
        feature_path = find_feature_yaml(args.governance_repo, args.feature_id)

    if not feature_path:
        return {
            "status": "fail",
            "error": f"Feature '{args.feature_id}' not found",
        }

    try:
        with open(feature_path) as f:
            feature_data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return {"status": "fail", "error": f"Failed to read feature.yaml: {e}"}

    if not isinstance(feature_data, dict):
        return {"status": "fail", "error": "feature.yaml is not a valid YAML mapping"}

    # Load index for domain/service lookups of dependency features
    index_data, _ = load_feature_index(args.governance_repo)
    index_by_id: dict[str, dict] = {}
    if index_data:
        for f in (index_data.get("features") or []):
            if f.get("id"):
                index_by_id[f["id"]] = f

    summaries, full_docs = build_context_paths(feature_data, index_by_id)

    return {"status": "pass", "summaries": summaries, "full_docs": full_docs}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Switch operations — manage active feature context.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list --governance-repo /path/to/repo/
  %(prog)s list --governance-repo /path/to/repo/ --status-filter all

  %(prog)s switch --governance-repo /path/to/repo/ --feature-id auth-login

  %(prog)s context-paths --governance-repo /path/to/repo/ \\
    --feature-id auth-login --domain platform --service identity
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    list_p = subparsers.add_parser("list", help="List features from feature-index.yaml")
    list_p.add_argument("--governance-repo", required=True, help="Governance repo root path")
    list_p.add_argument(
        "--status-filter",
        default="active",
        choices=["all", "active", "archived"],
        help="Filter by feature status (default: non-archived features)",
    )

    # switch
    switch_p = subparsers.add_parser("switch", help="Validate and prepare context for a feature switch")
    switch_p.add_argument("--governance-repo", required=True, help="Governance repo root path")
    switch_p.add_argument("--feature-id", required=True, help="Target feature identifier")
    switch_p.add_argument(
        "--domain",
        required=False,
        help="Domain for service-context fallback when feature-index.yaml is missing",
    )
    switch_p.add_argument(
        "--service",
        required=False,
        help="Service for service-context fallback when feature-index.yaml is missing",
    )
    switch_p.add_argument(
        "--personal-folder",
        required=False,
        help=(
            "Path to personal folder for context.yaml persistence. "
            "If omitted, defaults to <governance_repo_parent>/.lens/personal"
        ),
    )
    switch_p.add_argument(
        "--control-repo",
        required=False,
        dest="control_repo",
        help=(
            "Path to the control repo root. Defaults to '.' (the workspace root) for branch checkout. "
            "When provided and --personal-folder is omitted, context.yaml defaults to "
            "<control_repo>/.lens/personal."
        ),
    )

    # context-paths
    ctx_p = subparsers.add_parser("context-paths", help="Get cross-feature context file paths")
    ctx_p.add_argument("--governance-repo", required=True, help="Governance repo root path")
    ctx_p.add_argument("--feature-id", required=True, help="Feature identifier")
    ctx_p.add_argument("--domain", required=True, help="Feature domain")
    ctx_p.add_argument("--service", required=True, help="Feature service")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "list": cmd_list,
        "switch": cmd_switch,
        "context-paths": cmd_context_paths,
    }

    result = commands[args.command](args)
    json.dump(result, sys.stdout, indent=2, default=str)
    print()

    sys.exit(0 if result.get("status") in ("pass", "warning") else 1)


if __name__ == "__main__":
    main()
