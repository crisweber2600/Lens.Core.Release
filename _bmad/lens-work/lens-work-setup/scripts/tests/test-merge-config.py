# /// script
# requires-python = ">=3.9"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Tests for merge-config.py — anti-zombie config merge logic."""

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "merge-config.py"


def _load_merge_config():
    spec = importlib.util.spec_from_file_location("merge_config", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_merge_config()
merge_module_config = _mod.merge_module_config


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> dict:
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    return content if isinstance(content, dict) else {}


# ---------------------------------------------------------------------------
# Helpers via the public function
# ---------------------------------------------------------------------------

def make_module_yaml(tmp_path: Path, code: str = "lens", **extra) -> Path:
    data = {"code": code, "name": "Lens Workbench", "module_version": "1.0.0", "type": "standalone", **extra}
    p = tmp_path / "module.yaml"
    write_yaml(p, data)
    return p


def make_target_config(tmp_path: Path, content: dict) -> Path:
    p = tmp_path / "manifest.yaml"
    write_yaml(p, content)
    return p


# ---------------------------------------------------------------------------
# merge_module_config — list-shaped modules
# ---------------------------------------------------------------------------

class TestListShapedModules:
    def test_adds_entry_when_no_modules_key(self, tmp_path):
        m = make_module_yaml(tmp_path)
        t = make_target_config(tmp_path, {"project": "myproject"})
        merge_module_config(m, t)
        result = read_yaml(t)
        assert isinstance(result["modules"], list)
        codes = [e["code"] for e in result["modules"]]
        assert "lens" in codes

    def test_anti_zombie_removes_existing_entry(self, tmp_path):
        m = make_module_yaml(tmp_path, module_version="2.0.0")
        old_entry = {"code": "lens", "name": "Old Lens", "module_version": "1.0.0", "type": "standalone", "description": "old"}
        t = make_target_config(tmp_path, {"modules": [old_entry, {"code": "other", "name": "Other"}]})
        merge_module_config(m, t)
        result = read_yaml(t)
        modules = result["modules"]
        lens_entries = [e for e in modules if e.get("code") == "lens"]
        assert len(lens_entries) == 1, "Should have exactly one lens entry after anti-zombie"
        assert lens_entries[0]["module_version"] == "2.0.0"
        # Other module is preserved
        assert any(e.get("code") == "other" for e in modules)

    def test_adds_entry_to_empty_list(self, tmp_path):
        m = make_module_yaml(tmp_path)
        t = make_target_config(tmp_path, {"modules": []})
        merge_module_config(m, t)
        result = read_yaml(t)
        assert len(result["modules"]) == 1
        assert result["modules"][0]["code"] == "lens"


# ---------------------------------------------------------------------------
# merge_module_config — dict-shaped modules
# ---------------------------------------------------------------------------

class TestDictShapedModules:
    def test_adds_entry_when_modules_is_dict(self, tmp_path):
        m = make_module_yaml(tmp_path)
        t = make_target_config(tmp_path, {"modules": {"other": {"name": "Other"}}})
        merge_module_config(m, t)
        result = read_yaml(t)
        assert isinstance(result["modules"], dict)
        assert "lens" in result["modules"]
        assert result["modules"]["lens"]["code"] == "lens"

    def test_anti_zombie_removes_existing_dict_entry(self, tmp_path):
        m = make_module_yaml(tmp_path, module_version="2.0.0")
        t = make_target_config(tmp_path, {
            "modules": {
                "lens": {"code": "lens", "module_version": "1.0.0"},
                "other": {"name": "Other"},
            }
        })
        merge_module_config(m, t)
        result = read_yaml(t)
        assert result["modules"]["lens"]["module_version"] == "2.0.0"
        assert "other" in result["modules"]

    def test_empty_dict_modules(self, tmp_path):
        m = make_module_yaml(tmp_path)
        t = make_target_config(tmp_path, {"modules": {}})
        merge_module_config(m, t)
        result = read_yaml(t)
        assert "lens" in result["modules"]


# ---------------------------------------------------------------------------
# merge_module_config — invalid/unexpected shapes
# ---------------------------------------------------------------------------

class TestInvalidModulesShapes:
    def test_modules_is_null_treated_as_list(self, tmp_path):
        """modules: null in YAML should be normalized to a list."""
        m = make_module_yaml(tmp_path)
        t = make_target_config(tmp_path, {"modules": None})
        merge_module_config(m, t)
        result = read_yaml(t)
        assert isinstance(result["modules"], list)
        assert any(e.get("code") == "lens" for e in result["modules"])

    def test_modules_is_string_normalized_to_list(self, tmp_path):
        """modules: some-string should be normalized to a list."""
        m = make_module_yaml(tmp_path)
        # Write raw YAML with modules as a string
        t = tmp_path / "manifest.yaml"
        t.write_text("modules: some-invalid-string\n", encoding="utf-8")
        merge_module_config(m, t)
        result = read_yaml(t)
        assert isinstance(result["modules"], list)
        assert any(e.get("code") == "lens" for e in result["modules"])


# ---------------------------------------------------------------------------
# merge_module_config — empty/invalid YAML files
# ---------------------------------------------------------------------------

class TestEmptyOrInvalidYaml:
    def test_empty_target_config(self, tmp_path):
        """Empty target config file should be treated as {}."""
        m = make_module_yaml(tmp_path)
        t = tmp_path / "manifest.yaml"
        t.write_text("", encoding="utf-8")
        merge_module_config(m, t)
        result = read_yaml(t)
        assert "modules" in result

    def test_target_config_with_only_comments(self, tmp_path):
        """Target config with only YAML comments parses as None → {}."""
        m = make_module_yaml(tmp_path)
        t = tmp_path / "manifest.yaml"
        t.write_text("# just a comment\n", encoding="utf-8")
        merge_module_config(m, t)
        result = read_yaml(t)
        assert "modules" in result

    def test_module_yaml_empty_uses_defaults(self, tmp_path):
        """Empty module.yaml is normalized to {} and defaults are applied."""
        m = tmp_path / "module.yaml"
        m.write_text("", encoding="utf-8")
        t = make_target_config(tmp_path, {})
        # Should not raise — empty YAML is treated as {} and 'lens' code is defaulted
        merge_module_config(m, t)
        result = read_yaml(t)
        assert "modules" in result
        assert any(e.get("code") == "lens" for e in result["modules"])

    def test_module_yaml_non_dict_exits(self, tmp_path):
        """Non-dict module.yaml (e.g. a bare list) should cause sys.exit(1)."""
        m = tmp_path / "module.yaml"
        m.write_text("- item1\n- item2\n", encoding="utf-8")
        t = make_target_config(tmp_path, {})
        with pytest.raises(SystemExit) as exc_info:
            merge_module_config(m, t)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Entry field completeness
# ---------------------------------------------------------------------------

class TestEntryFields:
    def test_entry_contains_required_fields(self, tmp_path):
        m = make_module_yaml(tmp_path, description="Test module")
        t = make_target_config(tmp_path, {})
        merge_module_config(m, t)
        result = read_yaml(t)
        entry = result["modules"][0]
        for field in ("code", "name", "module_version", "type", "description"):
            assert field in entry, f"Missing field: {field}"

    def test_module_version_fallback_to_version(self, tmp_path):
        """Falls back to 'version' key when 'module_version' is absent."""
        m = tmp_path / "module.yaml"
        write_yaml(m, {"code": "lens", "name": "Lens", "version": "3.0.0", "type": "standalone", "description": ""})
        t = make_target_config(tmp_path, {})
        merge_module_config(m, t)
        result = read_yaml(t)
        entry = result["modules"][0]
        assert entry["module_version"] == "3.0.0"
