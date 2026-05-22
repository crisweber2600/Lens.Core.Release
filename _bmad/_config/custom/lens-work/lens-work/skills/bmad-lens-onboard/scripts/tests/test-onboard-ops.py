#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "onboard-ops.py"

PASS = 0
FAIL = 0


def assert_eq(label, got, expected):
    global PASS, FAIL
    if got == expected:
        print(f"  ✓ {label}")
        PASS += 1
    else:
        print(f"  ✗ {label}: expected {expected!r}, got {got!r}")
        FAIL += 1


def assert_true(label, condition):
    global PASS, FAIL
    if condition:
        print(f"  ✓ {label}")
        PASS += 1
    else:
        print(f"  ✗ {label}: condition was False")
        FAIL += 1


def run(args):
    return subprocess.run(
        ["python3", str(SCRIPT)] + args,
        capture_output=True,
        text=True,
    )


def parse(result):
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# preflight tests
# ---------------------------------------------------------------------------

def test_preflight_returns_json():
    print("\n[preflight]")
    tmp = tempfile.mkdtemp()
    shutil.rmtree(tmp)
    r = run(["preflight", "--governance-dir", tmp])
    data = parse(r)
    assert_true("returns status field", "status" in data)
    assert_true("returns checks field", "checks" in data)
    assert_true("checks is a list", isinstance(data["checks"], list))


def test_preflight_new_dir_ok():
    tmp = tempfile.mkdtemp()
    shutil.rmtree(tmp)
    r = run(["preflight", "--governance-dir", tmp])
    data = parse(r)
    dir_check = next((c for c in data["checks"] if c["name"] == "governance_dir"), None)
    assert_true("governance_dir check present", dir_check is not None)
    assert_eq("new dir is ok", dir_check["status"], "ok")


def test_preflight_existing_dir_warns():
    tmp = tempfile.mkdtemp()
    # make it non-empty
    (Path(tmp) / "somefile.txt").write_text("x")
    try:
        r = run(["preflight", "--governance-dir", tmp])
        data = parse(r)
        dir_check = next((c for c in data["checks"] if c["name"] == "governance_dir"), None)
        assert_true("governance_dir check present", dir_check is not None)
        assert_eq("existing non-empty dir warns", dir_check["status"], "warn")
        assert_eq("overall status is warn", data["status"], "warn")
    finally:
        shutil.rmtree(tmp)


def test_preflight_missing_governance_dir():
    r = run(["preflight"])
    assert_eq("missing --governance-dir exits 1", r.returncode, 1)


def test_preflight_has_git_check():
    tmp = tempfile.mkdtemp()
    shutil.rmtree(tmp)
    r = run(["preflight", "--governance-dir", tmp])
    data = parse(r)
    git_check = next((c for c in data["checks"] if c["name"] == "git"), None)
    assert_true("git check present", git_check is not None)
    assert_true("git check has status", "status" in (git_check or {}))


def test_preflight_has_python_check():
    tmp = tempfile.mkdtemp()
    shutil.rmtree(tmp)
    r = run(["preflight", "--governance-dir", tmp])
    data = parse(r)
    py_check = next((c for c in data["checks"] if c["name"] == "python"), None)
    assert_true("python check present", py_check is not None)
    assert_eq("python check passes", (py_check or {}).get("status"), "ok")


# ---------------------------------------------------------------------------
# scaffold tests
# ---------------------------------------------------------------------------

def test_scaffold_dry_run():
    print("\n[scaffold]")
    tmp = tempfile.mkdtemp()
    shutil.rmtree(tmp)
    r = run(["scaffold", "--governance-dir", tmp, "--owner", "testuser", "--dry-run"])
    assert_eq("dry-run exits 0", r.returncode, 0)
    data = parse(r)
    assert_eq("dry_run flag in output", data.get("dry_run"), True)
    assert_true("created list present", "created" in data)
    assert_true("no dir created", not Path(tmp).exists())


def test_scaffold_creates_structure():
    tmp = tempfile.mkdtemp()
    shutil.rmtree(tmp)
    try:
        r = run(["scaffold", "--governance-dir", tmp, "--owner", "cweber"])
        assert_eq("scaffold exits 0", r.returncode, 0)
        data = parse(r)
        assert_eq("status ok", data["status"], "ok")
        assert_true("features/ created", (Path(tmp) / "features").is_dir())
        assert_true("users/ created", (Path(tmp) / "users").is_dir())
        assert_true("feature-index.yaml created", (Path(tmp) / "feature-index.yaml").exists())
        assert_true("user profile created", (Path(tmp) / "users" / "cweber.md").exists())
    finally:
        shutil.rmtree(tmp)


def test_scaffold_feature_index_format():
    tmp = tempfile.mkdtemp()
    shutil.rmtree(tmp)
    try:
        run(["scaffold", "--governance-dir", tmp, "--owner", "cweber"])
        import yaml
        content = yaml.safe_load((Path(tmp) / "feature-index.yaml").read_text())
        assert_eq("version is '1'", content.get("version"), "1")
        assert_eq("features is empty list", content.get("features"), [])
    finally:
        shutil.rmtree(tmp)


def test_scaffold_existing_nonempty_dir_fails():
    tmp = tempfile.mkdtemp()
    (Path(tmp) / "existing.txt").write_text("x")
    try:
        r = run(["scaffold", "--governance-dir", tmp, "--owner", "cweber"])
        assert_eq("existing dir returns exit 1", r.returncode, 1)
        data = parse(r)
        assert_eq("status error", data["status"], "error")
    finally:
        shutil.rmtree(tmp)


def test_scaffold_missing_governance_dir():
    r = run(["scaffold", "--owner", "cweber"])
    assert_eq("missing --governance-dir exits 1", r.returncode, 1)


