"""Pure validation boundary for future subject-scoped runtime matching.

This module intentionally performs no discovery, compatibility calculation,
cardinality decision, or persistence.  It only turns a complete caller-supplied
scope into a defensively copied, canonical immutable value.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .models import ActualSession, DirectIdEvidence, PrescriptionSnapshot
from .ownership import subject_ref_errors
from .validators import validate_actual_session, validate_prescription


def _utf8_errors(value: object, field: str) -> tuple[str, ...]:
    if type(value) is not str:
        return (f"{field} must be an explicit string",)
    if not value or value.isspace():
        return (f"{field} must be non-empty",)
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return (f"{field} must be valid UTF-8",)
    return ()


def _utf8_key(value: str) -> bytes:
    """Return the normative unsigned-byte ordering key (Python bytes order)."""
    return value.encode("utf-8", errors="strict")


def _nested_provenance_errors(value: object, field: str) -> tuple[str, ...]:
    """Validate keys in mappings reachable through model-supported containers."""
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_errors = _utf8_errors(key, f"{field} key")
            errors.extend(key_errors)
            nested_field = f"{field}.{key}" if not key_errors else field
            errors.extend(_nested_provenance_errors(nested, nested_field))
    elif isinstance(value, (tuple, frozenset)):
        for nested in value:
            errors.extend(_nested_provenance_errors(nested, field))
    return tuple(errors)


def _provenance_errors(value: object, field: str) -> tuple[str, ...]:
    """Require a provenance object and validate all nested object keys."""
    if not isinstance(value, Mapping):
        return (f"{field} must be a mapping",)
    return _nested_provenance_errors(value, field)


class DirectIdEvidenceIssue(str, Enum):
    """Semantic target-ID conditions reserved for the later decision layer."""

    MISSING_RETURNED_PRESCRIPTION_ID = "MISSING_RETURNED_PRESCRIPTION_ID"
    MALFORMED_RETURNED_PRESCRIPTION_ID = "MALFORMED_RETURNED_PRESCRIPTION_ID"
    DUPLICATE_ASSERTION = "DUPLICATE_ASSERTION"
    CONTRADICTORY_ASSERTIONS = "CONTRADICTORY_ASSERTIONS"


@dataclass(frozen=True)
class RuntimeMatchingScope:
    """Validated complete inputs, with no matching result or inferred evidence."""

    subject_ref: str
    snapshots: tuple[PrescriptionSnapshot, ...]
    sessions: tuple[ActualSession, ...]
    direct_id_evidence: tuple[DirectIdEvidence, ...]
    direct_id_evidence_issues: tuple[DirectIdEvidenceIssue, ...] = ()


class RuntimeMatchingScopeError(ValueError):
    """The complete input scope is structurally or authoritatively corrupt."""

    def __init__(self, errors: Iterable[str]):
        self.errors = tuple(sorted(set(errors)))
        super().__init__("; ".join(self.errors))


def _semantic_evidence_issues(
        evidence: tuple[DirectIdEvidence, ...]) -> tuple[DirectIdEvidenceIssue, ...]:
    issues: set[DirectIdEvidenceIssue] = set()
    assertions: set[tuple[str, str]] = set()
    targets_by_session: dict[str, set[str]] = {}
    for item in evidence:
        target = item.returned_prescription_id
        if target is None:
            issues.add(DirectIdEvidenceIssue.MISSING_RETURNED_PRESCRIPTION_ID)
            continue
        if _utf8_errors(target, "returned_prescription_id"):
            issues.add(DirectIdEvidenceIssue.MALFORMED_RETURNED_PRESCRIPTION_ID)
            continue
        assertion = (item.session_id, target)
        if assertion in assertions:
            issues.add(DirectIdEvidenceIssue.DUPLICATE_ASSERTION)
        assertions.add(assertion)
        targets_by_session.setdefault(item.session_id, set()).add(target)
    if any(len(targets) > 1 for targets in targets_by_session.values()):
        issues.add(DirectIdEvidenceIssue.CONTRADICTORY_ASSERTIONS)
    return tuple(sorted(issues, key=lambda issue: _utf8_key(issue.value)))


def validate_runtime_matching_scope(
        subject_ref: object,
        snapshots: Iterable[PrescriptionSnapshot],
        sessions: Iterable[ActualSession],
        direct_id_evidence: Iterable[DirectIdEvidence] = (),
) -> RuntimeMatchingScope:
    """Validate and canonicalize one complete, explicitly supplied subject scope.

    Authoritative artifact corruption raises :class:`RuntimeMatchingScopeError`.
    Problems with the optional returned prescription target are instead retained
    as semantic evidence issues; they neither create a relationship nor resolve a
    target.  In particular, workout IDs and artifact metadata are never inspected.
    """
    snapshots = tuple(snapshots)
    sessions = tuple(sessions)
    direct_id_evidence = tuple(direct_id_evidence)
    errors = list(subject_ref_errors(subject_ref))

    snapshot_ids: list[str] = []
    for index, snapshot in enumerate(snapshots):
        label = f"snapshots[{index}]"
        if not isinstance(snapshot, PrescriptionSnapshot):
            errors.append(f"{label} must be a PrescriptionSnapshot")
            continue
        errors.extend(f"{label}: {error}" for error in validate_prescription(snapshot))
        for value, field in (
                (snapshot.prescription_snapshot_id, "prescription_snapshot_id"),
                (snapshot.workout_id, "workout_id"),
                (snapshot.decision_id, "decision_id")):
            errors.extend(_utf8_errors(value, f"{label}.{field}"))
        if type(snapshot.prescription_snapshot_id) is str:
            snapshot_ids.append(snapshot.prescription_snapshot_id)
        if not subject_ref_errors(subject_ref) and not subject_ref_errors(snapshot.subject_ref):
            if snapshot.subject_ref.encode("utf-8") != subject_ref.encode("utf-8"):
                errors.append(f"{label}.subject_ref does not byte-exactly match subject_ref")

    session_ids: list[str] = []
    for index, session in enumerate(sessions):
        label = f"sessions[{index}]"
        if not isinstance(session, ActualSession):
            errors.append(f"{label} must be an ActualSession")
            continue
        errors.extend(f"{label}: {error}" for error in validate_actual_session(session))
        errors.extend(_utf8_errors(session.session_id, f"{label}.session_id"))
        if type(session.session_id) is str:
            session_ids.append(session.session_id)
        if not subject_ref_errors(subject_ref) and not subject_ref_errors(session.subject_ref):
            if session.subject_ref.encode("utf-8") != subject_ref.encode("utf-8"):
                errors.append(f"{label}.subject_ref does not byte-exactly match subject_ref")

    if len(snapshot_ids) != len(set(snapshot_ids)):
        errors.append("prescription_snapshot_id must be unique in the complete scope")
    if len(session_ids) != len(set(session_ids)):
        errors.append("session_id must be unique in the complete scope")

    evidence_ids: list[str] = []
    session_id_set = set(session_ids)
    for index, item in enumerate(direct_id_evidence):
        label = f"direct_id_evidence[{index}]"
        if not isinstance(item, DirectIdEvidence):
            errors.append(f"{label} must be DirectIdEvidence")
            continue
        errors.extend(_utf8_errors(item.evidence_id, f"{label}.evidence_id"))
        errors.extend(_utf8_errors(item.session_id, f"{label}.session_id"))
        errors.extend(_utf8_errors(item.source, f"{label}.source"))
        errors.extend(_provenance_errors(item.provenance, f"{label}.provenance"))
        if type(item.evidence_id) is str:
            evidence_ids.append(item.evidence_id)
        if type(item.session_id) is str and item.session_id not in session_id_set:
            errors.append(f"{label}.session_id is outside the complete scope")
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("evidence_id must be unique in the complete scope")

    if errors:
        raise RuntimeMatchingScopeError(errors)

    canonical_snapshots = tuple(sorted(snapshots,
                                       key=lambda item: _utf8_key(item.prescription_snapshot_id)))
    canonical_sessions = tuple(sorted(sessions, key=lambda item: _utf8_key(item.session_id)))
    canonical_evidence = tuple(sorted(
        direct_id_evidence,
        key=lambda item: (_utf8_key(item.evidence_id), _utf8_key(item.session_id),
                          _utf8_key(item.source))))
    return RuntimeMatchingScope(
        subject_ref, canonical_snapshots, canonical_sessions, canonical_evidence,
        _semantic_evidence_issues(canonical_evidence))
