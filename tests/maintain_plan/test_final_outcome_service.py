"""Synthetic tests for the isolated final MAINTAIN_PLAN outcome draft."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from backend.maintain_plan.final_outcome_models import (
    FINAL_OUTCOME_EVALUATION_VERSION, FINAL_OUTCOME_POLICY, MaintainPlanOutcome,
)
from backend.maintain_plan.final_outcome_service import evaluate_final_outcome
from backend.maintain_plan.general_stability_service import (
    evaluate_general_stability, recovery_assessment_ref,
)
from backend.maintain_plan.models import CoverageStatus, OverallStatus, PolicyRef
from backend.maintain_plan.stability_models import *
from tests.maintain_plan.fixtures import RUN_EXECUTION

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
SNAPSHOT = VersionedArtifactRef("prescription-snapshot", "snapshot-1", "1")
SESSION = VersionedArtifactRef("actual-session", "session-1", "1")
ART = VersionedArtifactRef("test-producer", "producer", "1")
PROV = ProvenanceRef(ART, "synthetic", "final-fixture", "1")
ANALYZER = AnalyzerRef("canonical", "1", "1")


def assessment(name, observed, category=RecoveryCategory.LOW):
    return RecoveryAssessment(name, STABILITY_CONTRACT_VERSION, ANALYZER, "athlete",
        observed, observed + timedelta(minutes=1), category, CategoryMissingness.NOT_MISSING,
        (ART,), PROV)


def stability(category=RecoveryCategory.LOW):
    baseline = assessment("baseline", T0)
    evaluated_at = T0 + timedelta(hours=8)
    binding = PrescriptionBaselineBinding(SNAPSHOT, ART, "athlete", T0 + timedelta(hours=1),
        recovery_assessment_ref(baseline), ART, PROV)
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


@pytest.mark.parametrize(("execution", "expected"), [
    (OverallStatus.IN_LINE, MaintainPlanOutcome.POSITIVE),
    (OverallStatus.PARTIALLY_IN_LINE, MaintainPlanOutcome.NEUTRAL),
    (OverallStatus.DIFFERENT, MaintainPlanOutcome.NEGATIVE),
])
def test_stable_rows_of_approved_matrix(execution, expected):
    assert final(replace(RUN_EXECUTION, overall=execution)).outcome is expected


@pytest.mark.parametrize("execution", list(OverallStatus))
def test_every_execution_state_with_deteriorated_stability(execution):
    result = final(replace(RUN_EXECUTION, overall=execution), stability(RecoveryCategory.HIGH))
    expected = (MaintainPlanOutcome.INSUFFICIENT_DATA
                if execution is OverallStatus.INSUFFICIENT_DATA else MaintainPlanOutcome.NEGATIVE)
    assert result.outcome is expected


def test_insufficient_gates_have_precedence_over_deterioration():
    execution = replace(RUN_EXECUTION, overall=OverallStatus.INSUFFICIENT_DATA)
    assert final(execution, stability(RecoveryCategory.HIGH)).outcome is MaintainPlanOutcome.INSUFFICIENT_DATA
    insufficient = replace(stability(), overall=StabilityResult.INSUFFICIENT_DATA)
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
                       missing_fields=("z", "a", "a"), warnings=("b", "a"))
    component = replace(RUN_EXECUTION.component_results[0], identity=identity)
    execution = replace(RUN_EXECUTION, component_results=(component,))
    stable = replace(stability(), missing_fields=("m", "a"), warnings=("c", "b"))
    result = final(execution, stable)
    assert result.missing_fields == ("a", "m", "z")
    assert result.warnings == ("a", "b", "c")


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
