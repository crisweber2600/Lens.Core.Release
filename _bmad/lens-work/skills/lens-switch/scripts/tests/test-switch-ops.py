#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest>=8.0", "pyyaml>=6.0"]
# ///
"""Focused regression tests for switch-ops.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


SCRIPT = Path(__file__).parent.parent / "switch-ops.py"
MODULE_ROOT = SCRIPT.parents[3]
REPO_ROOT = MODULE_ROOT.parents[1]
SWITCH_SKILL = MODULE_ROOT / "skills" / "lens-switch" / "SKILL.md"
RELEASE_PROMPT = MODULE_ROOT / "prompts" / "lens-switch.prompt.md"
MODULE_HELP = MODULE_ROOT / "module-help.csv"
AGENT_MENU = MODULE_ROOT / "agents" / "lens.agent.md"


def first_existing_path(*paths: Path) -> Path:
    """Return the first existing path, or the first candidate if none exist."""
    if not paths:
        raise ValueError("first_existing_path requires at least one path")
    for path in paths:
        if path.exists():
            return path
    return paths[0]


STUB_PROMPT = first_existing_path(
    REPO_ROOT / ".github" / "prompts" / "lens-switch.prompt.md",
    REPO_ROOT / ".github" / "prompts" / "lens-new-domain.prompt.md",
    REPO_ROOT / ".github" / "prompts" / "lens-new-service.prompt.md",
)
MODULE_YAML = first_existing_path(
    MODULE_ROOT / "module.yaml",
    MODULE_HELP,
)
README = first_existing_path(
    MODULE_ROOT / "README.md",
    SWITCH_SKILL,
)


def read_text(path: Path) -> str:
    """Read repository text files as UTF-8 across platforms."""
    return path.read_text(encoding="utf-8")


def run_switch(args: list[str], cwd: Path | None = None) -> tuple[dict, int]:
    """Run switch-ops.py and return parsed JSON plus exit code."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - diagnostic path
        raise AssertionError(f"Non-JSON output\nstdout={result.stdout}\nstderr={result.stderr}") from exc
    return payload, result.returncode


def write_index(repo: Path, features: list[dict]) -> None:
    (repo / "feature-index.yaml").write_text(yaml.safe_dump({"features": features}, sort_keys=False))


def write_feature(repo: Path, domain: str, service: str, feature_id: str, data: dict) -> Path:
    feature_dir = repo / "features" / domain / service / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "feature.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    return feature_dir


def write_domain(repo: Path, domain: str, data: dict) -> None:
    domain_dir = repo / "features" / domain
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "domain.yaml").write_text(yaml.safe_dump(data, sort_keys=False))


def write_service(repo: Path, domain: str, service: str, data: dict) -> None:
    service_dir = repo / "features" / domain / service
    service_dir.mkdir(parents=True, exist_ok=True)
    (service_dir / "service.yaml").write_text(yaml.safe_dump(data, sort_keys=False))


def snapshot_files(root: Path) -> dict[str, str]:
    """Return relative file contents for no-write regression checks."""
    return {
        str(path.relative_to(root)): path.read_text()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test User"], capture_output=True, check=True)
    (path / "base.txt").write_text("base\n")
    subprocess.run(["git", "-C", str(path), "add", "base.txt"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], capture_output=True, check=True)


def create_branch(path: Path, branch: str) -> None:
    current = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(["git", "-C", str(path), "checkout", "-b", branch], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(path), "checkout", current], capture_output=True, check=True)


INDEX_ENTRIES = [
    {
        "id": "auth-login",
        "domain": "platform",
        "service": "identity",
        "status": "active",
        "owner": "cweber",
        "summary": "User authentication flow",
    },
    {
        "id": "user-profile",
        "domain": "platform",
        "service": "identity",
        "status": "businessplan-complete",
        "owner": "amelia",
        "summary": "User profile management",
    },
    {
        "id": "oauth-provider",
        "domain": "platform",
        "service": "auth",
        "status": "active",
        "owner": "cweber",
        "summary": "OAuth provider",
    },
    {
        "id": "legacy-sso",
        "domain": "platform",
        "service": "identity",
        "status": "archived",
        "owner": "cweber",
        "summary": "Old SSO integration",
    },
]

