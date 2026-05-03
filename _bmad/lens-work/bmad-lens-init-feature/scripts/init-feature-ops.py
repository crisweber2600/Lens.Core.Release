#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Init feature operations (new-codebase implementation).

This implementation currently exposes create-domain for the new-domain command.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

# source: old-codebase init-feature-ops.py SAFE_ID_PATTERN
SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_safe_id(domain: str) -> None:
    if not SAFE_ID_PATTERN.match(domain) or domain.endswith("-"):
        raise ValueError(
            f"Invalid domain: '{domain}'. "
            "Must match [a-z0-9][a-z0-9._-]{0,63} "
            "(lowercase alphanumeric, dots, hyphens, underscores)."
        )


def validate_safe_id_field(value: str, field_name: str) -> str | None:
    if not SAFE_ID_PATTERN.match(value) or value.endswith("-"):
        return (
            f"Invalid {field_name}: '{value}'. "
            "Must match [a-z0-9][a-z0-9._-]{0,63} "
            "(lowercase alphanumeric, dots, hyphens, underscores)."
        )
    return None


def git_command_argv(repo: str, args: list[str]) -> list[str]:
    return ["git", "-C", repo, *args]


def git_command_text(repo: str, args: list[str]) -> str:
    return shlex.join(git_command_argv(repo, args))


def run_git(repo: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(git_command_argv(repo, args), capture_output=True, text=True)
    if result.returncode != 0:
        msg = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"{git_command_text(repo, args)} failed: {msg}")
    return result


def unique_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered


def ensure_git_worktree(repo: str) -> None:
    result = subprocess.run(
        git_command_argv(repo, ["rev-parse", "--is-inside-work-tree"]),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise RuntimeError(f"{repo} is not a git worktree")


def ensure_clean_worktree(repo: str) -> None:
    result = subprocess.run(git_command_argv(repo, ["status", "--short"]), capture_output=True, text=True)
    if result.returncode != 0:
        msg = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"{git_command_text(repo, ['status', '--short'])} failed: {msg}")
    if result.stdout.strip():
        raise RuntimeError("Governance repo has local changes. Commit or stash before --execute-governance-git.")


def current_head_sha(repo: str) -> str | None:
    result = subprocess.run(git_command_argv(repo, ["rev-parse", "HEAD"]), capture_output=True, text=True)
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha if sha else None


def sync_governance_main(governance_repo: str) -> None:
    ensure_git_worktree(governance_repo)
    ensure_clean_worktree(governance_repo)
    run_git(governance_repo, ["checkout", "main"])
    run_git(governance_repo, ["pull", "--rebase", "--autostash", "origin", "main"])


def atomic_write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.dump(data, handle, default_flow_style=False, sort_keys=False, allow_unicode=True)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def write_context_yaml(personal_folder: str, domain: str, source: str, service: str | None = None) -> Path:
    context_path = Path(personal_folder) / "context.yaml"
    context_data = {
        "domain": domain,
        "service": service,
        "updated_at": now_iso(),
        "updated_by": source,
    }
    atomic_write_yaml(context_path, context_data)
    return context_path


def make_domain_yaml(domain: str, name: str, username: str, timestamp: str) -> dict:
    return {
        "kind": "domain",
        "id": domain,
        "name": name,
        "domain": domain,
        "status": "active",
        "owner": username,
        "created": timestamp,
        "updated": timestamp,
    }


def make_domain_constitution_md(domain: str, name: str) -> str:
    return (
        "---\n"
        "permitted_tracks: [quickplan, full, hotfix, tech-change,express,expressplan]\n"
        "required_artifacts:\n"
        "  planning:\n"
        "    - business-plan\n"
        "  dev:\n"
        "    - stories\n"
        "gate_mode: informational\n"
        "sensing_gate_mode: informational\n"
        "additional_review_participants: []\n"
        "enforce_stories: true\n"
        "enforce_review: true\n"
        "---\n"
        "\n"
        f"# {domain} Domain Constitution\n"
        "\n"
        "## Scope\n"
        "\n"
        f"This constitution governs all features under the `{domain}` domain.\n"
        "\n"
        "## Tracks\n"
        "\n"
        "All tracks listed in `permitted_tracks` are available for features in this domain.\n"
        "\n"
        "## Artifacts\n"
        "\n"
        "Planning artifacts and development artifacts listed in `required_artifacts` are required for features in this domain.\n"
        "\n"
        "## Review\n"
        "\n"
        "Reviews are `informational`. Sensing is `informational`.\n"
        "\n"
        "## Notes\n"
        "\n"
        "This is an auto-generated default constitution. Edit this file to add domain-specific governance rules.\n"
    )


