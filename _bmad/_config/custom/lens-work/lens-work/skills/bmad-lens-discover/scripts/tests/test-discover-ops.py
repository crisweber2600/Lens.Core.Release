#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for discover-ops.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SCRIPT = str(Path(__file__).parent.parent / "discover-ops.py")
PASS = 0
FAIL = 0


def run(args: list[str]) -> tuple[dict, int]:
    result = subprocess.run([sys.executable, SCRIPT] + args, capture_output=True, text=True)
    try:
        return json.loads(result.stdout), result.returncode
    except json.JSONDecodeError:
        return {"stderr": result.stderr, "stdout": result.stdout}, result.returncode


def assert_eq(name: str, actual, expected) -> None:
    global PASS, FAIL
    if actual == expected:
        PASS += 1
        print(f"  ✓ {name}", file=sys.stderr)
    else:
        FAIL += 1
        print(f"  ✗ {name}: expected {expected!r}, got {actual!r}", file=sys.stderr)


def assert_true(name: str, actual) -> None:
    assert_eq(name, bool(actual), True)


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test User"], check=True, capture_output=True)
    (path / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], check=True, capture_output=True)


def test_scan_tracks_project_root_relative_local_path() -> None:
    print("test_scan_tracks_project_root_relative_local_path", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        target_root = project_root / "TargetProjects"
        repo_path = target_root / "plugins" / "hermes" / "Lens.Hermes"
        init_repo(repo_path)

        inventory_path = project_root / "repo-inventory.yaml"
        inventory_path.write_text(
            yaml.dump(
                {
                    "repositories": [
                        {
                            "name": "Lens.Hermes",
                            "remote_url": "https://github.com/example/Lens.Hermes",
                            "local_path": "TargetProjects/plugins/hermes/Lens.Hermes",
                        }
                    ]
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        result, code = run([
            "scan",
            "--inventory-path", str(inventory_path),
            "--target-root", str(target_root),
            "--json",
        ])
        assert_eq("scan exit code", code, 0)
        assert_eq("already cloned count", len(result["already_cloned"]), 1)
        assert_eq("missing count", len(result["missing_from_disk"]), 0)
        assert_eq("untracked count", len(result["untracked"]), 0)


def test_scan_reports_untracked_repo_with_targetprojects_prefix() -> None:
    print("test_scan_reports_untracked_repo_with_targetprojects_prefix", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        target_root = project_root / "TargetProjects"
        repo_path = target_root / "plugins" / "hermes" / "Lens.Hermes"
        init_repo(repo_path)

        inventory_path = project_root / "repo-inventory.yaml"
        inventory_path.write_text("repositories: []\n", encoding="utf-8")

        result, code = run([
            "scan",
            "--inventory-path", str(inventory_path),
            "--target-root", str(target_root),
            "--json",
        ])
        assert_eq("scan exit code", code, 0)
        assert_eq("untracked count", len(result["untracked"]), 1)
        assert_eq(
            "untracked path uses project-root-relative TargetProjects prefix",
            result["untracked"][0]["local_path"],
            "TargetProjects/plugins/hermes/Lens.Hermes",
        )


if __name__ == "__main__":
    test_scan_tracks_project_root_relative_local_path()
    test_scan_reports_untracked_repo_with_targetprojects_prefix()

    print(f"\n{'=' * 40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'=' * 40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)