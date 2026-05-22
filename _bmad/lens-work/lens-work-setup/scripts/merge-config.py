# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""
merge-config.py — Anti-zombie config merge for the lens module.

Removes any existing lens section from the target config,
then writes the current module configuration values.
"""

import argparse
import sys
from pathlib import Path

import yaml


def merge_module_config(module_yaml_path: Path, target_config_path: Path) -> None:
    with open(module_yaml_path, "r", encoding="utf-8") as f:
        module_config = yaml.safe_load(f) or {}

    if not isinstance(module_config, dict):
        print(f"❌ module.yaml must contain a YAML mapping, got {type(module_config).__name__}", file=sys.stderr)
        sys.exit(1)

    module_code = module_config.get("code", "lens")

    with open(target_config_path, "r", encoding="utf-8") as f:
        target_config = yaml.safe_load(f) or {}

    if not isinstance(target_config, dict):
        print(f"❌ Target config must contain a YAML mapping, got {type(target_config).__name__}", file=sys.stderr)
        sys.exit(1)

    # Anti-zombie: remove existing module entry
    modules = target_config.get("modules", [])
    if isinstance(modules, list):
        cleaned = []
        for m in modules:
            if not isinstance(m, dict):
                print(f"⚠️  Skipping non-dict entry in modules list: {m!r}", file=sys.stderr)
                continue
            if m.get("code") != module_code:
                cleaned.append(m)
        target_config["modules"] = cleaned
    elif isinstance(modules, dict):
        modules.pop(module_code, None)
        target_config["modules"] = modules
    else:
        # Normalize unexpected types (null, string, etc.) to an empty list
        target_config["modules"] = []

    # Add current module entry
    entry = {
        "code": module_code,
        "name": module_config.get("name", ""),
        "module_version": module_config.get("module_version", module_config.get("version", "")),
        "type": module_config.get("type", "standalone"),
        "description": module_config.get("description", ""),
    }

    if isinstance(target_config["modules"], list):
        target_config["modules"].append(entry)
    else:
        target_config["modules"][module_code] = entry

    with open(target_config_path, "w", encoding="utf-8") as f:
        yaml.dump(target_config, f, default_flow_style=False, sort_keys=False)

    print(f"✅ Module '{module_code}' merged into {target_config_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge lens module config")
    parser.add_argument("--module-yaml", required=True, help="Path to module.yaml")
    parser.add_argument("--target-config", required=True, help="Path to target config file")
    args = parser.parse_args()

    module_path = Path(args.module_yaml)
    target_path = Path(args.target_config)

    if not module_path.exists():
        print(f"❌ Module YAML not found: {module_path}", file=sys.stderr)
        sys.exit(1)
    if not target_path.exists():
        print(f"❌ Target config not found: {target_path}", file=sys.stderr)
        sys.exit(1)

    merge_module_config(module_path, target_path)


if __name__ == "__main__":
    main()
