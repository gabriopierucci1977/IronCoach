"""Cross-subject regressions with internally valid canonical stability data."""

from dataclasses import replace
from datetime import timedelta

import pytest

import backend.maintain_plan.runtime_shadow_chain as shadow_chain
from backend.maintain_plan.final_outcome_validators import validate_final_outcome_inputs
from backend.maintain_plan.runtime_matching_decision import decide_runtime_matching
from backend.maintain_plan.runtime_matching_scope import validate_runtime_matching_scope
from backend.maintain_plan.runtime_shadow_consistency import (
    RuntimeShadowConsistencyError,
    validate_runtime_shadow_consistency,
)
from backend.maintain_plan.runtime_typed_shadow_chain import evaluate_runtime_typed_shadow_chain
from backend.maintain_plan.stability_validators import validate_general_stability_evaluation
from tests.maintain_plan.fixtures import RUN_MAPPING, RUN_PRESCRIPTION, RUN_SESSION
from tests.maintain_plan.test_final_outcome_service import PROV, RUN_EXECUTION, T0, stability
from tests.maintain_plan.test_runtime_typed_shadow_chain import runtime_stability_input


def chain_inputs(subject_ref):
    snapshot = replace(RUN_PRESCRIPTION, subject_ref=subject_ref)
    session = replace(RUN_SESSION, subject_ref=subject_ref)
    scope = validate_runtime_matching_scope(subject_ref, (snapshot,), (session,))
    return dict(
        subject_ref=subject_ref,
        matching=decide_runtime_matching(scope),
        snapshot=snapshot,
        session=session,
        mapping=RUN_MAPPING,
        execution=RUN_EXECUTION,
    )


@pytest.mark.parametrize('foreign_subject', ('athlete-1', 'ATHLETE'))
def test_valid_stability_for_another_subject_is_rejected(foreign_subject):
    value = stability()
    assert value.subject_ref == 'athlete'
    assert validate_general_stability_evaluation(value) == ()
    # ID e valutazioni canoniche coincidono: l'unica incoerenza e' il soggetto.
    assert validate_final_outcome_inputs(RUN_EXECUTION, value) == ()
    with pytest.raises(RuntimeShadowConsistencyError, match='chain subject_ref'):
        validate_runtime_shadow_consistency(
            **chain_inputs(foreign_subject), stability=value,
        )


def test_same_subject_is_accepted_without_rebinding_stability():
    value = stability()
    result = validate_runtime_shadow_consistency(
        **chain_inputs('athlete'), stability=value,
    )
    assert result.stability is value
    assert result.subject_ref == result.snapshot.subject_ref
    assert result.subject_ref == result.session.subject_ref
    assert result.subject_ref == result.stability.subject_ref


def test_foreign_subject_stops_before_final_outcome(monkeypatch):
    def unexpected_outcome(*args, **kwargs):
        pytest.fail('outcome evaluated despite foreign stability ownership')

    monkeypatch.setattr(shadow_chain, 'evaluate_runtime_outcome_shadow', unexpected_outcome)
    with pytest.raises(RuntimeShadowConsistencyError, match='chain subject_ref'):
        shadow_chain.evaluate_runtime_shadow_chain(
            **chain_inputs('athlete-1'),
            stability=stability(),
            evaluation_id='ownership-regression',
            evaluated_at=T0 + timedelta(hours=9),
            provenance_ref=PROV,
        )


def test_typed_chain_rejects_foreign_subject_before_outcome(monkeypatch):
    def unexpected_outcome(*args, **kwargs):
        pytest.fail('typed chain evaluated outcome for another subject')

    monkeypatch.setattr(shadow_chain, 'evaluate_runtime_outcome_shadow', unexpected_outcome)
    with pytest.raises(RuntimeShadowConsistencyError, match='chain subject_ref'):
        evaluate_runtime_typed_shadow_chain(
            **chain_inputs('athlete-1'),
            stability_input=runtime_stability_input(),
            stability_evaluation_id='ownership-stability',
            outcome_evaluation_id='ownership-outcome',
            evaluated_at=T0 + timedelta(hours=9),
            provenance_ref=PROV,
        )
