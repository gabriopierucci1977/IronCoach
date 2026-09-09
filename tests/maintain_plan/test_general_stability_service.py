"""Synthetic contract tests for the isolated general-stability P0 service."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from itertools import permutations

import pytest

from backend.maintain_plan.general_stability_service import (
    evaluate_compatibility, evaluate_general_stability, recovery_assessment_ref,
    recovery_candidate_set_ref, reported_problems_projection_ref,
)
from backend.maintain_plan.stability_models import *

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
ART = VersionedArtifactRef("test", "one", "1")
SESSION = VersionedArtifactRef("actual-session", "session", "1")
PROV = ProvenanceRef(ART, "synthetic", "fixture", "1")
ANALYZER = AnalyzerRef("canonical-recovery", "1", "1")


def assessment(name, observed, category=RecoveryCategory.LOW, analyzer=ANALYZER, subject="athlete"):
    return RecoveryAssessment(name, STABILITY_CONTRACT_VERSION, analyzer, subject, observed,
        observed + timedelta(minutes=1), category,
        CategoryMissingness.NOT_MISSING if category else CategoryMissingness.MISSING,
        (ART,), PROV)


BASELINE = assessment("baseline", T0)


def make_input(candidates=None, projection=True, session_end=T0 + timedelta(hours=2),
               next_at=None, baseline=BASELINE):
    evaluated = T0 + timedelta(hours=8)
    candidates = candidates if candidates is not None else (assessment("follow", T0 + timedelta(hours=3)),)
    binding = PrescriptionBaselineBinding(ART, ART, "athlete", T0 + timedelta(hours=1),
        recovery_assessment_ref(baseline) if baseline else None, ART, PROV)
    boundary = ActualSessionBoundary(SESSION, "athlete", session_end, PROV)
    next_decision = NextDecisionBoundary(ART, "athlete", next_at) if next_at else None
    cutoff = next_at if next_at and next_at <= evaluated else evaluated
    window = None if session_end is None else ReportedProblemsEventWindow(
        session_end, EventBoundary.EXCLUSIVE, cutoff,
        EventBoundary.EXCLUSIVE if next_at and next_at <= evaluated else EventBoundary.INCLUSIVE)
    projection_value = (ReportedProblemsProjectionSnapshot(
        "projection", "1", "1", SESSION, "athlete", ProjectionStatus.ACTIVE,
        ReportedProblemsEventCursor("event", 1), window, cutoff, ChannelCheckStatus.VERIFIED,
        ReportedProblemsResult.NO_KNOWN_ISSUE, False, (), PROV) if projection else None)
    candidate_set = RecoveryAssessmentCandidateSet(STABILITY_CONTRACT_VERSION, SESSION, "athlete",
        evaluated, evaluated, tuple(candidates), PROV)
    return GeneralStabilityInput(STABILITY_CONTRACT_VERSION, STABILITY_POLICY_ID,
        STABILITY_POLICY_VERSION, binding, baseline, boundary, candidate_set, next_decision,
        evaluated, projection_value, PROV)


def test_contracts_are_frozen_and_tuple_inputs_are_defensively_frozen():
    value = replace(BASELINE, evidence_refs=[ART])
    assert value.evidence_refs == (ART,)
    with pytest.raises(FrozenInstanceError):
        value.assessment_id = "changed"


def test_all_three_pure_ref_projections_copy_exact_fields():
    value = make_input()
    assert recovery_assessment_ref(BASELINE).analyzer_ref is BASELINE.analyzer_ref
    assert recovery_candidate_set_ref(value.candidate_set).logical_candidates[0].occurrence_count == 1
    assert reported_problems_projection_ref(value.reported_problems_projection).event_cursor.event_id == "event"
    assert reported_problems_projection_ref(replace(value.reported_problems_projection,
                                                     projection_version=None)) is None


@pytest.mark.parametrize("analyzer,status", [
    (ANALYZER, CompatibilityStatus.COMPATIBLE),
    (replace(ANALYZER, analyzer_version="2"), CompatibilityStatus.INCOMPATIBLE),
    (replace(ANALYZER, analyzer_version=None), CompatibilityStatus.UNDETERMINED),
])
def test_compatibility_complete_matrix(analyzer, status):
    follow = assessment("f", T0 + timedelta(hours=3), analyzer=analyzer)
    result = evaluate_compatibility(recovery_assessment_ref(BASELINE), recovery_assessment_ref(follow))
    assert result.status is status
    assert tuple(record.field for record in result.field_records) == tuple(CompatibilityField)


def test_candidate_order_permutations_duplicates_and_earliest_are_deterministic():
    first = assessment("first", T0 + timedelta(hours=3))
    later = assessment("later", T0 + timedelta(hours=4))
    expected = None
    for items in permutations((later, first, first)):
        result = evaluate_general_stability(make_input(items), evaluation_id="evaluation")
        if expected is None:
            expected = result
        assert result == expected
    assert result.selected_follow_up_ref.assessment_id == "first"
    assert result.selection_evidence.records[0].occurrence_count == 2
    assert CandidateDispositionReason.DUPLICATE_IDENTICAL in result.selection_evidence.records[0].reasons


def test_conflicting_content_for_same_identity_rejects_entire_input():
    first = assessment("same", T0 + timedelta(hours=3))
    conflict = replace(first, category=RecoveryCategory.HIGH)
    with pytest.raises(ValueError, match="conflicting content"):
        evaluate_general_stability(make_input((first, conflict)), evaluation_id="evaluation")


def test_incompatible_is_excluded_but_following_compatible_is_selected():
    incompatible = assessment("bad", T0 + timedelta(hours=3), analyzer=replace(ANALYZER, analyzer_version="2"))
    compatible = assessment("good", T0 + timedelta(hours=4))
    result = evaluate_general_stability(make_input((incompatible, compatible)), evaluation_id="evaluation")
    assert result.selected_follow_up_ref.assessment_id == "good"
    assert result.selection_evidence.records[0].disposition is CandidateDisposition.EXCLUDED


def test_missing_category_is_selected_not_skipped_and_is_insufficient():
    missing = assessment("missing", T0 + timedelta(hours=3), None)
    result = evaluate_general_stability(make_input((missing, assessment("later", T0 + timedelta(hours=4)))),
                                        evaluation_id="evaluation")
    assert result.selected_follow_up_ref.assessment_id == "missing"
    assert result.recovery_result is StabilityResult.INSUFFICIENT_DATA


def test_distinct_first_timestamp_is_ambiguous_without_tie_break():
    values = (assessment("a", T0 + timedelta(hours=3)), assessment("b", T0 + timedelta(hours=3)))
    result = evaluate_general_stability(make_input(values), evaluation_id="evaluation")
    assert result.selection_evidence.status is FollowUpSelectionStatus.AMBIGUOUS
    assert result.selected_follow_up_ref is None


@pytest.mark.parametrize("hour,reason,selected", [
    (2, CandidateDispositionReason.OBSERVED_AT_OR_BEFORE_SESSION_END, False),
    (3, None, True),
])
def test_session_boundary_is_exclusive(hour, reason, selected):
    result = evaluate_general_stability(make_input((assessment("f", T0 + timedelta(hours=hour)),)),
                                        evaluation_id="evaluation")
    assert (result.selected_follow_up_ref is not None) is selected
    if reason:
        assert reason in result.selection_evidence.records[0].reasons


def test_next_decision_boundary_is_exclusive_and_evaluated_cutoff_inclusive():
    next_at = T0 + timedelta(hours=4)
    result = evaluate_general_stability(make_input(
        (assessment("at-next", next_at), assessment("at-eval", T0 + timedelta(hours=8) - timedelta(minutes=1))),
        next_at=next_at), evaluation_id="evaluation")
    assert result.selected_follow_up_ref is None
    assert all(record.disposition is CandidateDisposition.EXCLUDED for record in result.selection_evidence.records)


def test_naive_datetime_and_ownership_mismatch_are_structural_errors():
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_general_stability(replace(make_input(), evaluated_at=T0.replace(tzinfo=None)),
                                   evaluation_id="evaluation")
    wrong = replace(make_input().candidate_set, subject_ref="foreign")
    with pytest.raises(ValueError, match="ownership"):
        evaluate_general_stability(replace(make_input(), candidate_set=wrong), evaluation_id="evaluation")


def test_missing_baseline_session_and_projection_use_canonical_paths():
    result = evaluate_general_stability(make_input(projection=False, session_end=None, baseline=None),
                                        evaluation_id="evaluation")
    assert result.overall is StabilityResult.INSUFFICIENT_DATA
    assert {"baseline_assessment", "prescription_binding.baseline_assessment_ref",
            "actual_session_boundary.session_end", "reported_problems_projection"} <= set(result.missing_fields)


@pytest.mark.parametrize("result,safety,evidence,stability,invalid", [
    (ReportedProblemsResult.NO_KNOWN_ISSUE, False, (), StabilityResult.STABLE, False),
    (ReportedProblemsResult.NO_KNOWN_ISSUE, True, (ART,), None, True),
    (ReportedProblemsResult.NO_KNOWN_ISSUE, False, (ART,), None, True),
    (ReportedProblemsResult.NO_KNOWN_ISSUE, None, (), None, True),
    (ReportedProblemsResult.ISSUE_REPORTED, True, (ART,), StabilityResult.DETERIORATED, False),
    (ReportedProblemsResult.ISSUE_REPORTED, True, (), StabilityResult.INSUFFICIENT_DATA, False),
    (ReportedProblemsResult.ISSUE_REPORTED, False, (), StabilityResult.INSUFFICIENT_DATA, False),
    (ReportedProblemsResult.ISSUE_REPORTED, None, (), StabilityResult.INSUFFICIENT_DATA, False),
    (ReportedProblemsResult.INSUFFICIENT_DATA, False, (), StabilityResult.INSUFFICIENT_DATA, False),
    (None, None, (), StabilityResult.INSUFFICIENT_DATA, False),
])
def test_complete_reported_problems_matrix(result, safety, evidence, stability, invalid):
    value = make_input()
    projection = replace(value.reported_problems_projection, result=result,
                         reliable_canonical_safety_signal=safety,
                         safety_signal_evidence_refs=evidence)
    if invalid:
        with pytest.raises(ValueError):
            evaluate_general_stability(replace(value, reported_problems_projection=projection),
                                       evaluation_id="evaluation")
    else:
        evaluated = evaluate_general_stability(replace(value, reported_problems_projection=projection),
                                               evaluation_id="evaluation")
        assert evaluated.reported_problems.stability_result is stability


@pytest.mark.parametrize(("field", "invalid"), [
    ("projection_status", ProjectionStatus.ACTIVE.value),
    ("projection_status", ChannelCheckStatus.VERIFIED),
    ("channel_check_status", ChannelCheckStatus.VERIFIED.value),
    ("channel_check_status", ProjectionStatus.ACTIVE),
    ("result", "BOGUS"),
    ("result", ReportedProblemsResult.NO_KNOWN_ISSUE.value),
    ("result", ProjectionStatus.ACTIVE),
    ("reliable_canonical_safety_signal", 0),
    ("reliable_canonical_safety_signal", 1),
    ("reliable_canonical_safety_signal", "false"),
])
def test_projection_rejects_raw_strings_foreign_enums_and_non_boolean_flags(field, invalid):
    value = make_input()
    projection = replace(value.reported_problems_projection, **{field: invalid})
    with pytest.raises(ValueError, match=field):
        evaluate_general_stability(replace(value, reported_problems_projection=projection),
                                   evaluation_id="e")


@pytest.mark.parametrize(("field", "invalid"), [
    ("category", RecoveryCategory.LOW.value),
    ("category", ProjectionStatus.ACTIVE),
    ("category_missingness", CategoryMissingness.NOT_MISSING.value),
    ("category_missingness", ProjectionStatus.ACTIVE),
])
def test_recovery_assessment_rejects_raw_strings_and_foreign_enums(field, invalid):
    value = make_input()
    baseline = replace(value.baseline_assessment, **{field: invalid})
    binding = replace(value.prescription_binding,
                      baseline_assessment_ref=recovery_assessment_ref(baseline))
    with pytest.raises(ValueError, match=field):
        evaluate_general_stability(replace(value, baseline_assessment=baseline,
                                           prescription_binding=binding), evaluation_id="e")


@pytest.mark.parametrize(("field", "invalid"), [
    ("start_boundary", EventBoundary.EXCLUSIVE.value),
    ("start_boundary", ProjectionStatus.ACTIVE),
    ("end_boundary", EventBoundary.INCLUSIVE.value),
    ("end_boundary", ChannelCheckStatus.VERIFIED),
])
def test_event_window_rejects_raw_strings_and_foreign_enums(field, invalid):
    value = make_input()
    window = replace(value.reported_problems_projection.event_window, **{field: invalid})
    projection = replace(value.reported_problems_projection, event_window=window)
    with pytest.raises(ValueError, match=field):
        evaluate_general_stability(replace(value, reported_problems_projection=projection),
                                   evaluation_id="e")


@pytest.mark.parametrize(("field", "missing_path"), [
    ("projection_status", "reported_problems_projection.projection_status"),
    ("channel_check_status", "reported_problems_projection.channel_check_status"),
    ("result", "reported_problems_projection.result"),
    ("reliable_canonical_safety_signal",
     "reported_problems_projection.reliable_canonical_safety_signal"),
])
def test_nullable_projection_fields_remain_legitimate_missingness(field, missing_path):
    value = make_input()
    changes = {field: None}
    if field == "reliable_canonical_safety_signal":
        changes["result"] = ReportedProblemsResult.INSUFFICIENT_DATA
    projection = replace(value.reported_problems_projection, **changes)
    output = evaluate_general_stability(replace(value, reported_problems_projection=projection),
                                        evaluation_id="e")
    assert output.reported_problems.stability_result is StabilityResult.INSUFFICIENT_DATA
    assert missing_path in output.reported_problems.missing_fields


def test_safety_deterioration_precedes_insufficient_recovery_and_aggregation_is_complete():
    value = make_input(baseline=None)
    projection = replace(value.reported_problems_projection,
        result=ReportedProblemsResult.ISSUE_REPORTED,
        reliable_canonical_safety_signal=True, safety_signal_evidence_refs=(ART,))
    result = evaluate_general_stability(replace(value, reported_problems_projection=projection),
                                        evaluation_id="evaluation")
    assert result.recovery_result is StabilityResult.INSUFFICIENT_DATA
    assert result.overall is StabilityResult.DETERIORATED
    assert result.performance_applicability is PerformanceApplicability.NOT_APPLICABLE


def test_deteriorated_recovery_and_stable_pair_aggregation():
    worse = assessment("worse", T0 + timedelta(hours=3), RecoveryCategory.HIGH)
    assert evaluate_general_stability(make_input((worse,)), evaluation_id="e").overall is StabilityResult.DETERIORATED
    assert evaluate_general_stability(make_input(), evaluation_id="e").overall is StabilityResult.STABLE


class Arbitrary:
    pass


BAD_OBJECTS = (None, "wrong", {"id": "wrong"}, Arbitrary(), ART, ProjectionStatus.ACTIVE)


@pytest.mark.parametrize("field", [
    "prescription_binding", "actual_session_boundary", "candidate_set", "provenance_ref",
])
@pytest.mark.parametrize("bad", BAD_OBJECTS)
def test_required_top_level_objects_are_rejected_before_dereference(field, bad):
    with pytest.raises(ValueError):
        evaluate_general_stability(replace(make_input(), **{field: bad}), evaluation_id="e")


@pytest.mark.parametrize(("container", "field", "bad"), [
    ("prescription_binding", "prescription_snapshot_ref", None),
    ("prescription_binding", "decision_ref", "wrong"),
    ("prescription_binding", "baseline_use_attestation_ref", {}),
    ("prescription_binding", "provenance_ref", Arbitrary()),
    ("actual_session_boundary", "actual_session_ref", ReportedProblemsEventCursor("wrong", 1)),
    ("actual_session_boundary", "provenance_ref", "wrong"),
    ("candidate_set", "actual_session_ref", {}),
    ("candidate_set", "provenance_ref", ProjectionStatus.ACTIVE),
    ("baseline_assessment", "analyzer_ref", None),
    ("baseline_assessment", "provenance_ref", {}),
    ("reported_problems_projection", "actual_session_ref", "wrong"),
    ("reported_problems_projection", "provenance_ref", ART),
    ("reported_problems_projection", "event_cursor", {}),
    ("reported_problems_projection", "event_window", Arbitrary()),
])
def test_nested_objects_are_type_checked_before_attribute_access(container, field, bad):
    value = make_input()
    nested = replace(getattr(value, container), **{field: bad})
    if container == "baseline_assessment":
        binding = replace(value.prescription_binding,
                          baseline_assessment_ref=recovery_assessment_ref(nested))
        value = replace(value, prescription_binding=binding)
    with pytest.raises(ValueError):
        evaluate_general_stability(replace(value, **{container: nested}), evaluation_id="e")


@pytest.mark.parametrize("bad", [None, "wrong", {}, Arbitrary(), ART, ProjectionStatus.ACTIVE])
def test_candidate_elements_are_rejected_before_dereference(bad):
    value = make_input()
    candidate_set = replace(value.candidate_set,
                            candidates=(value.candidate_set.candidates[0], bad))
    with pytest.raises(ValueError):
        evaluate_general_stability(replace(value, candidate_set=candidate_set), evaluation_id="e")


@pytest.mark.parametrize("field", ["analyzer_id", "analyzer_version", "assessment_schema_version"])
@pytest.mark.parametrize(("baseline_value", "follow_value", "expected_status", "sides"), [
    (None, "same", CompatibilityStatus.UNDETERMINED, ("baseline",)),
    ("same", None, CompatibilityStatus.UNDETERMINED, ("candidate",)),
    (None, None, CompatibilityStatus.UNDETERMINED, ("baseline", "candidate")),
    ("left", "right", CompatibilityStatus.INCOMPATIBLE, ()),
    ("same", "same", CompatibilityStatus.COMPATIBLE, ()),
])
def test_c1_missingness_is_attributed_to_the_correct_side(
        field, baseline_value, follow_value, expected_status, sides):
    baseline_analyzer = replace(ANALYZER, **{field: baseline_value})
    follow_analyzer = replace(ANALYZER, **{field: follow_value})
    baseline = assessment("baseline", T0, analyzer=baseline_analyzer)
    follow = assessment("follow", T0 + timedelta(hours=3), analyzer=follow_analyzer)
    compatibility = evaluate_compatibility(recovery_assessment_ref(baseline),
                                           recovery_assessment_ref(follow))
    expected = []
    if "baseline" in sides:
        expected.append(f"baseline_assessment.analyzer_ref.{field}")
    if "candidate" in sides:
        expected.append(f"candidate_set.candidates[].analyzer_ref.{field}")
    assert compatibility.status is expected_status
    assert compatibility.missing_fields == tuple(sorted(expected))

    output = evaluate_general_stability(make_input((follow,), baseline=baseline), evaluation_id="e")
    record = output.selection_evidence.records[0]
    assert record.missing_fields == tuple(sorted(expected))
    assert set(expected) <= set(output.selection_evidence.missing_fields)
    assert set(expected) <= set(output.missing_fields)
