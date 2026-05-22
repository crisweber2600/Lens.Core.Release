#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Validate Lens BMAD wrapper registry coverage across publication surfaces."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import yaml


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def prompt_is_supported_by_preflight(prompt_path: str) -> bool:
    name = Path(prompt_path).name
    return name.startswith("lens-work") or name.startswith("lens-") or name.startswith("len-")


def main() -> int:
    module_root = Path(__file__).resolve().parent.parent

    registry_path = module_root / "assets" / "lens-bmad-skill-registry.json"
    module_yaml_path = module_root / "module.yaml"
    module_help_path = module_root / "module-help.csv"
    help_topics_path = module_root / "skills" / "bmad-lens-help" / "assets" / "help-topics.yaml"
    installer_path = module_root / "_module-installer" / "installer.js"
    failures: list[str] = []

    registry = load_json(registry_path)
    module_yaml = load_yaml(module_yaml_path)
    module_help = load_csv(module_help_path)
    help_topics = load_yaml(help_topics_path)
    installer_text = installer_path.read_text(encoding="utf-8")

    module_prompts = set(module_yaml.get("prompts", []))
    adapter_prompts = set(module_yaml.get("adapters", {}).get("github-copilot", {}).get("stub_prompts", []))
    topic_commands = {topic["command"] for topic in help_topics.get("topics", [])}

    for adapter_prompt in adapter_prompts:
        if not prompt_is_supported_by_preflight(adapter_prompt):
            failures.append(
                f"preflight prompt allowlist missing adapter stub family: {adapter_prompt}"
            )

    for skill in registry.get("skills", []):
        prompt_file = skill["promptFile"]
        prompt_path = module_root / "prompts" / prompt_file
        adapter_prompt = f".github/prompts/{prompt_file}"
        if not prompt_path.exists():
            failures.append(f"missing prompt file: {prompt_file}")
        if prompt_file not in module_prompts:
            failures.append(f"module.yaml missing prompt entry: {prompt_file}")
        if adapter_prompt not in adapter_prompts:
            failures.append(f"module.yaml adapter missing stub prompt: {adapter_prompt}")
        if not any(
            row.get("skill") == "bmad-lens-bmad-skill"
            and row.get("display-name") == skill["id"]
            for row in module_help
        ):
            failures.append(f"module-help.csv missing wrapper row for: {skill['id']}")
        if skill["command"] not in topic_commands:
            failures.append(f"help-topics.yaml missing command: {skill['command']}")
        if f"file: '{prompt_file}'" not in installer_text:
            failures.append(f"installer.js missing STUB_PROMPTS entry: {prompt_file}")

    if failures:
        print("Lens BMAD registry validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Validated {len(registry.get('skills', []))} Lens BMAD registry entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())