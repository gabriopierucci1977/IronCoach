from dataclasses import replace
import pytest

from backend.maintain_plan.models import PlannedComponentRef
from backend.maintain_plan.runtime_matching_decision import CandidateCardinality, DecisionStatus, decide_runtime_matching
from backend.maintain_plan.runtime_matching_scope import validate_runtime_matching_scope
from backend.maintain_plan.runtime_shadow_consistency import RuntimeShadowConsistencyError, validate_runtime_shadow_consistency
from tests.maintain_plan.fixtures import RUN_MAPPING, RUN_PRESCRIPTION, RUN_SESSION
from tests.maintain_plan.test_final_outcome_service import RUN_EXECUTION, stability

SUBJECT = "athlete-1"


def matching():
    scope = validate_runtime_matching_scope(SUBJECT, (RUN_PRESCRIPTION,), (RUN_SESSION,))
    result = decide_runtime_matching(scope)
    assert result.status is DecisionStatus.MATCHED
    assert result.cardinality is CandidateCardinality.ONE
    return result


def chain():
    return validate_runtime_shadow_consistency(subject_ref=SUBJECT, matching=matching(), snapshot=RUN_PRESCRIPTION, session=RUN_SESSION, mapping=RUN_MAPPING, execution=RUN_EXECUTION, stability=stability())


def test_accepts_authoritative_chain():
    result = chain()
    assert result.subject_ref == SUBJECT
    assert result.execution.prescription_mapping_ref == result.mapping.mapping_id


def test_rejects_forged_pair():
    base = matching()
    forged = replace(base, selected_pair=replace(base.selected_pair, prescription_snapshot_id="foreign-snapshot"))
    with pytest.raises(RuntimeShadowConsistencyError, match="authoritative"):
        validate_runtime_shadow_consistency(subject_ref=SUBJECT, matching=forged, snapshot=RUN_PRESCRIPTION, session=RUN_SESSION, mapping=RUN_MAPPING, execution=RUN_EXECUTION, stability=stability())


def test_rejects_foreign_component_mapping():
    item = replace(RUN_MAPPING.component_mappings[0], planned_component_ref=PlannedComponentRef("foreign", "run"))
    with pytest.raises(RuntimeShadowConsistencyError, match="unknown planned"):
        validate_runtime_shadow_consistency(subject_ref=SUBJECT, matching=matching(), snapshot=RUN_PRESCRIPTION, session=RUN_SESSION, mapping=replace(RUN_MAPPING, component_mappings=(item,)), execution=RUN_EXECUTION, stability=stability())


def test_has_no_database_dependency(monkeypatch):
    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: pytest.fail("database access"))
    assert chain().subject_ref == SUBJECT


def test_does_not_persist_mapping():
    assert chain().mapping is RUN_MAPPING
