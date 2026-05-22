"""Tests for create-pr.py — subprocess-level tests only (no git or network access)."""
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "create-pr.py"


def _run(*args, **kwargs):
    return subprocess.run(
        ["uv", "run", "--script", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        **kwargs,
    )


class TestHelpFlag:
    def test_help_exits_zero(self):
        result = _run("--help")
        assert result.returncode == 0, f"--help should exit 0\nstdout: {result.stdout}\nstderr: {result.stderr}"

    def test_help_shows_source_branch(self):
        result = _run("--help")
        combined = result.stdout + result.stderr
        assert "source-branch" in combined or "source_branch" in combined


class TestArgumentParsing:
    def test_missing_required_args_exits_nonzero(self):
        result = _run()
        assert result.returncode != 0

    def test_url_only_flag_accepted(self):
        result = _run("--help")
        combined = result.stdout + result.stderr
        assert "url-only" in combined or "url_only" in combined


# TODO: Test parse_remote_url for GitHub HTTPS, SSH, and AzDO URLs
# TODO: Test PAT resolution order (env var → profile.yaml → fallback)
# TODO: Test HTTP 422 conflict path (PR already exists)
