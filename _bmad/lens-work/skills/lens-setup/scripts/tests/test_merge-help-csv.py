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


class MergeHelpCsvTests(unittest.TestCase):
    def test_filter_and_roundtrip_rows(self):
        module = load_script("merge-help-csv.py")
        rows = [
            ["Lens", "lens-map-audit", "Audit", "MA"],
            ["Other", "other-skill", "Other", "OT"],
        ]

        self.assertEqual(module.extract_module_codes(rows), {"Lens", "Other"})
        self.assertEqual(module.filter_rows(rows, "Lens"), [rows[1]])

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "module-help.csv"
            module.write_csv(str(target), ["module", "skill", "display-name", "menu-code"], rows)
            header, loaded = module.read_csv_rows(str(target))
            self.assertEqual(header, ["module", "skill", "display-name", "menu-code"])
            self.assertEqual(loaded, rows)


if __name__ == "__main__":
    unittest.main()

