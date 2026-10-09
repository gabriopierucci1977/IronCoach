from dataclasses import replace
from datetime import timedelta

import pytest

from backend.maintain_plan.runtime_matching_decision import CandidateCardinality, DecisionStatus, decide_runtime_matching
from backend.maintain_plan.runtime_matching_scope import validate_runtime_matching_scope
from backend.maintain_plan.runtime_shadow_chain import evaluate_runtime_shadow_chain
from backend.maintain_plan.runtime_shadow_consistency import RuntimeShadowConsistencyError
from tests.maintain_plan.fixtures import RUN_MAPPING, RUN_PRESCRIPTION, RUN_SESSION
from tests.maintain_plan.test_final_outcome_service import PROV, RUN_EXECUTION, T0, stability

SUBJECT = "athlete-1"


def matching():
    scope = validate_runtime_matching_scope(SUBJECT, (RUN_PRESCRIPTION,), (RUN_SESSION,))
    result = decide_runtime_matching(scope)
    assert result.status is DecisionStatus.MATCHED
    assert result.cardinality is CandidateCardinality.ONE
    return result


def chain():
    return evaluate_runtime_shadow_chain(
        subject_ref=SUBJECT,
        matching=matching(),
        snapshot=RUN_PRESCRIPTION,
        session=RUN_SESSION,
        mapping=RUN_MAPPING,
        execution=RUN_EXECUTION,
        stability=stability(),
        evaluation_id="chain-evaluation",
        evaluated_at=T0 + timedelta(hours=9),
        provenance_ref=PROV,
    )


def test_composes_consistency_before_outcome_shadow():
    result = chain()
    assert result.consistency.mapping is RUN_MAPPING
    assert result.outcome.runtime_input.evaluation_id == "chain-evaluation"


def test_rejects_forged_matching_before_outcome_evaluation():
    base = matching()
    forged = replace(
        base,
        selected_pair=replace(
            base.selected_pair,
            prescription_snapshot_id="foreign-snapshot",
        ),
    )
    with pytest.raises(RuntimeShadowConsistencyError):
        evaluate_runtime_shadow_chain(
            subject_ref=SUBJECT,
            matching=forged,
            snapshot=RUN_PRESCRIPTION,
            session=RUN_SESSION,
            mapping=RUN_MAPPING,
            execution=RUN_EXECUTION,
            stability=stability(),
            evaluation_id="chain-evaluation",
            evaluated_at=T0 + timedelta(hours=9),
            provenance_ref=PROV,
        )


def test_chain_has_no_database_dependency(monkeypatch):
    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: pytest.fail("database access"))
    assert chain().outcome.runtime_input.evaluation_id == "chain-evaluation"
