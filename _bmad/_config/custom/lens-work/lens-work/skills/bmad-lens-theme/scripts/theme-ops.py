#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
theme-ops.py — Lens theme loading and easter egg system.

Subcommands:
  list         List all available themes in a themes directory.
  load         Load a theme by name (or from user-profile.md) and return persona overlays.
  easter-egg   Check whether a phrase or date triggers an easter egg in the active theme.
  set          Persist a theme preference to user-profile.md.

All subcommands output JSON to stdout. Non-zero exit on error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import NoReturn

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_THEME = "default"

KNOWN_PERSONA_ROLES = frozenset({
    "lens", "analyst", "architect", "dev", "pm", "qa",
    "quick_dev", "sm", "tech_writer", "ux_designer",
    "brainstorming_coach", "creative_problem_solver", "design_thinking_coach",
})

KNOWN_THEME_KEYS = frozenset({
    "name", "description", "version", "author", "personas", "easter_eggs",
})

# Safety limits
MAX_THEME_BYTES = 100_000       # 100 KB — guards against YAML anchor expansion bombs
MAX_EGG_RESPONSE_CHARS = 2_000  # prompt injection mitigation for easter egg responses

# Regex for safe theme names (alpha, numeric, hyphens, underscores only)
_SLUG_RE = re.compile(r"^[A-Za-z0-9_-]+$")
# Strict ISO date format: exactly YYYY-MM-DD
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _out(data: dict, code: int = 0) -> NoReturn:
    print(json.dumps(data, indent=2, ensure_ascii=False))
    sys.exit(code)


def _validate_slug(value: str, label: str) -> tuple[str | None, int]:
    """Return (error_message, code) or (None, 0) if valid."""
    if not value or not value.strip():
        return f"{label} must not be empty", 1
    if not _SLUG_RE.match(value):
        return f"{label} '{value}' contains invalid characters (only alphanumeric, hyphens, underscores allowed)", 1
    return None, 0


def _safe_str(value: object) -> str:
    """Coerce any YAML scalar to string (handles int/float from unquoted YAML values)."""
    if value is None:
        return ""
    return str(value)


def _check_symlink(path: Path, base_dir: Path) -> bool:
    """Return True if the resolved path stays within base_dir (symlink traversal guard)."""
    try:
        return path.resolve().is_relative_to(base_dir.resolve())
    except (ValueError, OSError):
        return False


def _load_yaml_file(path: Path) -> tuple[dict | None, str | None]:
    """Load a YAML file. Returns (data, error_message)."""
    try:
        size = path.stat().st_size
        if size > MAX_THEME_BYTES:
            return None, f"Theme file too large ({size} bytes, max {MAX_THEME_BYTES})"
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            return None, f"Expected YAML mapping, got {type(data).__name__}"
        return data, None
    except yaml.YAMLError as exc:
        return None, f"YAML parse error: {exc}"
    except OSError as exc:
        return None, f"File read error: {exc}"


def _read_theme_name_from_profile(profile_path: Path) -> str | None:
    """
    Extract theme name from user-profile.md.
    Searches for a line matching: theme: <value>
    Returns the theme name string, or None if not found.
    """
    if not profile_path.exists():
        return None
    text = profile_path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^theme:\s*(\S+)", text)
    if match:
        return match.group(1).strip().strip('"').strip("'")
    return None


def _write_theme_to_profile(profile_path: Path, theme_name: str) -> str | None:
    """
    Write theme preference to user-profile.md.
    Updates the existing `theme:` line if present; appends it otherwise.
    Creates the file (and parent directories) if it does not exist.
    Returns an error message on failure, or None on success.
    """
    try:
        if profile_path.exists():
            text = profile_path.read_text(encoding="utf-8")
            if re.search(r"(?m)^theme:\s*", text):
                text = re.sub(r"(?m)^theme:\s*\S*", f"theme: {theme_name}", text)
            else:
                text = text.rstrip("\n") + f"\ntheme: {theme_name}\n"
        else:
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            text = f"theme: {theme_name}\n"
        profile_path.write_text(text, encoding="utf-8")
        return None
    except OSError as exc:
        return f"Failed to write profile: {exc}"


