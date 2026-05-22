"""Tests for preflight.py."""
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "preflight.py"


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


def _write_hash_manifest(workspace: Path, entries: dict[str, str]) -> None:
    manifest = workspace / ".lens/personal/.github-hashes"
    lines = []

    for rel_path, content in sorted(entries.items()):
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        lines.append(f"{digest}  {rel_path}")

    _write_file(manifest, "\n".join(lines) + ("\n" if lines else ""))


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


def _init_governance_git_repo(workspace: Path, name: str = "lens-governance") -> tuple[Path, Path]:
    remote = workspace / f"{name}-remote.git"
    worktree = workspace / "TargetProjects" / "lens" / name

    _git(["init", "--bare", "--initial-branch=main", str(remote)])
    _git(["clone", str(remote), str(worktree)])
    _git(["config", "user.name", "Test User"], cwd=worktree)
    _git(["config", "user.email", "test@example.com"], cwd=worktree)

    (worktree / "README.md").write_text("seed\n", encoding="utf-8")
    _git(["add", "README.md"], cwd=worktree)
    _git(["commit", "-m", "seed"], cwd=worktree)
    _git(["push", "-u", "origin", "main"], cwd=worktree)

    return worktree, remote


def _write_governance_setup(workspace: Path, governance_repo: Path, remote: Path) -> None:
    _write_file(
        workspace / ".lens/governance-setup.yaml",
        (
            f'governance_repo_path: "{governance_repo.relative_to(workspace).as_posix()}"\n'
            f'governance_remote_url: "{remote}"\n'
        ),
    )


