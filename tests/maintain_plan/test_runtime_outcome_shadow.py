import pytest

from backend.maintain_plan.final_outcome_models import MaintainPlanOutcome
from backend.maintain_plan.runtime_outcome_boundary import RuntimeOutcomeInputError
from backend.maintain_plan.runtime_outcome_shadow import (
    evaluate_runtime_outcome_shadow,
)
from backend.maintain_plan.stability_models import RecoveryCategory
from tests.maintain_plan.test_final_outcome_service import (
    PROV,
    RUN_EXECUTION,
    T0,
    stability,
)


def test_shadow_assembles_and_evaluates_explicit_canonical_inputs():
    result = evaluate_runtime_outcome_shadow(
        execution=RUN_EXECUTION,
        stability=stability(),
        evaluation_id="shadow-outcome",
        evaluated_at=T0.replace(hour=9),
        provenance_ref=PROV,
    )

    assert result.runtime_input.execution is RUN_EXECUTION
    assert result.evaluation.evaluation_id == "shadow-outcome"
    assert result.evaluation.outcome is MaintainPlanOutcome.POSITIVE


def test_shadow_preserves_final_outcome_precedence():
    result = evaluate_runtime_outcome_shadow(
        execution=RUN_EXECUTION,
        stability=stability(RecoveryCategory.HIGH),
        evaluation_id="shadow-deteriorated",
        evaluated_at=T0.replace(hour=9),
        provenance_ref=PROV,
    )

    assert result.evaluation.outcome is MaintainPlanOutcome.NEGATIVE


def test_shadow_rejects_invalid_inputs_before_evaluation():
    with pytest.raises(RuntimeOutcomeInputError):
        evaluate_runtime_outcome_shadow(
            execution=object(),
            stability=object(),
            evaluation_id="shadow-invalid",
            evaluated_at=T0.replace(hour=9),
            provenance_ref=PROV,
        )


def test_shadow_has_no_database_dependency(monkeypatch):
    import sqlite3

    monkeypatch.setattr(
        sqlite3,
        "connect",
        lambda *args, **kwargs: pytest.fail("database access"),
    )

    result = evaluate_runtime_outcome_shadow(
        execution=RUN_EXECUTION,
        stability=stability(),
        evaluation_id="shadow-pure",
        evaluated_at=T0.replace(hour=9),
        provenance_ref=PROV,
    )

    assert result.evaluation.outcome is MaintainPlanOutcome.POSITIVE


def test_shadow_is_not_wired_into_main_pipeline():
    from pathlib import Path

    source = (
        Path(__file__).parents[2] / "backend" / "main.py"
    ).read_text(encoding="utf-8")

    assert "runtime_outcome_shadow" not in source
    assert "evaluate_runtime_outcome_shadow" not in source
