import importlib.util
import unittest
from pathlib import Path


def load_script(name: str):
    try:
        import yaml  # noqa: F401
    except ImportError as exc:
        raise unittest.SkipTest("PyYAML is not installed") from exc

    script_path = Path(__file__).resolve().parents[1] / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MergeConfigTests(unittest.TestCase):
    def test_templates_and_user_settings(self):
        module = load_script("merge-config.py")
        module_yaml = {
            "code": "lens",
            "name": "Lens",
            "description": "desc",
            "feature_archive_path": {
                "result": "{project-root}/{value}",
                "user_setting": False,
            },
            "personal_choice": {
                "user_setting": True,
            },
        }
        answers = {
            "core": {
                "user_name": "Cris",
                "communication_language": "English",
                "output_folder": "{project-root}/_bmad-output",
            },
            "module": {
                "feature_archive_path": "docs/features",
                "personal_choice": "mine",
            },
        }

        transformed = module.apply_result_templates(module_yaml, answers["module"])
        self.assertEqual(
            transformed["feature_archive_path"], "{project-root}/docs/features"
        )
        self.assertEqual(transformed["personal_choice"], "mine")

        user_settings = module.extract_user_settings(module_yaml, answers)
        self.assertEqual(user_settings["user_name"], "Cris")
        self.assertEqual(user_settings["communication_language"], "English")
        self.assertEqual(user_settings["personal_choice"], "mine")


if __name__ == "__main__":
    unittest.main()