def build_container_git_steps(paths: list[str], commit_message: str) -> list[list[str]]:
    add_args = ["add", *paths]
    return [
        ["checkout", "main"],
        ["pull", "--rebase", "--autostash", "origin", "main"],
        add_args,
        ["commit", "-m", commit_message],
        ["push", "origin", "main"],
    ]


def build_container_result_fields(
    governance_git_commands: list[str],
    workspace_git_commands: list[str],
    governance_git_executed: bool = False,
    governance_commit_sha: str | None = None,
) -> dict:
    all_git_commands = [*governance_git_commands, *workspace_git_commands]
    remaining_git_commands = workspace_git_commands if governance_git_executed else all_git_commands
    return {
        "git_commands": all_git_commands,
        "governance_git_commands": governance_git_commands,
        "workspace_git_commands": workspace_git_commands,
        "remaining_git_commands": remaining_git_commands,
        "governance_git_executed": governance_git_executed,
        "governance_commit_sha": governance_commit_sha,
    }


def build_workspace_scaffold_commands(
    scaffold_entries: list[tuple[str, str]],
    scope: str,
    identifier: str,
) -> list[str]:
    grouped: dict[str, list[str]] = {}
    for workspace_root, rel_path in scaffold_entries:
        grouped.setdefault(workspace_root, []).append(rel_path)

    commands: list[str] = []
    for workspace_root, rel_paths in grouped.items():
        unique_rel_paths = unique_paths(rel_paths)
        noun = "folder" if len(unique_rel_paths) == 1 else "folders"
        commands.extend([
            f"git -C {workspace_root} add {' '.join(unique_rel_paths)}",
            f'git -C {workspace_root} commit -m "scaffold({scope}): add {identifier} {noun}"',
        ])
    return commands


def resolve_personal_folder(args: argparse.Namespace) -> Path:
    if args.personal_folder:
        return Path(args.personal_folder).expanduser().resolve()
    env_value = os.environ.get("LENS_PERSONAL_FOLDER")
    if env_value:
        return Path(env_value).expanduser().resolve()
    return (Path.cwd() / ".lens" / "personal").resolve()