def _load_theme_file(
    themes_dir: Path, theme_name: str
) -> tuple[dict | None, str | None, dict]:
    """
    Load a theme YAML file from themes_dir.
    Returns (theme_data, error_message, metadata).
    metadata may contain: fallback_from, fallback_reason.
    Falls back to default.yaml when theme_name is not found or corrupt.
    """
    theme_path = themes_dir / f"{theme_name}.yaml"

    if not _check_symlink(theme_path, themes_dir):
        return None, "Theme path escapes themes directory", {}

    if not theme_path.exists():
        if theme_name == DEFAULT_THEME:
            return None, f"Default theme file not found: {theme_path}", {}
        # Graceful fallback to default
        fallback_path = themes_dir / f"{DEFAULT_THEME}.yaml"
        if fallback_path.exists() and _check_symlink(fallback_path, themes_dir):
            data, err = _load_yaml_file(fallback_path)
            if err:
                return None, err, {}
            return data, None, {"fallback_from": theme_name}
        return None, f"Theme '{theme_name}' not found and default fallback unavailable", {}

    data, err = _load_yaml_file(theme_path)
    if err:
        # Corrupt theme: fall back to default
        if theme_name != DEFAULT_THEME:
            fallback_path = themes_dir / f"{DEFAULT_THEME}.yaml"
            if fallback_path.exists() and _check_symlink(fallback_path, themes_dir):
                fb_data, fb_err = _load_yaml_file(fallback_path)
                if not fb_err:
                    return fb_data, None, {"fallback_from": theme_name, "fallback_reason": err}
        return None, err, {}
    return data, None, {}


# ---------------------------------------------------------------------------
# Subcommand: list
# ---------------------------------------------------------------------------


def cmd_list(themes_dir: Path) -> None:
    if not themes_dir.is_dir():
        _out({"error": "themes_dir_not_found", "path": str(themes_dir)}, 1)

    themes = []
    warnings = []
    for theme_file in sorted(themes_dir.glob("*.yaml")):
        if not _check_symlink(theme_file, themes_dir):
            warnings.append({"file": theme_file.name, "warning": "Skipped: symlink escapes themes directory"})
            continue
        data, err = _load_yaml_file(theme_file)
        if err:
            warnings.append({"file": theme_file.name, "warning": f"Could not parse: {err}"})
            continue

        unknown_keys = [k for k in data if k not in KNOWN_THEME_KEYS]
        personas = data.get("personas") or {}
        if not isinstance(personas, dict):
            personas = {}
        entry: dict = {
            "name": _safe_str(data.get("name", theme_file.stem)),
            "description": _safe_str(data.get("description", "")),
            "version": _safe_str(data.get("version", "")),
            "author": _safe_str(data.get("author", "")),
            "persona_count": len(personas),
            "easter_egg_count": len(data.get("easter_eggs") or []),
            "file": theme_file.name,
        }
        if unknown_keys:
            entry["unknown_keys"] = unknown_keys
        themes.append(entry)

    result: dict = {"themes": themes, "count": len(themes)}
    if warnings:
        result["warnings"] = warnings
    _out(result)


# ---------------------------------------------------------------------------
# Subcommand: load
# ---------------------------------------------------------------------------


