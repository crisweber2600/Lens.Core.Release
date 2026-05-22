import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_script(name: str):
    script_path = Path(__file__).resolve().parents[1] / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CleanupLegacyTests(unittest.TestCase):
    def test_verify_and_cleanup_legacy_directories(self):
        module = load_script("cleanup-legacy.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bmad = root / "_bmad"
            installed = root / "skills"

            legacy_skill = bmad / "lens" / "lens-map-audit"
            legacy_skill.mkdir(parents=True)
            (legacy_skill / "SKILL.md").write_text("# skill\n", encoding="utf-8")
            (installed / "lens-map-audit").mkdir(parents=True)

            (bmad / "core").mkdir(parents=True)
            (bmad / "core" / "config.yaml").write_text("x: y\n", encoding="utf-8")
            (bmad / "_config").mkdir(parents=True)

            verified = module.verify_skills_installed(
                str(bmad), ["lens", "core", "_config"], str(installed)
            )
            self.assertEqual(verified, ["lens-map-audit"])

            removed, not_found, file_count = module.cleanup_directories(
                str(bmad), ["lens", "core", "_config", "missing"]
            )
            self.assertEqual(removed, ["lens", "core", "_config"])
            self.assertEqual(not_found, ["missing"])
            self.assertGreaterEqual(file_count, 2)


if __name__ == "__main__":
    unittest.main()

