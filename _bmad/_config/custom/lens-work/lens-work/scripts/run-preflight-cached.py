#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Wrap preflight.py with a TTL-based cache to skip redundant re-runs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run preflight.py with a TTL cache (default 300 s)."
    )
    parser.add_argument("--ttl", type=int, default=300, help="Cache TTL in seconds")
    parser.add_argument("--force", action="store_true", help="Ignore cache and run preflight")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--skip-constitution", action="store_true")
    parser.add_argument("--caller", default="")
    parser.add_argument("--governance-path", default="")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    _cwd = Path.cwd()
    project_root = (
        _cwd if (_cwd / "lens.core").exists()
        else next(p for p in script_dir.parents if (p / "lens.core").exists())
    )
    cache_file = project_root / ".lens/.preflight-cache"

    now = int(time.time())
    cached_at: int | None = None
    cache_valid = False

    if cache_file.is_file() and not args.force:
        raw = cache_file.read_text(encoding="utf-8").strip()
        if raw.isdigit():
            cached_at = int(raw)
            age = now - cached_at
            if age < args.ttl:
                cache_valid = True
                remaining = args.ttl - age
                if args.json:
                    print(json.dumps({
                        "status": "cached",
                        "cached_at": cached_at,
                        "age_seconds": age,
                        "ttl_remaining": remaining,
                        "ran_preflight": False,
                    }, indent=2))
                else:
                    print(f"[preflight-cached] Valid cache ({age}s old, {remaining}s remaining). Skipping re-run.")
                return 0

    print("[preflight-cached] Cache expired or forced. Running preflight...", flush=True)

    preflight_script = script_dir / "preflight.py"
    cmd = ["uv", "run", str(preflight_script)]
    if args.skip_constitution:
        cmd.append("--skip-constitution")
    if args.caller:
        cmd += ["--caller", args.caller]
    if args.governance_path:
        cmd += ["--governance-path", args.governance_path]

    result = subprocess.run(cmd)
    exit_code = result.returncode

    if exit_code == 0:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        written_at = int(time.time())
        cache_file.write_text(str(written_at), encoding="utf-8")

        if args.json:
            print(json.dumps({
                "status": "passed",
                "cached_at": written_at,
                "age_seconds": 0,
                "ttl_remaining": args.ttl,
                "ran_preflight": True,
            }, indent=2))
        else:
            print(f"[preflight-cached] Preflight passed. Cache refreshed (TTL: {args.ttl}s).")
    else:
        if args.json:
            print(json.dumps({
                "status": "failed",
                "cached_at": None,
                "age_seconds": None,
                "ttl_remaining": None,
                "ran_preflight": True,
            }, indent=2))
        else:
            print("[preflight-cached] Preflight FAILED. Cache not updated.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