def cmd_load(themes_dir: Path, theme_name: str) -> None:
    if not themes_dir.is_dir():
        _out({"error": "themes_dir_not_found", "path": str(themes_dir)}, 1)

    err, code = _validate_slug(theme_name, "theme name")
    if err:
        _out({"error": "invalid_theme_name", "detail": err}, code)

    data, load_err, meta = _load_theme_file(themes_dir, theme_name)
    if load_err:
        _out({"error": "theme_load_failed", "detail": load_err}, 1)

    assert data is not None  # type guard

    personas = data.get("personas") or {}
    if not isinstance(personas, dict):
        personas = {}
    missing_roles = [r for r in KNOWN_PERSONA_ROLES if r not in personas]
    extra_roles = [r for r in personas if r not in KNOWN_PERSONA_ROLES]

    result: dict = {
        "theme": _safe_str(data.get("name", theme_name)),
        "description": _safe_str(data.get("description", "")),
        "version": _safe_str(data.get("version", "")),
        "author": _safe_str(data.get("author", "")),
        "personas": personas,
    }
    if "fallback_from" in meta:
        result["fallback_from"] = meta["fallback_from"]
    if "fallback_reason" in meta:
        result["fallback_reason"] = meta["fallback_reason"]

    warnings = []
    if missing_roles:
        warnings.append({"type": "missing_roles", "roles": missing_roles})
    if extra_roles:
        warnings.append({"type": "extra_roles", "roles": extra_roles})

    unknown_theme_keys = [k for k in data if k not in KNOWN_THEME_KEYS]
    if unknown_theme_keys:
        warnings.append({"type": "unknown_theme_keys", "keys": unknown_theme_keys})

    if warnings:
        result["warnings"] = warnings

    _out(result)


# ---------------------------------------------------------------------------
# Subcommand: easter-egg
# ---------------------------------------------------------------------------


def cmd_easter_egg(
    themes_dir: Path,
    theme_name: str,
    phrase: str | None,
    check_date: str | None,
    already_fired: list[str] | None,
) -> None:
    if not themes_dir.is_dir():
        _out({"error": "themes_dir_not_found", "path": str(themes_dir)}, 1)

    err, code = _validate_slug(theme_name, "theme name")
    if err:
        _out({"error": "invalid_theme_name", "detail": err}, code)

    data, load_err, _meta = _load_theme_file(themes_dir, theme_name)
    if load_err:
        _out({"error": "theme_load_failed", "detail": load_err}, 1)

    assert data is not None  # type guard

    easter_eggs = data.get("easter_eggs") or []
    if not easter_eggs:
        _out({"triggered": False, "reason": "no_easter_eggs_in_theme"})

    fired_set = set(already_fired) if already_fired else set()
    triggered_egg = None

    normalized_phrase = phrase.lower().strip() if phrase else None
    parsed_date: date | None = None
    if check_date:
        if not _ISO_DATE_RE.match(check_date):
            _out({"error": "invalid_date_format", "detail": f"Expected ISO date (YYYY-MM-DD), got: {check_date}"}, 1)
        try:
            parsed_date = date.fromisoformat(check_date)
        except ValueError:
            _out({"error": "invalid_date_format", "detail": f"Expected ISO date (YYYY-MM-DD), got: {check_date}"}, 1)

    for egg in easter_eggs:
        if not isinstance(egg, dict):
            continue
        egg_id = egg.get("id", "unknown")
        if egg_id in fired_set:
            continue
        triggers = egg.get("triggers") or {}
        if not isinstance(triggers, dict):
            continue

        # Phrase matching — word-boundary to avoid false positives on short substrings
        if normalized_phrase:
            trigger_phrases = triggers.get("phrases") or []
            for trigger in trigger_phrases:
                if isinstance(trigger, str):
                    pattern = r"\b" + re.escape(trigger.lower()) + r"\b"
                    if re.search(pattern, normalized_phrase):
                        triggered_egg = egg
                        break

        # Date matching (MM-DD format in the theme file)
        if triggered_egg is None and parsed_date:
            trigger_date = triggers.get("date")
            if trigger_date and isinstance(trigger_date, str):
                try:
                    month, day = (int(x) for x in trigger_date.split("-"))
                    if parsed_date.month == month and parsed_date.day == day:
                        triggered_egg = egg
                except (ValueError, TypeError):
                    pass

        if triggered_egg:
            break

    if triggered_egg:
        response = _safe_str(triggered_egg.get("response", "")).strip()
        if len(response) > MAX_EGG_RESPONSE_CHARS:
            response = response[:MAX_EGG_RESPONSE_CHARS]
        _out({
            "triggered": True,
            "egg_id": triggered_egg.get("id", "unknown"),
            "response": response,
        })
    else:
        _out({"triggered": False})