def _remote_main_sha(remote: Path) -> str:
    output = _git(["ls-remote", str(remote), "refs/heads/main"])
    return output.split()[0]


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    _write_file(root / ".lens/LENS_VERSION", "4\n")
    _write_file(root / "lens.core/_bmad/lens-work/lifecycle.yaml", "schema_version: 4\n")
    _write_file(
        root / ".lens/personal/.preflight-timestamp",
        datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    return root


class TestHelpFlag:
    def test_help_exits_zero(self):
        result = _run("--help")
        assert result.returncode == 0, f"--help should exit 0\nstdout: {result.stdout}\nstderr: {result.stderr}"

    def test_help_contains_usage(self):
        result = _run("--help")
        combined = result.stdout + result.stderr
        assert "preflight" in combined.lower() or "usage" in combined.lower()


class TestArgumentParsing:
    def test_unknown_flag_exits_nonzero(self):
        result = _run("--unknown-arg-xyz")
        assert result.returncode != 0

    def test_skip_constitution_flag_accepted(self):
        # --skip-constitution is a valid flag; just verify it is recognized (may fail on env)
        result = _run("--skip-constitution", "--help")
        # --help should override and exit 0 even with additional flags
        assert result.returncode == 0

    def test_compat_trailing_dot_accepted(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        _write_hash_manifest(workspace, {})

        result = _run(".", cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr

    def test_source_root_cwd_resolves_workspace_root(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        _write_hash_manifest(workspace, {})
        source_root = workspace / "TargetProjects" / "lens.core" / "src" / "Lens.Core.Src"
        source_root.mkdir(parents=True, exist_ok=True)

        result = _run(cwd=source_root)

        assert result.returncode == 0, result.stdout + result.stderr


class TestGitHubSync:
    def test_prunes_manifest_tracked_stale_github_files(self, workspace: Path):
        keep_workflow = "name: keep\n"
        keep_prompt = "---\ndescription: keep\n---\n"

        _write_file(workspace / "lens.core/.github/workflows/keep.yml", keep_workflow)
        _write_file(workspace / "lens.core/.github/prompts/lens-keep.prompt.md", keep_prompt)
        _write_file(workspace / ".github/workflows/keep.yml", "name: old\n")
        _write_file(workspace / ".github/workflows/legacy/obsolete.yml", "name: obsolete\n")
        _write_file(workspace / ".github/prompts/lens-stale.prompt.md", "---\ndescription: stale\n---\n")
        _write_hash_manifest(
            workspace,
            {
                ".github/prompts/lens-stale.prompt.md": "---\ndescription: stale\n---\n",
                ".github/workflows/keep.yml": "name: old\n",
                ".github/workflows/legacy/obsolete.yml": "name: obsolete\n",
            },
        )

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (workspace / ".github/workflows/keep.yml").read_text(encoding="utf-8") == keep_workflow
        assert (workspace / ".github/prompts/lens-keep.prompt.md").read_text(encoding="utf-8") == keep_prompt
        assert not (workspace / ".github/workflows/legacy/obsolete.yml").exists()
        assert not (workspace / ".github/workflows/legacy").exists()
        assert not (workspace / ".github/prompts/lens-stale.prompt.md").exists()

        manifest_text = (workspace / ".lens/personal/.github-hashes").read_text(encoding="utf-8")
        assert ".github/workflows/legacy/obsolete.yml" not in manifest_text
        assert ".github/prompts/lens-stale.prompt.md" not in manifest_text
        assert ".github/workflows/keep.yml" in manifest_text
        assert ".github/prompts/lens-keep.prompt.md" in manifest_text

    def test_migrates_legacy_personal_state_when_lens_missing(self, tmp_path: Path):
        workspace = tmp_path / "workspace"
        _write_file(workspace / "LENS_VERSION", "4\n")
        _write_file(workspace / "lens.core/_bmad/lens-work/lifecycle.yaml", "schema_version: 4\n")
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        _write_file(workspace / ".github/lens/personal/profile.yaml", "experience_mode: lite\n")
        _write_file(
            workspace / ".github/lens/personal/.preflight-timestamp",
            datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (workspace / ".lens/personal/profile.yaml").read_text(encoding="utf-8") == "experience_mode: lite\n"
        assert (workspace / ".lens/LENS_VERSION").read_text(encoding="utf-8") == "4"
        assert not (workspace / ".github/lens/personal/profile.yaml").exists()

    def test_relocates_root_personal_state_into_personal_dir(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        _write_file(workspace / ".lens/profile.yaml", "experience_mode: lite\n")
        _write_file(workspace / ".lens/context.yaml", "domain: plugins\nservice: hermes\n")
        _write_file(workspace / ".lens/.github-hashes", "abc123  .github/workflows/keep.yml\n")
        _write_file(workspace / ".lens/.preflight-timestamp", datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        (workspace / ".lens/personal").mkdir(parents=True, exist_ok=True)

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (workspace / ".lens/personal/profile.yaml").read_text(encoding="utf-8") == "experience_mode: lite\n"
        assert (workspace / ".lens/personal/context.yaml").read_text(encoding="utf-8") == "domain: plugins\nservice: hermes\n"
        assert (workspace / ".lens/personal/.github-hashes").is_file()
        assert (workspace / ".lens/personal/.preflight-timestamp").is_file()
        assert not (workspace / ".lens/profile.yaml").exists()
        assert not (workspace / ".lens/context.yaml").exists()
        assert not (workspace / ".lens/.github-hashes").exists()
        assert not (workspace / ".lens/.preflight-timestamp").exists()
        assert (workspace / ".lens/LENS_VERSION").read_text(encoding="utf-8") == "4\n"

    def test_migrates_legacy_governance_setup_when_lens_copy_missing(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        governance_dir = workspace / "TargetProjects/lens/lens-governance"
        governance_dir.mkdir(parents=True, exist_ok=True)
        _write_file(
            workspace / "docs/lens-work/governance-setup.yaml",
            (
                '# Generated by setup-control-repo.py — 2026-04-16T00:00:00Z\n'
                'governance_repo_path: "TargetProjects/lens/lens-governance"\n'
                'governance_remote_url: "https://github.com/example/lens-governance.git"\n'
            ),
        )
        _write_hash_manifest(workspace, {})

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        active_setup = workspace / ".lens/governance-setup.yaml"
        assert active_setup.is_file()
        assert "TargetProjects/lens/lens-governance" in active_setup.read_text(encoding="utf-8")
        assert not (workspace / "docs/lens-work/governance-setup.yaml").exists()

    def test_migrates_legacy_personal_governance_setup_to_lens_root(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        governance_dir = workspace / "TargetProjects/lens/lens-governance"
        governance_dir.mkdir(parents=True, exist_ok=True)
        _write_file(
            workspace / ".lens/personal/governance-setup.yaml",
            (
                'governance_repo_path: "TargetProjects/lens/lens-governance"\n'
                'governance_remote_url: "https://github.com/example/lens-governance.git"\n'
            ),
        )
        _write_hash_manifest(workspace, {})

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        active_setup = workspace / ".lens/governance-setup.yaml"
        assert active_setup.is_file()
        assert "TargetProjects/lens/lens-governance" in active_setup.read_text(encoding="utf-8")
        assert not (workspace / ".lens/personal/governance-setup.yaml").exists()

    def test_resolves_governance_repo_from_lens_setup_file(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        _write_file(
            workspace / ".lens/governance-setup.yaml",
            'governance_repo_path: "TargetProjects/lens/missing-governance"\n',
        )
        _write_hash_manifest(workspace, {})

        result = _run(cwd=workspace)

        assert result.returncode == 1
        assert "Resolved governance repo from .lens/governance-setup.yaml" in result.stdout
        assert "Then run /new-project" in result.stdout

    def test_governance_sync_pulls_remote_main_even_with_fresh_timestamp(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        governance_repo, remote = _init_governance_git_repo(workspace)
        _write_governance_setup(workspace, governance_repo, remote)
        _write_hash_manifest(workspace, {})

        secondary = workspace / "governance-secondary"
        _git(["clone", str(remote), str(secondary)])
        _git(["config", "user.name", "Test User"], cwd=secondary)
        _git(["config", "user.email", "test@example.com"], cwd=secondary)
        (secondary / "REMOTE.md").write_text("remote\n", encoding="utf-8")
        _git(["add", "REMOTE.md"], cwd=secondary)
        _git(["commit", "-m", "remote update"], cwd=secondary)
        _git(["push", "origin", "main"], cwd=secondary)

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (governance_repo / "REMOTE.md").read_text(encoding="utf-8") == "remote\n"

    def test_governance_sync_pushes_local_main_even_with_fresh_timestamp(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        governance_repo, remote = _init_governance_git_repo(workspace)
        _write_governance_setup(workspace, governance_repo, remote)
        _write_hash_manifest(workspace, {})

        (governance_repo / "LOCAL.md").write_text("local\n", encoding="utf-8")
        _git(["add", "LOCAL.md"], cwd=governance_repo)
        _git(["commit", "-m", "local governance change"], cwd=governance_repo)

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert _remote_main_sha(remote) == _git(["rev-parse", "HEAD"], cwd=governance_repo)

    def test_governance_sync_warns_and_skips_dirty_worktree(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        governance_repo, remote = _init_governance_git_repo(workspace)
        _write_governance_setup(workspace, governance_repo, remote)
        _write_hash_manifest(workspace, {})
        remote_before = _remote_main_sha(remote)

        (governance_repo / "DIRTY.md").write_text("dirty\n", encoding="utf-8")

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Governance repo sync skipped" in result.stdout
        assert "local changes present" in result.stdout
        assert _remote_main_sha(remote) == remote_before

    def test_preserves_untracked_non_prompt_github_files(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        _write_file(workspace / ".github/local/custom.yml", "name: custom\n")
        _write_hash_manifest(workspace, {})

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (workspace / ".github/local/custom.yml").read_text(encoding="utf-8") == "name: custom\n"

    def test_prompt_hygiene_removes_untracked_prompt_files(self, workspace: Path):
        keep_prompt = "---\ndescription: keep\n---\n"

        _write_file(workspace / "lens.core/.github/prompts/lens-keep.prompt.md", keep_prompt)
        _write_file(workspace / ".github/prompts/lens-stale.prompt.md", "---\ndescription: stale\n---\n")
        _write_file(workspace / ".github/prompts/custom.prompt.md", "---\ndescription: custom\n---\n")
        _write_hash_manifest(workspace, {})

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (workspace / ".github/prompts/lens-keep.prompt.md").read_text(encoding="utf-8") == keep_prompt
        assert not (workspace / ".github/prompts/lens-stale.prompt.md").exists()
        assert not (workspace / ".github/prompts/custom.prompt.md").exists()

    def test_prompt_hygiene_removes_stale_len_prompt_files(self, workspace: Path):
        keep_prompt = "---\ndescription: keep\n---\n"

        _write_file(workspace / "lens.core/.github/prompts/len-keep.prompt.md", keep_prompt)
        _write_file(workspace / ".github/prompts/len-stale.prompt.md", "---\ndescription: stale\n---\n")
        _write_hash_manifest(workspace, {})

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (workspace / ".github/prompts/len-keep.prompt.md").read_text(encoding="utf-8") == keep_prompt
        assert not (workspace / ".github/prompts/len-stale.prompt.md").exists()

    def test_prompt_hygiene_keeps_release_tracked_len_prompt_files(self, workspace: Path):
        keep_prompt = "---\ndescription: keep\n---\n"

        _write_file(workspace / "lens.core/.github/prompts/len-keep.prompt.md", keep_prompt)
        _write_file(workspace / ".github/prompts/len-keep.prompt.md", "---\ndescription: old\n---\n")
        _write_hash_manifest(workspace, {})

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (workspace / ".github/prompts/len-keep.prompt.md").read_text(encoding="utf-8") == keep_prompt

    def test_removes_stale_managed_non_prompt_github_files(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        _write_file(workspace / ".github/instructions/lens-legacy.instructions.md", "legacy\n")
        _write_file(workspace / ".github/instructions/len-legacy.instructions.md", "legacy\n")
        _write_hash_manifest(workspace, {})

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert not (workspace / ".github/instructions/lens-legacy.instructions.md").exists()
        assert not (workspace / ".github/instructions/len-legacy.instructions.md").exists()

    def test_keeps_release_tracked_managed_non_prompt_github_files(self, workspace: Path):
        keep_contents = "active\n"
        _write_file(workspace / "lens.core/.github/instructions/lens-keep.instructions.md", keep_contents)
        _write_file(workspace / ".github/instructions/lens-keep.instructions.md", "old\n")
        _write_hash_manifest(workspace, {})

        result = _run(cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (workspace / ".github/instructions/lens-keep.instructions.md").read_text(encoding="utf-8") == keep_contents

    def test_onboard_caller_prints_dev_next_steps(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        _write_file(workspace / ".lens/personal/profile.yaml", "primary_role: dev\n")
        _write_hash_manifest(workspace, {})

        result = _run("--caller", "onboard", cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "[onboard] Next steps:" in result.stdout
        assert "Use /switch to load the feature you want to work on." in result.stdout
        assert "Then use /dev to continue implementation for that feature." in result.stdout
        assert "Use /next anytime to get the recommended next command for the current context." in result.stdout

    def test_onboard_caller_prints_non_dev_next_steps(self, workspace: Path):
        _write_file(workspace / "lens.core/.github/workflows/keep.yml", "name: keep\n")
        _write_file(workspace / ".lens/personal/profile.yaml", "primary_role: planner\n")
        _write_hash_manifest(workspace, {})

        result = _run("--caller", "onboard", cwd=workspace)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "[onboard] Next steps:" in result.stdout
        assert "Use /switch to continue existing work." in result.stdout
        assert "Use /new-* to create new work." in result.stdout
        assert "Use /next anytime to get the recommended next command for the current context." in result.stdout


# TODO: Test version comparison logic (requires monkeypatch or script refactor)
# TODO: Test TTL window calculation
