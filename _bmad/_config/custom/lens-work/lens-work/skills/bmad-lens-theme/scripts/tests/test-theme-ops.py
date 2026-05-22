#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "pytest"]
# ///
"""
Tests for theme-ops.py — list, load, easter-egg subcommands.
All tests use real temp directories and real theme files.
"""

import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).parent.parent / "theme-ops.py"
ASSETS_THEMES = Path(__file__).parent.parent.parent / "assets" / "themes"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(args: list[str], expect_code: int | None = None) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
    )
    if expect_code is not None:
        assert result.returncode == expect_code, (
            f"Expected exit {expect_code}, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return json.loads(result.stdout)


def write_theme(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


def minimal_theme(name: str = "test") -> dict:
    return {
        "name": name,
        "description": f"A test theme called {name}",
        "version": "1.0.0",
        "author": "Test",
        "personas": {
            "lens": {
                "name": "TestLens",
                "title": "Test Orchestrator",
                "communication_style": "Terse.",
                "flavor_phrases": ["Testing."],
            }
        },
        "easter_eggs": [],
    }


@pytest.fixture(scope="session")
def ops():
    spec = spec_from_file_location("theme_ops", SCRIPT)
    mod = module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture
def themes_dir(tmp_path: Path) -> Path:
    """Minimal themes dir with a default and a test theme."""
    d = tmp_path / "themes"
    d.mkdir()
    # Copy the real default theme from assets
    default_src = ASSETS_THEMES / "default.yaml"
    if default_src.exists():
        (d / "default.yaml").write_bytes(default_src.read_bytes())
    else:
        write_theme(d / "default.yaml", minimal_theme("default"))
    return d


@pytest.fixture
def full_themes_dir(tmp_path: Path) -> Path:
    """Themes dir with default + wh40k (real files from assets)."""
    d = tmp_path / "themes"
    d.mkdir()
    for name in ("default.yaml", "wh40k.yaml"):
        src = ASSETS_THEMES / name
        if src.exists():
            (d / name).write_bytes(src.read_bytes())
    return d


# ---------------------------------------------------------------------------
# Unit tests: helpers
# ---------------------------------------------------------------------------


class TestValidateSlug:
    def test_valid_slug(self, ops) -> None:
        err, code = ops._validate_slug("wh40k", "theme")
        assert err is None and code == 0

    def test_valid_slug_with_hyphens(self, ops) -> None:
        err, code = ops._validate_slug("my-theme", "theme")
        assert err is None and code == 0

    def test_valid_slug_with_underscores(self, ops) -> None:
        err, code = ops._validate_slug("my_theme", "theme")
        assert err is None and code == 0

    def test_empty_slug_rejected(self, ops) -> None:
        err, code = ops._validate_slug("", "theme")
        assert err is not None and code == 1

    def test_path_traversal_rejected(self, ops) -> None:
        err, code = ops._validate_slug("../../etc", "theme")
        assert err is not None and code == 1

    def test_slash_rejected(self, ops) -> None:
        err, code = ops._validate_slug("a/b", "theme")
        assert err is not None and code == 1


class TestReadThemeNameFromProfile:
    def test_reads_theme_name(self, ops, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        profile.write_text("# Profile\ntheme: wh40k\ntrack: full\n")
        assert ops._read_theme_name_from_profile(profile) == "wh40k"

    def test_missing_file_returns_none(self, ops, tmp_path: Path) -> None:
        assert ops._read_theme_name_from_profile(tmp_path / "missing.md") is None

    def test_no_theme_field_returns_none(self, ops, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        profile.write_text("# Profile\ntrack: full\n")
        assert ops._read_theme_name_from_profile(profile) is None

    def test_quoted_theme_name_stripped(self, ops, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        profile.write_text('theme: "wh40k"\n')
        assert ops._read_theme_name_from_profile(profile) == "wh40k"

    def test_single_quoted_theme_name_stripped(self, ops, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        profile.write_text("theme: 'wh40k'\n")
        assert ops._read_theme_name_from_profile(profile) == "wh40k"


# ---------------------------------------------------------------------------
# Integration tests: list subcommand
# ---------------------------------------------------------------------------


class TestList:
    def test_list_default_only(self, themes_dir: Path) -> None:
        out = run(["list", "--themes-dir", str(themes_dir)], expect_code=0)
        assert out["count"] >= 1
        names = [t["name"] for t in out["themes"]]
        assert "default" in names

    def test_list_includes_wh40k(self, full_themes_dir: Path) -> None:
        out = run(["list", "--themes-dir", str(full_themes_dir)], expect_code=0)
        names = [t["name"] for t in out["themes"]]
        assert "wh40k" in names

    def test_list_theme_has_required_fields(self, themes_dir: Path) -> None:
        out = run(["list", "--themes-dir", str(themes_dir)], expect_code=0)
        for theme in out["themes"]:
            for field in ("name", "description", "version", "author", "persona_count", "easter_egg_count", "file"):
                assert field in theme

    def test_list_missing_dir_returns_error(self, tmp_path: Path) -> None:
        out = run(["list", "--themes-dir", str(tmp_path / "nonexistent")], expect_code=1)
        assert out["error"] == "themes_dir_not_found"

    def test_list_corrupt_theme_produces_warning(self, themes_dir: Path) -> None:
        (themes_dir / "broken.yaml").write_text("---\n: [bad yaml\n")
        out = run(["list", "--themes-dir", str(themes_dir)], expect_code=0)
        warnings = out.get("warnings", [])
        assert any("broken.yaml" in w["file"] for w in warnings)

    def test_list_corrupt_theme_does_not_exclude_valid(self, themes_dir: Path) -> None:
        (themes_dir / "broken.yaml").write_text(": [bad yaml")
        out = run(["list", "--themes-dir", str(themes_dir)], expect_code=0)
        assert out["count"] >= 1  # at least the valid default is listed

    def test_list_extra_theme_file_discovered(self, themes_dir: Path) -> None:
        write_theme(themes_dir / "custom.yaml", minimal_theme("custom"))
        out = run(["list", "--themes-dir", str(themes_dir)], expect_code=0)
        names = [t["name"] for t in out["themes"]]
        assert "custom" in names

    def test_list_unknown_keys_in_theme_entry(self, themes_dir: Path) -> None:
        theme = minimal_theme("custom")
        theme["custom_field"] = "ignored"
        write_theme(themes_dir / "custom.yaml", theme)
        out = run(["list", "--themes-dir", str(themes_dir)], expect_code=0)
        custom = next(t for t in out["themes"] if t["name"] == "custom")
        assert "unknown_keys" in custom
        assert "custom_field" in custom["unknown_keys"]

    def test_list_empty_dir_returns_zero_count(self, tmp_path: Path) -> None:
        empty = tmp_path / "themes"
        empty.mkdir()
        out = run(["list", "--themes-dir", str(empty)], expect_code=0)
        assert out["count"] == 0
        assert out["themes"] == []


# ---------------------------------------------------------------------------
# Integration tests: load subcommand
# ---------------------------------------------------------------------------


class TestLoad:
    def test_load_default_theme(self, themes_dir: Path) -> None:
        out = run(["load", "--themes-dir", str(themes_dir), "--theme", "default"], expect_code=0)
        assert out["theme"] == "default"
        assert "personas" in out

    def test_load_wh40k_theme(self, full_themes_dir: Path) -> None:
        out = run(["load", "--themes-dir", str(full_themes_dir), "--theme", "wh40k"], expect_code=0)
        assert out["theme"] == "wh40k"
        assert "personas" in out
        # Check a known persona
        assert "dev" in out["personas"]
        assert "Magos" in out["personas"]["dev"]["name"]

    def test_load_returns_all_required_fields(self, themes_dir: Path) -> None:
        out = run(["load", "--themes-dir", str(themes_dir), "--theme", "default"], expect_code=0)
        for field in ("theme", "description", "version", "author", "personas"):
            assert field in out

    def test_load_missing_theme_falls_back_to_default(self, themes_dir: Path) -> None:
        out = run(["load", "--themes-dir", str(themes_dir), "--theme", "nonexistent"], expect_code=0)
        assert out.get("fallback_from") == "nonexistent"
        assert out["theme"] == "default"

    def test_load_corrupt_theme_falls_back_to_default(self, themes_dir: Path) -> None:
        (themes_dir / "broken.yaml").write_text(": [bad yaml")
        out = run(["load", "--themes-dir", str(themes_dir), "--theme", "broken"], expect_code=0)
        assert out.get("fallback_from") == "broken"
        assert out["theme"] == "default"
        assert "fallback_reason" in out

    def test_load_from_user_profile(self, full_themes_dir: Path, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        profile.write_text("theme: wh40k\ntrack: full\n")
        out = run(["load", "--themes-dir", str(full_themes_dir), "--user-profile", str(profile)], expect_code=0)
        assert out["theme"] == "wh40k"

    def test_load_from_user_profile_missing_falls_back_to_default(self, themes_dir: Path, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        profile.write_text("track: full\n")  # no theme field
        out = run(["load", "--themes-dir", str(themes_dir), "--user-profile", str(profile)], expect_code=0)
        assert out["theme"] == "default"

    def test_load_missing_user_profile_file_returns_error(self, themes_dir: Path, tmp_path: Path) -> None:
        out = run(["load", "--themes-dir", str(themes_dir), "--user-profile", str(tmp_path / "missing.md")], expect_code=1)
        assert out["error"] == "user_profile_not_found"

    def test_load_path_traversal_rejected(self, themes_dir: Path) -> None:
        out = run(["load", "--themes-dir", str(themes_dir), "--theme", "../../etc/passwd"], expect_code=1)
        assert out["error"] == "invalid_theme_name"

    def test_load_empty_theme_name_rejected(self, themes_dir: Path) -> None:
        out = run(["load", "--themes-dir", str(themes_dir), "--theme", ""], expect_code=1)
        assert out["error"] == "invalid_theme_name"

    def test_load_warns_on_missing_roles(self, themes_dir: Path) -> None:
        # Theme with only 'lens' persona — all others missing
        write_theme(themes_dir / "sparse.yaml", minimal_theme("sparse"))
        out = run(["load", "--themes-dir", str(themes_dir), "--theme", "sparse"], expect_code=0)
        warnings = out.get("warnings", [])
        assert any(w["type"] == "missing_roles" for w in warnings)

    def test_load_all_roles_no_missing_warning(self, full_themes_dir: Path) -> None:
        out = run(["load", "--themes-dir", str(full_themes_dir), "--theme", "wh40k"], expect_code=0)
        warnings = out.get("warnings", [])
        assert not any(w["type"] == "missing_roles" for w in warnings)

    def test_load_default_theme_has_all_roles(self, themes_dir: Path) -> None:
        out = run(["load", "--themes-dir", str(themes_dir), "--theme", "default"], expect_code=0)
        warnings = out.get("warnings", [])
        assert not any(w["type"] == "missing_roles" for w in warnings)

    def test_load_explicit_theme_overrides_profile(self, full_themes_dir: Path, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        profile.write_text("theme: wh40k\n")
        # explicit --theme default should override the profile preference for wh40k
        out = run(["load", "--themes-dir", str(full_themes_dir), "--theme", "default", "--user-profile", str(profile)], expect_code=0)
        assert out["theme"] == "default"
        assert "fallback_from" not in out

    def test_load_invalid_theme_name_in_profile(self, themes_dir: Path, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        profile.write_text("theme: ../../etc/passwd\n")
        out = run(["load", "--themes-dir", str(themes_dir), "--user-profile", str(profile)], expect_code=1)
        assert out["error"] == "invalid_theme_name_in_profile"

    def test_load_extra_roles_warning(self, themes_dir: Path) -> None:
        theme = minimal_theme("extra")
        theme["personas"]["rogue_trader"] = {"name": "Captain Vex", "title": "Rogue Trader"}
        write_theme(themes_dir / "extra.yaml", theme)
        out = run(["load", "--themes-dir", str(themes_dir), "--theme", "extra"], expect_code=0)
        warnings = out.get("warnings", [])
        assert any(w["type"] == "extra_roles" for w in warnings)

    def test_load_unknown_theme_keys_warning(self, themes_dir: Path) -> None:
        theme = minimal_theme("custom")
        theme["custom_field"] = "ignored"
        write_theme(themes_dir / "custom.yaml", theme)
        out = run(["load", "--themes-dir", str(themes_dir), "--theme", "custom"], expect_code=0)
        warnings = out.get("warnings", [])
        assert any(w["type"] == "unknown_theme_keys" for w in warnings)

    def test_load_missing_default_returns_error(self, tmp_path: Path) -> None:
        empty = tmp_path / "themes"
        empty.mkdir()
        out = run(["load", "--themes-dir", str(empty), "--theme", "default"], expect_code=1)
        assert out["error"] == "theme_load_failed"


# ---------------------------------------------------------------------------
# Integration tests: easter-egg subcommand
# ---------------------------------------------------------------------------


class TestEasterEgg:
    def test_no_trigger_returns_false(self, full_themes_dir: Path) -> None:
        out = run(["easter-egg", "--themes-dir", str(full_themes_dir), "--theme", "wh40k", "--phrase", "nothing special here"], expect_code=0)
        assert out["triggered"] is False

    def test_phrase_triggers_egg(self, full_themes_dir: Path) -> None:
        out = run(["easter-egg", "--themes-dir", str(full_themes_dir), "--theme", "wh40k", "--phrase", "praise the omnissiah"], expect_code=0)
        assert out["triggered"] is True
        assert out["egg_id"] == "praise-the-omnissiah"
        assert "Omnissiah" in out["response"] or len(out["response"]) > 0

    def test_phrase_partial_match_triggers(self, full_themes_dir: Path) -> None:
        # "I say praise the omnissiah and mean it" should still trigger
        out = run(["easter-egg", "--themes-dir", str(full_themes_dir), "--theme", "wh40k", "--phrase", "I say praise the omnissiah today"], expect_code=0)
        assert out["triggered"] is True

    def test_phrase_case_insensitive(self, full_themes_dir: Path) -> None:
        out = run(["easter-egg", "--themes-dir", str(full_themes_dir), "--theme", "wh40k", "--phrase", "PRAISE THE OMNISSIAH"], expect_code=0)
        assert out["triggered"] is True

    def test_for_the_emperor_egg(self, full_themes_dir: Path) -> None:
        out = run(["easter-egg", "--themes-dir", str(full_themes_dir), "--theme", "wh40k", "--phrase", "for the emperor"], expect_code=0)
        assert out["triggered"] is True
        assert out["egg_id"] == "for-the-emperor"

    def test_heresy_egg(self, full_themes_dir: Path) -> None:
        out = run(["easter-egg", "--themes-dir", str(full_themes_dir), "--theme", "wh40k", "--phrase", "this is fine"], expect_code=0)
        assert out["triggered"] is True
        assert out["egg_id"] == "heresy"

    def test_machine_spirit_egg(self, full_themes_dir: Path) -> None:
        out = run(["easter-egg", "--themes-dir", str(full_themes_dir), "--theme", "wh40k", "--phrase", "the build is broken"], expect_code=0)
        assert out["triggered"] is True
        assert out["egg_id"] == "machine-spirit-angry"

    def test_default_theme_no_easter_eggs(self, themes_dir: Path) -> None:
        out = run(["easter-egg", "--themes-dir", str(themes_dir), "--theme", "default", "--phrase", "praise the omnissiah"], expect_code=0)
        assert out["triggered"] is False
        assert out.get("reason") == "no_easter_eggs_in_theme"

    def test_date_trigger(self, tmp_path: Path) -> None:
        themes = tmp_path / "themes"
        themes.mkdir()
        write_theme(themes / "default.yaml", minimal_theme("default"))
        theme_data = minimal_theme("datetest")
        theme_data["easter_eggs"] = [{
            "id": "birthday",
            "triggers": {"date": "04-06"},
            "response": "Happy birthday!",
        }]
        write_theme(themes / "datetest.yaml", theme_data)
        out = run(["easter-egg", "--themes-dir", str(themes), "--theme", "datetest", "--date", "2026-04-06"], expect_code=0)
        assert out["triggered"] is True
        assert out["egg_id"] == "birthday"

    def test_date_no_match(self, tmp_path: Path) -> None:
        themes = tmp_path / "themes"
        themes.mkdir()
        write_theme(themes / "default.yaml", minimal_theme("default"))
        theme_data = minimal_theme("datetest")
        theme_data["easter_eggs"] = [{
            "id": "birthday",
            "triggers": {"date": "04-06"},
            "response": "Happy birthday!",
        }]
        write_theme(themes / "datetest.yaml", theme_data)
        out = run(["easter-egg", "--themes-dir", str(themes), "--theme", "datetest", "--date", "2026-04-07"], expect_code=0)
        assert out["triggered"] is False

    def test_invalid_date_format_returns_error(self, full_themes_dir: Path) -> None:
        out = run(["easter-egg", "--themes-dir", str(full_themes_dir), "--theme", "wh40k", "--date", "not-a-date"], expect_code=1)
        assert out["error"] == "invalid_date_format"

    def test_missing_trigger_returns_error(self, full_themes_dir: Path) -> None:
        out = run(["easter-egg", "--themes-dir", str(full_themes_dir), "--theme", "wh40k"], expect_code=1)
        assert out["error"] == "missing_trigger"

    def test_nonexistent_theme_falls_back_to_default_no_eggs(self, themes_dir: Path) -> None:
        out = run(["easter-egg", "--themes-dir", str(themes_dir), "--theme", "nonexistent", "--phrase", "test"], expect_code=0)
        # Falls back to default which has no easter eggs
        assert out["triggered"] is False
        assert out.get("fallback_from") == "nonexistent" or out.get("reason") == "no_easter_eggs_in_theme"

    def test_path_traversal_theme_rejected(self, full_themes_dir: Path) -> None:
        out = run(["easter-egg", "--themes-dir", str(full_themes_dir), "--theme", "../../etc", "--phrase", "test"], expect_code=1)
        assert out["error"] == "invalid_theme_name"

    def test_already_fired_suppresses_egg(self, full_themes_dir: Path) -> None:
        import json as _json
        fired = _json.dumps(["praise-the-omnissiah"])
        out = run(["easter-egg", "--themes-dir", str(full_themes_dir), "--theme", "wh40k",
                   "--phrase", "praise the omnissiah", "--already-fired", fired], expect_code=0)
        assert out["triggered"] is False

    def test_already_fired_allows_other_eggs(self, full_themes_dir: Path) -> None:
        import json as _json
        fired = _json.dumps(["praise-the-omnissiah"])
        out = run(["easter-egg", "--themes-dir", str(full_themes_dir), "--theme", "wh40k",
                   "--phrase", "for the emperor", "--already-fired", fired], expect_code=0)
        assert out["triggered"] is True
        assert out["egg_id"] == "for-the-emperor"

    def test_combined_phrase_and_date_trigger_phrase_wins(self, tmp_path: Path) -> None:
        themes = tmp_path / "themes"
        themes.mkdir()
        write_theme(themes / "default.yaml", minimal_theme("default"))
        theme_data = minimal_theme("combo")
        theme_data["easter_eggs"] = [
            {"id": "phrase-egg", "triggers": {"phrases": ["special phrase"]}, "response": "phrase triggered"},
            {"id": "date-egg", "triggers": {"date": "04-06"}, "response": "date triggered"},
        ]
        write_theme(themes / "combo.yaml", theme_data)
        # Provide both triggers — phrase is evaluated first
        out = run(["easter-egg", "--themes-dir", str(themes), "--theme", "combo",
                   "--phrase", "special phrase", "--date", "2026-04-06"], expect_code=0)
        assert out["triggered"] is True
        assert out["egg_id"] == "phrase-egg"

    def test_date_only_with_phrase_only_theme_returns_false(self, tmp_path: Path) -> None:
        themes = tmp_path / "themes"
        themes.mkdir()
        write_theme(themes / "default.yaml", minimal_theme("default"))
        theme_data = minimal_theme("phraseonly")
        theme_data["easter_eggs"] = [{"id": "p", "triggers": {"phrases": ["hello"]}, "response": "hi"}]
        write_theme(themes / "phraseonly.yaml", theme_data)
        out = run(["easter-egg", "--themes-dir", str(themes), "--theme", "phraseonly",
                   "--date", "2099-01-01"], expect_code=0)
        assert out["triggered"] is False


# ---------------------------------------------------------------------------
# Integration tests: set subcommand
# ---------------------------------------------------------------------------


class TestSet:
    def test_set_creates_new_profile(self, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        out = run(["set", "--user-profile", str(profile), "--theme", "wh40k"], expect_code=0)
        assert out["status"] == "ok"
        assert out["theme"] == "wh40k"
        assert profile.read_text().strip() == "theme: wh40k"

    def test_set_updates_existing_theme_line(self, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        profile.write_text("theme: default\ntrack: full\n")
        run(["set", "--user-profile", str(profile), "--theme", "wh40k"], expect_code=0)
        text = profile.read_text()
        assert "theme: wh40k" in text
        assert "theme: default" not in text
        assert "track: full" in text  # other fields preserved

    def test_set_appends_when_no_theme_line(self, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        profile.write_text("track: full\nusername: alice\n")
        run(["set", "--user-profile", str(profile), "--theme", "wh40k"], expect_code=0)
        text = profile.read_text()
        assert "theme: wh40k" in text
        assert "track: full" in text  # other fields preserved

    def test_set_creates_parent_directories(self, tmp_path: Path) -> None:
        profile = tmp_path / "users" / "alice" / "user-profile.md"
        run(["set", "--user-profile", str(profile), "--theme", "default"], expect_code=0)
        assert profile.exists()

    def test_set_path_traversal_rejected(self, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        out = run(["set", "--user-profile", str(profile), "--theme", "../../etc/passwd"], expect_code=1)
        assert out["error"] == "invalid_theme_name"

    def test_set_empty_theme_rejected(self, tmp_path: Path) -> None:
        profile = tmp_path / "user-profile.md"
        out = run(["set", "--user-profile", str(profile), "--theme", ""], expect_code=1)
        assert out["error"] == "invalid_theme_name"




# ---------------------------------------------------------------------------
# Integration tests: default and wh40k theme file integrity
# ---------------------------------------------------------------------------


class TestThemeFileIntegrity:
    def test_default_theme_is_valid_yaml(self) -> None:
        path = ASSETS_THEMES / "default.yaml"
        assert path.exists(), "default.yaml asset must exist"
        data = yaml.safe_load(path.read_text())
        assert isinstance(data, dict)
        assert data.get("name") == "default"

    def test_wh40k_theme_is_valid_yaml(self) -> None:
        path = ASSETS_THEMES / "wh40k.yaml"
        assert path.exists(), "wh40k.yaml asset must exist"
        data = yaml.safe_load(path.read_text())
        assert isinstance(data, dict)
        assert data.get("name") == "wh40k"

    def test_default_theme_has_all_known_roles(self, ops) -> None:
        data = yaml.safe_load((ASSETS_THEMES / "default.yaml").read_text())
        personas = set(data.get("personas", {}).keys())
        assert ops.KNOWN_PERSONA_ROLES == personas

    def test_wh40k_theme_has_all_known_roles(self, ops) -> None:
        data = yaml.safe_load((ASSETS_THEMES / "wh40k.yaml").read_text())
        personas = set(data.get("personas", {}).keys())
        assert ops.KNOWN_PERSONA_ROLES == personas

    def test_wh40k_has_easter_eggs(self) -> None:
        data = yaml.safe_load((ASSETS_THEMES / "wh40k.yaml").read_text())
        assert len(data.get("easter_eggs") or []) > 0

    def test_default_theme_has_no_easter_eggs(self) -> None:
        data = yaml.safe_load((ASSETS_THEMES / "default.yaml").read_text())
        assert (data.get("easter_eggs") or []) == []

    def test_all_wh40k_easter_eggs_have_required_fields(self) -> None:
        data = yaml.safe_load((ASSETS_THEMES / "wh40k.yaml").read_text())
        for egg in data.get("easter_eggs", []):
            assert "id" in egg
            assert "triggers" in egg
            assert "response" in egg
            assert isinstance(egg["triggers"], dict)
            triggers = egg["triggers"]
            assert "phrases" in triggers or "date" in triggers


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
