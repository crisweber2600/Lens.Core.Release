"""NS-1 + NS-2 + NS-3: create-service contract, boundary, and discovery tests.

All tests below are written against the expected API contract from tech-plan.md.
They start red (create-service does not yet exist) and turn green after NS-4–NS-7 implementation.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "init-feature-ops.py"

EXPECTED_SUCCESS_FIELDS = {
    "status",
    "scope",
    "dry_run",
    "path",
    "constitution_path",
    "created_marker_paths",
    "created_constitution_paths",
    "created_domain_marker",
    "created_domain_constitution",
    "target_projects_path",
    "docs_path",
    "context_path",
    "governance_git_executed",
    "governance_commit_sha",
    "git_commands",
    "governance_git_commands",
    "workspace_git_commands",
    "remaining_git_commands",
    "workspace_git_executed",
    "error",
}


def run_script(args, cwd=None, env=None):
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout or "{}")
    return completed, payload


def make_gov_repo(tmp_path, name="gov"):
    """Create a bare local git remote and a cloned governance worktree."""
    remote = tmp_path / f"{name}.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    gov = tmp_path / name
    subprocess.run(["git", "clone", str(remote), str(gov)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(gov), "checkout", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(gov), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(gov), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(gov), "commit", "--allow-empty", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(gov), "push", "-u", "origin", "main"], check=True, capture_output=True)
    return gov


# ---------------------------------------------------------------------------
# NS-1: CLI contract tests
# ---------------------------------------------------------------------------


def test_create_service_success_json_fields(tmp_path):
    """AC-1: Success path returns all required JSON fields."""
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-service",
            "--governance-repo", str(gov),
            "--domain", "platform",
            "--service", "auth",
            "--name", "Auth Service",
            "--username", "testuser",
            "--personal-folder", str(personal),
        ]
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert payload["scope"] == "service"
    missing = EXPECTED_SUCCESS_FIELDS - set(payload.keys())
    assert not missing, f"Missing fields: {missing}"


def test_create_service_dry_run_no_writes(tmp_path):
    """AC-2: --dry-run returns planned output without touching the filesystem."""
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-service",
            "--governance-repo", str(gov),
            "--domain", "platform",
            "--service", "auth",
            "--name", "Auth Service",
            "--username", "testuser",
            "--personal-folder", str(personal),
            "--dry-run",
        ]
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert payload["dry_run"] is True
    # No domain or service markers should exist
    assert not (gov / "features" / "platform" / "domain.yaml").exists()
    assert not (gov / "features" / "platform" / "auth" / "service.yaml").exists()
    assert not (gov / "constitutions" / "platform" / "auth" / "constitution.md").exists()
    assert not (personal / "context.yaml").exists()


def test_create_service_duplicate_rejected(tmp_path):
    """AC-3: Creating a service that already exists returns an error."""
    gov = tmp_path / "gov"
    existing = gov / "features" / "platform" / "auth" / "service.yaml"
    existing.parent.mkdir(parents=True)
    existing.write_text("kind: service\n", encoding="utf-8")
    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-service",
            "--governance-repo", str(gov),
            "--domain", "platform",
            "--service", "auth",
            "--personal-folder", str(personal),
        ]
    )
    assert completed.returncode == 1
    assert payload["status"] == "fail"
    assert "already exists" in payload["error"].lower()


def test_create_service_invalid_id_rejected(tmp_path):
    """AC-4: Invalid service IDs (uppercase, spaces, bad chars) are rejected."""
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    for bad_id in ["Auth", "auth service", "AUTH", "auth!", ""]:
        completed, payload = run_script(
            [
                "create-service",
                "--governance-repo", str(gov),
                "--domain", "platform",
                "--service", bad_id,
                "--personal-folder", str(personal),
            ]
        )
        assert completed.returncode == 1, f"Expected failure for service='{bad_id}'"
        assert payload["status"] == "fail"


def test_create_service_scaffold_paths(tmp_path):
    """AC-5: Scaffold output structure is correct with --target-projects-root and --docs-root."""
    gov = tmp_path / "gov"
    gov.mkdir()
    target = tmp_path / "target"
    docs = tmp_path / "docs"
    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-service",
            "--governance-repo", str(gov),
            "--domain", "platform",
            "--service", "auth",
            "--personal-folder", str(personal),
            "--target-projects-root", str(target),
            "--docs-root", str(docs),
        ]
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert (target / "platform" / "auth" / ".gitkeep").exists()
    assert (docs / "platform" / "auth" / ".gitkeep").exists()
    assert payload["target_projects_path"] == str(target / "platform" / "auth")
    assert payload["docs_path"] == str(docs / "platform" / "auth")
    assert len(payload["workspace_git_commands"]) > 0


def test_create_service_context_path(tmp_path):
    """AC-6: context_path is in output and context.yaml is written with service field."""
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-service",
            "--governance-repo", str(gov),
            "--domain", "platform",
            "--service", "auth",
            "--personal-folder", str(personal),
        ]
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["context_path"] is not None
    ctx = yaml.safe_load(Path(payload["context_path"]).read_text(encoding="utf-8"))
    assert ctx["domain"] == "platform"
    assert ctx["service"] == "auth"
    assert ctx["updated_by"] == "new-service"


def test_create_service_governance_git(tmp_path):
    """AC-7: --execute-governance-git returns governance_commit_sha."""
    gov = make_gov_repo(tmp_path)
    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-service",
            "--governance-repo", str(gov),
            "--domain", "platform",
            "--service", "auth",
            "--name", "Auth",
            "--personal-folder", str(personal),
            "--execute-governance-git",
        ]
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert payload["governance_git_executed"] is True
    assert payload["governance_commit_sha"]


def test_create_service_dry_run_plus_execute_git_rejected(tmp_path):
    """AC-8: Passing both --dry-run and --execute-governance-git must be rejected without file writes."""
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-service",
            "--governance-repo", str(gov),
            "--domain", "platform",
            "--service", "auth",
            "--personal-folder", str(personal),
            "--dry-run",
            "--execute-governance-git",
        ]
    )
    assert completed.returncode == 1
    assert payload["status"] == "fail"
    # No files must have been written
    assert not (gov / "features" / "platform" / "auth" / "service.yaml").exists()
    assert not (personal / "context.yaml").exists()


# ---------------------------------------------------------------------------
# NS-2: Service-not-feature boundary tests
# ---------------------------------------------------------------------------


def test_create_service_does_not_create_feature_yaml(tmp_path):
    """NS-2 AC-1: create-service must not create feature.yaml."""
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    run_script(
        [
            "create-service",
            "--governance-repo", str(gov),
            "--domain", "platform",
            "--service", "auth",
            "--personal-folder", str(personal),
        ]
    )
    # Walk entire gov tree looking for any feature.yaml
    feature_yamls = list(gov.rglob("feature.yaml"))
    assert not feature_yamls, f"feature.yaml must not be created: {feature_yamls}"


def test_create_service_does_not_create_summary_md(tmp_path):
    """NS-2 AC-2: create-service must not create summary.md."""
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    run_script(
        [
            "create-service",
            "--governance-repo", str(gov),
            "--domain", "platform",
            "--service", "auth",
            "--personal-folder", str(personal),
        ]
    )
    summaries = list(gov.rglob("summary.md"))
    assert not summaries, f"summary.md must not be created: {summaries}"


def test_create_service_does_not_create_feature_index_entry(tmp_path):
    """NS-2 AC-3: create-service must not create or modify feature-index.yaml."""
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    run_script(
        [
            "create-service",
            "--governance-repo", str(gov),
            "--domain", "platform",
            "--service", "auth",
            "--personal-folder", str(personal),
        ]
    )
    assert not (gov / "feature-index.yaml").exists(), "feature-index.yaml must not be created"


def test_create_service_does_not_create_control_branches(tmp_path):
    """NS-2 AC-4: create-service must not create control-repo branches."""
    gov = make_gov_repo(tmp_path)
    personal = tmp_path / "personal"
    run_script(
        [
            "create-service",
            "--governance-repo", str(gov),
            "--domain", "platform",
            "--service", "auth",
            "--personal-folder", str(personal),
            "--execute-governance-git",
        ]
    )
    result = subprocess.run(
        ["git", "-C", str(gov), "branch", "--list"],
        capture_output=True, text=True,
    )
    branches = [b.strip().lstrip("* ") for b in result.stdout.splitlines() if b.strip()]
    feature_branches = [b for b in branches if "platform" in b and b != "main"]
    assert not feature_branches, f"No feature branches should be created: {feature_branches}"


def test_create_service_with_existing_domain_is_idempotent(tmp_path):
    """NS-2 AC-5: When the parent domain already exists, create-service must not overwrite it."""
    gov = tmp_path / "gov"
    domain_marker = gov / "features" / "platform" / "domain.yaml"
    domain_const = gov / "constitutions" / "platform" / "constitution.md"
    domain_marker.parent.mkdir(parents=True)
    domain_const.parent.mkdir(parents=True)
    domain_marker.write_text("kind: domain\nid: platform\nstatus: active\n", encoding="utf-8")
    domain_const.write_text("# Existing\n", encoding="utf-8")
    original_domain_mtime = domain_marker.stat().st_mtime
    original_const_mtime = domain_const.stat().st_mtime

    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-service",
            "--governance-repo", str(gov),
            "--domain", "platform",
            "--service", "auth",
            "--personal-folder", str(personal),
        ]
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    # Domain files must be untouched
    assert domain_marker.stat().st_mtime == original_domain_mtime, "domain.yaml must not be overwritten"
    assert domain_const.stat().st_mtime == original_const_mtime, "domain constitution must not be overwritten"
    assert payload["created_domain_marker"] is False
    assert payload["created_domain_constitution"] is False


# ---------------------------------------------------------------------------
# NS-3: Prompt and help discovery expectation checks
# ---------------------------------------------------------------------------

SCRIPT_ROOT = Path(__file__).resolve().parents[2]  # skills/lens-init-feature
MODULE_ROOT = SCRIPT_ROOT.parents[1]               # _bmad/lens-work  (parents[0]=skills, parents[1]=lens-work)


def test_release_prompt_exists():
    """NS-3 AC-1: lens-new-service release prompt must exist at expected path."""
    release_prompt = MODULE_ROOT / "prompts" / "lens-new-service.prompt.md"
    assert release_prompt.exists(), (
        f"Release prompt not found: {release_prompt}. "
        "Must be created as part of NS-9."
    )


def test_release_prompt_references_create_service_intent():
    """NS-3 AC-1b: Release prompt must reference create-service intent."""
    release_prompt = MODULE_ROOT / "prompts" / "lens-new-service.prompt.md"
    if release_prompt.exists():
        content = release_prompt.read_text(encoding="utf-8")
        assert "create-service" in content, "Release prompt must reference create-service intent"


def test_skill_md_documents_new_service_intent():
    """NS-3 AC-2: SKILL.md must document the new-service intent flow."""
    skill_md = SCRIPT_ROOT / "SKILL.md"
    assert skill_md.exists(), f"SKILL.md not found at {skill_md}"
    content = skill_md.read_text(encoding="utf-8")
    assert "new-service" in content.lower(), "SKILL.md must document new-service intent"
    assert "create-service" in content, "SKILL.md must reference create-service subcommand"
