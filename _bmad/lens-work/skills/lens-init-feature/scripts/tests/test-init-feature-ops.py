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
    remote, gov = init_main_repo_with_remote(tmp_path)
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
    assert completed.returncode == 0
    assert payload["status"] == "pass"
    assert payload["governance_git_executed"] is True
    assert (gov / "features" / "risk" / "domain.yaml").exists()
    status_result = subprocess.run(
        ["git", "-C", str(gov), "status", "--short"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert status_result.stdout.strip() == ""
    remote_dirty = subprocess.run(
        ["git", "--git-dir", str(remote), "show", "main:DIRTY.txt"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert remote_dirty.stdout == "dirty\n"


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


# ---------------------------------------------------------------------------
# TestCreate
# ---------------------------------------------------------------------------
class TestCreate:
    def test_create_feature_execute_governance_git_auto_syncs_dirty_repo(self, tmp_path: Path):
        remote, gov = init_main_repo_with_remote(tmp_path)
        (gov / "DIRTY.txt").write_text("dirty\n", encoding="utf-8")

        completed, payload = run_script([
            "create",
            "--governance-repo", str(gov),
            "--feature-id", "lens-dev-new-codebase-auto-sync-test",
            "--domain", "lens-dev",
            "--service", "new-codebase",
            "--name", "Auto Sync Test",
            "--track", "express",
            "--username", "testuser",
            "--execute-governance-git",
        ])

        assert completed.returncode == 0
        assert payload["status"] == "pass"
        assert payload["governance_git_executed"] is True
        status_result = subprocess.run(
            ["git", "-C", str(gov), "status", "--short"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert status_result.stdout.strip() == ""
        remote_dirty = subprocess.run(
            ["git", "--git-dir", str(remote), "show", "main:DIRTY.txt"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert remote_dirty.stdout == "dirty\n"
        remote_feature = subprocess.run(
            [
                "git",
                "--git-dir",
                str(remote),
                "show",
                "main:features/lens-dev/new-codebase/lens-dev-new-codebase-auto-sync-test/feature.yaml",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "featureId: lens-dev-new-codebase-auto-sync-test" in remote_feature.stdout

    def test_create_feature_writes_feature_yaml(self, tmp_path: Path):
        gov = tmp_path / "gov"
        gov.mkdir()
        # pre-create domain and service markers so the test doesn't need git
        (gov / "features" / "lens-dev" / "new-codebase").mkdir(parents=True)
        (gov / "features" / "lens-dev" / "domain.yaml").write_text("{}", encoding="utf-8")
        (gov / "features" / "lens-dev" / "new-codebase" / "service.yaml").write_text("{}", encoding="utf-8")

        completed, payload = run_script([
            "create",
            "--governance-repo", str(gov),
            "--feature-id", "lens-dev-new-codebase-auth-refresh",
            "--domain", "lens-dev",
            "--service", "new-codebase",
            "--name", "Auth Refresh",
            "--track", "express",
            "--username", "testuser",
        ])

        assert completed.returncode == 0
        assert payload["status"] == "pass"
        assert payload["feature_id"] == "lens-dev-new-codebase-auth-refresh"
        assert payload["feature_slug"] == "auth-refresh"
        assert payload["starting_phase"] == "expressplan"
        assert payload["index_updated"] is True
        # express track defers the planning PR
        assert payload["planning_pr_created"] is False
        assert payload["gh_commands"] == []

        fy_path = gov / "features" / "lens-dev" / "new-codebase" / "lens-dev-new-codebase-auth-refresh" / "feature.yaml"
        assert fy_path.exists()
        data = yaml.safe_load(fy_path.read_text(encoding="utf-8"))
        assert data["featureId"] == "lens-dev-new-codebase-auth-refresh"
        assert data["featureSlug"] == "auth-refresh"
        assert data["domain"] == "lens-dev"
        assert data["service"] == "new-codebase"
        assert data["track"] == "express"
        assert data["phase"] == "expressplan"
        assert data["team"] == [{"username": "testuser", "role": "lead"}]

    def test_create_feature_writes_summary_md(self, tmp_path: Path):
        gov = tmp_path / "gov"
        gov.mkdir()
        (gov / "features" / "lens-dev" / "new-codebase").mkdir(parents=True)
        (gov / "features" / "lens-dev" / "domain.yaml").write_text("{}", encoding="utf-8")
        (gov / "features" / "lens-dev" / "new-codebase" / "service.yaml").write_text("{}", encoding="utf-8")

        completed, payload = run_script([
            "create",
            "--governance-repo", str(gov),
            "--feature-id", "lens-dev-new-codebase-summary-test",
            "--domain", "lens-dev",
            "--service", "new-codebase",
            "--name", "Summary Test",
            "--track", "express",
        ])

        assert completed.returncode == 0
        summary_path = gov / "features" / "lens-dev" / "new-codebase" / "lens-dev-new-codebase-summary-test" / "summary.md"
        assert summary_path.exists()
        content = summary_path.read_text(encoding="utf-8")
        assert "featureId: lens-dev-new-codebase-summary-test" in content
        assert "status: expressplan" in content
        assert "track: express" in content

    def test_create_feature_updates_feature_index(self, tmp_path: Path):
        gov = tmp_path / "gov"
        gov.mkdir()
        (gov / "features" / "lens-dev" / "new-codebase").mkdir(parents=True)
        (gov / "features" / "lens-dev" / "domain.yaml").write_text("{}", encoding="utf-8")
        (gov / "features" / "lens-dev" / "new-codebase" / "service.yaml").write_text("{}", encoding="utf-8")

        completed, payload = run_script([
            "create",
            "--governance-repo", str(gov),
            "--feature-id", "lens-dev-new-codebase-index-test",
            "--domain", "lens-dev",
            "--service", "new-codebase",
            "--name", "Index Test",
            "--track", "quickplan",
        ])

        assert completed.returncode == 0
        index_data = yaml.safe_load((gov / "feature-index.yaml").read_text(encoding="utf-8"))
        ids = [e.get("featureId") for e in index_data["features"]]
        assert "lens-dev-new-codebase-index-test" in ids

        entry = next(e for e in index_data["features"] if e.get("featureId") == "lens-dev-new-codebase-index-test")
        assert entry["featureSlug"] == "index-test"
        assert entry["status"] == "preplan"  # quickplan track starts at preplan
        assert entry["plan_branch"] == "lens-dev-new-codebase-index-test-plan"

        # non-express track creates an immediate planning PR
        assert payload["planning_pr_created"] is True
        assert len(payload["gh_commands"]) == 1
        assert "gh pr create" in payload["gh_commands"][0]
        assert "lens-dev-new-codebase-index-test-plan" in payload["gh_commands"][0]

    def test_create_feature_dry_run_no_files_written(self, tmp_path: Path):
        gov = tmp_path / "gov"
        gov.mkdir()

        completed, payload = run_script([
            "create",
            "--governance-repo", str(gov),
            "--feature-id", "lens-dev-new-codebase-dryrun-test",
            "--domain", "lens-dev",
            "--service", "new-codebase",
            "--name", "Dry Run Test",
            "--track", "express",
            "--dry-run",
        ])

        assert completed.returncode == 0
        assert payload["status"] == "pass"
        assert payload["dry_run"] is True
        feature_yaml = gov / "features" / "lens-dev" / "new-codebase" / "lens-dev-new-codebase-dryrun-test" / "feature.yaml"
        assert not feature_yaml.exists()
        assert not (gov / "feature-index.yaml").exists()

    def test_create_feature_rejects_duplicate(self, tmp_path: Path):
        gov = tmp_path / "gov"
        gov.mkdir()
        (gov / "features" / "lens-dev" / "new-codebase").mkdir(parents=True)
        (gov / "features" / "lens-dev" / "domain.yaml").write_text("{}", encoding="utf-8")
        (gov / "features" / "lens-dev" / "new-codebase" / "service.yaml").write_text("{}", encoding="utf-8")

        args_base = [
            "create", "--governance-repo", str(gov),
            "--feature-id", "lens-dev-new-codebase-dup-test",
            "--domain", "lens-dev", "--service", "new-codebase",
            "--name", "Dup Test", "--track", "express",
        ]
        run_script(args_base)
        completed, payload = run_script(args_base)

        assert completed.returncode == 1
        assert payload["status"] == "fail"
        assert "already exists" in payload["error"]

    def test_create_feature_rejects_invalid_track(self, tmp_path: Path):
        gov = tmp_path / "gov"
        gov.mkdir()

        completed, payload = run_script([
            "create",
            "--governance-repo", str(gov),
            "--feature-id", "lens-dev-new-codebase-bad-track",
            "--domain", "lens-dev",
            "--service", "new-codebase",
            "--track", "invalid-track",
        ])

        assert completed.returncode == 1
        assert payload["status"] == "fail"
        assert "Invalid track" in payload["error"]

    def test_create_feature_auto_creates_parent_markers(self, tmp_path: Path):
        gov = tmp_path / "gov"
        gov.mkdir()
        # No domain.yaml or service.yaml pre-created

        completed, payload = run_script([
            "create",
            "--governance-repo", str(gov),
            "--feature-id", "lens-dev-new-codebase-auto-parents",
            "--domain", "lens-dev",
            "--service", "new-codebase",
            "--name", "Auto Parents Test",
            "--track", "express",
        ])

        assert completed.returncode == 0
        assert (gov / "features" / "lens-dev" / "domain.yaml").exists()
        assert (gov / "features" / "lens-dev" / "new-codebase" / "service.yaml").exists()

    def test_create_feature_express_defers_planning_pr(self, tmp_path: Path):
        gov = tmp_path / "gov"
        gov.mkdir()
        (gov / "features" / "lens-dev" / "new-codebase").mkdir(parents=True)
        (gov / "features" / "lens-dev" / "domain.yaml").write_text("{}", encoding="utf-8")
        (gov / "features" / "lens-dev" / "new-codebase" / "service.yaml").write_text("{}", encoding="utf-8")

        completed, payload = run_script([
            "create",
            "--governance-repo", str(gov),
            "--feature-id", "lens-dev-new-codebase-express-pr",
            "--domain", "lens-dev",
            "--service", "new-codebase",
            "--name", "Express PR Test",
            "--track", "express",
        ])

        assert completed.returncode == 0
        assert payload["planning_pr_created"] is False
        assert payload["gh_commands"] == []

    def test_create_feature_non_express_emits_planning_pr_command(self, tmp_path: Path):
        gov = tmp_path / "gov"
        gov.mkdir()
        (gov / "features" / "lens-dev" / "new-codebase").mkdir(parents=True)
        (gov / "features" / "lens-dev" / "domain.yaml").write_text("{}", encoding="utf-8")
        (gov / "features" / "lens-dev" / "new-codebase" / "service.yaml").write_text("{}", encoding="utf-8")

        for non_express_track in ("quickplan", "full", "hotfix", "tech-change"):
            fid = f"lens-dev-new-codebase-pr-{non_express_track}"
            completed, payload = run_script([
                "create",
                "--governance-repo", str(gov),
                "--feature-id", fid,
                "--domain", "lens-dev",
                "--service", "new-codebase",
                "--name", f"PR test {non_express_track}",
                "--track", non_express_track,
            ])

            assert completed.returncode == 0, f"track={non_express_track}: {payload.get('error')}"
            assert payload["planning_pr_created"] is True, f"track={non_express_track}"
            assert len(payload["gh_commands"]) == 1, f"track={non_express_track}"
            cmd = payload["gh_commands"][0]
            assert "gh pr create" in cmd, f"track={non_express_track}"
            assert f"{fid}-plan" in cmd, f"track={non_express_track}"

    def test_create_feature_index_failure_rolls_back_files(self, tmp_path: Path):
        """If feature-index.yaml write fails, written feature.yaml/summary.md are removed."""
        gov = tmp_path / "gov"
        gov.mkdir()
        # Pre-create all sub-directories the script needs so their writes succeed
        (gov / "features" / "lens-dev" / "new-codebase").mkdir(parents=True)
        (gov / "features" / "lens-dev" / "domain.yaml").write_text("{}", encoding="utf-8")
        (gov / "features" / "lens-dev" / "new-codebase" / "service.yaml").write_text("{}", encoding="utf-8")

        # Make gov/ read-only: atomic_write_yaml for feature-index.yaml creates a temp file
        # in gov/ and then renames it — both operations fail when gov/ is not writable.
        # Sub-directories (features/…) retain their default writable permissions so
        # feature.yaml and summary.md are written first, then the rollback code removes them.
        gov.chmod(0o555)
        try:
            completed, payload = run_script([
                "create",
                "--governance-repo", str(gov),
                "--feature-id", "lens-dev-new-codebase-rollback-test",
                "--domain", "lens-dev",
                "--service", "new-codebase",
                "--name", "Rollback Test",
                "--track", "express",
            ])

            assert completed.returncode == 1
            assert payload["status"] == "fail"
            assert "feature-index.yaml" in payload["error"]
            # feature.yaml and summary.md must have been rolled back
            feature_dir = gov / "features" / "lens-dev" / "new-codebase" / "lens-dev-new-codebase-rollback-test"
            assert not (feature_dir / "feature.yaml").exists()
            assert not (feature_dir / "summary.md").exists()
        finally:
            gov.chmod(0o755)  # Restore write permission for tmp_path cleanup
