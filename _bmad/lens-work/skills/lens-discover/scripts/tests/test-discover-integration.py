import hashlib
import json
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "discover-ops.py"
COMMIT_MESSAGE = "[discover] Sync repo-inventory.yaml"


def run_json(args: list[str], cwd: Path | None = None) -> tuple[dict, int]:
    completed = subprocess.run(
        ["uv", "run", "--script", str(SCRIPT), *args, "--json"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Non-JSON output\nstdout={completed.stdout}\nstderr={completed.stderr}") from exc
    return payload, completed.returncode


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def init_bare_remote(path: Path) -> None:
    run_git(["init", "--bare", str(path)])
    run_git(["--git-dir", str(path), "symbolic-ref", "HEAD", "refs/heads/main"])


def clone_governance(remote: Path, destination: Path) -> None:
    run_git(["clone", str(remote), str(destination)])
    run_git(["checkout", "-b", "main"], cwd=destination)
    run_git(["config", "user.email", "test@example.com"], cwd=destination)
    run_git(["config", "user.name", "Test User"], cwd=destination)


def init_work_repo(path: Path, remote: Path) -> None:
    path.mkdir(parents=True)
    run_git(["init", str(path)])
    run_git(["-C", str(path), "remote", "add", "origin", str(remote)])


def commit_and_push_initial_inventory(governance: Path, inventory: list[dict]) -> str:
    (governance / "repo-inventory.yaml").write_text(
        json.dumps({"repositories": inventory}, indent=2) + "\n",
        encoding="utf-8",
    )
    run_git(["add", "repo-inventory.yaml"], cwd=governance)
    run_git(["commit", "-m", "initial inventory"], cwd=governance)
    run_git(["push", "-u", "origin", "main"], cwd=governance)
    return run_git(["rev-parse", "HEAD"], cwd=governance).stdout.strip()


def orchestrate_discover(governance: Path, target_root: Path) -> dict:
    inventory_path = governance / "repo-inventory.yaml"
    pre_hash = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    scan, scan_code = run_json(
        ["scan", "--inventory-path", str(inventory_path), "--target-root", str(target_root)]
    )
    assert scan_code == 0

    added_entries = []
    for entry in scan["untracked"]:
        remote_url = entry.get("remote_url")
        if not remote_url:
            continue
        result, code = run_json(
            [
                "add-entry",
                "--inventory-path",
                str(inventory_path),
                "--name",
                entry["name"],
                "--remote-url",
                remote_url,
                "--local-path",
                entry["local_path"],
            ]
        )
        assert code == 0
        if result["added"]:
            added_entries.append(entry["name"])

    validate, validate_code = run_json(["validate", "--inventory-path", str(inventory_path)])
    assert validate_code == 0
    assert validate["valid"] is True

    post_hash = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    committed = False
    if pre_hash != post_hash:
        run_git(["add", "repo-inventory.yaml"], cwd=governance)
        run_git(["commit", "-m", COMMIT_MESSAGE], cwd=governance)
        run_git(["push"], cwd=governance)
        committed = True

    return {
        "scan": scan,
        "added_entries": added_entries,
        "pre_hash": pre_hash,
        "post_hash": post_hash,
        "committed": committed,
    }


def test_integration_auto_commit_fires_on_changed_inventory(tmp_path: Path):
    governance_remote = tmp_path / "governance-bare.git"
    init_bare_remote(governance_remote)
    governance = tmp_path / "governance"
    clone_governance(governance_remote, governance)

    workspace = tmp_path / "workspace"
    target_root = workspace / "TargetProjects"
    registered_origin = tmp_path / "registered-origin.git"
    untracked_origin = tmp_path / "untracked-origin.git"
    init_bare_remote(registered_origin)
    init_bare_remote(untracked_origin)
    init_work_repo(target_root / "registered-repo", registered_origin)
    init_work_repo(target_root / "untracked-repo", untracked_origin)
    initial_head = commit_and_push_initial_inventory(
        governance,
        [
            {
                "name": "registered-repo",
                "remote_url": str(registered_origin),
                "local_path": "TargetProjects/registered-repo",
            }
        ],
    )

    result = orchestrate_discover(governance, target_root)

    new_head = run_git(["--git-dir", str(governance_remote), "rev-parse", "main"]).stdout.strip()
    diff_files = run_git(["diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], cwd=governance).stdout.splitlines()
    message = run_git(["log", "-1", "--pretty=%s"], cwd=governance).stdout.strip()

    assert result["added_entries"] == ["untracked-repo"]
    assert result["pre_hash"] != result["post_hash"]
    assert result["committed"] is True
    assert new_head != initial_head
    assert "repo-inventory.yaml" in diff_files
    assert message == COMMIT_MESSAGE


def test_integration_no_commit_on_noop(tmp_path: Path):
    governance_remote = tmp_path / "governance-bare.git"
    init_bare_remote(governance_remote)
    governance = tmp_path / "governance"
    clone_governance(governance_remote, governance)

    workspace = tmp_path / "workspace"
    target_root = workspace / "TargetProjects"
    synced_origin = tmp_path / "synced-origin.git"
    init_bare_remote(synced_origin)
    init_work_repo(target_root / "synced-repo", synced_origin)
    initial_head = commit_and_push_initial_inventory(
        governance,
        [
            {
                "name": "synced-repo",
                "remote_url": str(synced_origin),
                "local_path": "TargetProjects/synced-repo",
            }
        ],
    )

    result = orchestrate_discover(governance, target_root)
    final_head = run_git(["--git-dir", str(governance_remote), "rev-parse", "main"]).stdout.strip()

    assert result["scan"]["summary"]["missing_from_disk"] == 0
    assert result["scan"]["summary"]["untracked"] == 0
    assert result["added_entries"] == []
    assert result["pre_hash"] == result["post_hash"]
    assert result["committed"] is False
    assert final_head == initial_head