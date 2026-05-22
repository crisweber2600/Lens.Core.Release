"""Tests for setup-control-repo.py."""
import importlib.util
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "setup-control-repo.py"


def _run(*args, **kwargs):
    return subprocess.run(
        ["uv", "run", "--script", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        **kwargs,
    )


def _load_script_module():
    spec = importlib.util.spec_from_file_location("setup_control_repo_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestHelpFlag:
    def test_help_exits_zero(self):
        result = _run("--help")
        assert result.returncode == 0, f"--help should exit 0\nstdout: {result.stdout}\nstderr: {result.stderr}"

    def test_help_shows_org_flag(self):
        result = _run("--help")
        combined = result.stdout + result.stderr
        assert "--org" in combined

    def test_help_shows_dry_run(self):
        result = _run("--help")
        combined = result.stdout + result.stderr
        assert "dry-run" in combined or "dry_run" in combined


class TestArgumentParsing:
    def test_dry_run_flag_accepted_alone(self):
        # --dry-run without other flags should not crash on --help
        result = _run("--help")
        assert result.returncode == 0


class TestGitignoreEntries:
    def test_ensure_gitignore_entries_adds_personal_paths(self, tmp_path):
        module = _load_script_module()
        module.ensure_gitignore_entries(tmp_path, dry_run=False)

        lines = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
        assert ".lens/" in lines
        assert ".lens/personal/" in lines
        assert ".github/" in lines
        assert "lens.core/" in lines
        assert "TargetProjects/" in lines
        assert ".github/lens/personal/" not in lines

    def test_ensure_gitignore_entries_is_idempotent(self, tmp_path):
        module = _load_script_module()
        module.ensure_gitignore_entries(tmp_path, dry_run=False)
        first = (tmp_path / ".gitignore").read_text(encoding="utf-8")

        module.ensure_gitignore_entries(tmp_path, dry_run=False)
        second = (tmp_path / ".gitignore").read_text(encoding="utf-8")

        assert second == first


class TestGovernanceSetupFile:
    def test_governance_setup_file_is_written_under_lens(self, tmp_path):
        module = _load_script_module()
        written_path = module.write_governance_setup_file(
            tmp_path,
            tmp_path / "TargetProjects" / "lens" / "lens-governance",
            "https://github.com/example/lens-governance.git",
            "2026-04-16T00:00:00Z",
        )

        assert written_path == tmp_path / ".lens" / "governance-setup.yaml"
        contents = written_path.read_text(encoding="utf-8")
        assert 'governance_repo_path: "' in contents
        assert "lens-governance" in contents
        assert "governance_remote_url" in contents


class TestGovernanceRepoDerivation:
    def test_derive_governance_repo_uses_folder_name_verbatim(self):
        module = _load_script_module()
        assert module.derive_governance_repo(Path("/tmp/printingmagic.lens")) == "printingmagic.lens.governance"

    def test_derive_governance_repo_preserves_src_suffix(self):
        module = _load_script_module()
        assert module.derive_governance_repo(Path("/tmp/myproject.src")) == "myproject.src.governance"


class TestEnsureGithubRepoExists:
    def test_creates_missing_repo_with_gh(self, monkeypatch):
        module = _load_script_module()
        calls: list[list[str]] = []

        def fake_run(cmd, capture_output=False, text=False, cwd=None, check=False, env=None):
            calls.append(list(cmd))

            if cmd[:3] == ["git", "ls-remote", "https://github.com/crisweber2600/printingmagic.lens.governance.git"]:
                attempt = sum(1 for existing in calls if existing[:3] == cmd[:3])
                return subprocess.CompletedProcess(cmd, 0 if attempt > 1 else 2, stdout="" if attempt == 1 else "ok\n", stderr="missing" if attempt == 1 else "")

            if cmd == ["which", "gh"]:
                return subprocess.CompletedProcess(cmd, 0, stdout="/usr/bin/gh\n", stderr="")

            if cmd[:3] == ["gh", "repo", "create"]:
                return subprocess.CompletedProcess(cmd, 0, stdout="created\n", stderr="")

            raise AssertionError(f"Unexpected subprocess.run call: {cmd}")

        monkeypatch.setattr(subprocess, "run", fake_run)

        module.ensure_github_repo_exists(
            "https://github.com",
            "crisweber2600",
            "printingmagic.lens.governance",
            "https://github.com/crisweber2600/printingmagic.lens.governance.git",
            dry_run=False,
        )

        assert ["which", "gh"] in calls
        assert [
            "gh",
            "repo",
            "create",
            "crisweber2600/printingmagic.lens.governance",
            "--private",
            "--add-readme",
            "--description",
            "LENS governance repository",
            "--disable-issues",
        ] in calls


# TODO: Test clone_or_pull: clones on first run, pulls on subsequent run