FEATURE = {
    "featureId": "auth-login",
    "name": "User Authentication",
    "domain": "platform",
    "service": "identity",
    "phase": "dev",
    "track": "quickplan",
    "priority": "high",
    "updated": "2099-01-01T00:00:00Z",
    "dependencies": {
        "related": ["user-profile", "missing-related"],
        "depends_on": ["oauth-provider"],
        "blocks": ["user-profile"],
    },
    "target_repos": [
        {
            "repo": "lens.core.src",
            "remote_url": "https://github.com/crisweber2600/lens.core.src",
            "local_path": "TargetProjects/lens-dev/new-codebase/lens.core.src",
            "dev_branch_mode": "feature-id",
            "working_branch": "feature/auth-login",
        }
    ],
}


def test_stub_preflight_then_release_prompt():
    text = read_text(STUB_PROMPT)
    preflight = "uv run _bmad/lens-work/skills/lens-preflight/scripts/light-preflight.py"
    release = "_bmad/lens-work/prompts/lens-switch.prompt.md"
    assert preflight in text
    assert release in text
    assert text.index(preflight) < text.index(release)
    assert "If that command exits non-zero, stop" in text


def test_list_features_mode_numbering_and_target_repo(tmp_path: Path):
    write_index(tmp_path, INDEX_ENTRIES)
    write_feature(tmp_path, "platform", "identity", "auth-login", FEATURE)

    payload, code = run_switch(["list", "--governance-repo", str(tmp_path)])

    assert code == 0
    assert payload["status"] == "pass"
    assert payload["mode"] == "features"
    assert payload["total"] == 3
    assert [feature["num"] for feature in payload["features"]] == [1, 2, 3]
    assert "legacy-sso" not in {feature["id"] for feature in payload["features"]}
    first = payload["features"][0]
    assert {"num", "id", "domain", "service", "status", "owner", "summary", "target_repo"} <= first.keys()
    assert first["target_repo"]["repo"] == "lens.core.src"
    assert first["target_repo"]["working_branch"] == "feature/auth-login"


def test_list_domains_mode_when_index_missing(tmp_path: Path):
    write_domain(tmp_path, "platform", {"id": "platform", "name": "Platform", "domain": "platform"})
    write_service(
        tmp_path,
        "platform",
        "identity",
        {"id": "platform-identity", "name": "Identity", "domain": "platform", "service": "identity"},
    )

    payload, code = run_switch(["list", "--governance-repo", str(tmp_path)])

    assert code == 0
    assert payload["status"] == "pass"
    assert payload["mode"] == "domains"
    assert payload["total_domains"] == 1
    assert payload["total_services"] == 1
    assert payload["domains"][0]["services"][0]["id"] == "platform-identity"


