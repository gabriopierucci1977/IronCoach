from dataclasses import replace
from datetime import timedelta

import pytest

from backend.maintain_plan.runtime_stability_provider import RuntimeStabilityProviderError
from backend.maintain_plan.stability_models import VersionedArtifactRef
from backend.maintain_plan.runtime_typed_shadow_chain import evaluate_runtime_typed_shadow_chain
from backend.maintain_plan.runtime_matching_decision import CandidateCardinality, DecisionStatus, decide_runtime_matching
from backend.maintain_plan.runtime_matching_scope import validate_runtime_matching_scope
from tests.maintain_plan.fixtures import RUN_MAPPING, RUN_PRESCRIPTION, RUN_SESSION
from tests.maintain_plan.test_final_outcome_service import PROV, RUN_EXECUTION, T0
from tests.maintain_plan.test_general_stability_service import make_input

SUBJECT = "athlete-1"
SNAPSHOT_REF = VersionedArtifactRef("prescription-snapshot", "snapshot-1", "1")
SESSION_REF = VersionedArtifactRef("actual-session", "session-1", "1")


def runtime_stability_input():
    value = make_input()
    binding = replace(value.prescription_binding, prescription_snapshot_ref=SNAPSHOT_REF)
    boundary = replace(value.actual_session_boundary, actual_session_ref=SESSION_REF)
    candidates = replace(value.candidate_set, actual_session_ref=SESSION_REF)
    projection = (
        None
        if value.reported_problems_projection is None
        else replace(value.reported_problems_projection, actual_session_ref=SESSION_REF)
    )
    return replace(
        value,
        prescription_binding=binding,
        actual_session_boundary=boundary,
        candidate_set=candidates,
        reported_problems_projection=projection,
    )


def matching():
    scope = validate_runtime_matching_scope(SUBJECT, (RUN_PRESCRIPTION,), (RUN_SESSION,))
    result = decide_runtime_matching(scope)
    assert result.status is DecisionStatus.MATCHED
    assert result.cardinality is CandidateCardinality.ONE
    return result


def chain():
    return evaluate_runtime_typed_shadow_chain(
        subject_ref=SUBJECT,
        matching=matching(),
        snapshot=RUN_PRESCRIPTION,
        session=RUN_SESSION,
        mapping=RUN_MAPPING,
        execution=RUN_EXECUTION,
        stability_input=runtime_stability_input(),
        stability_evaluation_id="runtime-stability-1",
        outcome_evaluation_id="runtime-outcome-1",
        evaluated_at=T0 + timedelta(hours=9),
        provenance_ref=PROV,
    )


def test_typed_stability_feeds_consistency_and_outcome_chain():
    result = chain()
    assert result.stability.evaluation.evaluation_id == "runtime-stability-1"
    assert result.chain.outcome.runtime_input.evaluation_id == "runtime-outcome-1"


def test_invalid_stability_input_stops_before_outcome():
    with pytest.raises(RuntimeStabilityProviderError):
        evaluate_runtime_typed_shadow_chain(
            subject_ref=SUBJECT,
            matching=matching(),
            snapshot=RUN_PRESCRIPTION,
            session=RUN_SESSION,
            mapping=RUN_MAPPING,
            execution=RUN_EXECUTION,
            stability_input=object(),
            stability_evaluation_id="runtime-stability-1",
            outcome_evaluation_id="runtime-outcome-1",
            evaluated_at=T0 + timedelta(hours=9),
            provenance_ref=PROV,
        )


def test_typed_chain_has_no_database_dependency(monkeypatch):
    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: pytest.fail("database access"))
    assert chain().stability.evaluation.evaluation_id == "runtime-stability-1"
