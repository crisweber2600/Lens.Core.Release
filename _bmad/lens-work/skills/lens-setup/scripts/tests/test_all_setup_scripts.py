import subprocess
import sys
import unittest
from pathlib import Path


class SetupScriptTestSuite(unittest.TestCase):
    def test_scanner_named_tests_run(self):
        tests_dir = Path(__file__).resolve().parent
        for test_file in [
            "test_cleanup-legacy.py",
            "test_merge-config.py",
            "test_merge-help-csv.py",
        ]:
            with self.subTest(test_file=test_file):
                result = subprocess.run(
                    [sys.executable, str(tests_dir / test_file)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
                )


if __name__ == "__main__":
    unittest.main()