# ---------------------------------------------------------------------------
# Subcommand: set
# ---------------------------------------------------------------------------


def cmd_set(user_profile: Path, theme_name: str) -> None:
    err, code = _validate_slug(theme_name, "theme name")
    if err:
        _out({"error": "invalid_theme_name", "detail": err}, code)

    write_err = _write_theme_to_profile(user_profile, theme_name)
    if write_err:
        _out({"error": "profile_write_failed", "detail": write_err}, 1)

    _out({"status": "ok", "theme": theme_name, "path": str(user_profile)})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="theme-ops.py",
        description="Lens theme loading and easter egg system",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # --- list ---
    p_list = sub.add_parser("list", help="List available themes")
    p_list.add_argument("--themes-dir", required=True, type=Path)

    # --- load ---
    p_load = sub.add_parser("load", help="Load a theme and return persona overlays")
    p_load.add_argument("--themes-dir", required=True, type=Path)
    p_load.add_argument("--theme", default=None)
    p_load.add_argument("--user-profile", default=None, type=Path)

    # --- easter-egg ---
    p_ee = sub.add_parser("easter-egg", help="Check for easter egg triggers")
    p_ee.add_argument("--themes-dir", required=True, type=Path)
    p_ee.add_argument("--theme", required=True)
    p_ee.add_argument("--phrase", default=None)
    p_ee.add_argument("--date", default=None, dest="check_date")
    p_ee.add_argument(
        "--already-fired",
        default=None,
        help="JSON array of egg IDs already fired this session — those eggs are suppressed",
    )

    # --- set ---
    p_set = sub.add_parser("set", help="Persist a theme preference to user-profile.md")
    p_set.add_argument("--user-profile", required=True, type=Path)
    p_set.add_argument("--theme", required=True)

    args = parser.parse_args()

    if args.cmd == "list":
        cmd_list(args.themes_dir)

    elif args.cmd == "load":
        # Resolve theme name: explicit arg > user-profile > default
        theme_name = DEFAULT_THEME
        if args.theme is not None:
            theme_name = args.theme
        elif args.user_profile:
            if not args.user_profile.exists():
                _out({"error": "user_profile_not_found", "path": str(args.user_profile)}, 1)
            extracted = _read_theme_name_from_profile(args.user_profile)
            if extracted:
                err, code = _validate_slug(extracted, "theme name from user-profile")
                if err:
                    _out({"error": "invalid_theme_name_in_profile", "detail": err}, 1)
                theme_name = extracted
        cmd_load(args.themes_dir, theme_name)

    elif args.cmd == "easter-egg":
        if not args.phrase and not args.check_date:
            _out({"error": "missing_trigger", "detail": "Provide --phrase or --date"}, 1)
        already_fired: list[str] | None = None
        if args.already_fired:
            try:
                already_fired = json.loads(args.already_fired)
                if not isinstance(already_fired, list):
                    _out({"error": "invalid_already_fired", "detail": "Expected a JSON array of strings"}, 1)
            except json.JSONDecodeError as exc:
                _out({"error": "invalid_already_fired", "detail": str(exc)}, 1)
        cmd_easter_egg(args.themes_dir, args.theme, args.phrase, args.check_date, already_fired)

    elif args.cmd == "set":
        cmd_set(args.user_profile, args.theme)


if __name__ == "__main__":
    main()
