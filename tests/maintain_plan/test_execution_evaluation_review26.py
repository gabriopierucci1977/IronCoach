"""Regressions for findings reported against the superseded PR #26 head."""

from dataclasses import replace
import sqlite3

import pytest

from backend.maintain_plan.execution_evaluation_service import evaluate, evaluate_source_conflict_impact
from backend.maintain_plan.matching_service import build_mapping
from backend.maintain_plan.models import *
from backend.maintain_plan.repository import MaintainPlanRepository
from backend.maintain_plan.schema import MIGRATIONS, SCHEMA_VERSION, run_migrations
from tests.maintain_plan.fixtures import (BRICK_MAPPING, BRICK_PRESCRIPTION, BRICK_SESSION,
    NOW, RUN_PRESCRIPTION, RUN_SESSION, planned, prescription)
from tests.maintain_plan.test_execution_evaluation_hardening import canonical
from tests.maintain_plan.test_lifecycle_service import CONFLICT, resolution_log


def conflict_session_and_mapping():
    snapshot, session, mapping = canonical()
    conflict = dict(CONFLICT, field_path="components.run.quantity_observation")
    return snapshot, replace(session, source_conflicts=(conflict,)), mapping, conflict


def test_evaluated_impact_or_conflict_without_projection_is_rejected():
    snapshot, session, mapping, conflict = conflict_session_and_mapping()
    impact = evaluate_source_conflict_impact(session, mapping, conflict,
        impact_evaluation_id="impact", evaluation_version="1", evaluated_at=NOW)
    with pytest.raises(ValueError, match="exact projection and impact coverage"):
        evaluate(snapshot, session, mapping, evaluation_id="evaluation", evaluated_at=NOW,
                 conflict_impacts=(impact,))
    with pytest.raises(ValueError, match="exact projection and impact coverage"):
        evaluate(snapshot, session, mapping, evaluation_id="evaluation", evaluated_at=NOW)


def test_composition_is_compared_even_with_identical_components():
    multisport = replace(BRICK_SESSION, composition=Composition.MULTISPORT)
    result = evaluate(BRICK_PRESCRIPTION, multisport, BRICK_MAPPING,
                      evaluation_id="composition", evaluated_at=NOW)
    assert result.session_composition_result.status is AdherenceStatus.NOT_MET
    assert result.identity_aggregate.status is not AdherenceStatus.MET
    assert result.overall is not OverallStatus.IN_LINE
    equal = evaluate(BRICK_PRESCRIPTION, BRICK_SESSION, BRICK_MAPPING,
                     evaluation_id="equal", evaluated_at=NOW)
    assert equal.session_composition_result.status is AdherenceStatus.MET


def test_pool_swim_at_92_percent_uses_structured_distance_band():
    component = planned("swim", 0, Discipline.SWIM, mode=Mode.POOL,
                        quantity_target=PrescribedTarget(1000))
    component = replace(component, quantity=replace(component.quantity,
        primary_metric=QuantityMetric.DISTANCE, unit="meters",
        quantity_band_policy_ref=PolicyRef("pool-distance-bands", "1")))
    snapshot = prescription(component)
    observed = replace(RUN_SESSION.components[0], discipline=Discipline.SWIM,
        environment=Environment.OUTDOOR, mode=Mode.POOL,
        quantity_primary_metric="distance", quantity_unit="meters",
        quantity_observation={"value": 920},
        blocks=(ObservedBlock("swim-main", 0, block_type=BlockType.MAIN_SET),),
        intensity_methods=("RPE",), intensity_observations={
            "valid_coverage": .9, "time_in_target": .9, "time_above": 0, "time_below": .1})
    session = replace(RUN_SESSION, components=(observed,))
    mapping = build_mapping(snapshot, session, mapping_id="swim-map", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    result = evaluate(snapshot, session, mapping, evaluation_id="swim", evaluated_at=NOW)
    assert result.component_results[0].quantity.status is AdherenceStatus.PARTIALLY_MET
    assert result.component_results[0].quantity.band is SeverityBand.SECONDARY


@pytest.mark.parametrize("authorized,expected", [(True, AdherenceStatus.MET),
                                                   (False, AdherenceStatus.NOT_MET)])
def test_evaluator_honors_only_explicit_substitution(authorized, expected):
    snapshot, session, mapping = canonical()
    substitution = AllowedSubstitution(Discipline.BIKE, Environment.OUTDOOR, Mode.ROAD,
                                       PolicyRef("substitution", "1"))
    component = replace(snapshot.components[0],
        allowed_substitutions=(substitution,) if authorized else ())
    snapshot = replace(snapshot, components=(component,))
    session = replace(session, components=(replace(session.components[0], discipline=Discipline.BIKE),))
    result = evaluate(snapshot, session, mapping, evaluation_id="substitution", evaluated_at=NOW)
    assert result.component_results[0].identity.status is expected


def test_unresolved_impact_without_mapping_round_trips_and_evaluated_is_rejected(tmp_path):
    _, session, _, conflict = conflict_session_and_mapping()
    repository = MaintainPlanRepository(tmp_path / "unresolved.db")
    repository.create_actual_session(session)
    repository.create_source_conflict(session.session_id, conflict)
    unresolved = evaluate_source_conflict_impact(session, None, conflict,
        impact_evaluation_id="unresolved", evaluation_version="1", evaluated_at=NOW)
    repository.create_source_conflict_impact_evaluation(unresolved)
    assert repository.get_source_conflict_impact_evaluation("unresolved") == unresolved
    invalid = replace(unresolved, conflict_impact_evaluation_id="invalid",
                      status=ConflictImpactStatus.EVALUATED)
    with pytest.raises(ValueError):
        repository.create_source_conflict_impact_evaluation(invalid)
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute("SELECT count(*) FROM maintain_plan_source_conflict_impact_evaluations").fetchone() == (1,)


def test_v5_to_v6_preserves_rows_payload_constraints_and_is_idempotent(tmp_path):
    path = tmp_path / "upgrade.db"
    run_migrations(path, MIGRATIONS[:5])
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("INSERT INTO maintain_plan_prescription_snapshots VALUES ('ps','w','d','v','v','p')")
        connection.execute("INSERT INTO maintain_plan_actual_sessions VALUES ('s','2026-01-01','single','v','v','p')")
        connection.execute("INSERT INTO maintain_plan_prescription_mappings VALUES ('m','ps','s','AUTOMATIC','v','p')")
        connection.execute("INSERT INTO maintain_plan_source_conflicts VALUES ('c','s','v','v','p')")
        connection.execute("INSERT INTO maintain_plan_source_conflict_impact_evaluations VALUES ('i','1','s','c','m','EVALUATED','p','v','v','payload')")
        before = connection.execute("SELECT * FROM maintain_plan_source_conflict_impact_evaluations").fetchall()
    run_migrations(path); run_migrations(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT * FROM maintain_plan_source_conflict_impact_evaluations").fetchall() == before
        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (6,)
        info = connection.execute("PRAGMA table_info(maintain_plan_source_conflict_impact_evaluations)").fetchall()
        assert next(row for row in info if row[1] == "prescription_mapping_ref")[3] == 0
    assert SCHEMA_VERSION == 6
