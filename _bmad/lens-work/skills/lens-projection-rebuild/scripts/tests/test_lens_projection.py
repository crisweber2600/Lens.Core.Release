from __future__ import annotations

import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "lens_projection.py"
SPEC = importlib.util.spec_from_file_location("lens_projection", SCRIPT_PATH)
lens_projection = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(lens_projection)


class LensProjectionTests(unittest.TestCase):
    def test_doctor_blocks_missing_parent_and_reports_unpromoted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            feature_dir = docs / "features" / "feat-one"
            feature_dir.mkdir(parents=True)
            feature_dir.joinpath("feature.md").write_text(
                "---\n"
                "stable_id: feature:one\n"
                "entity_type: feature\n"
                "title: Feature One\n"
                "status: completed\n"
                "publication_state: published\n"
                "belongs_to: service:missing\n"
                "promotion_status: pending\n"
                "updated_at: 2026-05-21\n"
                "---\n"
                "# Feature One\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(
                project_root=root,
                work_intake_path="docs/features",
                feature_archive_path="docs/features",
                landscape_root="docs",
                reporting_output_path="_bmad-output/lens",
                include_drafts=False,
                verbose=False,
            )
            result = lens_projection.run_doctor(args)
            codes = {finding["code"] for finding in result["findings"]}
            self.assertEqual(result["status"], "blocked")
            self.assertIn("missing_parent_entity", codes)
            self.assertIn("completed_unpromoted", codes)

    def test_rebuild_writes_generated_outputs_when_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service_dir = root / "docs" / "program" / "domain" / "service" / "ledger"
            service_dir.mkdir(parents=True)
            root.joinpath("docs/program/ledger").mkdir(parents=True)
            root.joinpath("docs/program/ledger/program.md").write_text(
                "---\n"
                "stable_id: program:alpha\n"
                "entity_type: program\n"
                "title: Alpha\n"
                "status: active\n"
                "publication_state: published\n"
                "updated_at: 2026-05-21\n"
                "---\n",
                encoding="utf-8",
            )
            root.joinpath("docs/program/domain/ledger").mkdir(parents=True)
            root.joinpath("docs/program/domain/ledger/domain.md").write_text(
                "---\n"
                "stable_id: domain:identity\n"
                "entity_type: domain\n"
                "title: Identity\n"
                "status: active\n"
                "publication_state: published\n"
                "belongs_to: program:alpha\n"
                "updated_at: 2026-05-21\n"
                "---\n",
                encoding="utf-8",
            )
            service_dir.joinpath("service.md").write_text(
                "---\n"
                "stable_id: service:attendance\n"
                "entity_type: service\n"
                "title: Attendance\n"
                "status: active\n"
                "publication_state: published\n"
                "belongs_to: domain:identity\n"
                "updated_at: 2026-05-21\n"
                "---\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(
                project_root=root,
                work_intake_path="docs/features",
                feature_archive_path="docs/features",
                landscape_root="docs",
                reporting_output_path="_bmad-output/lens",
                include_drafts=False,
                verbose=False,
                force=False,
            )
            exit_code, result = lens_projection.run_rebuild(args)
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["status"], "complete")
            self.assertTrue(Path(result["json_path"]).exists())
            self.assertTrue(Path(result["markdown_path"]).exists())

    def test_doctor_validates_lens_lifecycle_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            feature_dir = docs / "features" / "feat-lens"
            feature_dir.mkdir(parents=True)
            feature_dir.joinpath("feature.md").write_text(
                "---\n"
                "stable_id: feature:lens\n"
                "entity_type: feature\n"
                "title: Lens Feature\n"
                "status: in_progress\n"
                "publication_state: published\n"
                "belongs_to: service:missing\n"
                "updated_at: 2026-05-21\n"
                "lens_feature_id: feat-lens\n"
                "lens_track: quickdev\n"
                "lens_phase: preplan\n"
                "lens_docs_path: docs/features/missing\n"
                "lens_constitution_status: blocked\n"
                "---\n"
                "# Lens Feature\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(
                project_root=root,
                work_intake_path="docs/features",
                feature_archive_path="docs/features",
                landscape_root="docs",
                reporting_output_path="_bmad-output/lens",
                include_drafts=False,
                verbose=True,
            )

            result = lens_projection.run_doctor(args)
            codes = {finding["code"] for finding in result["findings"]}

            self.assertEqual(result["status"], "blocked")
            self.assertIn("lens_phase_not_in_track", codes)
            self.assertIn("lens_docs_path_missing", codes)
            self.assertIn("lens_constitution_blocked", codes)
            self.assertEqual(result["entities"][0]["lens_context"]["lens_track"], "quickdev")


if __name__ == "__main__":
    unittest.main()