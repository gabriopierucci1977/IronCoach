from dataclasses import replace

import pytest

from backend.maintain_plan.runtime_matching_decision import (
    DecisionStatus,
    decide_runtime_matching,
)
from backend.maintain_plan.runtime_matching_scope import (
    validate_runtime_matching_scope,
)
from backend.maintain_plan.runtime_shadow_orchestration import (
    RuntimeShadowOrchestrationError,
    RuntimeShadowOrchestrationReason,
    RuntimeShadowOrchestrationStatus,
    orchestrate_runtime_shadow,
)
from backend.maintain_plan.final_outcome_models import MaintainPlanOutcome
from tests.maintain_plan.fixtures import (
    RUN_PRESCRIPTION,
    RUN_SESSION,
)
from tests.maintain_plan.test_final_outcome_service import (
    PROV,
    RUN_EXECUTION,
    T0,
    stability,
)


def matched_decision():
    decision = decide_runtime_matching(
        validate_runtime_matching_scope(
            "athlete-1",
            (RUN_PRESCRIPTION,),
            (RUN_SESSION,),
        )
    )
    assert decision.status is DecisionStatus.MATCHED
    return decision


def unresolved_decision():
    return decide_runtime_matching(
        validate_runtime_matching_scope(
            "athlete-1",
            (RUN_PRESCRIPTION,),
            (),
        )
    )


def test_matched_pair_without_evaluation_inputs_stays_unpublished():
    result = orchestrate_runtime_shadow(
        matching=matched_decision(),
    )

    assert result.status is RuntimeShadowOrchestrationStatus.MATCHED_OUTCOME_INPUTS_MISSING
    assert result.outcome is None
    assert result.reasons == (
        RuntimeShadowOrchestrationReason.OUTCOME_INPUTS_MISSING,
    )


def test_matched_pair_advances_only_with_explicit_evaluations():
    result = orchestrate_runtime_shadow(
        matching=matched_decision(),
        execution=RUN_EXECUTION,
        stability=stability(),
        evaluation_id="orchestration-shadow",
        evaluated_at=T0.replace(hour=9),
        provenance_ref=PROV,
    )

    assert result.status is RuntimeShadowOrchestrationStatus.OUTCOME_EVALUATED
    assert result.outcome is not None
    assert result.outcome.evaluation.outcome is MaintainPlanOutcome.POSITIVE


def test_unresolved_matching_does_not_infer_or_evaluate_outcome():
    result = orchestrate_runtime_shadow(
        matching=unresolved_decision(),
    )

    assert result.status is RuntimeShadowOrchestrationStatus.MATCHING_NOT_RESOLVED
    assert result.outcome is None
    assert result.reasons == (
        RuntimeShadowOrchestrationReason.MATCHING_NOT_RESOLVED,
    )


def test_unresolved_matching_rejects_supplied_outcome_inputs():
    with pytest.raises(RuntimeShadowOrchestrationError):
        orchestrate_runtime_shadow(
            matching=unresolved_decision(),
            execution=RUN_EXECUTION,
            stability=stability(),
            evaluation_id="orchestration-shadow",
            evaluated_at=T0.replace(hour=9),
            provenance_ref=PROV,
        )


def test_partial_outcome_inputs_are_rejected():
    with pytest.raises(RuntimeShadowOrchestrationError):
        orchestrate_runtime_shadow(
            matching=matched_decision(),
            execution=RUN_EXECUTION,
        )


def test_selected_pair_must_match_execution_refs():
    wrong_execution = replace(
        RUN_EXECUTION,
        actual_session_ref="different-session",
    )

    with pytest.raises(RuntimeShadowOrchestrationError):
        orchestrate_runtime_shadow(
            matching=matched_decision(),
            execution=wrong_execution,
            stability=stability(),
            evaluation_id="orchestration-shadow",
            evaluated_at=T0.replace(hour=9),
            provenance_ref=PROV,
        )


def test_orchestration_has_no_database_dependency(monkeypatch):
    import sqlite3

    monkeypatch.setattr(
        sqlite3,
        "connect",
        lambda *args, **kwargs: pytest.fail("database access"),
    )

    result = orchestrate_runtime_shadow(
        matching=matched_decision(),
        execution=RUN_EXECUTION,
        stability=stability(),
        evaluation_id="orchestration-pure",
        evaluated_at=T0.replace(hour=9),
        provenance_ref=PROV,
    )

    assert result.outcome is not None
