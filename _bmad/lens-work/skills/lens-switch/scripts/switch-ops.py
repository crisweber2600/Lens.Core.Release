#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Switch operations — manage active feature context for Lens agent sessions.

Reads feature-index.yaml and feature.yaml files to validate targets, writes the
local-only .lens/personal/context.yaml session pointer, computes cross-feature
context paths, and reports control-repo branch checkout status.
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


SAFE_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")
MAX_INDEX_BYTES = 1_000_000  # 1 MB sanity cap on feature-index.yaml
STALE_DAYS = 30
NEW_FEATURE_COMMAND = "/new-feature"


def fail(error: str, message: str) -> dict:
    """Return a structured failure payload."""
    return {"status": "fail", "error": error, "message": message}


def expand_config_value(value: str, workspace_root: Path) -> str:
    """Expand config placeholders used by Lens module config files."""
    return value.replace("{project-root}", str(workspace_root))


def read_yaml_mapping(path: Path) -> tuple[dict | None, str | None]:
    """Read a YAML mapping from path, returning a message on failure."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as exc:
        return None, str(exc)
    if not isinstance(data, dict):
        return None, f"{path} must contain a YAML mapping"
    return data, None


def resolve_governance_repo(args: argparse.Namespace) -> tuple[str | None, dict | None]:
    """Resolve governance repo from CLI, local override, then module config.

    Order:
      1. Explicit --governance-repo
      2. <workspace-root>/.lens/governance-setup.yaml governance_repo_path
      3. Module bmadconfig.yaml governance_repo_path

    Missing config returns config_missing with /lens-onboard guidance.
    """
    explicit = getattr(args, "governance_repo", None)
    if explicit:
        return explicit, None

    workspace_root = Path(getattr(args, "workspace_root", None) or os.getcwd())
    override_path = workspace_root / ".lens" / "governance-setup.yaml"
    if override_path.exists():
        data, error = read_yaml_mapping(override_path)
        if error:
            return None, fail("config_malformed", f"Could not read {override_path}: {error}")
        value = str(data.get("governance_repo_path") or "").strip()
        if value:
            return expand_config_value(value, workspace_root), None

    config_candidates: list[Path] = []
    module_config = getattr(args, "module_config", None)
    if module_config:
        config_candidates.append(Path(module_config))
    config_candidates.extend(
        [
            workspace_root / "_bmad" / "lens-work" / "bmadconfig.yaml",
            workspace_root / "lens.core" / "_bmad" / "lens-work" / "bmadconfig.yaml",
        ]
    )

    for config_path in config_candidates:
        if not config_path.exists():
            continue
        data, error = read_yaml_mapping(config_path)
        if error:
            return None, fail("config_malformed", f"Could not read {config_path}: {error}")
        value = str(data.get("governance_repo_path") or "").strip()
        if value:
            return expand_config_value(value, workspace_root), None

    return None, fail(
        "config_missing",
        "Governance repo config not found. Run /lens-onboard to set up governance config.",
    )


def normalize_target_repo_state(feature_data: dict) -> dict | None:
    """Return the primary target repo dev state summary from feature metadata."""
    target_repos = feature_data.get("target_repos") or []
    if not isinstance(target_repos, list):
        return None

    primary = next((entry for entry in target_repos if isinstance(entry, dict)), None)
    if not primary:
        return None

    repo = str(primary.get("repo") or primary.get("name") or "").strip() or None
    dev_branch_mode = str(primary.get("dev_branch_mode") or "").strip() or None
    working_branch = (
        str(primary.get("dev_branch_name") or primary.get("working_branch") or primary.get("branch") or "").strip() or None
    )
    base_branch = str(primary.get("dev_base_branch") or primary.get("default_branch") or "").strip() or None
    final_pr_url = str(primary.get("final_pr_url") or "").strip() or None
    final_review_report = str(primary.get("final_review_report") or "").strip() or None
    final_party_mode_report = str(primary.get("final_party_mode_report") or "").strip() or None

    pr_state = primary.get("pr_state")
    if pr_state is None and final_pr_url:
        pr_state = "created"
    final_pr_state = pr_state or ("not-required" if dev_branch_mode == "direct-default" else None)

    return {
        "repo": repo,
        "name": primary.get("name", ""),
        "local_path": primary.get("local_path", ""),
        "remote_url": primary.get("remote_url") or primary.get("url", ""),
        "dev_branch_mode": dev_branch_mode,
        "working_branch": working_branch,
        "base_branch": base_branch,
        "pr_state": pr_state,
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
            "Use lowercase alphanumeric characters, hyphens, dots, and underscores only."
        )
    return None


def load_feature_index(governance_repo: str) -> tuple[dict | None, dict | None]:
    """Load feature-index.yaml from the governance repo root.

    Returns (data, error_payload). On success error_payload is None.
    """
    index_path = Path(governance_repo) / "feature-index.yaml"
    if not index_path.exists():
        return None, fail("index_not_found", f"feature-index.yaml not found at {index_path}")

    if index_path.stat().st_size > MAX_INDEX_BYTES:
        return None, fail("index_malformed", f"feature-index.yaml exceeds size limit ({MAX_INDEX_BYTES} bytes)")

    try:
        with open(index_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return None, fail("index_malformed", f"Failed to parse feature-index.yaml: {e}")
    except OSError as e:
        return None, fail("index_malformed", f"Failed to read feature-index.yaml: {e}")

    if not isinstance(data, dict):
        return None, fail("index_malformed", "feature-index.yaml must be a YAML mapping")

    features = data.get("features")
    if not isinstance(features, list):
        return None, fail("index_malformed", "feature-index.yaml must contain a features list")

    for index, entry in enumerate(features):
        if not isinstance(entry, dict):
            return None, fail("index_malformed", f"feature-index.yaml features[{index}] must be a mapping")
        missing = [field for field in ("id", "domain", "service") if not entry.get(field)]
        if missing:
            return None, fail(
                "index_malformed",
                f"feature-index.yaml features[{index}] missing required field(s): {', '.join(missing)}",
            )

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


def write_context_yaml(
    personal_folder: str,
    domain: str,
    service: str,
    source: str,
    feature_id: str = "",
) -> Path:
    """Write context.yaml to the personal folder with current domain/service context."""
    context_path = Path(personal_folder) / "context.yaml"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_data: dict = {
        "domain": domain,
        "service": service,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "updated_by": source,
    }
    if feature_id:
        context_data["feature_id"] = feature_id

    fd, tmp_path = tempfile.mkstemp(dir=str(context_path.parent), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.safe_dump(context_data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, str(context_path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return context_path


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
    governance_repo: str,
    control_repo: str,
) -> dict[str, list[dict]]:
    """Derive cross-feature context paths from dependencies with exists flags."""
    deps = feature_data.get("dependencies") or {}
    depends_on: list[str] = deps.get("depends_on") or []
    related: list[str] = deps.get("related") or []
    blocks: list[str] = deps.get("blocks") or []

    def build_item(feature_id: str, kind: str) -> dict:
        path: Path | None = None
        entry = index_by_id.get(feature_id)
        if entry:
            d = entry.get("domain", "")
            s = entry.get("service", "")
            if kind == "related":
                path = Path(governance_repo) / "features" / d / s / feature_id / "summary.md"
            else:
                path = Path(control_repo) / "docs" / d / s / feature_id / "tech-plan.md"
        return {
            "id": feature_id,
            "path": str(path) if path else None,
            "exists": bool(path and path.exists()),
        }

    return {
        "related": [build_item(fid, "related") for fid in related],
        "depends_on": [build_item(fid, "depends_on") for fid in depends_on],
        "blocks": [build_item(fid, "blocks") for fid in blocks],
    }


def context_to_load_from_paths(context_paths: dict[str, list[dict]]) -> dict[str, list[str]]:
    """Return existing paths in the legacy context_to_load shape."""
    return {
        "summaries": [item["path"] for item in context_paths.get("related", []) if item.get("exists") and item.get("path")],
        "full_docs": [
            item["path"]
            for key in ("depends_on", "blocks")
            for item in context_paths.get(key, [])
            if item.get("exists") and item.get("path")
        ],
    }


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
        message = f"No features initialized and no domains registered. Run {NEW_FEATURE_COMMAND} to begin."
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
    governance_repo, config_error = resolve_governance_repo(args)
    if config_error:
        return config_error

    index_data, err = load_feature_index(governance_repo)
    if err:
        if err["error"] == "index_not_found":
            return scan_domain_inventory(governance_repo)
        return err

    raw_features: list[dict] = index_data.get("features") or []

    status_filter: str = args.status_filter
    if status_filter == "archived":
        raw_features = [f for f in raw_features if f.get("status") == "archived"]
    elif status_filter != "all":
        raw_features = [f for f in raw_features if f.get("status") != "archived"]

    features = []
    for i, f in enumerate(raw_features):
        feature_data = load_feature_yaml_for_index_entry(governance_repo, f)
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
    """Attempt git checkout of branch in control_repo. Returns (switched, error_code_or_msg)."""
    try:
        result = subprocess.run(
            ["git", "-C", control_repo, "checkout", branch],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True, None
        output = result.stderr.strip() or result.stdout.strip() or f"git checkout {branch} failed"
        if "pathspec" in output and "did not match any file" in output:
            return False, "branch_not_found"
        return False, output
    except OSError as e:
        return False, f"git not available: {e}"


def cmd_switch(args: argparse.Namespace) -> dict:
    """Validate and prepare context for switching to a feature."""
    err = validate_identifier(args.feature_id, "feature-id")
    if err:
        return fail("invalid_feature_id", err)

    governance_repo, config_error = resolve_governance_repo(args)
    if config_error:
        return config_error

    explicit_control_repo = getattr(args, "control_repo", None)
    personal_folder = resolve_personal_folder(governance_repo, args.personal_folder, explicit_control_repo)
    plan_branch = f"{args.feature_id}-plan"
    control_repo = explicit_control_repo or "."

    index_data, err = load_feature_index(governance_repo)
    if err:
        return err

    raw_features: list[dict] = index_data.get("features") or []
    index_by_id = {f.get("id"): f for f in raw_features if f.get("id")}

    index_entry = index_by_id.get(args.feature_id)
    if not index_entry:
        return fail("feature_not_found", f"Feature '{args.feature_id}' not found in feature-index.yaml")

    feature_path = feature_yaml_path_for_index_entry(governance_repo, index_entry)
    if not feature_path:
        return fail("feature_yaml_not_found", f"feature.yaml not found for '{args.feature_id}'")

    try:
        with open(feature_path) as f:
            feature_data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return fail("feature_yaml_malformed", f"Failed to read feature.yaml: {e}")

    if not isinstance(feature_data, dict):
        return fail("feature_yaml_malformed", "feature.yaml is not a valid YAML mapping")

    context_paths = build_context_paths(feature_data, index_by_id, governance_repo, control_repo)
    context_to_load = context_to_load_from_paths(context_paths)

    try:
        personal_context_path = str(
            write_context_yaml(
                personal_folder,
                str(feature_data.get("domain", "")),
                str(feature_data.get("service", "")),
                "lens-switch",
                feature_id=args.feature_id,
            )
        )
    except OSError as e:
        return fail("context_write_failed", f"Failed to write context.yaml: {e}")

    branch_switched2: bool | None = None
    branch_error2: str | None = None
    if control_repo:
        branch_switched2, branch_error2 = try_git_checkout(control_repo, plan_branch)

    owner = index_entry.get("owner", "")
    if not owner and isinstance(feature_data.get("team"), list) and feature_data["team"]:
        first_member = feature_data["team"][0]
        if isinstance(first_member, dict):
            owner = first_member.get("username", "")

    target_repo_state = normalize_target_repo_state(feature_data)
    feature_dir = str(feature_path.parent)
    out: dict = {
        "status": "pass",
        "plan_branch": plan_branch,
        "feature_id": args.feature_id,
        "domain": feature_data.get("domain", ""),
        "service": feature_data.get("service", ""),
        "phase": feature_data.get("phase", ""),
        "track": feature_data.get("track", ""),
        "priority": feature_data.get("priority", ""),
        "owner": owner,
        "stale": is_stale(feature_data),
        "context_path": feature_dir,
        "personal_context_path": personal_context_path,
        "target_repo_state": target_repo_state,
        "context_paths": context_paths,
        "context_to_load": context_to_load,
        "feature": {
            "id": args.feature_id,
            "name": feature_data.get("name", ""),
            "domain": feature_data.get("domain", ""),
            "service": feature_data.get("service", ""),
            "phase": feature_data.get("phase", ""),
            "track": feature_data.get("track", ""),
            "priority": feature_data.get("priority", ""),
            "status": index_entry.get("status", "active"),
            "owner": owner,
            "stale": is_stale(feature_data),
            "updated": str(feature_data.get("updated", "")),
            "context_path": feature_dir,
            "personal_context_path": personal_context_path,
            "target_repo": target_repo_state,
        },
    }
    if control_repo is not None:
        out["branch_switched"] = branch_switched2
        out["checked_out_branch"] = plan_branch if branch_switched2 else None
        out["branch_error"] = branch_error2
        if branch_error2:
            out["message"] = (
                f"Run {NEW_FEATURE_COMMAND} to initialize branches."
                if branch_error2 == "branch_not_found"
                else branch_error2
            )
    return out


def cmd_context_paths(args: argparse.Namespace) -> dict:
    """Get file paths needed for cross-feature context for a given feature."""
    err = validate_identifier(args.feature_id, "feature-id")
    if err:
        return fail("invalid_feature_id", err)

    err = validate_identifier(args.domain, "domain")
    if err:
        return fail("invalid_domain", err)

    err = validate_identifier(args.service, "service")
    if err:
        return fail("invalid_service", err)

    governance_repo, config_error = resolve_governance_repo(args)
    if config_error:
        return config_error

    # Prefer direct path using provided domain/service; fall back to scan
    direct_path = (
        Path(governance_repo)
        / "features"
        / args.domain
        / args.service
        / args.feature_id
        / "feature.yaml"
    )
    if direct_path.exists():
        feature_path: Path | None = direct_path
    else:
        feature_path = find_feature_yaml(governance_repo, args.feature_id)

    if not feature_path:
        return fail("feature_not_found", f"Feature '{args.feature_id}' not found")

    try:
        with open(feature_path) as f:
            feature_data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        return fail("feature_yaml_malformed", f"Failed to read feature.yaml: {e}")

    if not isinstance(feature_data, dict):
        return fail("feature_yaml_malformed", "feature.yaml is not a valid YAML mapping")

    # Load index for domain/service lookups of dependency features
    index_data, _ = load_feature_index(governance_repo)
    index_by_id: dict[str, dict] = {}
    if index_data:
        for f in (index_data.get("features") or []):
            if f.get("id"):
                index_by_id[f["id"]] = f

    control_repo = getattr(args, "control_repo", None) or os.getcwd()
    context_paths = build_context_paths(feature_data, index_by_id, governance_repo, control_repo)
    context_to_load = context_to_load_from_paths(context_paths)

    return {
        "status": "pass",
        "context_paths": context_paths,
        "summaries": context_to_load["summaries"],
        "full_docs": context_to_load["full_docs"],
    }


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
    list_p.add_argument("--governance-repo", required=False, help="Governance repo root path")
    list_p.add_argument("--workspace-root", required=False, help="Workspace root for config resolution")
    list_p.add_argument("--module-config", required=False, help="Explicit bmadconfig.yaml path")
    list_p.add_argument(
        "--status-filter",
        default="active",
        choices=["all", "active", "archived"],
        help="Filter by feature status (default: non-archived features)",
    )

    # switch
    switch_p = subparsers.add_parser("switch", help="Validate and prepare context for a feature switch")
    switch_p.add_argument("--governance-repo", required=False, help="Governance repo root path")
    switch_p.add_argument("--workspace-root", required=False, help="Workspace root for config resolution")
    switch_p.add_argument("--module-config", required=False, help="Explicit bmadconfig.yaml path")
    switch_p.add_argument("--feature-id", required=True, help="Target feature identifier")
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
    ctx_p.add_argument("--governance-repo", required=False, help="Governance repo root path")
    ctx_p.add_argument("--workspace-root", required=False, help="Workspace root for config resolution")
    ctx_p.add_argument("--module-config", required=False, help="Explicit bmadconfig.yaml path")
    ctx_p.add_argument("--feature-id", required=True, help="Feature identifier")
    ctx_p.add_argument("--domain", required=True, help="Feature domain")
    ctx_p.add_argument("--service", required=True, help="Feature service")
    ctx_p.add_argument("--control-repo", required=False, help="Control repo root path for docs context paths")

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
