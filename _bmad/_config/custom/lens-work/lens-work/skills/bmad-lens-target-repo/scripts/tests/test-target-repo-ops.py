#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for target-repo-ops.py."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SCRIPT = str(Path(__file__).parent.parent / "target-repo-ops.py")
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


def init_remote_repo(remote_root: Path, repo_name: str) -> str:
    remote_root.mkdir(parents=True, exist_ok=True)
    bare = remote_root / f"{repo_name}.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)

    work = remote_root / f"{repo_name}-work"
    subprocess.run(["git", "clone", str(bare), str(work)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(work), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(work), "config", "user.name", "Test User"], check=True, capture_output=True)
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(work), "add", "README.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(work), "commit", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(work), "branch", "-M", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(work), "push", "origin", "main"], check=True, capture_output=True)
    return str(bare)


def write_feature(governance_repo: Path, feature_id: str) -> None:
    feature_dir = governance_repo / "features" / "plugins" / "hermes" / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    feature_dir.joinpath("feature.yaml").write_text(
        yaml.dump(
            {
                "name": "Hermes Lens Plugin",
                "description": "",
                "featureId": feature_id,
                "domain": "plugins",
                "service": "hermes",
                "phase": "preplan",
                "track": "full",
                "milestones": {},
                "team": [{"username": "testuser", "role": "lead"}],
                "dependencies": {"depends_on": [], "depended_by": []},
                "target_repos": [],
                "links": {"retrospective": None, "issues": [], "pull_request": None},
                "priority": "medium",
                "created": "2026-04-13T00:00:00Z",
                "updated": "2026-04-13T00:00:00Z",
                "phase_transitions": [],
                "docs": {
                    "path": "docs/plugins/hermes/hermes-lens-plugin",
                    "governance_docs_path": "features/plugins/hermes/hermes-lens-plugin/docs",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_provision_existing_remote() -> None:
    print("test_provision_existing_remote", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        governance_repo = project_root / "TargetProjects" / "lens" / "lens-governance"
        governance_repo.mkdir(parents=True, exist_ok=True)
        governance_repo.joinpath("repo-inventory.yaml").write_text("repositories: []\n", encoding="utf-8")
        write_feature(governance_repo, "hermes-lens-plugin")

        remote_url = init_remote_repo(project_root / "remotes", "Lens.Hermes")

        result, code = run([
            "provision",
            "--governance-repo", str(governance_repo),
            "--feature-id", "hermes-lens-plugin",
            "--repo-name", "Lens.Hermes",
            "--remote-url", remote_url,
            "--default-branch", "main",
        ])
        assert_eq("provision status", result["status"], "pass")
        assert_eq("provision exit code", code, 0)
        assert_eq("local path", result["local_path"], "TargetProjects/plugins/hermes/Lens.Hermes")
        assert_true("cloned repo exists", (project_root / result["local_path"]).exists())

        inventory = yaml.safe_load((governance_repo / "repo-inventory.yaml").read_text(encoding="utf-8"))
        entry = inventory["repositories"][0]
        assert_eq("inventory local path", entry["local_path"], "TargetProjects/plugins/hermes/Lens.Hermes")

        feature = yaml.safe_load((governance_repo / "features" / "plugins" / "hermes" / "hermes-lens-plugin" / "feature.yaml").read_text(encoding="utf-8"))
        repo_entry = feature["target_repos"][0]
        assert_eq("feature repo local path", repo_entry["local_path"], "TargetProjects/plugins/hermes/Lens.Hermes")
        assert_eq("feature repo visibility", repo_entry["visibility"], "private")

        second_result, second_code = run([
            "provision",
            "--governance-repo", str(governance_repo),
            "--feature-id", "hermes-lens-plugin",
            "--repo-name", "Lens.Hermes",
            "--remote-url", remote_url,
            "--default-branch", "main",
        ])
        assert_eq("idempotent reprovision status", second_result["status"], "pass")
        assert_eq("idempotent reprovision exit code", second_code, 0)
        assert_eq("idempotent local repo status", second_result["clone"]["status"], "exists")


def test_provision_dry_run_create_remote() -> None:
    print("test_provision_dry_run_create_remote", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        governance_repo = project_root / "TargetProjects" / "lens" / "lens-governance"
        governance_repo.mkdir(parents=True, exist_ok=True)
        governance_repo.joinpath("repo-inventory.yaml").write_text("repositories: []\n", encoding="utf-8")
        write_feature(governance_repo, "hermes-lens-plugin")

        result, code = run([
            "provision",
            "--governance-repo", str(governance_repo),
            "--feature-id", "hermes-lens-plugin",
            "--repo-name", "Lens.Hermes",
            "--owner", "crisweber2600",
            "--visibility", "public",
            "--create-remote",
            "--dry-run",
        ])
        assert_eq("dry run status", result["status"], "pass")
        assert_eq("dry run exit code", code, 0)
        assert_eq("dry run local path normalized", result["local_path"], "TargetProjects/plugins/hermes/Lens.Hermes")
        assert_eq("dry run remote planned", result["remote"]["status"], "planned-create")
        assert_true("dry run inventory not written", len(yaml.safe_load((governance_repo / "repo-inventory.yaml").read_text(encoding="utf-8"))["repositories"]) == 0)


def test_provision_normalizes_relative_local_path() -> None:
    print("test_provision_normalizes_relative_local_path", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        governance_repo = project_root / "TargetProjects" / "lens" / "lens-governance"
        governance_repo.mkdir(parents=True, exist_ok=True)
        governance_repo.joinpath("repo-inventory.yaml").write_text("repositories: []\n", encoding="utf-8")
        write_feature(governance_repo, "hermes-lens-plugin")
        remote_url = init_remote_repo(project_root / "remotes", "Lens.Hermes")

        result, code = run([
            "provision",
            "--governance-repo", str(governance_repo),
            "--feature-id", "hermes-lens-plugin",
            "--repo-name", "Lens.Hermes",
            "--remote-url", remote_url,
            "--local-path", "plugins/hermes/Lens.Hermes",
        ])
        assert_eq("normalize local path status", result["status"], "pass")
        assert_eq("normalize local path exit code", code, 0)
        assert_eq("normalized local path", result["local_path"], "TargetProjects/plugins/hermes/Lens.Hermes")


def test_set_dev_branch_mode_updates_feature_and_inventory() -> None:
    print("test_set_dev_branch_mode_updates_feature_and_inventory", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        governance_repo = project_root / "TargetProjects" / "lens" / "lens-governance"
        governance_repo.mkdir(parents=True, exist_ok=True)
        governance_repo.joinpath("repo-inventory.yaml").write_text("repositories: []\n", encoding="utf-8")
        write_feature(governance_repo, "hermes-lens-plugin")
        remote_url = init_remote_repo(project_root / "remotes", "Lens.Hermes")

        provision_result, provision_code = run([
            "provision",
            "--governance-repo", str(governance_repo),
            "--feature-id", "hermes-lens-plugin",
            "--repo-name", "Lens.Hermes",
            "--remote-url", remote_url,
            "--default-branch", "main",
        ])
        assert_eq("provision before set mode", provision_code, 0)
        assert_eq("provision before set mode status", provision_result["status"], "pass")

        result, code = run([
            "set-dev-branch-mode",
            "--governance-repo", str(governance_repo),
            "--feature-id", "hermes-lens-plugin",
            "--mode", "feature-id-username",
            "--repo-name", "Lens.Hermes",
        ])
        assert_eq("set mode status", result["status"], "pass")
        assert_eq("set mode exit code", code, 0)
        assert_eq("set mode payload", result["dev_branch_mode"], "feature-id-username")

        inventory = yaml.safe_load((governance_repo / "repo-inventory.yaml").read_text(encoding="utf-8"))
        entry = inventory["repositories"][0]
        assert_eq("inventory dev branch mode", entry["dev_branch_mode"], "feature-id-username")

        feature = yaml.safe_load((governance_repo / "features" / "plugins" / "hermes" / "hermes-lens-plugin" / "feature.yaml").read_text(encoding="utf-8"))
        repo_entry = feature["target_repos"][0]
        assert_eq("feature dev branch mode", repo_entry["dev_branch_mode"], "feature-id-username")


def test_set_dev_branch_mode_dry_run_does_not_write() -> None:
    print("test_set_dev_branch_mode_dry_run_does_not_write", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        governance_repo = project_root / "TargetProjects" / "lens" / "lens-governance"
        governance_repo.mkdir(parents=True, exist_ok=True)
        governance_repo.joinpath("repo-inventory.yaml").write_text("repositories: []\n", encoding="utf-8")
        write_feature(governance_repo, "hermes-lens-plugin")
        remote_url = init_remote_repo(project_root / "remotes", "Lens.Hermes")

        provision_result, provision_code = run([
            "provision",
            "--governance-repo", str(governance_repo),
            "--feature-id", "hermes-lens-plugin",
            "--repo-name", "Lens.Hermes",
            "--remote-url", remote_url,
            "--default-branch", "main",
        ])
        assert_eq("dry-run provision exit code", provision_code, 0)
        assert_eq("dry-run provision status", provision_result["status"], "pass")

        result, code = run([
            "set-dev-branch-mode",
            "--governance-repo", str(governance_repo),
            "--feature-id", "hermes-lens-plugin",
            "--mode", "feature-id",
            "--repo-name", "Lens.Hermes",
            "--dry-run",
        ])
        assert_eq("dry-run set mode status", result["status"], "pass")
        assert_eq("dry-run set mode exit code", code, 0)
        assert_true("dry-run set mode flag", result["dry_run"])

        inventory = yaml.safe_load((governance_repo / "repo-inventory.yaml").read_text(encoding="utf-8"))
        entry = inventory["repositories"][0]
        assert_true("inventory dev branch mode absent after dry run", "dev_branch_mode" not in entry)


if __name__ == "__main__":
    test_provision_existing_remote()
    test_provision_dry_run_create_remote()
    test_provision_normalizes_relative_local_path()
    test_set_dev_branch_mode_updates_feature_and_inventory()
    test_set_dev_branch_mode_dry_run_does_not_write()

    print(f"\n{'=' * 40}", file=sys.stderr)
    print(f"Results: {PASS} passed, {FAIL} failed", file=sys.stderr)
    print(f"{'=' * 40}", file=sys.stderr)
    sys.exit(1 if FAIL > 0 else 0)