#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Print Lens feature lifecycle state without ad hoc parsing snippets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from lens_config import ConfigError, discover_feature_yaml, load_lens_config, normalize_absolute_path  # noqa: E402


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def resolve_governance_repo(args: argparse.Namespace) -> Path:
    """Resolve governance repo following the standard order.

    Order:
      1. Explicit --governance-repo CLI argument
      2. <workspace-root>/.lens/governance-setup.yaml  governance_repo_path
      3. Module bmadconfig.yaml governance_repo_path
    """
    if args.governance_repo:
        return normalize_absolute_path(args.governance_repo)

    workspace_root = normalize_absolute_path(args.workspace_root or Path.cwd())

    # Step 2: per-user .lens/governance-setup.yaml override
    override_path = workspace_root / ".lens" / "governance-setup.yaml"
    if override_path.is_file():
        try:
            raw = yaml.safe_load(override_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigError(f"Could not read {override_path}: {exc}") from exc
        if isinstance(raw, dict):
            value = str(raw.get("governance_repo_path") or "").strip()
            if value:
                value = value.replace("{project-root}", str(workspace_root))
                return normalize_absolute_path(value)

    # Step 3: bmadconfig.yaml via lens_config
    config = load_lens_config(args.module_config, start=workspace_root)
    return Path(config.data["governance_repo_path"])


def resolve_feature_yaml(args: argparse.Namespace) -> Path:
    if args.feature_path:
        path = normalize_absolute_path(args.feature_path)
        if not path.is_file():
            raise FileNotFoundError(f"feature.yaml not found: {path}")
        return path

    if not args.feature_id:
        raise ValueError("Provide --feature-id or --feature-path")

    governance_repo = resolve_governance_repo(args)
    path = discover_feature_yaml(governance_repo, args.feature_id)
    if path is None:
        raise FileNotFoundError(f"feature.yaml not found for '{args.feature_id}'")
    return path


def build_state(feature_path: Path) -> dict[str, Any]:
    data = load_yaml_mapping(feature_path)
    links = data.get("links") if isinstance(data.get("links"), dict) else {}
    docs = data.get("docs") if isinstance(data.get("docs"), dict) else {}
    return {
        "feature_id": data.get("featureId") or data.get("feature_id") or data.get("id"),
        "name": data.get("name"),
        "domain": data.get("domain"),
        "service": data.get("service"),
        "phase": data.get("phase"),
        "track": data.get("track"),
        "target_repos": data.get("target_repos") or [],
        "docs_path": docs.get("path"),
        "governance_docs_path": docs.get("governance_docs_path"),
        "pull_request": links.get("pull_request"),
        "issues": links.get("issues") or [],
        "feature_yaml_path": str(feature_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print Lens feature lifecycle state.")
    parser.add_argument("--feature-id", required=False, help="Feature identifier to discover in governance features/")
    parser.add_argument("--feature-path", required=False, help="Direct path to feature.yaml")
    parser.add_argument("--governance-repo", required=False, help="Governance repo root path")
    parser.add_argument("--workspace-root", required=False, help="Workspace/project root for config discovery")
    parser.add_argument("--module-config", required=False, help="Explicit lens-work bmadconfig.yaml path")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        state = build_state(resolve_feature_yaml(args))
    except (ConfigError, FileNotFoundError, OSError, ValueError, yaml.YAMLError) as exc:
        print(json.dumps({"status": "fail", "error": "lifecycle_state_failed", "message": str(exc)}, indent=2))
        return 1

    print(json.dumps({"status": "pass", **state}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
