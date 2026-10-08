import pytest

from backend.maintain_plan.runtime_matching_decision import DecisionStatus
from backend.maintain_plan.runtime_matching_scope import RuntimeMatchingScopeError
from backend.maintain_plan.runtime_shadow import evaluate_runtime_matching_shadow


def test_shadow_empty_scope_is_not_evaluable():
    result = evaluate_runtime_matching_shadow(
        subject_ref="athlete-shadow",
        snapshots=(),
        sessions=(),
    )

    assert result.subject_ref == "athlete-shadow"
    assert result.snapshot_count == 0
    assert result.session_count == 0
    assert result.decision.status is DecisionStatus.NOT_EVALUABLE
    assert result.decision.candidates == ()


def test_shadow_rejects_invalid_ownership_before_decision():
    with pytest.raises(RuntimeMatchingScopeError):
        evaluate_runtime_matching_shadow(
            subject_ref="",
            snapshots=(),
            sessions=(),
        )
