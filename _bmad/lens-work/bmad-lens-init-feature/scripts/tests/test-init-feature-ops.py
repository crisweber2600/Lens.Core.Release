import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "init-feature-ops.py"
EXPECTED_CONSTITUTION_BODY = """\
---
permitted_tracks: [quickplan, full, hotfix, tech-change]
required_artifacts:
  planning:
    - business-plan
  dev:
    - stories
gate_mode: informational
sensing_gate_mode: informational
additional_review_participants: []
enforce_stories: true
enforce_review: true
---

# {domain} Domain Constitution

## Scope

This constitution governs all features under the `{domain}` domain.

## Tracks

All tracks listed in `permitted_tracks` are available for features in this domain.

## Artifacts

Planning artifacts and development artifacts listed in `required_artifacts` are required for features in this domain.

## Review

Reviews are `informational`. Sensing is `informational`.

## Notes

This is an auto-generated default constitution. Edit this file to add domain-specific governance rules.
"""


def run_script(args: list[str]):
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(completed.stdout or "{}")
    return completed, payload


def init_main_repo_with_remote(base_tmp: Path) -> tuple[Path, Path]:
    remote = base_tmp / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)

    gov = base_tmp / "gov"
    subprocess.run(["git", "clone", str(remote), str(gov)], check=True)
    subprocess.run(["git", "-C", str(gov), "checkout", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(gov), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(gov), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(gov), "commit", "--allow-empty", "-m", "init"], check=True)
    subprocess.run(["git", "-C", str(gov), "push", "-u", "origin", "main"], check=True)
    return remote, gov


def assert_iso8601(value: str) -> None:
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


@pytest.mark.parametrize("slug", ["lens-dev", "platform", "my-domain-1", "a", "x" * 64])
def test_validate_safe_id_valid(tmp_path: Path, slug: str):
    gov = tmp_path / "gov"
    gov.mkdir()
    completed, payload = run_script(["create-domain", "--governance-repo", str(gov), f"--domain={slug}", "--dry-run"])
    assert completed.returncode == 0
    assert payload["status"] == "pass"


@pytest.mark.parametrize("slug", ["UPPER", "-leading", "trailing-", "has space", "a/b", "x" * 65])
def test_validate_safe_id_invalid(tmp_path: Path, slug: str):
    gov = tmp_path / "gov"
    gov.mkdir()
    completed, payload = run_script(["create-domain", "--governance-repo", str(gov), f"--domain={slug}", "--dry-run"])
    assert completed.returncode == 1
    assert payload["status"] == "fail"
    assert "Invalid domain" in payload["error"]


def test_create_domain_dry_run(tmp_path: Path):
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-domain",
            "--governance-repo",
            str(gov),
            "--domain",
            "my-domain",
            "--personal-folder",
            str(personal),
            "--dry-run",
        ]
    )
    assert completed.returncode == 0
    assert payload["status"] == "pass"
    assert payload["dry_run"] is True
    assert payload["path"]
    assert payload["constitution_path"]
    assert payload["context_path"]
    assert payload["governance_git_executed"] is False
    assert not Path(payload["path"]).exists()
    assert not Path(payload["constitution_path"]).exists()
    assert not Path(payload["context_path"]).exists()


def test_create_domain_basic(tmp_path: Path):
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-domain",
            "--governance-repo",
            str(gov),
            "--domain",
            "platform",
            "--personal-folder",
            str(personal),
        ]
    )
    assert completed.returncode == 0
    assert payload["status"] == "pass"
    assert (gov / "features" / "platform" / "domain.yaml").exists()
    assert (gov / "constitutions" / "platform" / "constitution.md").exists()
    assert (personal / "context.yaml").exists()


def test_create_domain_with_scaffolds(tmp_path: Path):
    gov = tmp_path / "gov"
    gov.mkdir()
    target = tmp_path / "target"
    docs = tmp_path / "docs"
    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-domain",
            "--governance-repo",
            str(gov),
            "--domain",
            "infra",
            "--target-projects-root",
            str(target),
            "--docs-root",
            str(docs),
            "--personal-folder",
            str(personal),
        ]
    )
    assert completed.returncode == 0
    assert payload["status"] == "pass"
    assert (target / "infra" / ".gitkeep").exists()
    assert (docs / "infra" / ".gitkeep").exists()
    assert (personal / "context.yaml").exists()
    assert payload["created_marker_paths"] == ["features/infra/domain.yaml"]
    assert payload["created_constitution_paths"] == ["constitutions/infra/constitution.md"]
    assert payload["target_projects_path"] == str(target / "infra")
    assert payload["docs_path"] == str(docs / "infra")