def cmd_create_domain(args: argparse.Namespace) -> dict:
    domain = args.domain
    name = args.name if args.name else domain
    username = args.username if args.username else ""
    governance_repo = args.governance_repo

    try:
        validate_safe_id(domain)
    except ValueError as exc:
        return {"status": "fail", "scope": "domain", "dry_run": bool(args.dry_run), "error": str(exc)}

    gov_path = Path(governance_repo)
    if not gov_path.is_dir():
        return {
            "status": "fail",
            "scope": "domain",
            "dry_run": bool(args.dry_run),
            "error": f"Governance repo not found: {governance_repo}",
        }

    marker_path = gov_path / "features" / domain / "domain.yaml"
    constitution_path = gov_path / "constitutions" / domain / "constitution.md"
    marker_paths = [marker_path.relative_to(gov_path).as_posix()]
    constitution_paths = [constitution_path.relative_to(gov_path).as_posix()]

    tp_gitkeep_path: Path | None = None
    workspace_scaffold_entries: list[tuple[str, str]] = []
    if args.target_projects_root:
        target_projects_root = Path(args.target_projects_root)
        tp_gitkeep_path = target_projects_root / domain / ".gitkeep"
        workspace_scaffold_entries.append(
            (str(target_projects_root.parent), (Path(target_projects_root.name) / domain / ".gitkeep").as_posix())
        )

    docs_gitkeep_path: Path | None = None
    if args.docs_root:
        docs_root = Path(args.docs_root)
        docs_gitkeep_path = docs_root / domain / ".gitkeep"
        workspace_scaffold_entries.append(
            (str(docs_root.parent), (Path(docs_root.name) / domain / ".gitkeep").as_posix())
        )

    personal_folder = resolve_personal_folder(args)
    context_path = str((personal_folder / "context.yaml"))

    gov_paths = marker_paths + constitution_paths
    gov_steps = build_container_git_steps(gov_paths, f"feat(domain): add {domain} container")
    governance_git_commands = [git_command_text(governance_repo, step) for step in gov_steps]
    workspace_git_commands = build_workspace_scaffold_commands(workspace_scaffold_entries, "domain", domain)

    if args.execute_governance_git and not args.dry_run:
        try:
            sync_governance_main(governance_repo)
        except RuntimeError as exc:
            return {
                "status": "fail",
                "scope": "domain",
                "dry_run": False,
                "error": f"Governance git preflight failed: {exc}",
                **build_container_result_fields(governance_git_commands, workspace_git_commands),
            }

    if marker_path.exists():
        return {
            "status": "fail",
            "scope": "domain",
            "dry_run": bool(args.dry_run),
            "error": f"Domain '{domain}' already exists at {marker_path}",
        }

    if args.dry_run:
        return {
            "status": "pass",
            "dry_run": True,
            "scope": "domain",
            "path": str(marker_path),
            "constitution_path": str(constitution_path),
            "created_marker_paths": marker_paths,
            "created_constitution_paths": constitution_paths,
            "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
            "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
            "context_path": context_path,
            "error": None,
            **build_container_result_fields(governance_git_commands, workspace_git_commands),
        }

    timestamp = now_iso()

    try:
        atomic_write_yaml(marker_path, make_domain_yaml(domain, name, username, timestamp))
    except OSError as exc:
        return {"status": "fail", "scope": "domain", "dry_run": False, "error": f"Failed to write domain marker: {exc}"}

    try:
        constitution_path.parent.mkdir(parents=True, exist_ok=True)
        constitution_path.write_text(make_domain_constitution_md(domain, name), encoding="utf-8")
    except OSError as exc:
        return {
            "status": "fail",
            "scope": "domain",
            "dry_run": False,
            "error": f"Failed to write domain constitution: {exc}",
        }

    if tp_gitkeep_path is not None:
        try:
            tp_gitkeep_path.parent.mkdir(parents=True, exist_ok=True)
            tp_gitkeep_path.touch()
        except OSError as exc:
            return {
                "status": "fail",
                "scope": "domain",
                "dry_run": False,
                "error": f"Failed to scaffold TargetProjects domain folder: {exc}",
            }

    if docs_gitkeep_path is not None:
        try:
            docs_gitkeep_path.parent.mkdir(parents=True, exist_ok=True)
            docs_gitkeep_path.touch()
        except OSError as exc:
            return {
                "status": "fail",
                "scope": "domain",
                "dry_run": False,
                "error": f"Failed to scaffold docs domain folder: {exc}",
            }

    try:
        written_context_path = str(write_context_yaml(str(personal_folder), domain, "new-domain"))
    except OSError as exc:
        return {"status": "fail", "scope": "domain", "dry_run": False, "error": f"Failed to write context.yaml: {exc}"}

    governance_commit_sha: str | None = None
    governance_git_executed = False
    if args.execute_governance_git:
        try:
            for step in gov_steps[2:]:
                run_git(governance_repo, step)
            governance_commit_sha = current_head_sha(governance_repo)
            governance_git_executed = True
        except RuntimeError as exc:
            return {
                "status": "fail",
                "scope": "domain",
                "dry_run": False,
                "path": str(marker_path),
                "constitution_path": str(constitution_path),
                "created_marker_paths": marker_paths,
                "created_constitution_paths": constitution_paths,
                "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
                "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
                "context_path": written_context_path,
                "error": f"Governance git execution failed: {exc}",
                **build_container_result_fields(
                    governance_git_commands,
                    workspace_git_commands,
                    governance_commit_sha=current_head_sha(governance_repo),
                ),
            }

    return {
        "status": "pass",
        "dry_run": False,
        "scope": "domain",
        "path": str(marker_path),
        "constitution_path": str(constitution_path),
        "created_marker_paths": marker_paths,
        "created_constitution_paths": constitution_paths,
        "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
        "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
        "context_path": written_context_path,
        "error": None,
        **build_container_result_fields(
            governance_git_commands,
            workspace_git_commands,
            governance_git_executed=governance_git_executed,
            governance_commit_sha=governance_commit_sha,
        ),
    }


