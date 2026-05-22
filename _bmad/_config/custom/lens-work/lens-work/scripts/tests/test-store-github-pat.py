"""Tests for store-github-pat.py — subprocess-level tests only (no credential or filesystem access)."""
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "store-github-pat.py"


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

    def test_help_shows_export_flag(self):
        result = _run("--help")
        combined = result.stdout + result.stderr
        assert "--export" in combined


# NOTE: PAT storage via getpass.getpass() requires an interactive terminal.
# Never test this in CI — it will hang waiting for user input.
# TODO: Test GitHub host detection from repo-inventory.yaml in a temp dir
# TODO: Test --export flag generates correct eval-safe export commands
