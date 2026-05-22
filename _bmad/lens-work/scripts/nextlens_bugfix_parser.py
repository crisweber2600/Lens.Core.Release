#!/usr/bin/env python3
"""
Normalize /lens-nextlens-bugfix intake into governed bug-reporter fields.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from typing import Any, Mapping

from bugbash_schema import SchemaValidationError

NEXTLENS_SOURCE = "nextlens-bugfix"
NEXTLENS_QUEUE = "QuickDev"
NEXTLENS_NAMESPACE = "nextlens"

_REQUIRED_FIELDS: tuple[str, ...] = (
    "what_happened",
    "what_should_have_happened",
    "chat_history",
)
_OPTIONAL_TEXT_FIELDS: tuple[str, ...] = (
    "severity",
    "salmon_signal_id",
    "suspected_target_surface",
    "validation_request",
    "operator_notes",
)
_SECRET_PLACEHOLDER = "[REDACTED SECRET]"
_DEFAULT_EVIDENCE_REFERENCE = "Transcript summary only; raw chat history omitted by default."
_TITLE_WIDTH = 72
_SNIPPET_WIDTH = 140
_MAX_CHAT_SNIPPETS = 3

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str | Any], ...] = (
    (
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.IGNORECASE,
        ),
        _SECRET_PLACEHOLDER,
    ),
    (
        re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
        _SECRET_PLACEHOLDER,
    ),
    (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        _SECRET_PLACEHOLDER,
    ),
    (
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*"),
        f"Bearer {_SECRET_PLACEHOLDER}",
    ),
    (
        re.compile(r"(?im)\b(api[_-]?key|secret|token|password)(\s*[:=]\s*)([^\s,;]+)"),
        lambda match: f"{match.group(1)}{match.group(2)}{_SECRET_PLACEHOLDER}",
    ),
)


@dataclass(frozen=True)
class NextLensBugfixReport:
    title: str
    description: str
    repro_or_evidence: str
    expected_behavior: str
    actual_behavior: str
    evidence_summary: str
    chat_evidence_reference: str
    chat_log: str
    queue: str = NEXTLENS_QUEUE
    source: str = NEXTLENS_SOURCE
    namespace: str = NEXTLENS_NAMESPACE
    severity: str | None = None
    salmon_signal_id: str | None = None
    evidence_refs: tuple[str, ...] = ()
    suspected_target_surface: str | None = None
    validation_request: str | None = None
    operator_notes: str | None = None
    transcript_persisted: bool = False
    secrets_redacted: bool = False

    def to_bug_reporter_fields(self) -> dict[str, str]:
        return {
            "title": self.title,
            "description": self.description,
            "chat_log": self.chat_log,
            "queue": self.queue,
            "source": self.source,
            "namespace": self.namespace,
        }


def parse_nextlens_bugfix_intake(intake: Mapping[str, Any]) -> NextLensBugfixReport:
    values = _validate_required_fields(intake)
    optional = {key: _normalize_optional_text(intake.get(key), key) for key in _OPTIONAL_TEXT_FIELDS}
    evidence_refs = _normalize_evidence_refs(intake.get("evidence_refs"))

    actual_behavior, actual_redacted = _sanitize_text(values["what_happened"])
    expected_behavior, expected_redacted = _sanitize_text(values["what_should_have_happened"])
    chat_history, chat_redacted = _sanitize_text(values["chat_history"])
    operator_notes, notes_redacted = _sanitize_text(optional["operator_notes"]) if optional["operator_notes"] else (None, False)
    validation_request, validation_redacted = _sanitize_text(optional["validation_request"]) if optional["validation_request"] else (None, False)
    suspected_target_surface, surface_redacted = (
        _sanitize_text(optional["suspected_target_surface"]) if optional["suspected_target_surface"] else (None, False)
    )
    severity = optional["severity"].lower() if optional["severity"] else None
    salmon_signal_id = optional["salmon_signal_id"]

    evidence_summary = _build_evidence_summary(chat_history)
    chat_evidence_reference = _build_chat_evidence_reference(evidence_refs)
    chat_log = _build_chat_log(evidence_summary, chat_evidence_reference)
    title = _build_title(actual_behavior)
    description = _build_description(
        actual_behavior=actual_behavior,
        expected_behavior=expected_behavior,
        evidence_summary=evidence_summary,
        chat_evidence_reference=chat_evidence_reference,
        severity=severity,
        salmon_signal_id=salmon_signal_id,
        evidence_refs=evidence_refs,
        suspected_target_surface=suspected_target_surface,
        validation_request=validation_request,
        operator_notes=operator_notes,
    )

    secrets_redacted = any(
        (
            actual_redacted,
            expected_redacted,
            chat_redacted,
            notes_redacted,
            validation_redacted,
            surface_redacted,
        )
    )

    return NextLensBugfixReport(
        title=title,
        description=description,
        repro_or_evidence=evidence_summary,
        expected_behavior=expected_behavior,
        actual_behavior=actual_behavior,
        evidence_summary=evidence_summary,
        chat_evidence_reference=chat_evidence_reference,
        chat_log=chat_log,
        severity=severity,
        salmon_signal_id=salmon_signal_id,
        evidence_refs=tuple(evidence_refs),
        suspected_target_surface=suspected_target_surface,
        validation_request=validation_request,
        operator_notes=operator_notes,
        transcript_persisted=False,
        secrets_redacted=secrets_redacted,
    )


def _validate_required_fields(intake: Mapping[str, Any]) -> dict[str, str]:
    errors: list[str] = []
    values: dict[str, str] = {}
    for field in _REQUIRED_FIELDS:
        value = intake.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"'{field}' is required and must be non-empty")
            continue
        values[field] = _normalize_text(value)
    if errors:
        raise SchemaValidationError(
            "NextLens bugfix intake validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
        )
    return values


def _normalize_optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SchemaValidationError(f"'{field_name}' must be a string when provided")
    normalized = _normalize_text(value)
    return normalized or None


def _normalize_evidence_refs(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = re.split(r"[\r\n,]+", value)
    elif isinstance(value, (list, tuple)):
        items = []
        for item in value:
            if not isinstance(item, str):
                raise SchemaValidationError("'evidence_refs' items must be strings")
            items.append(item)
    else:
        raise SchemaValidationError("'evidence_refs' must be a string or list of strings")

    refs: list[str] = []
    for item in items:
        normalized = _normalize_text(item)
        if normalized:
            refs.append(normalized)
    return refs


def _normalize_text(value: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _sanitize_text(value: str) -> tuple[str, bool]:
    sanitized = value
    redacted = False
    for pattern, replacement in _SECRET_PATTERNS:
        sanitized, count = pattern.subn(replacement, sanitized)
        if count:
            redacted = True
    return sanitized, redacted


def _build_title(actual_behavior: str) -> str:
    summary = textwrap.shorten(actual_behavior.replace("\n", " "), width=_TITLE_WIDTH, placeholder="...")
    return f"NextLens bug: {summary}"


def _build_evidence_summary(chat_history: str) -> str:
    lines = [line for line in chat_history.splitlines() if line.strip()]
    selected = _select_chat_snippets(lines)
    summary_lines = [
        f"Transcript digest: {len(lines)} lines across {len(chat_history)} characters.",
        "Raw transcript omitted by default.",
    ]
    summary_lines.extend(f"- {snippet}" for snippet in selected)
    return "\n".join(summary_lines)


def _select_chat_snippets(lines: list[str]) -> list[str]:
    if not lines:
        return ["No transcript content available after normalization."]

    positions = [0]
    if len(lines) > 1:
        positions.append(1)
    if len(lines) > 2:
        positions.append(len(lines) - 1)

    snippets: list[str] = []
    seen: set[str] = set()
    for position in positions:
        snippet = textwrap.shorten(lines[position], width=_SNIPPET_WIDTH, placeholder="...")
        if snippet and snippet not in seen:
            snippets.append(snippet)
            seen.add(snippet)
        if len(snippets) >= _MAX_CHAT_SNIPPETS:
            break
    return snippets


def _build_chat_evidence_reference(evidence_refs: list[str]) -> str:
    if evidence_refs:
        return "Evidence refs: " + ", ".join(evidence_refs)
    return _DEFAULT_EVIDENCE_REFERENCE


def _build_chat_log(evidence_summary: str, chat_evidence_reference: str) -> str:
    return f"{evidence_summary}\n{chat_evidence_reference}"


def _build_description(
    *,
    actual_behavior: str,
    expected_behavior: str,
    evidence_summary: str,
    chat_evidence_reference: str,
    severity: str | None,
    salmon_signal_id: str | None,
    evidence_refs: list[str],
    suspected_target_surface: str | None,
    validation_request: str | None,
    operator_notes: str | None,
) -> str:
    sections = [
        "Namespace: nextlens",
        "Source: nextlens-bugfix",
        "Queue: QuickDev",
        "",
        "Actual Behavior:",
        actual_behavior,
        "",
        "Expected Behavior:",
        expected_behavior,
        "",
        "Observed Evidence:",
        evidence_summary,
        "",
        "Chat Evidence Reference:",
        chat_evidence_reference,
    ]

    if severity:
        sections.extend(["", f"Severity: {severity}"])
    if salmon_signal_id:
        sections.extend(["", f"Salmon Signal ID: {salmon_signal_id}"])
    if evidence_refs:
        sections.extend(["", "Evidence References:", *[f"- {ref}" for ref in evidence_refs]])
    if suspected_target_surface:
        sections.extend(["", f"Suspected Target Surface: {suspected_target_surface}"])
    if validation_request:
        sections.extend(["", "Validation Request:", validation_request])
    if operator_notes:
        sections.extend(["", "Operator Notes:", operator_notes])

    return "\n".join(sections)
