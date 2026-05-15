#!/usr/bin/env python3
"""Tests for nextlens_bugfix_parser.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


TEST_FILE = Path(__file__).resolve()
SCRIPTS_DIR = TEST_FILE.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
SCRIPT = SCRIPTS_DIR / "nextlens_bugfix_parser.py"


def load_parser_module():
    spec = importlib.util.spec_from_file_location("nextlens_bugfix_parser", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def base_intake(**overrides):
    data = {
        "what_happened": "Applying a Lens patch from NextLens crashes after selecting the target tree.",
        "what_should_have_happened": "NextLens should open the patch preview and keep the session alive.",
        "chat_history": (
            "User: I selected the patch target and the panel disappeared.\n"
            "Assistant: I saw the command restart.\n"
            "User: It happens every time on the dogfood build."
        ),
    }
    data.update(overrides)
    return data


def test_complete_input_normalizes_bug_reporter_fields():
    ops = load_parser_module()

    report = ops.parse_nextlens_bugfix_intake(
        base_intake(
            severity="High",
            salmon_signal_id="SALMON-42",
            evidence_refs=["runbook://session/123", "screenshot://dogfood/error.png"],
            suspected_target_surface="TargetProjects\\nextlens\\src\\NextLens\\Runtime",
            validation_request="Confirm the fix in dogfood and run the parser regression suite.",
            operator_notes="Only seen after upgrading to the latest dogfood snapshot.",
        )
    )

    assert report.queue == "QuickDev"
    assert report.source == "nextlens-bugfix"
    assert report.namespace == "nextlens"
    assert report.title.startswith("NextLens bug:")
    assert "Actual Behavior:" in report.description
    assert "Expected Behavior:" in report.description
    assert "Observed Evidence:" in report.description
    assert "Severity: high" in report.description
    assert "Salmon Signal ID: SALMON-42" in report.description
    assert "runbook://session/123" in report.chat_evidence_reference
    assert report.to_bug_reporter_fields()["source"] == "nextlens-bugfix"
    assert report.to_bug_reporter_fields()["namespace"] == "nextlens"


@pytest.mark.parametrize("missing_field", ["what_happened", "what_should_have_happened", "chat_history"])
def test_missing_required_fields_raise_actionable_error(missing_field: str):
    ops = load_parser_module()
    intake = base_intake()
    intake[missing_field] = "   "

    with pytest.raises(Exception) as exc:
        ops.parse_nextlens_bugfix_intake(intake)

    assert missing_field in str(exc.value)
    assert "required" in str(exc.value)


def test_large_transcript_input_is_minimized_by_default():
    ops = load_parser_module()
    large_chat = "\n".join(f"User: noisy transcript line {index} with repeated detail" for index in range(1, 121))

    report = ops.parse_nextlens_bugfix_intake(base_intake(chat_history=large_chat))

    assert report.transcript_persisted is False
    assert "Raw transcript omitted by default." in report.chat_log
    assert "noisy transcript line 87" not in report.chat_log
    assert len(report.chat_log) < len(large_chat)


def test_optional_salmon_metadata_is_preserved():
    ops = load_parser_module()

    report = ops.parse_nextlens_bugfix_intake(
        base_intake(severity="critical", salmon_signal_id="SG-9001")
    )

    assert report.severity == "critical"
    assert report.salmon_signal_id == "SG-9001"
    assert "Severity: critical" in report.description
    assert "Salmon Signal ID: SG-9001" in report.description


def test_expected_and_actual_fields_map_directly():
    ops = load_parser_module()
    intake = base_intake(
        what_happened="The preview flashes and closes before rendering anything useful.",
        what_should_have_happened="The preview should remain open until the operator accepts or cancels.",
    )

    report = ops.parse_nextlens_bugfix_intake(intake)

    assert report.actual_behavior == intake["what_happened"]
    assert report.expected_behavior == intake["what_should_have_happened"]
    assert report.repro_or_evidence == report.evidence_summary


def test_transcript_minimization_prefers_evidence_reference_over_raw_log():
    ops = load_parser_module()
    chat_history = (
        "User: Step 1 open the patch tool.\n"
        "Assistant: Step 2 select the tree.\n"
        "User: Step 3 watch the tool disappear."
    )

    report = ops.parse_nextlens_bugfix_intake(
        base_intake(
            chat_history=chat_history,
            evidence_refs="artifact://transcripts/nextlens-session-17.md",
        )
    )

    assert report.chat_evidence_reference == "Evidence refs: artifact://transcripts/nextlens-session-17.md"
    assert report.chat_log != chat_history
    assert "artifact://transcripts/nextlens-session-17.md" in report.chat_log


def test_secret_like_input_is_redacted_before_durable_output():
    ops = load_parser_module()
    chat_history = (
        "User: Authorization: Bearer ghp_1234567890abcdefghijklmnopqrstuvwxyz\n"
        "Assistant: password=hunter2\n"
        "User: Here is the follow-up context."
    )

    report = ops.parse_nextlens_bugfix_intake(
        base_intake(
            what_happened="NextLens failed right after I pasted token=supersecretvalue into the prompt.",
            chat_history=chat_history,
            operator_notes="api_key: abcdefghijklmnopqrstuvwxyz",
        )
    )

    assert report.secrets_redacted is True
    assert "supersecretvalue" not in report.description
    assert "hunter2" not in report.chat_log
    assert "abcdefghijklmnopqrstuvwxyz" not in report.description
    assert "[REDACTED SECRET]" in report.description
    assert "[REDACTED SECRET]" in report.chat_log
