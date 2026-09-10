"""Structural validation for the isolated general-stability trust boundary."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

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

_SELECTION_REASONS = frozenset({
    CandidateDispositionReason.SELECTED_EARLIEST,
    CandidateDispositionReason.LATER_THAN_SELECTED,
    CandidateDispositionReason.FIRST_TIMESTAMP_AMBIGUITY,
})


def _derive_follow_up_selection(
    candidate_set_ref: RecoveryAssessmentCandidateSetRef,
    records: tuple[CandidateSelectionRecord, ...],
) -> FollowUpSelectionEvidence:
    """Derive disposition, reasons and status from immutable candidate facts."""
    selectable = tuple(record for record in records
                       if record.compatibility.status is CompatibilityStatus.COMPATIBLE
                       and record.temporal_eligibility is TemporalEligibility.ELIGIBLE
                       and record.freshness is Freshness.IN_WINDOW
                       and record.candidate_ref.subject_ref == candidate_set_ref.subject_ref)
    earliest = min((record.candidate_ref.observed_at.astimezone(timezone.utc)
                    for record in selectable), default=None)
    earliest_records = tuple(record for record in selectable
                             if record.candidate_ref.observed_at.astimezone(timezone.utc) == earliest)
    ambiguous = len(earliest_records) > 1
    selected_ref = (earliest_records[0].candidate_ref
                    if len(earliest_records) == 1 else None)
    derived = []
    for record in records:
        reasons = [reason for reason in record.reasons if reason not in _SELECTION_REASONS]
        if record in earliest_records and ambiguous:
            disposition = CandidateDisposition.ELIGIBLE_NOT_SELECTED
            reasons.append(CandidateDispositionReason.FIRST_TIMESTAMP_AMBIGUITY)
        elif record.candidate_ref == selected_ref:
            disposition = CandidateDisposition.SELECTED
            reasons.append(CandidateDispositionReason.SELECTED_EARLIEST)
        elif record in selectable:
            disposition = CandidateDisposition.ELIGIBLE_NOT_SELECTED
            reasons.append(CandidateDispositionReason.LATER_THAN_SELECTED)
        else:
            disposition = CandidateDisposition.EXCLUDED
        derived.append(replace(record, disposition=disposition,
                               reasons=tuple(sorted(set(reasons), key=lambda item: item.value))))
    status = (FollowUpSelectionStatus.AMBIGUOUS if ambiguous else
              FollowUpSelectionStatus.SELECTED if selected_ref is not None else
              FollowUpSelectionStatus.NO_ELIGIBLE_CANDIDATE)
    missing = tuple(sorted({path for record in derived for path in record.missing_fields} |
                           ({"candidate_set.candidates"} if not derived else set())))
    return FollowUpSelectionEvidence(candidate_set_ref, tuple(derived), selected_ref,
                                     status, missing, ())


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
    if type(ref) is not VersionedArtifactRef:
        return (f"{name} must be a VersionedArtifactRef",)
    for field in ("artifact_type", "artifact_id", "artifact_version"):
        _text(getattr(ref, field), f"{name}.{field}", errors)
    return tuple(errors)


def validate_provenance(ref: ProvenanceRef, name="provenance_ref") -> tuple[str, ...]:
    if type(ref) is not ProvenanceRef:
        return (f"{name} must be a ProvenanceRef",)
    errors = list(validate_artifact_ref(ref.producer, f"{name}.producer"))
    for field in ("provenance_type", "provenance_id", "provenance_version"):
        _text(getattr(ref, field), f"{name}.{field}", errors)
    return tuple(errors)


def validate_assessment(value: RecoveryAssessment, name="assessment") -> tuple[str, ...]:
    errors: list[str] = []
    if type(value) is not RecoveryAssessment:
        return (f"{name} must be a RecoveryAssessment",)
    _text(value.assessment_id, f"{name}.assessment_id", errors)
    _text(value.contract_version, f"{name}.contract_version", errors)
    _text(value.subject_ref, f"{name}.subject_ref", errors)
    if type(value.analyzer_ref) is not AnalyzerRef:
        errors.append(f"{name}.analyzer_ref must be an AnalyzerRef")
    else:
        for field in ("analyzer_id", "analyzer_version", "assessment_schema_version"):
            _text(getattr(value.analyzer_ref, field), f"{name}.analyzer_ref.{field}", errors, nullable=True)
    _datetime(value.observed_at, f"{name}.observed_at", errors)
    _datetime(value.assessed_at, f"{name}.assessed_at", errors)
    if aware(value.observed_at) and aware(value.assessed_at) and value.observed_at > value.assessed_at:
        errors.append(f"{name}.observed_at must not follow assessed_at")
    if value.category_missingness is CategoryMissingness.NOT_MISSING:
        if type(value.category) is not RecoveryCategory:
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


def validate_assessment_ref(value: RecoveryAssessmentRef, name="assessment_ref") -> tuple[str, ...]:
    if type(value) is not RecoveryAssessmentRef:
        return (f"{name} must be a RecoveryAssessmentRef",)
    errors: list[str] = []
    _text(value.assessment_id, f"{name}.assessment_id", errors)
    _text(value.contract_version, f"{name}.contract_version", errors)
    _text(value.subject_ref, f"{name}.subject_ref", errors)
    _datetime(value.observed_at, f"{name}.observed_at", errors)
    _datetime(value.assessed_at, f"{name}.assessed_at", errors)
    if type(value.analyzer_ref) is not AnalyzerRef:
        errors.append(f"{name}.analyzer_ref must be an AnalyzerRef")
    else:
        for field in ("analyzer_id", "analyzer_version", "assessment_schema_version"):
            _text(getattr(value.analyzer_ref, field), f"{name}.analyzer_ref.{field}",
                  errors, nullable=True)
    return tuple(errors)


def validate_general_stability_input(value: GeneralStabilityInput) -> tuple[str, ...]:
    errors: list[str] = []
    if type(value) is not GeneralStabilityInput:
        return ("input must be GeneralStabilityInput",)
    if (value.contract_version, value.policy_id, value.policy_version) != (
            STABILITY_CONTRACT_VERSION, STABILITY_POLICY_ID, STABILITY_POLICY_VERSION):
        errors.append("stability contract and policy versions must be exact")
    _datetime(value.evaluated_at, "evaluated_at", errors)
    errors.extend(validate_provenance(value.provenance_ref))

    binding = value.prescription_binding
    binding_valid = type(binding) is PrescriptionBaselineBinding
    if not binding_valid:
        errors.append("prescription_binding must be a PrescriptionBaselineBinding")
    else:
        for ref, name in ((binding.prescription_snapshot_ref, "prescription_snapshot_ref"),
                          (binding.decision_ref, "decision_ref"),
                          (binding.baseline_use_attestation_ref, "baseline_use_attestation_ref")):
            errors.extend(validate_artifact_ref(ref, name))
        if binding.baseline_assessment_ref is not None:
            errors.extend(validate_assessment_ref(binding.baseline_assessment_ref,
                                                  "baseline_assessment_ref"))
        errors.extend(validate_provenance(binding.provenance_ref, "prescription_binding.provenance_ref"))
        _text(binding.subject_ref, "prescription_binding.subject_ref", errors)
        _datetime(binding.prescription_communicated_at, "prescription_communicated_at", errors)

    session = value.actual_session_boundary
    session_valid = type(session) is ActualSessionBoundary
    if not session_valid:
        errors.append("actual_session_boundary must be an ActualSessionBoundary")
    else:
        errors.extend(validate_artifact_ref(session.actual_session_ref, "actual_session_ref"))
        _text(session.subject_ref, "actual_session_boundary.subject_ref", errors)
        _datetime(session.session_end, "session_end", errors, nullable=True)
        if session.provenance_ref is not None:
            errors.extend(validate_provenance(session.provenance_ref, "actual_session_boundary.provenance_ref"))

    candidates = value.candidate_set
    candidates_valid = type(candidates) is RecoveryAssessmentCandidateSet
    valid_candidates: list[RecoveryAssessment] = []
    if not candidates_valid:
        errors.append("candidate_set must be a RecoveryAssessmentCandidateSet")
    else:
        errors.extend(validate_artifact_ref(candidates.actual_session_ref, "candidate_set.actual_session_ref"))
        errors.extend(validate_provenance(candidates.provenance_ref, "candidate_set.provenance_ref"))
        _text(candidates.subject_ref, "candidate_set.subject_ref", errors)
        _text(candidates.contract_version, "candidate_set.contract_version", errors)
        if candidates.contract_version != STABILITY_CONTRACT_VERSION:
            errors.append("candidate set contract_version is unsupported")
        _datetime(candidates.captured_at, "candidate_set.captured_at", errors)
        _datetime(candidates.evaluated_cutoff_at, "candidate_set.evaluated_cutoff_at", errors)
        if type(candidates.candidates) is not tuple:
            errors.append("candidate_set.candidates must be a tuple")
        else:
            for candidate in candidates.candidates:
                candidate_errors = validate_assessment(candidate, "candidate_set.candidates[]")
                errors.extend(candidate_errors)
                if type(candidate) is RecoveryAssessment:
                    valid_candidates.append(candidate)

    if binding_valid and session_valid and candidates_valid:
        subjects = (binding.subject_ref, session.subject_ref, candidates.subject_ref)
        if all(type(subject) is str for subject in subjects) and len(set(subjects)) != 1:
            errors.append("binding, session, and candidate set ownership must agree")
        if (type(candidates.actual_session_ref) is VersionedArtifactRef and
                type(session.actual_session_ref) is VersionedArtifactRef and
                candidates.actual_session_ref != session.actual_session_ref):
            errors.append("candidate set must reference the exact actual session")

    baseline = value.baseline_assessment
    if baseline is not None:
        errors.extend(validate_assessment(baseline, "baseline_assessment"))
        if type(baseline) is RecoveryAssessment and binding_valid and baseline.subject_ref != binding.subject_ref:
            errors.append("baseline ownership must agree")
        if (type(baseline) is RecoveryAssessment and binding_valid and
                type(binding.baseline_assessment_ref) is RecoveryAssessmentRef and
                binding.baseline_assessment_ref != RecoveryAssessmentRef(
                    baseline.assessment_id, baseline.contract_version, baseline.analyzer_ref,
                    baseline.subject_ref, baseline.observed_at, baseline.assessed_at)):
            errors.append("baseline binding ref must equal the derived baseline ref")
        if (type(baseline) is RecoveryAssessment and binding_valid and
                aware(binding.prescription_communicated_at) and aware(baseline.observed_at) and
                aware(baseline.assessed_at) and
                (baseline.observed_at > binding.prescription_communicated_at or
                 baseline.assessed_at > binding.prescription_communicated_at)):
            errors.append("baseline timestamps must not follow prescription communication")
    elif binding_valid and binding.baseline_assessment_ref is not None:
        errors.append("baseline ref is present without its assessment")

    for candidate in valid_candidates:
        if aware(candidate.assessed_at) and aware(candidates.captured_at) and candidate.assessed_at > candidates.captured_at:
            errors.append("candidate assessed_at must not follow captured_at")
        if aware(candidate.observed_at) and aware(value.evaluated_at) and candidate.observed_at > value.evaluated_at:
            errors.append("candidate observed_at must not follow evaluated_at")
        if aware(candidate.assessed_at) and aware(value.evaluated_at) and candidate.assessed_at > value.evaluated_at:
            errors.append("candidate assessed_at must not follow evaluated_at")
    if candidates_valid and aware(candidates.captured_at) and aware(value.evaluated_at) and candidates.captured_at > value.evaluated_at:
        errors.append("candidate set captured_at must not follow evaluated_at")
    if candidates_valid and candidates.evaluated_cutoff_at != value.evaluated_at:
        errors.append("candidate set cutoff must equal evaluated_at")
    if session_valid and binding_valid and session.session_end is not None and aware(session.session_end):
        if aware(binding.prescription_communicated_at) and binding.prescription_communicated_at > session.session_end:
            errors.append("prescription communication must not follow session_end")
        if aware(value.evaluated_at) and value.evaluated_at < session.session_end:
            errors.append("evaluated_at must not precede session_end")
    decision = value.next_decision_boundary
    if decision is not None:
        if type(decision) is not NextDecisionBoundary:
            errors.append("next_decision_boundary must be a NextDecisionBoundary or null")
        else:
            errors.extend(validate_artifact_ref(decision.decision_ref, "next_decision.decision_ref"))
            _text(decision.subject_ref, "next_decision.subject_ref", errors)
            _datetime(decision.decision_at, "next_decision.decision_at", errors)
            if binding_valid and decision.subject_ref != binding.subject_ref:
                errors.append("next decision ownership must agree")
            if (session_valid and session.session_end is not None and aware(session.session_end) and
                    aware(decision.decision_at) and decision.decision_at <= session.session_end):
                errors.append("next decision must be strictly after session_end")
    projection = value.reported_problems_projection
    if projection is not None:
        errors.extend(validate_projection_structure(projection))
        if type(projection) is ReportedProblemsProjectionSnapshot:
            if binding_valid and projection.subject_ref != binding.subject_ref:
                errors.append("reported problems ownership must agree")
            if session_valid and projection.actual_session_ref != session.actual_session_ref:
                errors.append("reported problems must reference the exact actual session")
    return tuple(errors)


def validate_projection_structure(value: ReportedProblemsProjectionSnapshot) -> tuple[str, ...]:
    errors: list[str] = []
    if type(value) is not ReportedProblemsProjectionSnapshot:
        return ("reported_problems_projection must be a ReportedProblemsProjectionSnapshot",)
    _text(value.projection_id, "projection_id", errors)
    _text(value.projection_version, "projection_version", errors, nullable=True)
    _text(value.projection_schema_version, "projection_schema_version", errors, nullable=True)
    _text(value.subject_ref, "projection.subject_ref", errors)
    errors.extend(validate_artifact_ref(value.actual_session_ref, "projection.actual_session_ref"))
    errors.extend(validate_provenance(value.provenance_ref, "projection.provenance_ref"))
    for field, enum_type in (
        ("projection_status", ProjectionStatus),
        ("channel_check_status", ChannelCheckStatus),
        ("result", ReportedProblemsResult),
    ):
        item = getattr(value, field)
        if item is not None and type(item) is not enum_type:
            errors.append(f"projection.{field} must be {enum_type.__name__} or null")
    if (value.reliable_canonical_safety_signal is not None and
            type(value.reliable_canonical_safety_signal) is not bool):
        errors.append("projection.reliable_canonical_safety_signal must be bool or null")
    if value.event_window is not None:
        if type(value.event_window) is not ReportedProblemsEventWindow:
            errors.append("projection.event_window must be ReportedProblemsEventWindow or null")
        else:
            _datetime(value.event_window.start_at, "projection.event_window.start_at", errors)
            _datetime(value.event_window.end_at, "projection.event_window.end_at", errors)
            for field in ("start_boundary", "end_boundary"):
                if type(getattr(value.event_window, field)) is not EventBoundary:
                    errors.append(f"projection.event_window.{field} must be EventBoundary")
    if value.event_cursor is not None:
        if type(value.event_cursor) is not ReportedProblemsEventCursor:
            errors.append("projection.event_cursor must be ReportedProblemsEventCursor or null")
        else:
            _text(value.event_cursor.event_id, "event_cursor.event_id", errors)
            if type(value.event_cursor.event_sequence) is not int or value.event_cursor.event_sequence < 0:
                errors.append("event_cursor.event_sequence must be a non-negative integer")
    if type(value.event_window) is ReportedProblemsEventWindow:
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


def _expected_compatibility(
    baseline: RecoveryAssessmentRef,
    follow_up: RecoveryAssessmentRef,
) -> tuple[CompatibilityStatus, tuple[CompatibilityFieldRecord, ...], tuple[str, ...]]:
    pairs = (
        (CompatibilityField.CONTRACT_VERSION, baseline.contract_version, follow_up.contract_version),
        (CompatibilityField.ANALYZER_ID, baseline.analyzer_ref.analyzer_id,
         follow_up.analyzer_ref.analyzer_id),
        (CompatibilityField.ANALYZER_VERSION, baseline.analyzer_ref.analyzer_version,
         follow_up.analyzer_ref.analyzer_version),
        (CompatibilityField.ASSESSMENT_SCHEMA_VERSION,
         baseline.analyzer_ref.assessment_schema_version,
         follow_up.analyzer_ref.assessment_schema_version),
        (CompatibilityField.SUBJECT_REF, baseline.subject_ref, follow_up.subject_ref),
    )
    records = tuple(CompatibilityFieldRecord(
        field,
        FieldComparison.MISSING if left is None or right is None else
        FieldComparison.EQUAL if left == right else FieldComparison.DIFFERENT,
        left, right,
    ) for field, left, right in pairs)
    status = (CompatibilityStatus.INCOMPATIBLE
              if any(record.comparison is FieldComparison.DIFFERENT for record in records)
              else CompatibilityStatus.UNDETERMINED
              if any(record.comparison is FieldComparison.MISSING for record in records)
              else CompatibilityStatus.COMPATIBLE)
    missing = []
    for record in records:
        if record.comparison is not FieldComparison.MISSING:
            continue
        if record.field is CompatibilityField.ANALYZER_ID:
            suffix = "analyzer_ref.analyzer_id"
        elif record.field is CompatibilityField.ANALYZER_VERSION:
            suffix = "analyzer_ref.analyzer_version"
        elif record.field is CompatibilityField.ASSESSMENT_SCHEMA_VERSION:
            suffix = "analyzer_ref.assessment_schema_version"
        else:
            continue
        if record.baseline_value is None:
            missing.append(f"baseline_assessment.{suffix}")
        if record.follow_up_value is None:
            missing.append(f"candidate_set.candidates[].{suffix}")
    return status, records, tuple(sorted(set(missing)))


def _validate_evaluation_compatibility(
    value: RecoveryAssessmentCompatibility,
    name: str,
) -> tuple[str, ...]:
    errors: list[str] = []
    if type(value) is not RecoveryAssessmentCompatibility:
        return (f"{name} must be a RecoveryAssessmentCompatibility",)
    errors.extend(validate_assessment_ref(value.baseline_ref, f"{name}.baseline_ref"))
    errors.extend(validate_assessment_ref(value.follow_up_ref, f"{name}.follow_up_ref"))
    if (type(value.baseline_ref) is RecoveryAssessmentRef and
            type(value.follow_up_ref) is RecoveryAssessmentRef):
        status, records, missing = _expected_compatibility(value.baseline_ref, value.follow_up_ref)
        if value.status is not status:
            errors.append(f"{name}.status does not match its refs")
        if value.field_records != records:
            errors.append(f"{name}.field_records do not match its refs")
        if value.missing_fields != missing:
            errors.append(f"{name}.missing_fields do not match its refs")
    _canonical_strings(value.missing_fields, f"{name}.missing_fields", errors, paths=True)
    _canonical_strings(value.warnings, f"{name}.warnings", errors)
    return tuple(errors)


def validate_general_stability_evaluation(
    value: GeneralStabilityEvaluation,
) -> tuple[str, ...]:
    """Validate every output invariant expressible without the discarded input payload."""
    errors: list[str] = []
    if type(value) is not GeneralStabilityEvaluation:
        return ("evaluation must be a GeneralStabilityEvaluation",)
    if (value.contract_version, value.policy_id, value.policy_version) != (
            STABILITY_CONTRACT_VERSION, STABILITY_POLICY_ID, STABILITY_POLICY_VERSION):
        errors.append("stability evaluation contract and policy versions must be exact")
    _text(value.evaluation_id, "evaluation.evaluation_id", errors)
    _text(value.subject_ref, "evaluation.subject_ref", errors)
    _datetime(value.evaluated_at, "evaluation.evaluated_at", errors)
    errors.extend(validate_provenance(value.provenance_ref, "evaluation.provenance_ref"))
    _canonical_strings(value.missing_fields, "evaluation.missing_fields", errors, paths=True)
    _canonical_strings(value.warnings, "evaluation.warnings", errors)
    if (type(value.missing_fields) is tuple and
            tuple(sorted(set(value.missing_fields))) != value.missing_fields):
        errors.append("evaluation.missing_fields must be unique and canonically ordered")
    if type(value.warnings) is tuple and tuple(sorted(set(value.warnings))) != value.warnings:
        errors.append("evaluation.warnings must be unique and canonically ordered")

    binding = value.prescription_binding
    boundary = value.actual_session_boundary
    candidate_set = value.candidate_set_ref
    selection = value.selection_evidence
    if type(binding) is not PrescriptionBaselineBinding:
        errors.append("evaluation.prescription_binding must be a PrescriptionBaselineBinding")
    else:
        for ref, name in ((binding.prescription_snapshot_ref, "prescription_snapshot_ref"),
                          (binding.decision_ref, "decision_ref"),
                          (binding.baseline_use_attestation_ref, "baseline_use_attestation_ref")):
            errors.extend(validate_artifact_ref(ref, name))
        errors.extend(validate_provenance(binding.provenance_ref, "binding.provenance_ref"))
        _datetime(binding.prescription_communicated_at, "prescription_communicated_at", errors)
        if binding.subject_ref != value.subject_ref:
            errors.append("prescription binding ownership must match evaluation")
        if binding.baseline_assessment_ref != value.baseline_ref:
            errors.append("top-level baseline ref must match prescription binding")
    if value.baseline_ref is not None:
        errors.extend(validate_assessment_ref(value.baseline_ref, "evaluation.baseline_ref"))
        if type(value.baseline_ref) is RecoveryAssessmentRef and value.baseline_ref.subject_ref != value.subject_ref:
            errors.append("baseline ownership must match evaluation")
    if type(boundary) is not ActualSessionBoundary:
        errors.append("evaluation.actual_session_boundary must be an ActualSessionBoundary")
    else:
        errors.extend(validate_artifact_ref(boundary.actual_session_ref, "actual_session_ref"))
        _datetime(boundary.session_end, "session_end", errors, nullable=True)
        if boundary.subject_ref != value.subject_ref:
            errors.append("actual session ownership must match evaluation")
        if boundary.provenance_ref is not None:
            errors.extend(validate_provenance(boundary.provenance_ref, "boundary.provenance_ref"))
    valid_occurrences = []
    if type(candidate_set) is not RecoveryAssessmentCandidateSetRef:
        errors.append("evaluation.candidate_set_ref must be a RecoveryAssessmentCandidateSetRef")
    else:
        if candidate_set.contract_version != value.contract_version:
            errors.append("candidate set contract version must match evaluation")
        if candidate_set.subject_ref != value.subject_ref:
            errors.append("candidate set ownership must match evaluation")
        if type(boundary) is ActualSessionBoundary and candidate_set.actual_session_ref != boundary.actual_session_ref:
            errors.append("candidate set must reference the exact actual session")
        _datetime(candidate_set.captured_at, "candidate_set_ref.captured_at", errors)
        _datetime(candidate_set.evaluated_cutoff_at, "candidate_set_ref.evaluated_cutoff_at", errors)
        if candidate_set.evaluated_cutoff_at != value.evaluated_at:
            errors.append("candidate set cutoff must match evaluation timestamp")
        if type(candidate_set.logical_candidates) is not tuple:
            errors.append("candidate_set_ref.logical_candidates must be a tuple")
        else:
            for occurrence in candidate_set.logical_candidates:
                if type(occurrence) is not RecoveryAssessmentCandidateOccurrence:
                    errors.append("logical candidate must be a RecoveryAssessmentCandidateOccurrence")
                else:
                    errors.extend(validate_assessment_ref(occurrence.candidate_ref, "logical candidate ref"))
                    if type(occurrence.occurrence_count) is not int or occurrence.occurrence_count < 1:
                        errors.append("logical candidate occurrence_count must be positive")
                    elif type(occurrence.candidate_ref) is RecoveryAssessmentRef:
                        valid_occurrences.append(occurrence)

    selected_records: list[CandidateSelectionRecord] = []
    valid_records: list[CandidateSelectionRecord] = []
    baseline_absent = (value.baseline_ref is None and
                       type(binding) is PrescriptionBaselineBinding and
                       binding.baseline_assessment_ref is None)
    if type(selection) is not FollowUpSelectionEvidence:
        errors.append("selection_evidence must be FollowUpSelectionEvidence")
    else:
        if selection.candidate_set_ref != candidate_set:
            errors.append("selection candidate-set ref must equal top-level candidate-set ref")
        if selection.selected_follow_up_ref != value.selected_follow_up_ref:
            errors.append("selection selected ref must equal top-level selected ref")
        _canonical_strings(selection.missing_fields, "selection.missing_fields", errors, paths=True)
        _canonical_strings(selection.warnings, "selection.warnings", errors)
        occurrences = {item.candidate_ref: item.occurrence_count for item in valid_occurrences}
        records = selection.records if type(selection.records) is tuple else ()
        if type(selection.records) is not tuple:
            errors.append("selection.records must be a tuple")
        elif not baseline_absent and (len(records) != len(occurrences) or {
                record.candidate_ref for record in records
                if type(record) is CandidateSelectionRecord and
                type(record.candidate_ref) is RecoveryAssessmentRef} != set(occurrences)):
            errors.append("selection records must exactly cover logical candidates")
        for record in records:
            if type(record) is not CandidateSelectionRecord:
                errors.append("selection record must be CandidateSelectionRecord")
                continue
            errors.extend(validate_assessment_ref(record.candidate_ref, "selection candidate ref"))
            _canonical_strings(record.missing_fields, "selection record missing_fields",
                               errors, paths=True)
            _canonical_strings(record.warnings, "selection record warnings", errors)
            errors.extend(_validate_evaluation_compatibility(record.compatibility,
                                                              "selection compatibility"))
            if type(record.compatibility) is RecoveryAssessmentCompatibility:
                if record.compatibility.baseline_ref != value.baseline_ref:
                    errors.append("selection compatibility baseline ref must match top-level baseline")
                if record.compatibility.follow_up_ref != record.candidate_ref:
                    errors.append("selection compatibility follow-up ref must match candidate")
            if (type(record.candidate_ref) is RecoveryAssessmentRef and
                    record.occurrence_count != occurrences.get(record.candidate_ref)):
                errors.append("selection occurrence count must match candidate set")
            expected_record_missing = (set(record.compatibility.missing_fields)
                                       if type(record.compatibility) is RecoveryAssessmentCompatibility
                                       else set())
            reasons_valid = type(record.reasons) is tuple and all(
                type(reason) is CandidateDispositionReason for reason in record.reasons)
            if not reasons_valid:
                errors.append("selection reasons must be typed")
            if reasons_valid and CandidateDispositionReason.CATEGORY_UNAVAILABLE in record.reasons:
                expected_record_missing.add("candidate_set.candidates[].category")
            if (type(record.missing_fields) is tuple and
                    set(record.missing_fields) != expected_record_missing):
                errors.append("selection record missing fields contradict its evidence")
            eligibility_valid = type(record.temporal_eligibility) is TemporalEligibility
            freshness_valid = type(record.freshness) is Freshness
            if not eligibility_valid:
                errors.append("selection temporal eligibility is invalid")
            if not freshness_valid:
                errors.append("selection freshness is invalid")
            if (eligibility_valid and freshness_valid and
                    record.temporal_eligibility is TemporalEligibility.ELIGIBLE and
                    record.freshness is not Freshness.IN_WINDOW):
                errors.append("eligible candidate must be in-window")
            if (eligibility_valid and freshness_valid and
                    record.temporal_eligibility is TemporalEligibility.EXCLUDED and
                    record.freshness is not Freshness.OUT_OF_WINDOW):
                errors.append("excluded candidate must be out-of-window")
            if (eligibility_valid and freshness_valid and
                    record.temporal_eligibility is TemporalEligibility.UNDETERMINED and
                    record.freshness is not Freshness.UNDETERMINED):
                errors.append("undetermined temporal eligibility requires undetermined freshness")
            record_structurally_valid = (
                type(record.candidate_ref) is RecoveryAssessmentRef and
                type(record.compatibility) is RecoveryAssessmentCompatibility and
                type(record.temporal_eligibility) is TemporalEligibility and
                type(record.freshness) is Freshness and
                type(record.disposition) is CandidateDisposition and reasons_valid)
            record_structurally_valid = (record_structurally_valid and
                                         type(record.missing_fields) is tuple and
                                         type(record.warnings) is tuple and
                                         type(record.occurrence_count) is int and
                                         record.occurrence_count >= 1)
            if record_structurally_valid:
                valid_records.append(record)
            if record.disposition is CandidateDisposition.SELECTED:
                if record_structurally_valid:
                    selected_records.append(record)
                if reasons_valid and CandidateDispositionReason.SELECTED_EARLIEST not in record.reasons:
                    errors.append("selected candidate requires SELECTED_EARLIEST reason")
            elif (record.disposition is CandidateDisposition.EXCLUDED and
                  record.temporal_eligibility is TemporalEligibility.ELIGIBLE and
                  type(record.compatibility) is RecoveryAssessmentCompatibility and
                  record.compatibility.status is CompatibilityStatus.COMPATIBLE and
                  record.candidate_ref.subject_ref == value.subject_ref):
                errors.append("eligible compatible owned candidate cannot be excluded")
        if baseline_absent:
            expected_missing = ("baseline_assessment",
                                "prescription_binding.baseline_assessment_ref")
            if (records or selection.selected_follow_up_ref is not None or
                    selection.status is not FollowUpSelectionStatus.NO_ELIGIBLE_CANDIDATE or
                    selection.missing_fields != expected_missing):
                errors.append("baseline-absent selection branch is internally inconsistent")
        elif (len(valid_records) == len(records) and
              type(candidate_set) is RecoveryAssessmentCandidateSetRef and
              type(candidate_set.logical_candidates) is tuple and
              len(valid_occurrences) == len(candidate_set.logical_candidates)):
            expected_selection = _derive_follow_up_selection(candidate_set, tuple(valid_records))
            if selection != expected_selection:
                errors.append("selection evidence contradicts deterministic selection")

    selected_record = selected_records[0] if len(selected_records) == 1 else None
    if value.compatibility is not None:
        errors.extend(_validate_evaluation_compatibility(value.compatibility, "compatibility"))
    if value.selected_follow_up_ref is None:
        if value.compatibility is not None:
            errors.append("compatibility requires a selected follow-up")
    else:
        errors.extend(validate_assessment_ref(value.selected_follow_up_ref,
                                              "selected_follow_up_ref"))
        if (type(value.selected_follow_up_ref) is RecoveryAssessmentRef and
                value.selected_follow_up_ref.subject_ref != value.subject_ref):
            errors.append("selected follow-up ownership must match evaluation")
        if value.compatibility is None:
            errors.append("selected follow-up requires compatibility")
        elif type(value.compatibility) is not RecoveryAssessmentCompatibility:
            errors.append("selected follow-up requires typed compatibility")
        elif (value.compatibility.baseline_ref != value.baseline_ref or
              value.compatibility.follow_up_ref != value.selected_follow_up_ref):
            errors.append("top-level compatibility refs must match baseline and selected follow-up")
        elif selected_record is not None and value.compatibility != selected_record.compatibility:
            errors.append("top-level and selected-record compatibility must be identical")

    definitive_recovery = value.recovery_result in (StabilityResult.STABLE,
                                                     StabilityResult.DETERIORATED)
    if definitive_recovery and (
            value.baseline_ref is None or value.selected_follow_up_ref is None or
            value.compatibility is None or
            value.compatibility.status is not CompatibilityStatus.COMPATIBLE or
            selected_record is None or
            selected_record.temporal_eligibility is not TemporalEligibility.ELIGIBLE or
            selected_record.freshness is not Freshness.IN_WINDOW or
            CandidateDispositionReason.CATEGORY_UNAVAILABLE in selected_record.reasons or
            "baseline_assessment.category" in value.missing_fields or
            "candidate_set.candidates[].category" in value.missing_fields or
            "actual_session_boundary.session_end" in value.missing_fields):
        errors.append("definitive recovery requires compatible, selected, evaluable recovery evidence")
    recovery_evidence_complete = (
        value.baseline_ref is not None and value.selected_follow_up_ref is not None and
        value.compatibility is not None and
        value.compatibility.status is CompatibilityStatus.COMPATIBLE and
        selected_record is not None and
        selected_record.temporal_eligibility is TemporalEligibility.ELIGIBLE and
        selected_record.freshness is Freshness.IN_WINDOW and
        CandidateDispositionReason.CATEGORY_UNAVAILABLE not in selected_record.reasons and
        "baseline_assessment.category" not in value.missing_fields and
        "candidate_set.candidates[].category" not in value.missing_fields and
        "actual_session_boundary.session_end" not in value.missing_fields)
    if recovery_evidence_complete and value.recovery_result is StabilityResult.INSUFFICIENT_DATA:
        errors.append("complete recovery evidence cannot be INSUFFICIENT_DATA")

    reported = value.reported_problems
    if type(reported) is not ReportedProblemsEvaluation:
        errors.append("reported_problems must be ReportedProblemsEvaluation")
    else:
        _datetime(reported.cutoff_at, "reported_problems.cutoff_at", errors)
        if aware(reported.cutoff_at) and aware(value.evaluated_at) and reported.cutoff_at > value.evaluated_at:
            errors.append("reported-problems cutoff must not follow evaluation")
        _canonical_strings(reported.missing_fields, "reported_problems.missing_fields", errors, paths=True)
        _canonical_strings(reported.warnings, "reported_problems.warnings", errors)
        for ref in reported.evidence_refs if type(reported.evidence_refs) is tuple else ():
            errors.extend(validate_artifact_ref(ref, "reported_problems.evidence_refs[]"))
        if type(reported.evidence_refs) is not tuple:
            errors.append("reported_problems.evidence_refs must be a tuple")
        if reported.projection_ref is not None:
            projection = reported.projection_ref
            if type(projection) is not ReportedProblemsProjectionRef:
                errors.append("reported projection ref must be ReportedProblemsProjectionRef")
            else:
                if type(boundary) is ActualSessionBoundary and projection.actual_session_ref != boundary.actual_session_ref:
                    errors.append("reported projection must reference the exact actual session")
                if projection.subject_ref != value.subject_ref:
                    errors.append("reported projection ownership must match evaluation")
        expected_reported = (StabilityResult.STABLE
                             if reported.result is ReportedProblemsResult.NO_KNOWN_ISSUE
                             else StabilityResult.DETERIORATED
                             if reported.result is ReportedProblemsResult.ISSUE_REPORTED and reported.evidence_refs
                             else StabilityResult.INSUFFICIENT_DATA)
        if reported.stability_result is not expected_reported:
            errors.append("reported-problems stability result contradicts its evidence")
        if reported.result is ReportedProblemsResult.NO_KNOWN_ISSUE and reported.evidence_refs:
            errors.append("no-known-issue forbids safety evidence")
        if reported.stability_result is StabilityResult.STABLE and reported.missing_fields:
            errors.append("stable reported problems cannot contain missing fields")
        if reported.projection_ref is None and (
                reported.result is not ReportedProblemsResult.INSUFFICIENT_DATA or
                "reported_problems_projection" not in reported.missing_fields):
            errors.append("missing projection ref requires explicit insufficient data")

    required_missing = set(selection.missing_fields if type(selection) is FollowUpSelectionEvidence else ())
    if type(reported) is ReportedProblemsEvaluation:
        required_missing.update(reported.missing_fields)
    if value.baseline_ref is None:
        required_missing.update(("prescription_binding.baseline_assessment_ref",
                                 "baseline_assessment"))
    if type(boundary) is ActualSessionBoundary and boundary.session_end is None:
        required_missing.add("actual_session_boundary.session_end")
    if (type(value.missing_fields) is tuple and
            not required_missing.issubset(value.missing_fields)):
        errors.append("top-level missing fields must include dimension and selection missingness")

    if value.performance_applicability is not PerformanceApplicability.NOT_APPLICABLE:
        errors.append("performance must be NOT_APPLICABLE")
    if type(value.recovery_result) is StabilityResult and type(reported) is ReportedProblemsEvaluation:
        expected_overall = (StabilityResult.DETERIORATED
                            if StabilityResult.DETERIORATED in
                            (value.recovery_result, reported.stability_result)
                            else StabilityResult.INSUFFICIENT_DATA
                            if StabilityResult.INSUFFICIENT_DATA in
                            (value.recovery_result, reported.stability_result)
                            else StabilityResult.STABLE)
        if value.overall is not expected_overall:
            errors.append("stability overall contradicts its required dimensions")
    return tuple(errors)
