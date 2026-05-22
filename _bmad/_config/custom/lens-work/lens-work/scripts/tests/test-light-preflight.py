"""Tests for light-preflight.py."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


SCRIPT = Path(__file__).parent.parent / "light-preflight.py"


def _run(*args, **kwargs):
    return subprocess.run(
        ["uv", "run", "--script", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        **kwargs,
    )


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed (cwd={cwd}): {(result.stderr or result.stdout).strip()}"
        )
    return result.stdout.strip()


def _remote_head_sha(remote: Path, branch: str) -> str:
    output = _git(["ls-remote", str(remote), f"refs/heads/{branch}"])
    return output.split()[0]


def _init_control_repo(workspace: Path, remote: Path, branch: str = "feature-sync") -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    _git(["init", "--bare", "--initial-branch", branch, str(remote)])
    _git(["init", "--initial-branch", branch], cwd=workspace)
    _git(["config", "user.name", "Test User"], cwd=workspace)
    _git(["config", "user.email", "test@example.com"], cwd=workspace)

    _write_file(workspace / ".gitignore", ".lens/\nlens.core/\nTargetProjects/\n")
    _write_file(workspace / "README.md", "workspace\n")
    _git(["add", ".gitignore", "README.md"], cwd=workspace)
    _git(["commit", "-m", "seed"], cwd=workspace)
    _git(["remote", "add", "origin", str(remote)], cwd=workspace)
    _git(["push", "-u", "origin", branch], cwd=workspace)

    _write_file(workspace / "lens.core/_bmad/lens-work/lifecycle.yaml", "schema_version: 4\n")


def _init_governance_repo(workspace: Path, remote: Path, name: str = "lens-governance") -> Path:
    repo = workspace / "TargetProjects" / "lens" / name

    _git(["init", "--bare", "--initial-branch", "main", str(remote)])
    _git(["clone", str(remote), str(repo)])
    _git(["config", "user.name", "Test User"], cwd=repo)
    _git(["config", "user.email", "test@example.com"], cwd=repo)

    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(["add", "README.md"], cwd=repo)
    _git(["commit", "-m", "seed"], cwd=repo)
    _git(["push", "-u", "origin", "main"], cwd=repo)

    return repo


def _write_governance_setup(workspace: Path, governance_repo: Path) -> None:
    _write_file(
        workspace / ".lens/governance-setup.yaml",
        f'governance_repo_path: "{governance_repo.relative_to(workspace).as_posix()}"\n',
    )


def _payload(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert result.stdout.strip(), f"expected JSON payload\nstdout: {result.stdout}\nstderr: {result.stderr}"
    return json.loads(result.stdout)


def _status_porcelain(repo: Path) -> str:
    return _git(["status", "--short"], cwd=repo)


def _secondary_clone(remote: Path, dest: Path) -> Path:
    _git(["clone", str(remote), str(dest)])
    _git(["config", "user.name", "Test User"], cwd=dest)
    _git(["config", "user.email", "test@example.com"], cwd=dest)
    return dest


def _write_bmadconfig_governance(workspace: Path, governance_repo: Path) -> None:
    """Write a minimal bmadconfig.yaml that points governance_repo_path at the test repo."""

    config_dir = workspace / "lens.core" / "_bmad" / "lens-work"
    config_dir.mkdir(parents=True, exist_ok=True)
    rel = governance_repo.relative_to(workspace).as_posix()
    (config_dir / "bmadconfig.yaml").write_text(
        f'governance_repo_path: "{{project-root}}/{rel}"\n',
        encoding="utf-8",
    )


def test_skips_when_fresh_timestamp(tmp_path: Path):
    workspace = tmp_path / "workspace"
    _init_control_repo(workspace, tmp_path / "control-remote.git")
    governance_repo = _init_governance_repo(workspace, tmp_path / "governance-remote.git")
    _write_governance_setup(workspace, governance_repo)
    _write_file(
        workspace / ".lens/personal/.light-preflight-timestamp",
        datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    result = _run("--json", cwd=workspace)
    payload = _payload(result)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["status"] == "cached"
    assert payload["ran_light_preflight"] is False


def test_fresh_cache_bypassed_when_governance_remote_has_new_commits(tmp_path: Path):
    workspace = tmp_path / "workspace"
    governance_remote = tmp_path / "governance-remote.git"

    _init_control_repo(workspace, tmp_path / "control-remote.git")
    governance_repo = _init_governance_repo(workspace, governance_remote)
    _write_governance_setup(workspace, governance_repo)

    # Simulate another contributor pushing to the governance remote.
    governance_secondary = _secondary_clone(governance_remote, tmp_path / "governance-secondary")
    _write_file(governance_secondary / "REMOTE-GOVERNANCE.md", "remote governance\n")
    _git(["add", "REMOTE-GOVERNANCE.md"], cwd=governance_secondary)
    _git(["commit", "-m", "remote governance update"], cwd=governance_secondary)
    _git(["push", "origin", "main"], cwd=governance_secondary)

    # Write a fresh cache timestamp so the classic behavior would short-circuit.
    _write_file(
        workspace / ".lens/personal/.light-preflight-timestamp",
        datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    result = _run("--json", cwd=workspace)
    payload = _payload(result)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["status"] == "passed", payload
    assert payload["ran_light_preflight"] is True
    assert (governance_repo / "REMOTE-GOVERNANCE.md").read_text(encoding="utf-8") == "remote governance\n"


def test_no_remote_probe_flag_honors_fresh_cache(tmp_path: Path):
    workspace = tmp_path / "workspace"
    governance_remote = tmp_path / "governance-remote.git"

    _init_control_repo(workspace, tmp_path / "control-remote.git")
    governance_repo = _init_governance_repo(workspace, governance_remote)
    _write_governance_setup(workspace, governance_repo)

    governance_secondary = _secondary_clone(governance_remote, tmp_path / "governance-secondary")
    _write_file(governance_secondary / "REMOTE-GOVERNANCE.md", "remote governance\n")
    _git(["add", "REMOTE-GOVERNANCE.md"], cwd=governance_secondary)
    _git(["commit", "-m", "remote governance update"], cwd=governance_secondary)
    _git(["push", "origin", "main"], cwd=governance_secondary)

    _write_file(
        workspace / ".lens/personal/.light-preflight-timestamp",
        datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    result = _run("--json", "--no-remote-probe", cwd=workspace)
    payload = _payload(result)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["status"] == "cached"
    assert payload["ran_light_preflight"] is False
    assert not (governance_repo / "REMOTE-GOVERNANCE.md").exists()


def test_governance_path_falls_back_to_bmadconfig(tmp_path: Path):
    """When .lens/governance-setup.yaml is absent, read governance_repo_path
    from lens.core/_bmad/lens-work/bmadconfig.yaml so the governance repo
    still gets synced."""

    workspace = tmp_path / "workspace"
    governance_remote = tmp_path / "governance-remote.git"

    _init_control_repo(workspace, tmp_path / "control-remote.git")
    governance_repo = _init_governance_repo(workspace, governance_remote)
    # Intentionally do NOT call _write_governance_setup — force the fallback.
    _write_bmadconfig_governance(workspace, governance_repo)

    # Another contributor advances the governance remote.
    governance_secondary = _secondary_clone(governance_remote, tmp_path / "governance-secondary")
    _write_file(governance_secondary / "REMOTE-GOVERNANCE.md", "remote governance\n")
    _git(["add", "REMOTE-GOVERNANCE.md"], cwd=governance_secondary)
    _git(["commit", "-m", "remote governance update"], cwd=governance_secondary)
    _git(["push", "origin", "main"], cwd=governance_secondary)

    result = _run("--json", "--force", cwd=workspace)
    payload = _payload(result)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["status"] == "passed", payload
    governance_result = payload["repos"][1]
    assert governance_result["status"] == "synced", payload
    assert governance_result["pulled"] is True, payload
    assert (governance_repo / "REMOTE-GOVERNANCE.md").read_text(encoding="utf-8") == "remote governance\n"


def test_accepts_compat_trailing_dot(tmp_path: Path):
    workspace = tmp_path / "workspace"
    _init_control_repo(workspace, tmp_path / "control-remote.git")
    governance_repo = _init_governance_repo(workspace, tmp_path / "governance-remote.git")
    _write_governance_setup(workspace, governance_repo)
    _write_file(
        workspace / ".lens/personal/.light-preflight-timestamp",
        datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    result = _run("--json", ".", cwd=workspace)
    payload = _payload(result)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["status"] == "cached"


def test_source_root_cwd_resolves_workspace_root(tmp_path: Path):
    workspace = tmp_path / "workspace"
    _init_control_repo(workspace, tmp_path / "control-remote.git")
    source_root = workspace / "TargetProjects" / "lens.core" / "src" / "Lens.Core.Src"
    source_root.mkdir(parents=True, exist_ok=True)

    result = _run("--json", cwd=source_root)
    payload = _payload(result)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["status"] == "passed"


def test_commits_dirty_control_repo_and_pushes(tmp_path: Path):
    workspace = tmp_path / "workspace"
    control_remote = tmp_path / "control-remote.git"

    _init_control_repo(workspace, control_remote)
    governance_repo = _init_governance_repo(workspace, tmp_path / "governance-remote.git")
    _write_governance_setup(workspace, governance_repo)
    _write_file(workspace / "LOCAL.md", "control\n")

    result = _run("--json", cwd=workspace)
    payload = _payload(result)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["status"] == "passed"
    assert _status_porcelain(workspace) == ""
    assert _git(["log", "-1", "--pretty=%s"], cwd=workspace) == "chore(lens): auto-commit control repo before light preflight sync"
    assert _remote_head_sha(control_remote, "feature-sync") == _git(["rev-parse", "HEAD"], cwd=workspace)


def test_commits_dirty_governance_repo_and_pushes(tmp_path: Path):
    workspace = tmp_path / "workspace"
    governance_remote = tmp_path / "governance-remote.git"

    _init_control_repo(workspace, tmp_path / "control-remote.git")
    governance_repo = _init_governance_repo(workspace, governance_remote)
    _write_governance_setup(workspace, governance_repo)
    _write_file(governance_repo / "LOCAL.md", "governance\n")

    result = _run("--json", cwd=workspace)
    payload = _payload(result)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["status"] == "passed"
    assert _status_porcelain(governance_repo) == ""
    assert _git(["log", "-1", "--pretty=%s"], cwd=governance_repo) == "chore(lens): auto-commit governance repo before light preflight sync"
    assert _remote_head_sha(governance_remote, "main") == _git(["rev-parse", "HEAD"], cwd=governance_repo)


def test_pulls_remote_updates_for_control_and_governance(tmp_path: Path):
    workspace = tmp_path / "workspace"
    control_remote = tmp_path / "control-remote.git"
    governance_remote = tmp_path / "governance-remote.git"

    _init_control_repo(workspace, control_remote)
    governance_repo = _init_governance_repo(workspace, governance_remote)
    _write_governance_setup(workspace, governance_repo)

    control_secondary = _secondary_clone(control_remote, tmp_path / "control-secondary")
    _write_file(control_secondary / "REMOTE-CONTROL.md", "remote control\n")
    _git(["add", "REMOTE-CONTROL.md"], cwd=control_secondary)
    _git(["commit", "-m", "remote control update"], cwd=control_secondary)
    _git(["push", "origin", "feature-sync"], cwd=control_secondary)

    governance_secondary = _secondary_clone(governance_remote, tmp_path / "governance-secondary")
    _write_file(governance_secondary / "REMOTE-GOVERNANCE.md", "remote governance\n")
    _git(["add", "REMOTE-GOVERNANCE.md"], cwd=governance_secondary)
    _git(["commit", "-m", "remote governance update"], cwd=governance_secondary)
    _git(["push", "origin", "main"], cwd=governance_secondary)

    result = _run("--json", cwd=workspace)
    payload = _payload(result)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["status"] == "passed"
    assert (workspace / "REMOTE-CONTROL.md").read_text(encoding="utf-8") == "remote control\n"
    assert (governance_repo / "REMOTE-GOVERNANCE.md").read_text(encoding="utf-8") == "remote governance\n"


def test_missing_governance_repo_is_a_soft_skip(tmp_path: Path):
    workspace = tmp_path / "workspace"
    _init_control_repo(workspace, tmp_path / "control-remote.git")
    _write_file(
        workspace / ".lens/governance-setup.yaml",
        'governance_repo_path: "TargetProjects/lens/missing-governance"\n',
    )

    result = _run("--json", cwd=workspace)
    payload = _payload(result)

    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["status"] == "passed"
    governance_result = payload["repos"][1]
    assert governance_result["status"] == "skipped"
    assert "missing directory" in governance_result["detail"]


def test_interrupted_control_repo_fails(tmp_path: Path):
    workspace = tmp_path / "workspace"
    _init_control_repo(workspace, tmp_path / "control-remote.git")
    governance_repo = _init_governance_repo(workspace, tmp_path / "governance-remote.git")
    _write_governance_setup(workspace, governance_repo)

    merge_head = _git(["rev-parse", "--git-path", "MERGE_HEAD"], cwd=workspace)
    _write_file(workspace / merge_head, "deadbeef\n")

    result = _run("--json", cwd=workspace)
    payload = _payload(result)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert "merge in progress" in str(payload["error"])