# ---------------------------------------------------------------------------
# NS-4: Service marker and constitution builders
# ADR-3 delegation boundary: create-service calls create-domain helpers
# (make_domain_yaml, make_domain_constitution_md) for parent domain creation.
# There is exactly one code path that writes domain.yaml — owned by those helpers.
# ---------------------------------------------------------------------------


def get_service_marker_path(gov_path: Path, domain: str, service: str) -> Path:
    return gov_path / "features" / domain / service / "service.yaml"


def get_service_constitution_path(gov_path: Path, domain: str, service: str) -> Path:
    return gov_path / "constitutions" / domain / service / "constitution.md"


def make_service_yaml(domain: str, service: str, name: str, username: str, timestamp: str) -> dict:
    return {
        "kind": "service",
        "id": f"{domain}-{service}",
        "name": name,
        "domain": domain,
        "service": service,
        "status": "active",
        "owner": username,
        "created": timestamp,
        "updated": timestamp,
    }


def make_service_constitution_md(domain: str, service: str, name: str) -> str:
    display = name or service
    return (
        "---\n"
        "permitted_tracks: [quickplan, full, hotfix, tech-change, express, expressplan]\n"
        "required_artifacts:\n"
        "  planning:\n"
        "    - business-plan\n"
        "  dev:\n"
        "    - stories\n"
        "gate_mode: informational\n"
        "sensing_gate_mode: informational\n"
        "additional_review_participants: []\n"
        "enforce_stories: true\n"
        "enforce_review: true\n"
        "---\n"
        "\n"
        f"# {display} Service Constitution\n"
        "\n"
        f"This constitution defines governance rules for the **{display}** service "
        f"within the `{domain}` domain.\n"
        "\n"
        "## Scope\n"
        "\n"
        f"Applies to all repositories within the `{domain}/{service}` service.\n"
        "Inherits domain-level constraints and may add further restrictions.\n"
        "\n"
        "## Tracks\n"
        "\n"
        "All standard tracks are permitted: `quickplan`, `full`, `hotfix`, `tech-change`, "
        "`express`, `expressplan`.\n"
        "\n"
        "## Artifacts\n"
        "\n"
        "- **Planning phase:** a `business-plan` is required before promotion to dev.\n"
        "- **Dev phase:** at least one story file must exist before dev work begins.\n"
        "\n"
        "## Review\n"
        "\n"
        "Peer review is enforced for all features in this service.\n"
        "Additional participants may be named at the repo level.\n"
        "\n"
        "## Notes\n"
        "\n"
        "This constitution was initialized with service defaults.\n"
        f"Update it to reflect the specific governance needs of the {display} service.\n"
    )


# ---------------------------------------------------------------------------
# NS-5: create-service command handler
# NS-6: Context writer extended (service param added to write_context_yaml above)
# NS-7: Governance git behavior follows the same create-domain pattern
# ---------------------------------------------------------------------------


