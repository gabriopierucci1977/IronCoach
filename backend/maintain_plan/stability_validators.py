"""Structural validation for the isolated general-stability trust boundary."""

from __future__ import annotations

from datetime import datetime

from .stability_models import *

MISSING_PATHS = frozenset({
    "prescription_binding.baseline_assessment_ref", "baseline_assessment",
    "baseline_assessment.analyzer_ref.analyzer_id",
    "baseline_assessment.analyzer_ref.analyzer_version",
    "baseline_assessment.analyzer_ref.assessment_schema_version",
    "baseline_assessment.category", "actual_session_boundary.session_end",
    "candidate_set.candidates",
    "candidate_set.candidates[].analyzer_ref.analyzer_id",
    "candidate_set.candidates[].analyzer_ref.analyzer_version",
    "candidate_set.candidates[].analyzer_ref.assessment_schema_version",
    "candidate_set.candidates[].category", "reported_problems_projection",
    "reported_problems_projection.projection_version",
    "reported_problems_projection.projection_schema_version",
    "reported_problems_projection.projection_status",
    "reported_problems_projection.event_cursor",
    "reported_problems_projection.event_window",
    "reported_problems_projection.checked_through_at",
    "reported_problems_projection.channel_check_status",
    "reported_problems_projection.result",
    "reported_problems_projection.reliable_canonical_safety_signal",
    "reported_problems_projection.safety_signal_evidence_refs",
})


def aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _text(value: object, name: str, errors: list[str], *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if type(value) is not str or not value or value.isspace():
        errors.append(f"{name} must be a non-empty string")


def _datetime(value: object, name: str, errors: list[str], *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not aware(value):
        errors.append(f"{name} must be timezone-aware")


def _canonical_strings(values: tuple[str, ...], name: str, errors: list[str], *, paths=False) -> None:
    if type(values) is not tuple:
        errors.append(f"{name} must be a tuple")
        return
    for value in values:
        _text(value, name, errors)
        if paths and value not in MISSING_PATHS:
            errors.append(f"{name} contains an unsupported canonical path")


def validate_artifact_ref(ref: VersionedArtifactRef, name="artifact_ref") -> tuple[str, ...]:
    errors: list[str] = []
    if not isinstance(ref, VersionedArtifactRef):
        return (f"{name} must be a VersionedArtifactRef",)
    for field in ("artifact_type", "artifact_id", "artifact_version"):
        _text(getattr(ref, field), f"{name}.{field}", errors)
    return tuple(errors)


def validate_provenance(ref: ProvenanceRef, name="provenance_ref") -> tuple[str, ...]:
    errors = list(validate_artifact_ref(ref.producer, f"{name}.producer")) if isinstance(ref, ProvenanceRef) else [f"{name} must be a ProvenanceRef"]
    if isinstance(ref, ProvenanceRef):
        for field in ("provenance_type", "provenance_id", "provenance_version"):
            _text(getattr(ref, field), f"{name}.{field}", errors)
    return tuple(errors)


def validate_assessment(value: RecoveryAssessment, name="assessment") -> tuple[str, ...]:
    errors: list[str] = []
    if not isinstance(value, RecoveryAssessment):
        return (f"{name} must be a RecoveryAssessment",)
    _text(value.assessment_id, f"{name}.assessment_id", errors)
    _text(value.contract_version, f"{name}.contract_version", errors)
    _text(value.subject_ref, f"{name}.subject_ref", errors)
    if not isinstance(value.analyzer_ref, AnalyzerRef):
        errors.append(f"{name}.analyzer_ref must be an AnalyzerRef")
    else:
        for field in ("analyzer_id", "analyzer_version", "assessment_schema_version"):
            _text(getattr(value.analyzer_ref, field), f"{name}.analyzer_ref.{field}", errors, nullable=True)
    _datetime(value.observed_at, f"{name}.observed_at", errors)
    _datetime(value.assessed_at, f"{name}.assessed_at", errors)
    if aware(value.observed_at) and aware(value.assessed_at) and value.observed_at > value.assessed_at:
        errors.append(f"{name}.observed_at must not follow assessed_at")
    if value.category_missingness is CategoryMissingness.NOT_MISSING:
        if not isinstance(value.category, RecoveryCategory):
            errors.append(f"{name}.category is required when NOT_MISSING")
    elif value.category_missingness in (CategoryMissingness.MISSING, CategoryMissingness.NOT_ASSESSABLE):
        if value.category is not None:
            errors.append(f"{name}.category must be null when unavailable")
    else:
        errors.append(f"{name}.category_missingness is invalid")
    if type(value.evidence_refs) is not tuple:
        errors.append(f"{name}.evidence_refs must be a tuple")
    else:
        for ref in value.evidence_refs:
            errors.extend(validate_artifact_ref(ref, f"{name}.evidence_refs[]"))
    errors.extend(validate_provenance(value.provenance_ref, f"{name}.provenance_ref"))
    _canonical_strings(value.missing_fields, f"{name}.missing_fields", errors, paths=True)
    _canonical_strings(value.warnings, f"{name}.warnings", errors)
    return tuple(errors)


def validate_general_stability_input(value: GeneralStabilityInput) -> tuple[str, ...]:
    errors: list[str] = []
    if not isinstance(value, GeneralStabilityInput):
        return ("input must be GeneralStabilityInput",)
    if (value.contract_version, value.policy_id, value.policy_version) != (
            STABILITY_CONTRACT_VERSION, STABILITY_POLICY_ID, STABILITY_POLICY_VERSION):
        errors.append("stability contract and policy versions must be exact")
    _datetime(value.evaluated_at, "evaluated_at", errors)
    binding, session, candidates = value.prescription_binding, value.actual_session_boundary, value.candidate_set
    for ref, name in ((binding.prescription_snapshot_ref, "prescription_snapshot_ref"),
                      (binding.decision_ref, "decision_ref"),
                      (binding.baseline_use_attestation_ref, "baseline_use_attestation_ref"),
                      (session.actual_session_ref, "actual_session_ref"),
                      (candidates.actual_session_ref, "candidate_set.actual_session_ref")):
        errors.extend(validate_artifact_ref(ref, name))
    errors.extend(validate_provenance(binding.provenance_ref, "prescription_binding.provenance_ref"))
    errors.extend(validate_provenance(candidates.provenance_ref, "candidate_set.provenance_ref"))
    errors.extend(validate_provenance(value.provenance_ref))
    if session.provenance_ref is not None:
        errors.extend(validate_provenance(session.provenance_ref, "actual_session_boundary.provenance_ref"))
    subjects = (binding.subject_ref, session.subject_ref, candidates.subject_ref)
    for subject in subjects:
        _text(subject, "subject_ref", errors)
    if len(set(subjects)) != 1:
        errors.append("binding, session, and candidate set ownership must agree")
    if candidates.actual_session_ref != session.actual_session_ref:
        errors.append("candidate set must reference the exact actual session")
    if candidates.contract_version != STABILITY_CONTRACT_VERSION:
        errors.append("candidate set contract_version is unsupported")
    for stamp, name in ((binding.prescription_communicated_at, "prescription_communicated_at"),
                        (session.session_end, "session_end"), (candidates.captured_at, "candidate_set.captured_at"),
                        (candidates.evaluated_cutoff_at, "candidate_set.evaluated_cutoff_at")):
        _datetime(stamp, name, errors, nullable=name == "session_end")
    baseline = value.baseline_assessment
    if baseline is not None:
        errors.extend(validate_assessment(baseline, "baseline_assessment"))
        if baseline.subject_ref != binding.subject_ref:
            errors.append("baseline ownership must agree")
        from .general_stability_service import recovery_assessment_ref
        if (binding.baseline_assessment_ref is not None and
                binding.baseline_assessment_ref != recovery_assessment_ref(baseline)):
            errors.append("baseline binding ref must equal the derived baseline ref")
        if aware(binding.prescription_communicated_at) and (baseline.observed_at > binding.prescription_communicated_at or baseline.assessed_at > binding.prescription_communicated_at):
            errors.append("baseline timestamps must not follow prescription communication")
    elif binding.baseline_assessment_ref is not None:
        errors.append("baseline ref is present without its assessment")
    for candidate in candidates.candidates:
        errors.extend(validate_assessment(candidate, "candidate_set.candidates[]"))
        if aware(candidate.assessed_at) and aware(candidates.captured_at) and candidate.assessed_at > candidates.captured_at:
            errors.append("candidate assessed_at must not follow captured_at")
        if aware(candidate.observed_at) and aware(value.evaluated_at) and candidate.observed_at > value.evaluated_at:
            errors.append("candidate observed_at must not follow evaluated_at")
        if aware(candidate.assessed_at) and aware(value.evaluated_at) and candidate.assessed_at > value.evaluated_at:
            errors.append("candidate assessed_at must not follow evaluated_at")
    if aware(candidates.captured_at) and aware(value.evaluated_at) and candidates.captured_at > value.evaluated_at:
        errors.append("candidate set captured_at must not follow evaluated_at")
    if candidates.evaluated_cutoff_at != value.evaluated_at:
        errors.append("candidate set cutoff must equal evaluated_at")
    if session.session_end is not None and aware(session.session_end):
        if binding.prescription_communicated_at > session.session_end:
            errors.append("prescription communication must not follow session_end")
        if aware(value.evaluated_at) and value.evaluated_at < session.session_end:
            errors.append("evaluated_at must not precede session_end")
    decision = value.next_decision_boundary
    if decision is not None:
        errors.extend(validate_artifact_ref(decision.decision_ref, "next_decision.decision_ref"))
        _text(decision.subject_ref, "next_decision.subject_ref", errors)
        _datetime(decision.decision_at, "next_decision.decision_at", errors)
        if decision.subject_ref != binding.subject_ref:
            errors.append("next decision ownership must agree")
        if session.session_end is not None and aware(decision.decision_at) and decision.decision_at <= session.session_end:
            errors.append("next decision must be strictly after session_end")
    projection = value.reported_problems_projection
    if projection is not None:
        errors.extend(validate_projection_structure(projection))
        if projection.subject_ref != binding.subject_ref:
            errors.append("reported problems ownership must agree")
        if projection.actual_session_ref != session.actual_session_ref:
            errors.append("reported problems must reference the exact actual session")
    return tuple(errors)


def validate_projection_structure(value: ReportedProblemsProjectionSnapshot) -> tuple[str, ...]:
    errors: list[str] = []
    _text(value.projection_id, "projection_id", errors)
    _text(value.projection_version, "projection_version", errors, nullable=True)
    _text(value.projection_schema_version, "projection_schema_version", errors, nullable=True)
    _text(value.subject_ref, "projection.subject_ref", errors)
    errors.extend(validate_artifact_ref(value.actual_session_ref, "projection.actual_session_ref"))
    errors.extend(validate_provenance(value.provenance_ref, "projection.provenance_ref"))
    if value.event_cursor is not None:
        _text(value.event_cursor.event_id, "event_cursor.event_id", errors)
        if type(value.event_cursor.event_sequence) is not int or value.event_cursor.event_sequence < 0:
            errors.append("event_cursor.event_sequence must be a non-negative integer")
    if value.event_window is not None:
        _datetime(value.event_window.start_at, "event_window.start_at", errors)
        _datetime(value.event_window.end_at, "event_window.end_at", errors)
        if aware(value.event_window.start_at) and aware(value.event_window.end_at) and value.event_window.start_at > value.event_window.end_at:
            errors.append("event window start must not follow end")
    _datetime(value.checked_through_at, "checked_through_at", errors, nullable=True)
    if type(value.safety_signal_evidence_refs) is not tuple:
        errors.append("safety evidence refs must be a tuple")
    else:
        for ref in value.safety_signal_evidence_refs:
            errors.extend(validate_artifact_ref(ref, "safety_signal_evidence_refs[]"))
    _canonical_strings(value.missing_fields, "projection.missing_fields", errors, paths=True)
    _canonical_strings(value.warnings, "projection.warnings", errors)
    return tuple(errors)
