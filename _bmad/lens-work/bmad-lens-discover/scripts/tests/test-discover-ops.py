import hashlib
import json
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "discover-ops.py"


def run_discover(args: list[str]) -> tuple[dict, int]:
    completed = subprocess.run(
        ["uv", "run", "--script", str(SCRIPT), *args, "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Non-JSON output\nstdout={completed.stdout}\nstderr={completed.stderr}") from exc
    return payload, completed.returncode


def run_scan(inventory_path: Path, target_root: Path) -> dict:
    payload, code = run_discover(
        ["scan", "--inventory-path", str(inventory_path), "--target-root", str(target_root)]
    )
    assert code == 0
    return payload


def run_add_entry(inventory_path: Path, name: str, remote_url: str, local_path: str) -> dict:
    payload, code = run_discover(
        [
            "add-entry",
            "--inventory-path",
            str(inventory_path),
            "--name",
            name,
            "--remote-url",
            remote_url,
            "--local-path",
            local_path,
        ]
    )
    assert code == 0
    return payload


def run_validate(inventory_path: Path) -> tuple[dict, int]:
    return run_discover(["validate", "--inventory-path", str(inventory_path)])


def mark_git_repo(path: Path) -> None:
    path.mkdir(parents=True)
    (path / ".git").mkdir()


def test_scan_reports_already_cloned_from_repositories_key(tmp_path: Path):
    workspace = tmp_path / "workspace"
    target_root = workspace / "TargetProjects"
    repo = target_root / "repo-a"
    mark_git_repo(repo)
    inventory = tmp_path / "repo-inventory.yaml"
    inventory.write_text(
        "repositories:\n"
        "  - name: repo-a\n"
        "    remote_url: https://github.com/org/repo-a\n"
        "    local_path: TargetProjects/repo-a\n",
        encoding="utf-8",
    )

    result = run_scan(inventory, target_root)

    assert result["summary"]["already_cloned"] == 1
    assert result["summary"]["missing_from_disk"] == 0
    assert result["summary"]["untracked"] == 0
    assert result["already_cloned"][0]["name"] == "repo-a"


def test_scan_accepts_legacy_repos_key_and_reports_untracked(tmp_path: Path):
    workspace = tmp_path / "workspace"
    target_root = workspace / "TargetProjects"
    tracked = target_root / "tracked"
    untracked = target_root / "untracked"
    mark_git_repo(tracked)
    mark_git_repo(untracked)
    inventory = tmp_path / "repo-inventory.yaml"
    inventory.write_text(
        "repos:\n"
        "  - name: tracked\n"
        "    remote_url: https://github.com/org/tracked\n"
        "    local_path: TargetProjects/tracked\n",
        encoding="utf-8",
    )

    result = run_scan(inventory, target_root)

    assert result["summary"] == {"missing_from_disk": 0, "untracked": 1, "already_cloned": 1}
    assert result["untracked"][0]["name"] == "untracked"


def test_scan_reports_missing_from_disk(tmp_path: Path):
    workspace = tmp_path / "workspace"
    target_root = workspace / "TargetProjects"
    target_root.mkdir(parents=True)
    inventory = tmp_path / "repo-inventory.yaml"
    inventory.write_text(
        "repos:\n"
        "  - name: my-repo\n"
        "    remote_url: https://github.com/org/my-repo\n"
        "    local_path: TargetProjects/my-repo\n",
        encoding="utf-8",
    )

    result = run_scan(inventory, target_root)

    assert result["summary"]["missing_from_disk"] == 1
    assert result["summary"]["already_cloned"] == 0
    assert result["summary"]["untracked"] == 0
    assert result["missing_from_disk"][0]["name"] == "my-repo"


def test_scan_matches_inventory_path_with_backslashes(tmp_path: Path):
    workspace = tmp_path / "workspace"
    target_root = workspace / "TargetProjects"
    repo = target_root / "nested" / "repo-a"
    mark_git_repo(repo)
    inventory = tmp_path / "repo-inventory.yaml"
    inventory.write_text(
        "repositories:\n"
        "  - name: repo-a\n"
        "    remote_url: https://github.com/org/repo-a\n"
        "    local_path: 'TargetProjects\\nested\\repo-a'\n",
        encoding="utf-8",
    )

    result = run_scan(inventory, target_root)

    assert result["summary"] == {"missing_from_disk": 0, "untracked": 0, "already_cloned": 1}
    assert result["already_cloned"][0]["local_path"] == "TargetProjects\\nested\\repo-a"


def test_scan_reports_untracked_repo_without_remote(tmp_path: Path):
    workspace = tmp_path / "workspace"
    target_root = workspace / "TargetProjects"
    repo = target_root / "local-only"
    mark_git_repo(repo)
    inventory = tmp_path / "repo-inventory.yaml"
    inventory.write_text("repositories: []\n", encoding="utf-8")

    result = run_scan(inventory, target_root)

    assert result["summary"] == {"missing_from_disk": 0, "untracked": 1, "already_cloned": 0}
    assert result["untracked"][0]["name"] == "local-only"
    assert "remote_url" not in result["untracked"][0]


def test_add_entry_creates_new_entry(tmp_path: Path):
    inventory = tmp_path / "repo-inventory.yaml"
    inventory.write_text("repos: []\n", encoding="utf-8")

    result = run_add_entry(
        inventory,
        "new-repo",
        "https://github.com/org/new-repo",
        "TargetProjects/new-repo",
    )

    assert result["added"] is True
    content = inventory.read_text(encoding="utf-8")
    assert "repositories:" in content
    assert "repos:" not in content
    assert "- name: new-repo" in content
    assert "remote_url: https://github.com/org/new-repo" in content
    assert "local_path: TargetProjects/new-repo" in content


def test_add_entry_is_idempotent_by_remote_url(tmp_path: Path):
    inventory = tmp_path / "repo-inventory.yaml"
    original = (
        "repos:\n"
        "  - name: existing-repo\n"
        "    remote_url: https://github.com/org/existing-repo\n"
        "    local_path: TargetProjects/existing-repo\n"
    )
    inventory.write_text(original, encoding="utf-8")

    result = run_add_entry(
        inventory,
        "renamed-repo",
        "https://github.com/org/existing-repo",
        "TargetProjects/renamed-repo",
    )

    assert result == {"added": False, "reason": "already_exists"}
    assert inventory.read_text(encoding="utf-8") == original


def test_validate_passes_well_formed_inventory(tmp_path: Path):
    inventory = tmp_path / "repo-inventory.yaml"
    inventory.write_text(
        "repos:\n"
        "  - name: repo-a\n"
        "    remote_url: https://github.com/org/repo-a\n"
        "  - name: repo-b\n"
        "    remote_url: https://github.com/org/repo-b\n",
        encoding="utf-8",
    )

    result, code = run_validate(inventory)

    assert code == 0
    assert result == {"valid": True, "errors": []}


def test_validate_fails_missing_name(tmp_path: Path):
    inventory = tmp_path / "repo-inventory.yaml"
    inventory.write_text(
        "repos:\n"
        "  - remote_url: https://github.com/org/repo-missing-name\n",
        encoding="utf-8",
    )

    result, code = run_validate(inventory)

    assert code == 1
    assert result["valid"] is False
    assert len(result["errors"]) == 1
    assert result["errors"][0]["index"] == 0
    assert "name" in result["errors"][0]["issue"]


def test_noop_run_produces_unchanged_hash(tmp_path: Path):
    workspace = tmp_path / "workspace"
    target_root = workspace / "TargetProjects"
    repo = target_root / "synced-repo"
    mark_git_repo(repo)
    inventory = tmp_path / "repo-inventory.yaml"
    inventory.write_text(
        "repos:\n"
        "  - name: synced-repo\n"
        "    remote_url: https://github.com/org/synced-repo\n"
        f"    local_path: {repo}\n",
        encoding="utf-8",
    )
    before = hashlib.sha256(inventory.read_bytes()).hexdigest()

    result = run_scan(inventory, target_root)
    after = hashlib.sha256(inventory.read_bytes()).hexdigest()

    assert result["summary"]["missing_from_disk"] == 0
    assert result["summary"]["untracked"] == 0
    assert before == after