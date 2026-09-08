"""Adversarial matrix for normative execution evaluation behavior."""

from dataclasses import FrozenInstanceError, replace
import sqlite3

import pytest

from backend.maintain_plan.execution_evaluation_service import evaluate, evaluate_source_conflict_impact
from backend.maintain_plan.matching_service import build_mapping, match
from backend.maintain_plan.models import *
from backend.maintain_plan.schema import MIGRATIONS, run_migrations
from tests.maintain_plan.fixtures import NOW, RUN_PRESCRIPTION, RUN_SESSION
from tests.maintain_plan.test_lifecycle_service import (
    CONFLICT, conflict_projection, resolution_event)


def canonical(*, quantity=60, valid=.9, in_target=.85, above=.05, below=.1,
              support=SupportStatus.SUPPORTED):
    snapshot = replace(RUN_PRESCRIPTION, components=(replace(
        RUN_PRESCRIPTION.components[0], support_status=support),))
    component = replace(RUN_SESSION.components[0], environment=Environment.OUTDOOR,
        mode=Mode.ROAD, blocks=(ObservedBlock("run-main", 0, block_type=BlockType.MAIN_SET),),
        quantity_primary_metric="active_duration", quantity_unit="minutes",
        quantity_observation=None if quantity is None else {"value": quantity},
        intensity_methods=("RPE",), intensity_observations=None if valid is None else {
            "valid_coverage": valid, "time_in_target": in_target,
            "time_above": above, "time_below": below})
    session = replace(RUN_SESSION, components=(component,))
    mapping = build_mapping(snapshot, session, mapping_id="map", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    return snapshot, session, mapping


def run_evaluation(**kwargs):
    snapshot, session, mapping = canonical(**kwargs)
    return evaluate(snapshot, session, mapping, evaluation_id="eval", evaluated_at=NOW)


@pytest.mark.parametrize("value,status,direction,band", [
    (47.999, AdherenceStatus.NOT_MET, Direction.LOWER, SeverityBand.OUT_OF_BAND),
    (48, AdherenceStatus.PARTIALLY_MET, Direction.LOWER, SeverityBand.SECONDARY),
    (53.999, AdherenceStatus.PARTIALLY_MET, Direction.LOWER, SeverityBand.SECONDARY),
    (54, AdherenceStatus.MET, Direction.IN_LINE, SeverityBand.MAIN),
    (63, AdherenceStatus.MET, Direction.IN_LINE, SeverityBand.MAIN),
    (63.001, AdherenceStatus.PARTIALLY_MET, Direction.HIGHER, SeverityBand.SECONDARY),
    (69, AdherenceStatus.PARTIALLY_MET, Direction.HIGHER, SeverityBand.SECONDARY),
    (69.001, AdherenceStatus.NOT_MET, Direction.HIGHER, SeverityBand.OUT_OF_BAND),
])
def test_quantity_boundaries_are_inclusive_and_never_coerced(value, status, direction, band):
    result = run_evaluation(quantity=value).component_results[0].quantity
    assert (result.status, result.direction, result.band) == (status, direction, band)


@pytest.mark.parametrize("valid,in_target,status,direction,band", [
    (.7999, .9, AdherenceStatus.INSUFFICIENT_DATA, None, None),
    (.8, .8, AdherenceStatus.MET, Direction.IN_LINE, SeverityBand.MAIN),
    (.9, .7999, AdherenceStatus.PARTIALLY_MET, Direction.LOWER, SeverityBand.SECONDARY),
    (.9, .6, AdherenceStatus.PARTIALLY_MET, Direction.LOWER, SeverityBand.SECONDARY),
    (.9, .5999, AdherenceStatus.NOT_MET, Direction.LOWER, SeverityBand.OUT_OF_BAND),
])
def test_continuous_intensity_boundaries(valid, in_target, status, direction, band):
    result = run_evaluation(valid=valid, in_target=in_target, above=.1, below=.2).component_results[0].intensity
    assert (result.status, result.direction, result.band) == (status, direction, band)


@pytest.mark.parametrize("above,below,direction", [
    (.2, .1, Direction.HIGHER), (.1, .2, Direction.LOWER), (.1, .1, Direction.MIXED),
    (None, .1, Direction.UNDETERMINED),
])
def test_intensity_direction_has_no_heuristic_tie_break(above, below, direction):
    assert run_evaluation(in_target=.7, above=above, below=below).component_results[0].intensity.direction is direction


@pytest.mark.parametrize("quantity,valid,missing", [
    (None, .9, "quantity"), (60, None, "intensity"), (None, None, "both")])
def test_missing_required_dimension_makes_dose_and_overall_insufficient(quantity, valid, missing):
    result = run_evaluation(quantity=quantity, valid=valid)
    component = result.component_results[0]
    assert component.dose.status is DoseStatus.INSUFFICIENT_DATA
    assert component.dose.direction is component.dose.severity_band is None
    assert result.overall is OverallStatus.INSUFFICIENT_DATA
    assert missing


def test_unsupported_capability_has_detail_but_no_partial_session_aggregate():
    result = run_evaluation(support=SupportStatus.UNSUPPORTED)
    component = result.component_results[0]
    assert component.support_status is SupportStatus.UNSUPPORTED
    assert (component.identity, component.quantity, component.intensity,
            component.structure, component.dose) == (None, None, None, None, None)
    assert result.evaluation_coverage.status is CoverageStatus.UNSUPPORTED
    assert result.overall is result.dose_aggregate is None


def test_overall_precedence_and_no_compensation():
    insufficient = run_evaluation(quantity=None, in_target=.1)
    assert insufficient.component_results[0].intensity.status is AdherenceStatus.NOT_MET
    assert insufficient.overall is OverallStatus.INSUFFICIENT_DATA
    different = run_evaluation(quantity=40, in_target=.9)
    assert different.overall is OverallStatus.DIFFERENT
    partial = run_evaluation(quantity=50, in_target=.9)
    assert partial.overall is OverallStatus.PARTIALLY_IN_LINE


def test_direct_id_preserves_execution_deviation_and_evaluation_is_immutable():
    snapshot, session, _ = canonical(quantity=40)
    direct = DirectIdEvidence("direct", session.session_id, snapshot.workout_id,
                              "Garmin", {})
    result = match(snapshot, (session,), matching_result_id="matched", mapping_id="direct-map",
                   created_at=NOW, direct_id_evidence=(direct,))
    evaluation = evaluate(snapshot, session, result.prescription_mapping,
                          evaluation_id="direct-eval", evaluated_at=NOW)
    assert evaluation.component_results[0].quantity.status is AdherenceStatus.NOT_MET
    with pytest.raises(FrozenInstanceError):
        evaluation.overall = OverallStatus.IN_LINE


@pytest.mark.parametrize("path,dimensions", [
    ("components.run.discipline", (AffectedDimension.IDENTITY, AffectedDimension.DECISION)),
    ("components.run.environment", (AffectedDimension.IDENTITY, AffectedDimension.DECISION)),
    ("components.run.quantity_observation", (AffectedDimension.QUANTITY, AffectedDimension.DOSE, AffectedDimension.DECISION)),
    ("components.run.intensity_observations", (AffectedDimension.INTENSITY, AffectedDimension.DOSE, AffectedDimension.DECISION)),
    ("components.run.blocks.main.block_type", (AffectedDimension.STRUCTURE, AffectedDimension.DECISION)),
    ("components.run.blocks.main.repetitions", (AffectedDimension.STRUCTURE, AffectedDimension.DECISION)),
    ("transitions.run-bike.duration_minutes", (AffectedDimension.STRUCTURE, AffectedDimension.DECISION)),
])
def test_conflict_field_path_classification_is_contract_only(path, dimensions):
    snapshot, session, mapping = canonical()
    conflict = {"conflict_id": "c", "schema_version": "maintain-plan-source-conflict/1.0.0-draft",
                "field_path": path, "values": ({"value": 1, "source": "Garmin"},
                {"value": 2, "source": "Strava"}), "provenance": {}, "captured_at": NOW,
                "missing_fields": (), "warnings": ()}
    session = replace(session, source_conflicts=(conflict,))
    impact = evaluate_source_conflict_impact(session, mapping, conflict,
        impact_evaluation_id="impact", evaluation_version="1", evaluated_at=NOW)
    assert impact.affected_dimensions == dimensions


def test_irrelevant_conflict_has_no_affected_axis_and_duplicate_is_rejected():
    snapshot, session, mapping = canonical()
    conflict = {"conflict_id": "c", "schema_version": "maintain-plan-source-conflict/1.0.0-draft",
                "field_path": "weather_context.temperature", "values": ({"value": 1, "source": "A"}, {"value": 2, "source": "B"}),
                "provenance": {}, "captured_at": NOW, "missing_fields": (), "warnings": ()}
    session = replace(session, source_conflicts=(conflict,))
    impact = evaluate_source_conflict_impact(session, mapping, conflict,
        impact_evaluation_id="impact", evaluation_version="1", evaluated_at=NOW)
    assert impact.status is ConflictImpactStatus.EVALUATED
    assert impact.affected_dimensions == ()
    duplicate = replace(session, source_conflicts=(conflict, conflict))
    with pytest.raises(ValueError, match="source conflict"):
        evaluate_source_conflict_impact(duplicate, mapping, conflict,
            impact_evaluation_id="bad", evaluation_version="1", evaluated_at=NOW)


@pytest.mark.parametrize("projection,status", [
    (conflict_projection(()), AdherenceStatus.INSUFFICIENT_DATA),
    (conflict_projection((resolution_event("resolved", 1,
        ConflictResolutionEventType.RESOLVED, value=10, source="garmin"),), "resolved"),
     AdherenceStatus.MET),
    (conflict_projection((resolution_event("unknown", 1,
        ConflictResolutionEventType.UNKNOWN_ANSWER),), "unknown"),
     AdherenceStatus.INSUFFICIENT_DATA),
    (conflict_projection((resolution_event("first", 1,
        ConflictResolutionEventType.RESOLVED, value=10, source="garmin"),
        resolution_event("withdrawn", 2, ConflictResolutionEventType.RESOLUTION_WITHDRAWN,
                         "first", withdrawn="first")), "withdrawn"),
     AdherenceStatus.INSUFFICIENT_DATA),
])
def test_projection_state_controls_only_the_affected_axis(projection, status):
    snapshot, session, mapping = canonical()
    conflict = dict(CONFLICT, field_path="components.run.quantity_observation")
    session = replace(session, source_conflicts=(conflict,))
    impact = SourceConflictImpactEvaluation("impact", "1",
        SourceConflictRef(session.session_id, conflict["conflict_id"]), mapping.mapping_id,
        ConflictImpactStatus.EVALUATED, (AffectedDimension.QUANTITY, AffectedDimension.DOSE, AffectedDimension.DECISION),
        PolicyRef("maintain-plan-source-conflict-impact", "1.0.0-draft"), {}, NOW)
    result = evaluate(snapshot, session, mapping, evaluation_id="conflicted", evaluated_at=NOW,
                      conflict_projections=(projection,), conflict_impacts=(impact,))
    component = result.component_results[0]
    assert component.quantity.status is status
    assert component.identity.status is AdherenceStatus.MET
    assert component.intensity.status is AdherenceStatus.MET
    assert component.structure.status is AdherenceStatus.MET


def test_projection_and_impact_cross_ownership_are_validation_errors():
    snapshot, session, mapping = canonical()
    session = replace(session, source_conflicts=(CONFLICT,))
    projection = replace(conflict_projection(()), actual_session_ref=ActualSessionRef("foreign"))
    with pytest.raises(ValueError, match="hash mismatch|foreign-session"):
        evaluate(snapshot, session, mapping, evaluation_id="bad", evaluated_at=NOW,
                 conflict_projections=(projection,))
    impact = SourceConflictImpactEvaluation("impact", "1",
        SourceConflictRef(session.session_id, CONFLICT["conflict_id"]), "foreign-map",
        ConflictImpactStatus.EVALUATED, (AffectedDimension.QUANTITY,),
        PolicyRef("maintain-plan-source-conflict-impact", "1.0.0-draft"), {}, NOW)
    with pytest.raises(ValueError, match="cross-mapping"):
        evaluate(snapshot, session, mapping, evaluation_id="bad", evaluated_at=NOW,
                 conflict_impacts=(impact,))
    valid_projection = conflict_projection(())
    with pytest.raises(ValueError, match="must not be duplicated"):
        evaluate(snapshot, session, mapping, evaluation_id="bad", evaluated_at=NOW,
                 conflict_projections=(valid_projection, valid_projection))
    valid_impact = replace(impact, prescription_mapping_ref=mapping.mapping_id)
    with pytest.raises(ValueError, match="must not be duplicated"):
        evaluate(snapshot, session, mapping, evaluation_id="bad", evaluated_at=NOW,
                 conflict_impacts=(valid_impact, valid_impact))


def test_invalid_input_raises_validation_error_without_partial_result():
    snapshot, session, mapping = canonical()
    foreign = replace(mapping, actual_session_ref="foreign")
    with pytest.raises(ValueError, match="mapping") as error:
        evaluate(snapshot, session, foreign, evaluation_id="bad", evaluated_at=NOW)
    assert not isinstance(error.value, (KeyError, IndexError, AttributeError))


def test_v1_through_v5_checksums_and_real_v4_upgrade_are_exact(tmp_path):
    expected = {
        1: "527e9211c82ee7f94791c9feef8c9dbb42220cd88182e1dcb3471319e6966a0c",
        2: "843592bd9964051fa377912770a953aec3f8a5675133dd603f258883663b26fc",
        3: "7607d1dd4e9d6a7bf7ebae0668986d9a938572560e52f46d506b22123303ba00",
        4: "8b2dbd6ff037088309066e82829fa7f708a49cbfdc0447581f2c5b117025c3e1",
        5: "7a9f07febe192eedc230b927bc582d4b069c6a21b3d5acb64482f1021da058a8"}
    assert {m.version: m.checksum for m in MIGRATIONS} == expected
    path = tmp_path / "upgrade.db"
    run_migrations(path, MIGRATIONS[:4])
    with sqlite3.connect(path) as connection:
        before = connection.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
    run_migrations(path)
    run_migrations(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM maintain_plan_schema_migrations").fetchone() == (5,)
        assert connection.execute("SELECT count(*) FROM maintain_plan_source_conflict_impact_evaluations").fetchone() == (0,)
        assert before
