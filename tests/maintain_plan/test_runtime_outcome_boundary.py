from dataclasses import FrozenInstanceError

import pytest

from backend.maintain_plan.runtime_outcome_boundary import (
    RuntimeOutcomeInputError,
    build_runtime_outcome_input,
)
from tests.maintain_plan.test_final_outcome_service import (
    PROV,
    RUN_EXECUTION,
    T0,
    stability,
)


def test_boundary_accepts_valid_canonical_inputs():
    result = build_runtime_outcome_input(
        execution=RUN_EXECUTION,
        stability=stability(),
        evaluation_id="runtime-final",
        evaluated_at=T0.replace(hour=9),
        provenance_ref=PROV,
    )

    assert result.execution is RUN_EXECUTION
    assert result.evaluation_id == "runtime-final"
    assert result.provenance_ref is PROV


def test_boundary_rejects_wrong_top_level_types_without_dereferencing():
    with pytest.raises(RuntimeOutcomeInputError) as caught:
        build_runtime_outcome_input(
            execution=object(),
            stability=object(),
            evaluation_id="runtime-final",
            evaluated_at=T0,
            provenance_ref=object(),
        )

    assert "execution must be an ExecutionEvaluation" in caught.value.errors
    assert "stability must be a GeneralStabilityEvaluation" in caught.value.errors


def test_boundary_rejects_invalid_final_metadata():
    with pytest.raises(RuntimeOutcomeInputError) as caught:
        build_runtime_outcome_input(
            execution=RUN_EXECUTION,
            stability=stability(),
            evaluation_id=" ",
            evaluated_at=T0.replace(tzinfo=None),
            provenance_ref=PROV,
        )

    assert "evaluation_id must be a non-empty string" in caught.value.errors
    assert "evaluated_at must be a timezone-aware datetime" in caught.value.errors


def test_boundary_is_immutable():
    result = build_runtime_outcome_input(
        execution=RUN_EXECUTION,
        stability=stability(),
        evaluation_id="runtime-final",
        evaluated_at=T0.replace(hour=9),
        provenance_ref=PROV,
    )

    with pytest.raises(FrozenInstanceError):
        result.evaluation_id = "changed"


def test_boundary_has_no_database_dependency(monkeypatch):
    import sqlite3

    monkeypatch.setattr(
        sqlite3,
        "connect",
        lambda *args, **kwargs: pytest.fail("database access"),
    )

    result = build_runtime_outcome_input(
        execution=RUN_EXECUTION,
        stability=stability(),
        evaluation_id="runtime-final",
        evaluated_at=T0.replace(hour=9),
        provenance_ref=PROV,
    )

    assert result.execution is RUN_EXECUTION