def test_scaffold_missing_owner():
    tmp = tempfile.mkdtemp()
    shutil.rmtree(tmp)
    r = run(["scaffold", "--governance-dir", tmp])
    assert_eq("missing --owner exits 1", r.returncode, 1)


def test_scaffold_created_list_has_expected_paths():
    tmp = tempfile.mkdtemp()
    shutil.rmtree(tmp)
    try:
        r = run(["scaffold", "--governance-dir", tmp, "--owner", "alice"])
        data = parse(r)
        assert_true("features/ in created", "features/" in data.get("created", []))
        assert_true("users/ in created", "users/" in data.get("created", []))
        assert_true("feature-index.yaml in created", "feature-index.yaml" in data.get("created", []))
    finally:
        shutil.rmtree(tmp)


def test_scaffold_path_traversal_rejected():
    r = run(["scaffold", "--governance-dir", "../evil-path", "--owner", "cweber"])
    assert_eq("path traversal exits 1", r.returncode, 1)
    data = parse(r)
    assert_true("error message mentions traversal", "traversal" in data.get("message", "").lower())


# ---------------------------------------------------------------------------
# write-config tests
# ---------------------------------------------------------------------------

def test_write_config_dry_run():
    print("\n[write-config]")
    tmp = tempfile.mkdtemp()
    try:
        r = run([
            "write-config",
            "--governance-dir", tmp,
            "--username", "cweber",
            "--dry-run",
        ])
        assert_eq("dry-run exits 0", r.returncode, 0)
        data = parse(r)
        assert_eq("dry_run flag in output", data.get("dry_run"), True)
        assert_true("files_written in output", "files_written" in data)
        # No actual files written
        assert_true("user profile not written", not (Path(tmp) / "users" / "cweber.md").exists())
    finally:
        shutil.rmtree(tmp)


def test_write_config_creates_user_profile():
    tmp = tempfile.mkdtemp()
    try:
        r = run([
            "write-config",
            "--governance-dir", tmp,
            "--username", "cweber",
            "--default-ide", "vscode",
        ])
        assert_eq("exits 0", r.returncode, 0)
        profile = Path(tmp) / "users" / "cweber.md"
        assert_true("user profile exists", profile.exists())
        content = profile.read_text()
        assert_true("contains username", "cweber" in content)
        assert_true("contains ide", "vscode" in content)
    finally:
        shutil.rmtree(tmp)


def test_write_config_creates_config_yaml():
    tmp = tempfile.mkdtemp()
    try:
        r = run([
            "write-config",
            "--governance-dir", tmp,
            "--username", "cweber",
            "--github-pat", "ghp_abc123",
        ])
        assert_eq("exits 0", r.returncode, 0)
        config = Path(tmp) / "_bmad" / "config.user.yaml"
        assert_true("config.user.yaml exists", config.exists())
        content = config.read_text()
        assert_true("contains github_pat", "ghp_abc123" in content)
    finally:
        shutil.rmtree(tmp)


def test_write_config_multiple_repos():
    tmp = tempfile.mkdtemp()
    try:
        r = run([
            "write-config",
            "--governance-dir", tmp,
            "--username", "cweber",
            "--target-repos", "https://github.com/org/repo1,https://github.com/org/repo2",
        ])
        assert_eq("exits 0", r.returncode, 0)
        profile = Path(tmp) / "users" / "cweber.md"
        content = profile.read_text()
        assert_true("repo1 in profile", "repo1" in content)
        assert_true("repo2 in profile", "repo2" in content)
    finally:
        shutil.rmtree(tmp)


def test_write_config_missing_governance_dir():
    r = run(["write-config", "--username", "cweber"])
    assert_eq("missing --governance-dir exits 1", r.returncode, 1)


def test_write_config_missing_username():
    tmp = tempfile.mkdtemp()
    try:
        r = run(["write-config", "--governance-dir", tmp])
        assert_eq("missing --username exits 1", r.returncode, 1)
    finally:
        shutil.rmtree(tmp)


def test_write_config_path_traversal_rejected():
    r = run(["write-config", "--governance-dir", "../evil", "--username", "cweber"])
    assert_eq("path traversal exits 1", r.returncode, 1)


def test_write_config_files_written_list():
    tmp = tempfile.mkdtemp()
    try:
        r = run([
            "write-config",
            "--governance-dir", tmp,
            "--username", "alice",
        ])
        data = parse(r)
        assert_true("files_written present", len(data.get("files_written", [])) == 2)
        assert_true("profile in files_written", any("alice.md" in f for f in data["files_written"]))
        assert_true("config in files_written", any("config.user.yaml" in f for f in data["files_written"]))
    finally:
        shutil.rmtree(tmp)


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_preflight_returns_json()
    test_preflight_new_dir_ok()
    test_preflight_existing_dir_warns()
    test_preflight_missing_governance_dir()
    test_preflight_has_git_check()
    test_preflight_has_python_check()

    test_scaffold_dry_run()
    test_scaffold_creates_structure()
    test_scaffold_feature_index_format()
    test_scaffold_existing_nonempty_dir_fails()
    test_scaffold_missing_governance_dir()
    test_scaffold_missing_owner()
    test_scaffold_created_list_has_expected_paths()
    test_scaffold_path_traversal_rejected()

    test_write_config_dry_run()
    test_write_config_creates_user_profile()
    test_write_config_creates_config_yaml()
    test_write_config_multiple_repos()
    test_write_config_missing_governance_dir()
    test_write_config_missing_username()
    test_write_config_path_traversal_rejected()
    test_write_config_files_written_list()

    print(f"\n{'=' * 40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(0 if FAIL == 0 else 1)