def cmd_create_service(args: argparse.Namespace) -> dict:
    # NS-5 AC-4: mutual exclusion guard — no file writes before this check
    if args.dry_run and args.execute_governance_git:
        return {
            "status": "fail",
            "scope": "service",
            "dry_run": True,
            "error": "--dry-run and --execute-governance-git are mutually exclusive.",
        }

    domain = args.domain
    service = args.service
    name = args.name if args.name else service
    username = args.username if args.username else ""
    governance_repo = args.governance_repo

    err = validate_safe_id_field(domain, "domain")
    if err:
        return {"status": "fail", "scope": "service", "dry_run": bool(args.dry_run), "error": err}

    err = validate_safe_id_field(service, "service")
    if err:
        return {"status": "fail", "scope": "service", "dry_run": bool(args.dry_run), "error": err}

    gov_path = Path(governance_repo)
    if not gov_path.is_dir():
        return {
            "status": "fail",
            "scope": "service",
            "dry_run": bool(args.dry_run),
            "error": f"Governance repo not found: {governance_repo}",
        }

    # Service marker and constitution paths
    service_marker_path = get_service_marker_path(gov_path, domain, service)
    service_const_path = get_service_constitution_path(gov_path, domain, service)
    service_marker_paths = [service_marker_path.relative_to(gov_path).as_posix()]
    service_const_paths = [service_const_path.relative_to(gov_path).as_posix()]

    # Domain marker and constitution paths (ADR-3 delegation)
    domain_marker_path = gov_path / "features" / domain / "domain.yaml"
    domain_const_path = gov_path / "constitutions" / domain / "constitution.md"
    domain_marker_rel = domain_marker_path.relative_to(gov_path).as_posix()
    domain_const_rel = domain_const_path.relative_to(gov_path).as_posix()

    parent_domain_absent = not domain_marker_path.exists()
    created_domain_marker = False
    created_domain_constitution = False

    # Scaffold paths
    tp_gitkeep_path: Path | None = None
    workspace_scaffold_entries: list[tuple[str, str]] = []
    if args.target_projects_root:
        tp_root = Path(args.target_projects_root)
        tp_gitkeep_path = tp_root / domain / service / ".gitkeep"
        workspace_scaffold_entries.append(
            (str(tp_root.parent), (Path(tp_root.name) / domain / service / ".gitkeep").as_posix())
        )

    docs_gitkeep_path: Path | None = None
    if args.docs_root:
        docs_root = Path(args.docs_root)
        docs_gitkeep_path = docs_root / domain / service / ".gitkeep"
        workspace_scaffold_entries.append(
            (str(docs_root.parent), (Path(docs_root.name) / domain / service / ".gitkeep").as_posix())
        )

    personal_folder = resolve_personal_folder(args)
    context_path = str(personal_folder / "context.yaml")

    # Build governance git paths: domain artifacts first if absent, then service artifacts
    gov_marker_paths = []
    if parent_domain_absent:
        gov_marker_paths.extend([domain_marker_rel, domain_const_rel])
    gov_marker_paths.extend(service_marker_paths + service_const_paths)

    gov_steps = build_container_git_steps(
        gov_marker_paths, f"feat(service): add {domain}/{service} container"
    )
    governance_git_commands = [git_command_text(governance_repo, step) for step in gov_steps]
    workspace_git_commands = build_workspace_scaffold_commands(
        workspace_scaffold_entries, "service", f"{domain}-{service}"
    )

    # NS-7: governance git preflight (validate -> sync -> duplicate check -> write)
    if args.execute_governance_git and not args.dry_run:
        try:
            sync_governance_main(governance_repo)
        except RuntimeError as exc:
            return {
                "status": "fail",
                "scope": "service",
                "dry_run": False,
                "error": f"Governance git preflight failed: {exc}",
                **build_container_result_fields(governance_git_commands, workspace_git_commands),
            }

    if service_marker_path.exists():
        return {
            "status": "fail",
            "scope": "service",
            "dry_run": bool(args.dry_run),
            "error": f"Service '{domain}/{service}' already exists at {service_marker_path}",
        }

    if args.dry_run:
        return {
            "status": "pass",
            "dry_run": True,
            "scope": "service",
            "path": str(service_marker_path),
            "constitution_path": str(service_const_path),
            "created_marker_paths": service_marker_paths,
            "created_constitution_paths": service_const_paths,
            "created_domain_marker": parent_domain_absent,
            "created_domain_constitution": parent_domain_absent,
            "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
            "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
            "context_path": context_path,
            "error": None,
            **build_container_result_fields(governance_git_commands, workspace_git_commands),
        }

    timestamp = now_iso()

    # ADR-3: Auto-establish missing parent domain using create-domain helpers
    if parent_domain_absent:
        domain_name = domain
        try:
            atomic_write_yaml(domain_marker_path, make_domain_yaml(domain, domain_name, username, timestamp))
            created_domain_marker = True
        except OSError as exc:
            return {"status": "fail", "scope": "service", "dry_run": False,
                    "error": f"Failed to write parent domain marker: {exc}"}
        try:
            domain_const_path.parent.mkdir(parents=True, exist_ok=True)
            domain_const_path.write_text(make_domain_constitution_md(domain, domain_name), encoding="utf-8")
            created_domain_constitution = True
        except OSError as exc:
            return {"status": "fail", "scope": "service", "dry_run": False,
                    "error": f"Failed to write parent domain constitution: {exc}"}

    # Write service marker
    try:
        atomic_write_yaml(service_marker_path, make_service_yaml(domain, service, name, username, timestamp))
    except OSError as exc:
        return {"status": "fail", "scope": "service", "dry_run": False,
                "error": f"Failed to write service marker: {exc}"}

    # Write service constitution
    try:
        service_const_path.parent.mkdir(parents=True, exist_ok=True)
        service_const_path.write_text(make_service_constitution_md(domain, service, name), encoding="utf-8")
    except OSError as exc:
        return {"status": "fail", "scope": "service", "dry_run": False,
                "error": f"Failed to write service constitution: {exc}"}

    # Write scaffold .gitkeep files
    if tp_gitkeep_path is not None:
        try:
            tp_gitkeep_path.parent.mkdir(parents=True, exist_ok=True)
            tp_gitkeep_path.touch()
        except OSError as exc:
            return {"status": "fail", "scope": "service", "dry_run": False,
                    "error": f"Failed to scaffold TargetProjects service folder: {exc}"}

    if docs_gitkeep_path is not None:
        try:
            docs_gitkeep_path.parent.mkdir(parents=True, exist_ok=True)
            docs_gitkeep_path.touch()
        except OSError as exc:
            return {"status": "fail", "scope": "service", "dry_run": False,
                    "error": f"Failed to scaffold docs service folder: {exc}"}

    # NS-6: Write context with service value
    try:
        written_context_path = str(write_context_yaml(str(personal_folder), domain, "new-service", service))
    except OSError as exc:
        return {"status": "fail", "scope": "service", "dry_run": False,
                "error": f"Failed to write context.yaml: {exc}"}

    # NS-7: Execute governance git if requested
    governance_commit_sha: str | None = None
    governance_git_executed = False
    if args.execute_governance_git:
        try:
            for step in gov_steps[2:]:
                run_git(governance_repo, step)
            governance_commit_sha = current_head_sha(governance_repo)
            governance_git_executed = True
        except RuntimeError as exc:
            return {
                "status": "fail",
                "scope": "service",
                "dry_run": False,
                "path": str(service_marker_path),
                "constitution_path": str(service_const_path),
                "created_marker_paths": service_marker_paths,
                "created_constitution_paths": service_const_paths,
                "created_domain_marker": created_domain_marker,
                "created_domain_constitution": created_domain_constitution,
                "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
                "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
                "context_path": written_context_path,
                "error": f"Governance git execution failed: {exc}",
                **build_container_result_fields(
                    governance_git_commands,
                    workspace_git_commands,
                    governance_commit_sha=current_head_sha(governance_repo),
                ),
            }

    return {
        "status": "pass",
        "dry_run": False,
        "scope": "service",
        "path": str(service_marker_path),
        "constitution_path": str(service_const_path),
        "created_marker_paths": service_marker_paths,
        "created_constitution_paths": service_const_paths,
        "created_domain_marker": created_domain_marker,
        "created_domain_constitution": created_domain_constitution,
        "target_projects_path": str(tp_gitkeep_path.parent) if tp_gitkeep_path else None,
        "docs_path": str(docs_gitkeep_path.parent) if docs_gitkeep_path else None,
        "context_path": written_context_path,
        "error": None,
        **build_container_result_fields(
            governance_git_commands,
            workspace_git_commands,
            governance_git_executed=governance_git_executed,
            governance_commit_sha=governance_commit_sha,
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lens init-feature ops")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_domain = subparsers.add_parser("create-domain", help="Create a governance domain")
    create_domain.add_argument("--governance-repo", required=True)
    create_domain.add_argument("--domain", required=True)
    create_domain.add_argument("--name")
    create_domain.add_argument("--username", default="")
    create_domain.add_argument("--target-projects-root")
    create_domain.add_argument("--docs-root")
    create_domain.add_argument("--personal-folder")
    create_domain.add_argument("--execute-governance-git", action="store_true")
    create_domain.add_argument("--dry-run", action="store_true")

    create_service = subparsers.add_parser("create-service", help="Create a governance service container")
    create_service.add_argument("--governance-repo", required=True)
    create_service.add_argument("--domain", required=True)
    create_service.add_argument("--service", required=True)
    create_service.add_argument("--name")
    create_service.add_argument("--username", default="")
    create_service.add_argument("--target-projects-root")
    create_service.add_argument("--docs-root")
    create_service.add_argument("--personal-folder")
    create_service.add_argument("--execute-governance-git", action="store_true")
    create_service.add_argument("--dry-run", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "create-domain":
        result = cmd_create_domain(args)
    elif args.command == "create-service":
        result = cmd_create_service(args)
    else:
        result = {"status": "fail", "error": f"Unsupported command: {args.command}"}

    print(json.dumps(result, indent=2, sort_keys=False))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
