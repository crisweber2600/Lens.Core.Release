#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""
preflight.py — Full Lens workspace and onboarding validation.

Checks runtime tooling, configuration, governance repo structure, control repo
integrity, and target projects path. Produces pass/fail/warn results per check.

Usage:
    python3 preflight.py [options]

Options:
    --governance-repo PATH   Path to local governance repo root.
    --control-repo PATH      Path to lens.core control repo root. Default: CWD.
    --target-projects PATH   Root path for target project clones.
    --json                   Output structured JSON to stdout instead of human text.
    -h, --help               Show this help and exit.

Exit codes:
    0   All required checks pass (warnings do not affect exit code).
    1   One or more required checks failed.
"""

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    category: str
    status: str          # "pass" | "fail" | "warn"
    reason: str


@dataclass
class PreflightReport:
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, category: str, ok: bool, reason: str, warn: bool = False) -> None:
        if warn:
            status = "warn"
        elif ok:
            status = "pass"
        else:
            status = "fail"
        self.checks.append(CheckResult(name=name, category=category, status=status, reason=reason))

    @property
    def status(self) -> str:
        return "fail" if any(c.status == "fail" for c in self.checks) else "pass"

    def summary(self) -> dict:
        return {
            "pass": sum(1 for c in self.checks if c.status == "pass"),
            "fail": sum(1 for c in self.checks if c.status == "fail"),
            "warn": sum(1 for c in self.checks if c.status == "warn"),
        }

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "checks": [
                {"name": c.name, "category": c.category, "status": c.status, "reason": c.reason}
                for c in self.checks
            ],
            "summary": self.summary(),
        }


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_config(control_repo: Path, report: PreflightReport) -> None:
    has_config = (control_repo / "_bmad" / "config.yaml").exists()
    has_user_config = (control_repo / "_bmad" / "config.user.yaml").exists()
    report.add(
        "bmadconfig present",
        "Config",
        has_config or has_user_config,
        "Found config.yaml" if has_config else (
            "Found config.user.yaml" if has_user_config
            else f"No config.yaml or config.user.yaml found under {control_repo / '_bmad'}"
        ),
    )


def _run_version(cmd: list[str]) -> tuple[bool, str]:
    """Run a version command and return (success, version_string_or_error)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        output = (result.stdout + result.stderr).strip().splitlines()
        return result.returncode == 0, output[0] if output else "(no output)"
    except FileNotFoundError:
        return False, f"`{cmd[0]}` not found on PATH"
    except subprocess.TimeoutExpired:
        return False, f"`{cmd[0]}` timed out"


def check_python(report: PreflightReport) -> None:
    major, minor = sys.version_info.major, sys.version_info.minor
    ok = (major, minor) >= (3, 12)
    report.add(
        "Python >= 3.12",
        "Runtime",
        ok,
        f"Python {major}.{minor}" if ok else f"Python {major}.{minor} — requires >= 3.12",
    )


def check_uv(report: PreflightReport) -> None:
    ok, version = _run_version(["uv", "--version"])
    report.add(
        "uv available",
        "Runtime",
        ok,
        version if ok else f"uv not found — install from https://docs.astral.sh/uv/: {version}",
    )


def check_git(report: PreflightReport) -> None:
    ok, version_str = _run_version(["git", "--version"])
    if not ok:
        report.add("Git >= 2.40", "Runtime", False, f"Git not found: {version_str}")
        return

    # Parse "git version 2.44.0" → (2, 44, 0)
    try:
        parts = version_str.replace("git version", "").strip().split(".")
        major, minor = int(parts[0]), int(parts[1])
        sufficient = (major, minor) >= (2, 40)
        report.add(
            "Git >= 2.40",
            "Runtime",
            sufficient,
            version_str if sufficient else f"{version_str} — requires >= 2.40",
        )
    except (IndexError, ValueError):
        report.add("Git >= 2.40", "Runtime", True, version_str + " (version parse skipped)")