def test_config_resolution_precedence_and_missing(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    override_gov = tmp_path / "override-gov"
    config_gov = tmp_path / "config-gov"
    override_gov.mkdir()
    config_gov.mkdir()
    write_index(override_gov, [INDEX_ENTRIES[0]])
    write_index(config_gov, [INDEX_ENTRIES[1]])

    (workspace / ".lens").mkdir()
    (workspace / ".lens" / "governance-setup.yaml").write_text(
        yaml.safe_dump({"governance_repo_path": str(override_gov)})
    )
    config_dir = workspace / "_bmad" / "lens-work"
    config_dir.mkdir(parents=True)
    (config_dir / "bmadconfig.yaml").write_text(yaml.safe_dump({"governance_repo_path": str(config_gov)}))

    payload, _ = run_switch(["list", "--workspace-root", str(workspace)])
    assert [feature["id"] for feature in payload["features"]] == ["auth-login"]

    (workspace / ".lens" / "governance-setup.yaml").unlink()
    payload, _ = run_switch(["list", "--workspace-root", str(workspace)])
    assert [feature["id"] for feature in payload["features"]] == ["user-profile"]

    (config_dir / "bmadconfig.yaml").unlink()
    payload, code = run_switch(["list", "--workspace-root", str(workspace)])
    assert code == 1
    assert payload["error"] == "config_missing"
    assert "/lens-onboard" in payload["message"]


@pytest.mark.parametrize("feature_id", ["../../etc/passwd", "has spaces", "CamelCase"])
def test_switch_rejects_invalid_feature_id_before_index_read(tmp_path: Path, feature_id: str):
    payload, code = run_switch(["switch", "--governance-repo", str(tmp_path), "--feature-id", feature_id])

    assert code == 1
    assert payload["status"] == "fail"
    assert payload["error"] == "invalid_feature_id"


def test_switch_index_errors_are_structured(tmp_path: Path):
    payload, code = run_switch(["switch", "--governance-repo", str(tmp_path), "--feature-id", "auth-login"])
    assert code == 1
    assert payload["error"] == "index_not_found"

    (tmp_path / "feature-index.yaml").write_text("features: [")
    payload, code = run_switch(["switch", "--governance-repo", str(tmp_path), "--feature-id", "auth-login"])
    assert code == 1
    assert payload["error"] == "index_malformed"

    (tmp_path / "feature-index.yaml").write_text(yaml.safe_dump({"features": [{"id": "auth-login"}]}))
    payload, code = run_switch(["switch", "--governance-repo", str(tmp_path), "--feature-id", "auth-login"])
    assert code == 1
    assert payload["error"] == "index_malformed"


def test_switch_unknown_feature_fails_without_scan(tmp_path: Path):
    write_index(tmp_path, INDEX_ENTRIES)

    payload, code = run_switch(["switch", "--governance-repo", str(tmp_path), "--feature-id", "missing-feature"])

    assert code == 1
    assert payload["error"] == "feature_not_found"


def test_switch_success_full_contract_context_paths_and_context_file(tmp_path: Path):
    governance = tmp_path / "governance"
    control = tmp_path / "control"
    governance.mkdir()
    control.mkdir()
    init_git_repo(control)
    create_branch(control, "auth-login-plan")
    write_index(governance, INDEX_ENTRIES)
    feature_dir = write_feature(governance, "platform", "identity", "auth-login", FEATURE)
    summary_dir = governance / "features" / "platform" / "identity" / "user-profile"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "summary.md").write_text("# User Profile\n")
    depends_doc = control / "docs" / "platform" / "auth" / "oauth-provider"
    depends_doc.mkdir(parents=True, exist_ok=True)
    (depends_doc / "tech-plan.md").write_text("# OAuth\n")
    governance_before = snapshot_files(governance)

    payload, code = run_switch(
        [
            "switch",
            "--governance-repo",
            str(governance),
            "--feature-id",
            "auth-login",
            "--control-repo",
            str(control),
        ]
    )

    assert code == 0
    assert payload["status"] == "pass"
    assert payload["feature_id"] == "auth-login"
    assert payload["domain"] == "platform"
    assert payload["service"] == "identity"
    assert payload["phase"] == "dev"
    assert payload["track"] == "quickplan"
    assert payload["priority"] == "high"
    assert payload["owner"] == "cweber"
    assert payload["stale"] is False
    assert Path(payload["context_path"]) == feature_dir
    assert payload["target_repo_state"]["repo"] == "lens.core.src"
    assert payload["target_repo_state"]["working_branch"] == "feature/auth-login"
    assert payload["target_repo_state"]["dev_branch_mode"] == "feature-id"
    assert payload["target_repo_state"]["pr_state"] is None
    assert payload["branch_switched"] is True
    assert payload["checked_out_branch"] == "auth-login-plan"
    assert payload["branch_error"] is None

    context_file = Path(payload["personal_context_path"])
    assert context_file == control / ".lens" / "personal" / "context.yaml"
    context_data = yaml.safe_load(context_file.read_text())
    assert context_data["domain"] == "platform"
    assert context_data["service"] == "identity"
    assert context_data["updated_by"] == "lens-switch"
    assert "T" in context_data["updated_at"]
    assert context_data["feature_id"] == "auth-login"

    context_paths = payload["context_paths"]
    assert context_paths["related"][0]["id"] == "user-profile"
    assert context_paths["related"][0]["exists"] is True
    assert context_paths["related"][1] == {"id": "missing-related", "path": None, "exists": False}
    assert context_paths["depends_on"][0]["exists"] is True
    assert context_paths["blocks"][0]["exists"] is False
    assert payload["context_to_load"]["summaries"] == [context_paths["related"][0]["path"]]
    assert payload["context_to_load"]["full_docs"] == [context_paths["depends_on"][0]["path"]]

    assert snapshot_files(governance) == governance_before


