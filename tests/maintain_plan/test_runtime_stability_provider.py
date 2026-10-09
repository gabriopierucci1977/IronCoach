from dataclasses import replace

import pytest

from backend.maintain_plan.runtime_stability_provider import (
    RuntimeStabilityProviderError,
    provide_runtime_stability,
)
from backend.maintain_plan.stability_models import GeneralStabilityEvaluation
from tests.maintain_plan.test_general_stability_service import make_input


def test_provider_evaluates_explicit_typed_input():
    result = provide_runtime_stability(make_input(), evaluation_id="runtime-stability-1")
    assert result.evaluation.evaluation_id == "runtime-stability-1"
    assert type(result.evaluation) is GeneralStabilityEvaluation
    assert result.evaluation.subject_ref == "athlete"


def test_provider_rejects_non_typed_input():
    with pytest.raises(RuntimeStabilityProviderError, match="GeneralStabilityInput"):
        provide_runtime_stability(object(), evaluation_id="runtime-stability-1")


def test_provider_rejects_invalid_evaluation_id():
    with pytest.raises(RuntimeStabilityProviderError, match="evaluation_id"):
        provide_runtime_stability(make_input(), evaluation_id="")


def test_provider_rejects_incoherent_ownership():
    value = make_input()
    binding = replace(value.prescription_binding, subject_ref="foreign")
    with pytest.raises(RuntimeStabilityProviderError, match="ownership"):
        provide_runtime_stability(
            replace(value, prescription_binding=binding),
            evaluation_id="runtime-stability-1",
        )


def test_provider_has_no_database_dependency(monkeypatch):
    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: pytest.fail("database access"))
    assert provide_runtime_stability(make_input(), evaluation_id="runtime-stability-1").evaluation.evaluation_id == "runtime-stability-1"
