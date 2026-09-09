"""Pure deterministic MAINTAIN_PLAN general-stability evaluation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import timezone

from .stability_models import *
from .stability_validators import validate_general_stability_input


def _ref_key(ref: VersionedArtifactRef):
    return ref.artifact_type, ref.artifact_id, ref.artifact_version


def _nullable(value):
    return (0, "") if value is None else (1, value)


def recovery_ref_sort_key(ref: RecoveryAssessmentRef):
    """The normative total key; nullable values are never stringified."""
    analyzer = ref.analyzer_ref
    return (ref.observed_at.astimezone(timezone.utc), ref.assessed_at.astimezone(timezone.utc),
            ref.assessment_id, ref.contract_version, _nullable(analyzer.analyzer_id),
            _nullable(analyzer.analyzer_version), _nullable(analyzer.assessment_schema_version),
            ref.subject_ref)


def recovery_assessment_ref(value: RecoveryAssessment) -> RecoveryAssessmentRef:
    return RecoveryAssessmentRef(value.assessment_id, value.contract_version, value.analyzer_ref,
                                 value.subject_ref, value.observed_at, value.assessed_at)


def _canonical_assessment(value: RecoveryAssessment):
    return replace(value, evidence_refs=tuple(sorted(value.evidence_refs, key=_ref_key)),
                   missing_fields=tuple(sorted(set(value.missing_fields))),
                   warnings=tuple(sorted(set(value.warnings))))


def _logical_candidates(candidate_set: RecoveryAssessmentCandidateSet):
    groups = defaultdict(list)
    for candidate in candidate_set.candidates:
        groups[recovery_assessment_ref(candidate)].append(candidate)
    logical = []
    for ref, values in groups.items():
        canonical = {_canonical_assessment(item) for item in values}
        if len(canonical) != 1:
            raise ValueError("same recovery assessment identity has conflicting content")
        logical.append((ref, next(iter(canonical)), len(values)))
    return tuple(sorted(logical, key=lambda item: recovery_ref_sort_key(item[0])))


def recovery_candidate_set_ref(value: RecoveryAssessmentCandidateSet) -> RecoveryAssessmentCandidateSetRef:
    logical = _logical_candidates(value)
    return RecoveryAssessmentCandidateSetRef(
        value.contract_version, value.actual_session_ref, value.subject_ref, value.captured_at,
        value.evaluated_cutoff_at,
        tuple(RecoveryAssessmentCandidateOccurrence(ref, count) for ref, _, count in logical))


def reported_problems_projection_ref(
        value: ReportedProblemsProjectionSnapshot) -> ReportedProblemsProjectionRef | None:
    if value.projection_version is None or value.projection_schema_version is None:
        return None
    return ReportedProblemsProjectionRef(
        value.projection_id, value.projection_version, value.projection_schema_version,
        value.actual_session_ref, value.subject_ref, value.event_cursor, value.checked_through_at)


# Readable aliases for callers using the projection wording of the contract.
project_recovery_assessment_ref = recovery_assessment_ref
project_recovery_candidate_set_ref = recovery_candidate_set_ref
project_reported_problems_projection_ref = reported_problems_projection_ref


def evaluate_compatibility(baseline: RecoveryAssessmentRef,
                           follow_up: RecoveryAssessmentRef) -> RecoveryAssessmentCompatibility:
    pairs = (
        (CompatibilityField.CONTRACT_VERSION, baseline.contract_version, follow_up.contract_version, None),
        (CompatibilityField.ANALYZER_ID, baseline.analyzer_ref.analyzer_id,
         follow_up.analyzer_ref.analyzer_id, "candidate_set.candidates[].analyzer_ref.analyzer_id"),
        (CompatibilityField.ANALYZER_VERSION, baseline.analyzer_ref.analyzer_version,
         follow_up.analyzer_ref.analyzer_version, "candidate_set.candidates[].analyzer_ref.analyzer_version"),
        (CompatibilityField.ASSESSMENT_SCHEMA_VERSION, baseline.analyzer_ref.assessment_schema_version,
         follow_up.analyzer_ref.assessment_schema_version,
         "candidate_set.candidates[].analyzer_ref.assessment_schema_version"),
        (CompatibilityField.SUBJECT_REF, baseline.subject_ref, follow_up.subject_ref, None),
    )
    records, missing = [], []
    for field, left, right, path in pairs:
        comparison = (FieldComparison.MISSING if left is None or right is None else
                      FieldComparison.EQUAL if left == right else FieldComparison.DIFFERENT)
        records.append(CompatibilityFieldRecord(field, comparison, left, right))
        if comparison is FieldComparison.MISSING and path:
            missing.append(path)
    status = (CompatibilityStatus.INCOMPATIBLE
              if any(item.comparison is FieldComparison.DIFFERENT for item in records)
              else CompatibilityStatus.UNDETERMINED
              if any(item.comparison is FieldComparison.MISSING for item in records)
              else CompatibilityStatus.COMPATIBLE)
    return RecoveryAssessmentCompatibility(baseline, follow_up, status, tuple(records),
                                           tuple(sorted(set(missing))), ())


def _select(value: GeneralStabilityInput, baseline_ref: RecoveryAssessmentRef):
    logical = _logical_candidates(value.candidate_set)
    session_end = value.actual_session_boundary.session_end
    next_at = value.next_decision_boundary.decision_at if value.next_decision_boundary else None
    drafts, eligible = [], []
    for ref, assessment, count in logical:
        compatibility = evaluate_compatibility(baseline_ref, ref)
        reasons = []
        missing = list(compatibility.missing_fields)
        if count > 1:
            reasons.append(CandidateDispositionReason.DUPLICATE_IDENTICAL)
        if ref.subject_ref != value.candidate_set.subject_ref:
            reasons.append(CandidateDispositionReason.FOREIGN_SUBJECT)
        if compatibility.status is CompatibilityStatus.INCOMPATIBLE:
            reasons.append(CandidateDispositionReason.INCOMPATIBLE)
        elif compatibility.status is CompatibilityStatus.UNDETERMINED:
            reasons.append(CandidateDispositionReason.COMPATIBILITY_UNDETERMINED)
        if assessment.category is None:
            reasons.append(CandidateDispositionReason.CATEGORY_UNAVAILABLE)
            missing.append("candidate_set.candidates[].category")
        temporal = TemporalEligibility.ELIGIBLE
        freshness = Freshness.IN_WINDOW
        if session_end is None:
            temporal, freshness = TemporalEligibility.UNDETERMINED, Freshness.UNDETERMINED
        else:
            if ref.observed_at <= session_end:
                reasons.append(CandidateDispositionReason.OBSERVED_AT_OR_BEFORE_SESSION_END)
            if ref.assessed_at <= session_end:
                reasons.append(CandidateDispositionReason.ASSESSED_AT_OR_BEFORE_SESSION_END)
            if next_at is not None and ref.observed_at >= next_at:
                reasons.append(CandidateDispositionReason.OBSERVED_AT_OR_AFTER_NEXT_DECISION)
            if next_at is not None and ref.assessed_at >= next_at:
                reasons.append(CandidateDispositionReason.ASSESSED_AT_OR_AFTER_NEXT_DECISION)
            temporal_reasons = {CandidateDispositionReason.OBSERVED_AT_OR_BEFORE_SESSION_END,
                                CandidateDispositionReason.ASSESSED_AT_OR_BEFORE_SESSION_END,
                                CandidateDispositionReason.OBSERVED_AT_OR_AFTER_NEXT_DECISION,
                                CandidateDispositionReason.ASSESSED_AT_OR_AFTER_NEXT_DECISION}
            if any(reason in temporal_reasons for reason in reasons):
                temporal, freshness = TemporalEligibility.EXCLUDED, Freshness.OUT_OF_WINDOW
        can_select = (ref.subject_ref == value.candidate_set.subject_ref and
                      compatibility.status is CompatibilityStatus.COMPATIBLE and
                      temporal is TemporalEligibility.ELIGIBLE)
        if can_select:
            eligible.append(ref)
        drafts.append([ref, count, compatibility, temporal, freshness, reasons, missing, can_select])
    first = min((ref.observed_at.astimezone(timezone.utc) for ref in eligible), default=None)
    first_refs = [ref for ref in eligible if ref.observed_at.astimezone(timezone.utc) == first]
    ambiguous = len(first_refs) > 1
    selected = None if ambiguous or not first_refs else first_refs[0]
    records = []
    for ref, count, compatibility, temporal, freshness, reasons, missing, can_select in drafts:
        if can_select and ambiguous and ref in first_refs:
            disposition = CandidateDisposition.ELIGIBLE_NOT_SELECTED
            reasons.append(CandidateDispositionReason.FIRST_TIMESTAMP_AMBIGUITY)
        elif ref == selected:
            disposition = CandidateDisposition.SELECTED
            reasons.append(CandidateDispositionReason.SELECTED_EARLIEST)
        elif can_select:
            disposition = CandidateDisposition.ELIGIBLE_NOT_SELECTED
            reasons.append(CandidateDispositionReason.LATER_THAN_SELECTED)
        else:
            disposition = CandidateDisposition.EXCLUDED
        records.append(CandidateSelectionRecord(
            ref, disposition, tuple(sorted(set(reasons), key=lambda x: x.value)), compatibility,
            temporal, freshness, count, tuple(sorted(set(missing))), ()))
    status = (FollowUpSelectionStatus.AMBIGUOUS if ambiguous else
              FollowUpSelectionStatus.SELECTED if selected else
              FollowUpSelectionStatus.NO_ELIGIBLE_CANDIDATE)
    missing = () if selected else (("candidate_set.candidates",) if not logical else ())
    return FollowUpSelectionEvidence(recovery_candidate_set_ref(value.candidate_set), tuple(records),
                                     selected, status, missing, ())


def _reported(value: GeneralStabilityInput) -> ReportedProblemsEvaluation:
    session_end = value.actual_session_boundary.session_end
    decision_at = value.next_decision_boundary.decision_at if value.next_decision_boundary else None
    cutoff = decision_at if decision_at is not None and decision_at <= value.evaluated_at else value.evaluated_at
    projection = value.reported_problems_projection
    if projection is None:
        return ReportedProblemsEvaluation(None, cutoff, ReportedProblemsResult.INSUFFICIENT_DATA,
            StabilityResult.INSUFFICIENT_DATA, (), ("reported_problems_projection",), ())
    if (projection.result is ReportedProblemsResult.NO_KNOWN_ISSUE and
            (projection.reliable_canonical_safety_signal is not False or
             bool(projection.safety_signal_evidence_refs))):
        raise ValueError("NO_KNOWN_ISSUE requires false safety flag and empty evidence")
    ref = reported_problems_projection_ref(projection)
    missing = []
    for field, path in ((projection.projection_version, "reported_problems_projection.projection_version"),
                        (projection.projection_schema_version, "reported_problems_projection.projection_schema_version"),
                        (projection.projection_status, "reported_problems_projection.projection_status"),
                        (projection.event_cursor, "reported_problems_projection.event_cursor"),
                        (projection.event_window, "reported_problems_projection.event_window"),
                        (projection.checked_through_at, "reported_problems_projection.checked_through_at"),
                        (projection.channel_check_status, "reported_problems_projection.channel_check_status"),
                        (projection.result, "reported_problems_projection.result"),
                        (projection.reliable_canonical_safety_signal,
                         "reported_problems_projection.reliable_canonical_safety_signal")):
        if field is None:
            missing.append(path)
    expected_window = None if session_end is None else ReportedProblemsEventWindow(
        session_end, EventBoundary.EXCLUSIVE, cutoff,
        EventBoundary.EXCLUSIVE if decision_at is not None and decision_at <= value.evaluated_at
        else EventBoundary.INCLUSIVE)
    consumable = (not missing and projection.projection_status is ProjectionStatus.ACTIVE and
                  projection.channel_check_status is ChannelCheckStatus.VERIFIED and
                  projection.event_window == expected_window and
                  projection.checked_through_at is not None and projection.checked_through_at >= cutoff and
                  not projection.missing_fields)
    if not consumable:
        if projection.projection_status is not ProjectionStatus.ACTIVE and projection.projection_status is not None:
            missing.append("reported_problems_projection.projection_status")
        if projection.channel_check_status is not ChannelCheckStatus.VERIFIED and projection.channel_check_status is not None:
            missing.append("reported_problems_projection.channel_check_status")
        if projection.event_window != expected_window and projection.event_window is not None:
            missing.append("reported_problems_projection.event_window")
        if projection.checked_through_at is not None and projection.checked_through_at < cutoff:
            missing.append("reported_problems_projection.checked_through_at")
        missing.extend(projection.missing_fields)
        return ReportedProblemsEvaluation(ref, cutoff, ReportedProblemsResult.INSUFFICIENT_DATA,
            StabilityResult.INSUFFICIENT_DATA, (), tuple(sorted(set(missing))), tuple(sorted(set(projection.warnings))))
    result, safety, evidence = projection.result, projection.reliable_canonical_safety_signal, tuple(sorted(set(projection.safety_signal_evidence_refs), key=_ref_key))
    if result is ReportedProblemsResult.NO_KNOWN_ISSUE:
        stability = StabilityResult.STABLE
    elif result is ReportedProblemsResult.ISSUE_REPORTED and safety is True:
        if evidence:
            stability = StabilityResult.DETERIORATED
        else:
            stability = StabilityResult.INSUFFICIENT_DATA
            missing.append("reported_problems_projection.safety_signal_evidence_refs")
    else:
        stability = StabilityResult.INSUFFICIENT_DATA
    return ReportedProblemsEvaluation(ref, cutoff, result or ReportedProblemsResult.INSUFFICIENT_DATA,
                                      stability, evidence, tuple(sorted(set(missing))),
                                      tuple(sorted(set(projection.warnings))))


def evaluate_general_stability(value: GeneralStabilityInput, *, evaluation_id: str) -> GeneralStabilityEvaluation:
    """Validate completely, then return one all-or-nothing deterministic evaluation."""
    if type(evaluation_id) is not str or not evaluation_id or evaluation_id.isspace():
        raise ValueError("evaluation_id must be a non-empty string")
    errors = validate_general_stability_input(value)
    if errors:
        raise ValueError("invalid general stability input: " + "; ".join(errors))
    # Detect conflicting duplicate identities before producing any partial object.
    candidate_set_ref = recovery_candidate_set_ref(value.candidate_set)
    baseline_ref = recovery_assessment_ref(value.baseline_assessment) if value.baseline_assessment else None
    missing = []
    if value.baseline_assessment is None:
        missing.append("baseline_assessment")
    else:
        for field, path in (
            (value.baseline_assessment.analyzer_ref.analyzer_id,
             "baseline_assessment.analyzer_ref.analyzer_id"),
            (value.baseline_assessment.analyzer_ref.analyzer_version,
             "baseline_assessment.analyzer_ref.analyzer_version"),
            (value.baseline_assessment.analyzer_ref.assessment_schema_version,
             "baseline_assessment.analyzer_ref.assessment_schema_version"),
        ):
            if field is None:
                missing.append(path)
    if value.prescription_binding.baseline_assessment_ref is None:
        missing.append("prescription_binding.baseline_assessment_ref")
    if baseline_ref is None or value.prescription_binding.baseline_assessment_ref is None:
        selection = FollowUpSelectionEvidence(candidate_set_ref, (), None,
            FollowUpSelectionStatus.NO_ELIGIBLE_CANDIDATE, tuple(sorted(set(missing))), ())
        compatibility = None
        recovery = StabilityResult.INSUFFICIENT_DATA
    else:
        selection = _select(value, baseline_ref)
        compatibility = next((record.compatibility for record in selection.records
                              if record.candidate_ref == selection.selected_follow_up_ref), None)
        if selection.selected_follow_up_ref is None:
            recovery = StabilityResult.INSUFFICIENT_DATA
        else:
            selected = next(item for item in value.candidate_set.candidates
                            if recovery_assessment_ref(item) == selection.selected_follow_up_ref)
            if value.baseline_assessment.category is None:
                missing.append("baseline_assessment.category")
                recovery = StabilityResult.INSUFFICIENT_DATA
            elif selected.category is None:
                missing.append("candidate_set.candidates[].category")
                recovery = StabilityResult.INSUFFICIENT_DATA
            else:
                severity = {category: rank for rank, category in enumerate(RecoveryCategory)}
                recovery = (StabilityResult.DETERIORATED
                            if severity[selected.category] > severity[value.baseline_assessment.category]
                            else StabilityResult.STABLE)
    if value.actual_session_boundary.session_end is None:
        missing.append("actual_session_boundary.session_end")
        recovery = StabilityResult.INSUFFICIENT_DATA
    if not value.candidate_set.candidates:
        missing.append("candidate_set.candidates")
    reported = _reported(value)
    missing.extend(selection.missing_fields)
    missing.extend(reported.missing_fields)
    dimensions = (recovery, reported.stability_result)
    overall = (StabilityResult.DETERIORATED if StabilityResult.DETERIORATED in dimensions else
               StabilityResult.INSUFFICIENT_DATA if StabilityResult.INSUFFICIENT_DATA in dimensions else
               StabilityResult.STABLE)
    return GeneralStabilityEvaluation(
        evaluation_id, value.contract_version, value.policy_id, value.policy_version,
        value.evaluated_at, value.prescription_binding.subject_ref, value.prescription_binding,
        value.actual_session_boundary, baseline_ref, candidate_set_ref,
        selection.selected_follow_up_ref, compatibility, selection, recovery, reported,
        PerformanceApplicability.NOT_APPLICABLE, overall, value.provenance_ref,
        tuple(sorted(set(missing))), ())


class GeneralStabilityService:
    """Small stateless facade matching the package's service-oriented API style."""

    def evaluate(self, value: GeneralStabilityInput, *, evaluation_id: str) -> GeneralStabilityEvaluation:
        return evaluate_general_stability(value, evaluation_id=evaluation_id)