def test_switch_target_repo_state_null_and_stale_true(tmp_path: Path):
    write_index(tmp_path, INDEX_ENTRIES)
    write_feature(tmp_path, "platform", "identity", "auth-login", {**FEATURE, "updated": "2020-01-01T00:00:00Z", "target_repos": []})

    payload, code = run_switch(["switch", "--governance-repo", str(tmp_path), "--feature-id", "auth-login"])

    assert code == 0
    assert payload["stale"] is True
    assert payload["target_repo_state"] is None


def test_branch_missing_reports_new_feature_guidance(tmp_path: Path):
    governance = tmp_path / "governance"
    control = tmp_path / "control"
    governance.mkdir()
    control.mkdir()
    init_git_repo(control)
    write_index(governance, INDEX_ENTRIES)
    write_feature(governance, "platform", "identity", "auth-login", FEATURE)

    payload, code = run_switch(
        ["switch", "--governance-repo", str(governance), "--feature-id", "auth-login", "--control-repo", str(control)]
    )

    assert code == 0
    assert payload["branch_switched"] is False
    assert payload["checked_out_branch"] is None
    assert payload["branch_error"] == "branch_not_found"
    assert payload["message"] == "Run /new-feature to initialize branches."


def test_branch_dirty_tree_reports_raw_git_error(tmp_path: Path):
    governance = tmp_path / "governance"
    control = tmp_path / "control"
    governance.mkdir()
    control.mkdir()
    init_git_repo(control)
    (control / "conflict.txt").write_text("main\n")
    subprocess.run(["git", "-C", str(control), "add", "conflict.txt"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(control), "commit", "-m", "add conflict"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(control), "checkout", "-b", "auth-login-plan"], capture_output=True, check=True)
    (control / "conflict.txt").write_text("plan\n")
    subprocess.run(["git", "-C", str(control), "commit", "-am", "plan conflict"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(control), "checkout", "-"], capture_output=True, check=True)
    (control / "conflict.txt").write_text("dirty\n")
    write_index(governance, INDEX_ENTRIES)
    write_feature(governance, "platform", "identity", "auth-login", FEATURE)

    payload, code = run_switch(
        ["switch", "--governance-repo", str(governance), "--feature-id", "auth-login", "--control-repo", str(control)]
    )

    assert code == 0
    assert payload["branch_switched"] is False
    assert payload["branch_error"] != "branch_not_found"
    assert "local changes" in payload["branch_error"].lower()


def test_context_paths_command_returns_exists_flags(tmp_path: Path):
    control = tmp_path / "control"
    control.mkdir()
    write_index(tmp_path, INDEX_ENTRIES)
    write_feature(tmp_path, "platform", "identity", "auth-login", FEATURE)

    payload, code = run_switch(
        [
            "context-paths",
            "--governance-repo",
            str(tmp_path),
            "--feature-id",
            "auth-login",
            "--domain",
            "platform",
            "--service",
            "identity",
            "--control-repo",
            str(control),
        ]
    )

    assert code == 0
    assert payload["status"] == "pass"
    assert set(payload["context_paths"]) == {"related", "depends_on", "blocks"}
    assert payload["context_paths"]["related"][0]["path"].endswith("summary.md")
    assert payload["context_paths"]["depends_on"][0]["path"].endswith("tech-plan.md")
    assert payload["context_paths"]["blocks"][0]["path"].endswith("tech-plan.md")


def test_switch_visible_strings_do_not_reference_deprecated_command():
    deprecated = "init" + "-feature"
    for path in (SWITCH_SKILL, RELEASE_PROMPT, STUB_PROMPT):
        assert deprecated not in read_text(path)


def test_discovery_surfaces_include_switch_consistently():
    assert "lens-switch,switch-feature,FE,Switch the active Lens feature context" in read_text(MODULE_HELP)
    assert "lens-switch.prompt.md" in read_text(MODULE_YAML)
    assert "[SW] Switch" in read_text(AGENT_MENU)
    assert "/switch" in read_text(README)


def test_skill_documents_contracts_and_focused_command():
    text = read_text(SWITCH_SKILL)
    assert "List Success - Features Mode" in text
    assert "List Success - Domains Mode" in text
    assert "Switch Success" in text
    assert "Switch Failure" in text
    assert "stale" in text and "30 days" in text
    assert "target_repo_state" in text
    assert "context_paths" in text
    assert "branch_switched" in text
    assert "uv run --with pytest _bmad/lens-work/skills/lens-switch/scripts/tests/test-switch-ops.py -q" in text


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, *sys.argv[1:]]))