def test_create_domain_duplicate_fails(tmp_path: Path):
    gov = tmp_path / "gov"
    (gov / "features" / "platform").mkdir(parents=True)
    (gov / "features" / "platform" / "domain.yaml").write_text("kind: domain\n", encoding="utf-8")

    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-domain",
            "--governance-repo",
            str(gov),
            "--domain",
            "platform",
            "--personal-folder",
            str(personal),
        ]
    )
    assert completed.returncode == 1
    assert payload["status"] == "fail"
    assert "already exists" in payload["error"]
    assert not (gov / "constitutions" / "platform" / "constitution.md").exists()


def test_create_domain_execute_governance_git(tmp_path: Path):
    _, gov = init_main_repo_with_remote(tmp_path)
    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-domain",
            "--governance-repo",
            str(gov),
            "--domain",
            "finance",
            "--personal-folder",
            str(personal),
            "--execute-governance-git",
        ]
    )
    assert completed.returncode == 0
    assert payload["status"] == "pass"
    assert payload["governance_git_executed"] is True
    assert isinstance(payload["governance_commit_sha"], str)
    assert payload["governance_commit_sha"]
    assert (gov / "features" / "finance" / "domain.yaml").exists()
    assert (gov / "constitutions" / "finance" / "constitution.md").exists()


def test_create_domain_governance_git_dirty_repo(tmp_path: Path):
    _, gov = init_main_repo_with_remote(tmp_path)
    (gov / "DIRTY.txt").write_text("dirty\n", encoding="utf-8")
    personal = tmp_path / "personal"
    completed, payload = run_script(
        [
            "create-domain",
            "--governance-repo",
            str(gov),
            "--domain",
            "risk",
            "--personal-folder",
            str(personal),
            "--execute-governance-git",
        ]
    )
    assert completed.returncode == 1
    assert payload["status"] == "fail"
    assert "preflight failed" in payload["error"].lower()
    assert not (gov / "features" / "risk" / "domain.yaml").exists()


def test_domain_yaml_schema_parity(tmp_path: Path):
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    completed, _ = run_script(
        [
            "create-domain",
            "--governance-repo",
            str(gov),
            "--domain",
            "payments",
            "--personal-folder",
            str(personal),
        ]
    )
    assert completed.returncode == 0

    data = yaml.safe_load((gov / "features" / "payments" / "domain.yaml").read_text(encoding="utf-8"))
    assert set(data.keys()) == {"kind", "id", "name", "domain", "status", "owner", "created", "updated"}
    assert data["kind"] == "domain"
    assert data["id"] == "payments"
    assert data["status"] == "active"
    assert_iso8601(data["created"])
    assert_iso8601(data["updated"])


def test_constitution_content_parity(tmp_path: Path):
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    completed, _ = run_script(
        [
            "create-domain",
            "--governance-repo",
            str(gov),
            "--domain",
            "audit",
            "--personal-folder",
            str(personal),
        ]
    )
    assert completed.returncode == 0

    content = (gov / "constitutions" / "audit" / "constitution.md").read_text(encoding="utf-8")
    assert content == EXPECTED_CONSTITUTION_BODY.replace("{domain}", "audit")


def test_context_yaml_schema_parity(tmp_path: Path):
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    completed, _ = run_script(
        [
            "create-domain",
            "--governance-repo",
            str(gov),
            "--domain",
            "core",
            "--personal-folder",
            str(personal),
        ]
    )
    assert completed.returncode == 0

    data = yaml.safe_load((personal / "context.yaml").read_text(encoding="utf-8"))
    assert set(data.keys()) == {"domain", "service", "updated_at", "updated_by"}
    assert data["domain"] == "core"
    assert data["service"] is None
    assert data["updated_by"] == "new-domain"
    assert_iso8601(data["updated_at"])


def test_create_domain_name_defaults_to_slug(tmp_path: Path):
    gov = tmp_path / "gov"
    gov.mkdir()
    personal = tmp_path / "personal"
    completed, _ = run_script(
        [
            "create-domain",
            "--governance-repo",
            str(gov),
            "--domain",
            "ops",
            "--personal-folder",
            str(personal),
        ]
    )
    assert completed.returncode == 0

    data = yaml.safe_load((gov / "features" / "ops" / "domain.yaml").read_text(encoding="utf-8"))
    assert data["name"] == "ops"
