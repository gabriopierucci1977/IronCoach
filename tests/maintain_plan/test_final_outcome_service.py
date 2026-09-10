"""Synthetic tests for the isolated final MAINTAIN_PLAN outcome draft."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from backend.maintain_plan.final_outcome_models import (
    FINAL_OUTCOME_EVALUATION_VERSION, FINAL_OUTCOME_POLICY, MaintainPlanOutcome,
)
from backend.maintain_plan.final_outcome_service import evaluate_final_outcome
from backend.maintain_plan.final_outcome_validators import validate_final_outcome_inputs
from backend.maintain_plan.execution_evaluation_service import evaluate as evaluate_execution
from backend.maintain_plan.general_stability_service import (
    evaluate_general_stability, recovery_assessment_ref,
)
from backend.maintain_plan.models import (
    AdherenceStatus, CoverageStatus, Direction, EvaluationApplicability, OverallStatus,
    PolicyRef, SeverityBand,
)
from backend.maintain_plan.stability_models import *
from tests.maintain_plan.fixtures import (
    BRICK_EXECUTION as RAW_BRICK_EXECUTION,
    RUN_EXECUTION as RAW_RUN_EXECUTION,
    OPTIONAL_PLANNED_ONLY, STRENGTH_EXECUTION,
    RUN_MAPPING, RUN_PRESCRIPTION, RUN_SESSION, STRENGTH_REQUIRED, execution,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
SNAPSHOT = VersionedArtifactRef("prescription-snapshot", "snapshot-1", "1")
SESSION = VersionedArtifactRef("actual-session", "session-1", "1")
ART = VersionedArtifactRef("test-producer", "producer", "1")
PROV = ProvenanceRef(ART, "synthetic", "final-fixture", "1")
ANALYZER = AnalyzerRef("canonical", "1", "1")


def dose_consistent_fixture(value):
    components = []
    for component in value.component_results:
        if component.dose is None:
            components.append(component)
        else:
            components.append(replace(
                component,
                quantity=replace(component.quantity, direction=Direction.IN_LINE,
                                 band=SeverityBand.MAIN),
                intensity=replace(component.intensity, direction=Direction.IN_LINE,
                                  band=SeverityBand.MAIN),
            ))
    return replace(value, component_results=tuple(components))


RUN_EXECUTION = dose_consistent_fixture(RAW_RUN_EXECUTION)
BRICK_EXECUTION = dose_consistent_fixture(RAW_BRICK_EXECUTION)


def assessment(name, observed, category=RecoveryCategory.LOW):
    return RecoveryAssessment(name, STABILITY_CONTRACT_VERSION, ANALYZER, "athlete",
        observed, observed + timedelta(minutes=1), category, CategoryMissingness.NOT_MISSING,
        (ART,), PROV)


def stability(category=RecoveryCategory.LOW, *, baseline_present=True):
    baseline = assessment("baseline", T0) if baseline_present else None
    evaluated_at = T0 + timedelta(hours=8)
    binding = PrescriptionBaselineBinding(SNAPSHOT, ART, "athlete", T0 + timedelta(hours=1),
        recovery_assessment_ref(baseline) if baseline else None, ART, PROV)
    boundary = ActualSessionBoundary(SESSION, "athlete", T0 + timedelta(hours=2), PROV)
    candidates = RecoveryAssessmentCandidateSet(STABILITY_CONTRACT_VERSION, SESSION, "athlete",
        evaluated_at, evaluated_at, (assessment("follow", T0 + timedelta(hours=3), category),), PROV)
    window = ReportedProblemsEventWindow(T0 + timedelta(hours=2), EventBoundary.EXCLUSIVE,
                                         evaluated_at, EventBoundary.INCLUSIVE)
    projection = ReportedProblemsProjectionSnapshot(
        "projection", "1", "1", SESSION, "athlete", ProjectionStatus.ACTIVE,
        ReportedProblemsEventCursor("event", 1), window, evaluated_at,
        ChannelCheckStatus.VERIFIED, ReportedProblemsResult.NO_KNOWN_ISSUE,
        False, (), PROV)
    value = GeneralStabilityInput(STABILITY_CONTRACT_VERSION, STABILITY_POLICY_ID,
        STABILITY_POLICY_VERSION, binding, baseline, boundary, candidates, None,
        evaluated_at, projection, PROV)
    return evaluate_general_stability(value, evaluation_id="stability-evaluation")


def final(execution=RUN_EXECUTION, stability_value=None, **kwargs):
    return evaluate_final_outcome(execution, stability_value or stability(),
        evaluation_id=kwargs.get("evaluation_id", "final-evaluation"),
        evaluated_at=kwargs.get("evaluated_at", T0 + timedelta(hours=9)),
        provenance_ref=kwargs.get("provenance_ref", PROV))


def execution_with_overall(overall):
    status = {
        OverallStatus.IN_LINE: AdherenceStatus.MET,
        OverallStatus.PARTIALLY_IN_LINE: AdherenceStatus.PARTIALLY_MET,
        OverallStatus.DIFFERENT: AdherenceStatus.NOT_MET,
        OverallStatus.INSUFFICIENT_DATA: AdherenceStatus.INSUFFICIENT_DATA,
    }[overall]
    component = RUN_EXECUTION.component_results[0]
    component = replace(component, identity=replace(component.identity, status=status))
    return replace(RUN_EXECUTION, component_results=(component,),
                   identity_aggregate=replace(RUN_EXECUTION.identity_aggregate,
                                              status=status), overall=overall)


def insufficient_stability():
    value = stability()
    reported = replace(value.reported_problems, projection_ref=None,
        result=ReportedProblemsResult.INSUFFICIENT_DATA,
        stability_result=StabilityResult.INSUFFICIENT_DATA, evidence_refs=(),
        missing_fields=("reported_problems_projection",))
    return replace(value, reported_problems=reported,
                   overall=StabilityResult.INSUFFICIENT_DATA,
                   missing_fields=("reported_problems_projection",))


@pytest.mark.parametrize(("execution", "expected"), [
    (OverallStatus.IN_LINE, MaintainPlanOutcome.POSITIVE),
    (OverallStatus.PARTIALLY_IN_LINE, MaintainPlanOutcome.NEUTRAL),
    (OverallStatus.DIFFERENT, MaintainPlanOutcome.NEGATIVE),
])
def test_stable_rows_of_approved_matrix(execution, expected):
    assert final(execution_with_overall(execution)).outcome is expected


@pytest.mark.parametrize("execution", list(OverallStatus))
def test_every_execution_state_with_deteriorated_stability(execution):
    result = final(execution_with_overall(execution), stability(RecoveryCategory.HIGH))
    expected = (MaintainPlanOutcome.INSUFFICIENT_DATA
                if execution is OverallStatus.INSUFFICIENT_DATA else MaintainPlanOutcome.NEGATIVE)
    assert result.outcome is expected


def test_insufficient_gates_have_precedence_over_deterioration():
    execution = execution_with_overall(OverallStatus.INSUFFICIENT_DATA)
    assert final(execution, stability(RecoveryCategory.HIGH)).outcome is MaintainPlanOutcome.INSUFFICIENT_DATA
    insufficient = insufficient_stability()
    assert final(stability_value=insufficient).outcome is MaintainPlanOutcome.INSUFFICIENT_DATA


@pytest.mark.parametrize("coverage", [status for status in CoverageStatus
                                       if status is not CoverageStatus.FULLY_SUPPORTED])
def test_non_full_coverage_prevents_a_definitive_outcome(coverage):
    execution = replace(RUN_EXECUTION,
        evaluation_coverage=replace(RUN_EXECUTION.evaluation_coverage, status=coverage),
        identity_aggregate=None, quantity_aggregate=None, intensity_aggregate=None,
        structure_aggregate=None, dose_aggregate=None, overall=None)
    result = final(execution, stability(RecoveryCategory.HIGH))
    assert result.outcome is None
    assert result.execution_overall is None


def test_canonical_missing_baseline_reaches_insufficient_final_outcome():
    missing = stability(baseline_present=False)
    assert missing.selection_evidence.records == ()
    assert final(stability_value=missing).outcome is MaintainPlanOutcome.INSUFFICIENT_DATA


def test_qualified_refs_and_cross_input_bindings_must_agree():
    result = final()
    assert result.execution_ref.prescription_mapping_ref == "mapping-1"
    assert result.stability_ref.prescription_snapshot_ref == SNAPSHOT
    wrong = replace(stability(), actual_session_boundary=replace(
        stability().actual_session_boundary,
        actual_session_ref=VersionedArtifactRef("actual-session", "other", "1")))
    with pytest.raises(ValueError, match="actual session refs must agree"):
        final(stability_value=wrong)


@pytest.mark.parametrize("bad", ["raw", {}, object()])
def test_wrong_primary_input_types_are_clean_value_errors(bad):
    with pytest.raises(ValueError):
        final(execution=bad)


def test_wrong_nested_types_raw_and_foreign_enums_are_rejected():
    with pytest.raises(ValueError, match="evaluation_coverage.status"):
        final(replace(RUN_EXECUTION, evaluation_coverage=replace(
            RUN_EXECUTION.evaluation_coverage, status=CoverageStatus.FULLY_SUPPORTED.value)))
    with pytest.raises(ValueError, match="execution.overall"):
        final(replace(RUN_EXECUTION, overall=StabilityResult.STABLE))
    with pytest.raises(ValueError, match="execution.policy"):
        final(replace(RUN_EXECUTION, policy=MappingProxyType({})))


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        final(evaluated_at=T0.replace(tzinfo=None))


def test_diagnostics_are_propagated_deduplicated_and_sorted():
    identity = replace(RUN_EXECUTION.component_results[0].identity,
                       missing_fields=("quantity",), warnings=("b", "a"))
    component = replace(RUN_EXECUTION.component_results[0], identity=identity)
    execution = replace(RUN_EXECUTION, component_results=(component,))
    stable = replace(stability(), warnings=("b", "c"))
    result = final(execution, stable)
    assert result.missing_fields == ("quantity",)
    assert result.warnings == ("a", "b", "c")


def test_deeply_frozen_sets_are_valid_generic_payloads():
    execution = replace(RUN_EXECUTION, provenance={"labels": {"steady"}})
    assert execution.provenance["labels"] == frozenset({"steady"})
    assert final(execution=execution).outcome is MaintainPlanOutcome.POSITIVE


def test_artifact_is_deeply_immutable_and_deterministic():
    first = final()
    second = final()
    assert first == second
    assert first.evaluation_version == FINAL_OUTCOME_EVALUATION_VERSION
    assert first.policy == FINAL_OUTCOME_POLICY
    with pytest.raises(FrozenInstanceError):
        first.outcome = MaintainPlanOutcome.NEGATIVE


def test_matrix_ignores_interval_recovery_score_legacy_analyzers_and_generic_payloads():
    noisy = replace(RUN_EXECUTION, provenance=MappingProxyType({
        "interval_recovery": "bad", "score": -999, "legacy_analyzer": "negative",
        "generic_payload": ("must", "not", "decide"),
    }))
    assert final(noisy).outcome is MaintainPlanOutcome.POSITIVE


def test_rejects_stability_overall_contradictions():
    base = stability()
    cases = (
        replace(base, recovery_result=StabilityResult.DETERIORATED),
        replace(base, reported_problems=replace(
            base.reported_problems, result=ReportedProblemsResult.ISSUE_REPORTED,
            stability_result=StabilityResult.DETERIORATED, evidence_refs=(ART,))),
        replace(base, reported_problems=replace(
            base.reported_problems, result=ReportedProblemsResult.INSUFFICIENT_DATA,
            stability_result=StabilityResult.INSUFFICIENT_DATA)),
        replace(base, overall=StabilityResult.DETERIORATED),
    )
    for invalid in cases:
        with pytest.raises(ValueError, match="overall contradicts"):
            final(stability_value=invalid)


def test_rejects_candidate_set_and_selection_ref_mismatches():
    base = stability()
    foreign_session = VersionedArtifactRef("actual-session", "foreign", "1")
    mismatched_selection = replace(base, selection_evidence=replace(
        base.selection_evidence, candidate_set_ref=replace(
            base.selection_evidence.candidate_set_ref,
            actual_session_ref=foreign_session)))
    foreign_candidate_set = replace(base, candidate_set_ref=replace(
        base.candidate_set_ref, actual_session_ref=foreign_session))
    for invalid in (mismatched_selection, foreign_candidate_set):
        with pytest.raises(ValueError):
            final(stability_value=invalid)


def test_rejects_baseline_selected_and_compatibility_ref_mismatches():
    base = stability()
    foreign = replace(base.baseline_ref, assessment_id="foreign")
    selected_foreign = replace(base.selected_follow_up_ref, assessment_id="foreign")
    cases = (
        replace(base, baseline_ref=foreign),
        replace(base, selected_follow_up_ref=selected_foreign),
        replace(base, compatibility=replace(base.compatibility, baseline_ref=foreign)),
        replace(base, compatibility=replace(base.compatibility, follow_up_ref=selected_foreign)),
    )
    for invalid in cases:
        with pytest.raises(ValueError):
            final(stability_value=invalid)


def test_rejects_reported_projection_session_and_subject_mismatches():
    base = stability()
    projection = base.reported_problems.projection_ref
    cases = (
        replace(base, reported_problems=replace(base.reported_problems,
            projection_ref=replace(projection, actual_session_ref=VersionedArtifactRef(
                "actual-session", "foreign", "1")))),
        replace(base, reported_problems=replace(base.reported_problems,
            projection_ref=replace(projection, subject_ref="foreign"))),
    )
    for invalid in cases:
        with pytest.raises(ValueError):
            final(stability_value=invalid)


def test_rejects_stability_ownership_performance_policy_and_versions():
    base = stability()
    cases = (
        replace(base, subject_ref="foreign"),
        replace(base, prescription_binding=replace(base.prescription_binding,
            prescription_snapshot_ref=VersionedArtifactRef("prescription", "foreign", "1"))),
        replace(base, actual_session_boundary=replace(base.actual_session_boundary,
            actual_session_ref=VersionedArtifactRef("actual-session", "foreign", "1"))),
        replace(base, performance_applicability="NOT_APPLICABLE"),
        replace(base, policy_id="foreign"),
        replace(base, policy_version="9"),
        replace(base, contract_version="foreign"),
    )
    for invalid in cases:
        with pytest.raises(ValueError):
            final(stability_value=invalid)


def test_rejects_foreign_execution_policies_and_internal_contradictions():
    cases = (
        replace(RUN_EXECUTION, policy=PolicyRef("foreign", "9")),
        replace(RUN_EXECUTION, evaluation_coverage=replace(
            RUN_EXECUTION.evaluation_coverage, policy=PolicyRef("foreign", "9"))),
        replace(RUN_EXECUTION, identity_aggregate=replace(
            RUN_EXECUTION.identity_aggregate, policy=PolicyRef("foreign", "9"))),
        replace(RUN_EXECUTION, overall=OverallStatus.DIFFERENT),
        replace(RUN_EXECUTION, evaluation_coverage=replace(
            RUN_EXECUTION.evaluation_coverage, status=CoverageStatus.UNSUPPORTED)),
    )
    for invalid in cases:
        with pytest.raises(ValueError):
            final(invalid)


def test_execution_aggregates_are_derived_from_component_results():
    altered = execution_with_overall(OverallStatus.DIFFERENT)
    canonical_component = RUN_EXECUTION.component_results[0]
    altered = replace(altered, component_results=(canonical_component,))
    with pytest.raises(ValueError, match="aggregate status contradicts components"):
        final(altered)


@pytest.mark.parametrize("refs", [(), ("result-run", "result-run"),
                                   ("foreign",)])
def test_execution_aggregate_rejects_empty_duplicate_or_foreign_refs(refs):
    invalid = replace(RUN_EXECUTION, identity_aggregate=replace(
        RUN_EXECUTION.identity_aggregate, component_result_refs=refs))
    with pytest.raises(ValueError, match="refs must exactly match"):
        final(invalid)


def test_execution_aggregate_rejects_incomplete_refs_and_non_applicable_components():
    incomplete = replace(BRICK_EXECUTION, identity_aggregate=replace(
        BRICK_EXECUTION.identity_aggregate,
        component_result_refs=BRICK_EXECUTION.identity_aggregate.component_result_refs[:1]))
    non_applicable = replace(RUN_EXECUTION, component_results=(replace(
        RUN_EXECUTION.component_results[0],
        evaluation_applicability=EvaluationApplicability.NOT_APPLICABLE),))
    for invalid in (incomplete, non_applicable):
        with pytest.raises(ValueError):
            final(invalid)


def test_execution_output_validator_accepts_canonical_examples_for_every_coverage():
    partial = execution((RUN_EXECUTION.component_results[0], STRENGTH_REQUIRED),
                        CoverageStatus.PARTIALLY_UNSUPPORTED)
    no_required = execution((OPTIONAL_PLANNED_ONLY,), CoverageStatus.NO_REQUIRED_COMPONENTS)
    for valid in (RUN_EXECUTION, STRENGTH_EXECUTION, partial, no_required):
        assert validate_final_outcome_inputs(valid, stability()) == ()
    generated = evaluate_execution(RUN_PRESCRIPTION, RUN_SESSION, RUN_MAPPING,
                                   evaluation_id="canonical-execution",
                                   evaluated_at=T0 + timedelta(hours=8))
    assert validate_final_outcome_inputs(generated, stability()) == ()