def check_gh(report: PreflightReport) -> None:
    ok, version = _run_version(["gh", "--version"])
    report.add(
        "gh (GitHub CLI) available",
        "Runtime",
        ok,
        version if ok else f"gh not found — install from https://cli.github.com/: {version}",
    )


def check_governance_repo(governance_repo: Path | None, report: PreflightReport) -> None:
    if governance_repo is None:
        report.add(
            "Governance repo accessible",
            "Governance repo",
            False,
            "governance_repo_path not configured — set in _bmad/config.yaml",
        )
        return

    if not governance_repo.is_dir():
        report.add(
            "Governance repo accessible",
            "Governance repo",
            False,
            f"Directory not found: {governance_repo}",
        )
        return

    report.add("Governance repo accessible", "Governance repo", True, str(governance_repo))

    # Check expected top-level structure
    for expected in ["features", "constitutions"]:
        exists = (governance_repo / expected).is_dir()
        report.add(
            f"Governance repo: {expected}/ present",
            "Governance repo",
            exists,
            f"Found {governance_repo / expected}" if exists else f"Missing {governance_repo / expected}",
        )


def check_lifecycle_yaml(control_repo: Path, report: PreflightReport) -> None:
    lifecycle_path = control_repo / "_bmad" / "lens-work" / "lifecycle.yaml"
    exists = lifecycle_path.exists()
    report.add(
        "lifecycle.yaml present",
        "Control repo",
        exists,
        str(lifecycle_path) if exists else f"Missing — expected at {lifecycle_path}",
    )


def check_target_projects(target_projects: Path | None, report: PreflightReport) -> None:
    if target_projects is None:
        report.add(
            "Target projects path accessible",
            "Target projects",
            True,
            "target_projects_path not configured — skipped (warn only)",
            warn=True,
        )
        return

    exists = target_projects.is_dir()
    report.add(
        "Target projects path accessible",
        "Target projects",
        True,  # warn only — path may not be cloned yet
        str(target_projects) if exists else f"Directory not found: {target_projects} — will be needed for discover",
        warn=not exists,
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def print_human(report: PreflightReport) -> None:
    current_category = None
    for check in report.checks:
        if check.category != current_category:
            current_category = check.category
            print(f"\n  {current_category}")
            print(f"  {'─' * len(current_category)}")
        icon = "✓" if check.status == "pass" else ("⚠" if check.status == "warn" else "✗")
        print(f"  {icon}  {check.name}")
        if check.status != "pass":
            print(f"     {check.reason}")

    summary = report.summary()
    total = sum(summary.values())
    print(f"\n  {total} checks — {summary['pass']} pass, {summary['fail']} fail, {summary['warn']} warn")

    if report.status == "pass":
        print("\n  [LENS:PREFLIGHT] Workspace ready.\n")
    else:
        print(f"\n  [LENS:PREFLIGHT] {summary['fail']} check(s) failed — run /preflight for a remediation report.\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full Lens workspace and onboarding validation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--governance-repo", metavar="PATH", help="Path to local governance repo root.")
    parser.add_argument("--control-repo", metavar="PATH", default=".", help="Path to lens.core control repo root.")
    parser.add_argument("--target-projects", metavar="PATH", help="Root path for target project clones.")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output structured JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    control_repo = Path(args.control_repo).resolve()
    governance_repo = Path(args.governance_repo).resolve() if args.governance_repo else None
    target_projects = Path(args.target_projects).resolve() if args.target_projects else None

    report = PreflightReport()

    # Config
    check_config(control_repo, report)

    # Runtime tooling
    check_python(report)
    check_uv(report)
    check_git(report)
    check_gh(report)

    # Governance repo
    check_governance_repo(governance_repo, report)

    # Control repo
    check_lifecycle_yaml(control_repo, report)

    # Target projects (warn only)
    check_target_projects(target_projects, report)

    if args.json_output:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_human(report)

    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
