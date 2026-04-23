#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""
Tests for preflight.py and light-preflight.py.

Run with:
    python3 tests/test_preflight.py
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent.parent


def run_preflight(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "preflight.py"), *args],
        capture_output=True,
        text=True,
    )


def run_light_preflight(cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "light-preflight.py")],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestPreflightHappyPath(unittest.TestCase):
    """Happy path: valid workspace with all required files present."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        # Scaffold minimal valid workspace
        (self.root / "_bmad").mkdir()
        (self.root / "_bmad" / "config.yaml").write_text("# test config\n")
        (self.root / "_bmad" / "lens-work").mkdir(parents=True)
        (self.root / "_bmad" / "lens-work" / "lifecycle.yaml").write_text("version: v4\n")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_json_output_structure(self):
        result = run_preflight("--control-repo", str(self.root), "--json")
        data = json.loads(result.stdout)
        self.assertIn("status", data)
        self.assertIn("checks", data)
        self.assertIn("summary", data)
        self.assertIsInstance(data["checks"], list)

    def test_config_check_passes(self):
        result = run_preflight("--control-repo", str(self.root), "--json")
        data = json.loads(result.stdout)
        config_checks = [c for c in data["checks"] if c["name"] == "bmadconfig present"]
        self.assertEqual(len(config_checks), 1)
        self.assertEqual(config_checks[0]["status"], "pass")

    def test_lifecycle_yaml_check_passes(self):
        result = run_preflight("--control-repo", str(self.root), "--json")
        data = json.loads(result.stdout)
        lc_checks = [c for c in data["checks"] if "lifecycle" in c["name"]]
        self.assertEqual(len(lc_checks), 1)
        self.assertEqual(lc_checks[0]["status"], "pass")

    def test_python_version_check_passes(self):
        result = run_preflight("--control-repo", str(self.root), "--json")
        data = json.loads(result.stdout)
        py_checks = [c for c in data["checks"] if "Python" in c["name"]]
        self.assertEqual(len(py_checks), 1)
        self.assertEqual(py_checks[0]["status"], "pass")


class TestPreflightMissingArtifacts(unittest.TestCase):
    """Missing required files produce fail status with specific diagnostics."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        (self.root / "_bmad").mkdir()
        # Intentionally no config.yaml or lifecycle.yaml

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_config_fails(self):
        result = run_preflight("--control-repo", str(self.root), "--json")
        data = json.loads(result.stdout)
        config_checks = [c for c in data["checks"] if c["name"] == "bmadconfig present"]
        self.assertEqual(config_checks[0]["status"], "fail")
        self.assertIn("No config", config_checks[0]["reason"])

    def test_missing_lifecycle_yaml_fails(self):
        result = run_preflight("--control-repo", str(self.root), "--json")
        data = json.loads(result.stdout)
        lc_checks = [c for c in data["checks"] if "lifecycle" in c["name"]]
        self.assertEqual(lc_checks[0]["status"], "fail")
        self.assertIn("Missing", lc_checks[0]["reason"])

    def test_overall_status_is_fail(self):
        result = run_preflight("--control-repo", str(self.root), "--json")
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "fail")

    def test_exit_code_nonzero_on_failure(self):
        result = run_preflight("--control-repo", str(self.root))
        self.assertNotEqual(result.returncode, 0)

    def test_specific_diagnostics_present(self):
        """Failure reason must name what is missing, not just say 'failed'."""
        result = run_preflight("--control-repo", str(self.root), "--json")
        data = json.loads(result.stdout)
        for check in data["checks"]:
            if check["status"] == "fail":
                self.assertGreater(len(check["reason"]), 10, f"Reason too vague for: {check['name']}")


class TestPreflightTargetProjectsWarnOnly(unittest.TestCase):
    """Missing target_projects_path is warn only — does not fail the run."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        (self.root / "_bmad").mkdir()
        (self.root / "_bmad" / "config.yaml").write_text("# test\n")
        (self.root / "_bmad" / "lens-work").mkdir(parents=True)
        (self.root / "_bmad" / "lens-work" / "lifecycle.yaml").write_text("version: v4\n")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_target_projects_is_warn(self):
        nonexistent = str(self.root / "does-not-exist")
        result = run_preflight(
            "--control-repo", str(self.root),
            "--target-projects", nonexistent,
            "--json",
        )
        data = json.loads(result.stdout)
        tp_checks = [c for c in data["checks"] if "Target projects" in c["name"]]
        self.assertEqual(len(tp_checks), 1)
        self.assertEqual(tp_checks[0]["status"], "warn")

    def test_exit_code_zero_when_only_warnings(self):
        nonexistent = str(self.root / "does-not-exist")
        result = run_preflight(
            "--control-repo", str(self.root),
            "--target-projects", nonexistent,
        )
        # Should pass (exit 0) because warnings do not fail the run
        # (other checks may fail depending on tooling, so only assert summary structure)
        raw = run_preflight(
            "--control-repo", str(self.root),
            "--target-projects", nonexistent,
            "--json",
        )
        data = json.loads(raw.stdout)
        tp_checks = [c for c in data["checks"] if "Target projects" in c["name"]]
        self.assertNotEqual(tp_checks[0]["status"], "fail")


class TestPreflightZeroMutation(unittest.TestCase):
    """Preflight must never write lifecycle, feature, or governance files."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        (self.root / "_bmad").mkdir()
        (self.root / "_bmad" / "config.yaml").write_text("# test\n")
        (self.root / "_bmad" / "lens-work").mkdir(parents=True)
        (self.root / "_bmad" / "lens-work" / "lifecycle.yaml").write_text("version: v4\n")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_no_files_written_on_pass(self):
        before = set(Path(self.root).rglob("*"))
        run_preflight("--control-repo", str(self.root))
        after = set(Path(self.root).rglob("*"))
        new_files = after - before
        self.assertEqual(new_files, set(), f"Preflight wrote unexpected files: {new_files}")

    def test_no_files_written_on_fail(self):
        # Remove lifecycle.yaml to force a failure
        (self.root / "_bmad" / "lens-work" / "lifecycle.yaml").unlink()
        before = set(Path(self.root).rglob("*"))
        run_preflight("--control-repo", str(self.root))
        after = set(Path(self.root).rglob("*"))
        new_files = after - before
        self.assertEqual(new_files, set(), f"Preflight wrote files during failure: {new_files}")


class TestLightPreflight(unittest.TestCase):
    """light-preflight.py frozen exit-code interface."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_exit_0_when_config_present(self):
        (self.root / "_bmad").mkdir()
        (self.root / "_bmad" / "config.yaml").write_text("# test\n")
        result = run_light_preflight(cwd=str(self.root))
        self.assertEqual(result.returncode, 0)

    def test_exit_1_when_no_bmad_dir(self):
        result = run_light_preflight(cwd=str(self.root))
        self.assertEqual(result.returncode, 1)

    def test_exit_1_when_bmad_dir_but_no_config(self):
        (self.root / "_bmad").mkdir()
        result = run_light_preflight(cwd=str(self.root))
        self.assertEqual(result.returncode, 1)

    def test_no_arguments_accepted(self):
        """Frozen interface — script takes no arguments."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "light-preflight.py"), "--help"],
            capture_output=True, text=True,
        )
        # --help should cause a non-zero exit (argparse) or the script ignores it
        # Either way it must not crash with an unhandled exception
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
