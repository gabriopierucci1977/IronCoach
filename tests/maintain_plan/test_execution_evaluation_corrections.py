"""Regression tests for the independent P1/P2 execution review."""

from dataclasses import replace

import pytest

from backend.maintain_plan.execution_evaluation_service import (
    classify_source_conflict_field_path, evaluate, evaluate_source_conflict_impact)
from backend.maintain_plan.matching_service import build_mapping
from backend.maintain_plan.models import *
from tests.maintain_plan.fixtures import INTERVAL_PRESCRIPTION, NOW, RUN_SESSION
from tests.maintain_plan.test_lifecycle_service import CONFLICT, conflict_projection


def interval_case(targets, *, valid=None, window=EvaluationWindow.AVERAGE,
                  include_recovery=True, order=None):
    count = len(targets)
    block = replace(INTERVAL_PRESCRIPTION.components[0].structure.blocks[0],
                    planned_repetitions=count, evaluation_window=window)
    component = replace(INTERVAL_PRESCRIPTION.components[0],
        structure=replace(INTERVAL_PRESCRIPTION.components[0].structure, blocks=(block,)))
    snapshot = replace(INTERVAL_PRESCRIPTION, components=(component,))
    indices = list(range(count)) if order is None else order
    repetitions = tuple(ObservedRepetition(
        f"rep-{index}", index, block.block_id,
        intensity_observation={"value": 4.5},
        valid_coverage=None if valid is None else {"value": valid[index]},
        time_in_target={"value": targets[index], "window": window.value},
    ) for index in indices)
    blocks = [ObservedBlock(block.block_id, 0, repetitions, BlockType.WORK)]
    if include_recovery:
        blocks.append(ObservedBlock("recovery", 1, block_type=BlockType.RECOVERY))
    observed = replace(RUN_SESSION.components[0], environment=Environment.OUTDOOR,
        mode=Mode.ROAD, blocks=tuple(blocks), quantity_primary_metric="active_duration",
        quantity_unit="minutes", quantity_observation={"value": 2400},
        intensity_methods=("RPE",), intensity_observations={
            "valid_coverage": 1, "time_in_target": 1, "time_above": 0, "time_below": 0})
    session = replace(RUN_SESSION, components=(observed,))
    mapping = build_mapping(snapshot, session, mapping_id="interval-map", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    return snapshot, session, mapping


def evaluated(case):
    return evaluate(*case, evaluation_id="interval-evaluation", evaluated_at=NOW)


def test_intervals_zero_repetitions_ignore_favorable_component_aggregate():
    snapshot, session, mapping = interval_case([.8] * 6, valid=[.8] * 6)
    empty = replace(session.components[0].blocks[0], repetitions=())
    session = replace(session, components=(replace(session.components[0],
        blocks=(empty,) + session.components[0].blocks[1:]),))
    mapping = build_mapping(snapshot, session, mapping_id="zero-map", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    result = evaluate(snapshot, session, mapping, evaluation_id="zero-reps", evaluated_at=NOW).component_results[0]
    assert result.intensity.status is AdherenceStatus.INSUFFICIENT_DATA
    assert result.structure.status is AdherenceStatus.NOT_MET


def test_one_required_repetition_unevaluable_invalidates_interval_intensity():
    case = interval_case([.8] * 6, valid=[.8, .8, .79, .8, .8, .8])
    assert evaluated(case).component_results[0].intensity.status is AdherenceStatus.INSUFFICIENT_DATA


@pytest.mark.parametrize("hits,status,band", [
    (10, AdherenceStatus.MET, SeverityBand.MAIN),
    (9, AdherenceStatus.MET, SeverityBand.MAIN),
    (8, AdherenceStatus.PARTIALLY_MET, SeverityBand.SECONDARY),
    (7, AdherenceStatus.PARTIALLY_MET, SeverityBand.SECONDARY),
    (6, AdherenceStatus.NOT_MET, SeverityBand.OUT_OF_BAND),
])
def test_interval_90_and_70_percent_boundaries(hits, status, band):
    targets = [.8] * hits + [.69] * (10 - hits)
    result = evaluated(interval_case(targets, valid=[.8] * 10)).component_results[0].intensity
    assert (result.status, result.band) == (status, band)


def test_wrong_or_missing_evaluation_window_is_unevaluable():
    snapshot, session, mapping = interval_case([.8] * 6, valid=[.8] * 6)
    repetition = replace(session.components[0].blocks[0].repetitions[0],
                         time_in_target={"value": .8, "window": "PEAK"})
    block = replace(session.components[0].blocks[0], repetitions=(repetition,) + session.components[0].blocks[0].repetitions[1:])
    session = replace(session, components=(replace(session.components[0], blocks=(block,) + session.components[0].blocks[1:]),))
    assert evaluate(snapshot, session, mapping, evaluation_id="bad-window", evaluated_at=NOW).component_results[0].intensity.status is AdherenceStatus.INSUFFICIENT_DATA


def test_missing_recovery_and_wrong_repetition_order_affect_structure():
    no_recovery = evaluated(interval_case([.8] * 6, valid=[.8] * 6, include_recovery=False))
    assert no_recovery.component_results[0].structure.status is AdherenceStatus.NOT_MET
    wrong_order = evaluated(interval_case([.8] * 6, valid=[.8] * 6,
                                           order=[0, 2, 1, 3, 4, 5]))
    assert wrong_order.component_results[0].structure.status is AdherenceStatus.PARTIALLY_MET


@pytest.mark.parametrize("path", [
    "weather_context.discipline", "weather_context.blocks",
    "notes.duration_minutes", "components.run.unknown.distance",
    "transitions.duration_minutes", None, True,
])
def test_unknown_field_paths_never_match_by_token(path):
    assert classify_source_conflict_field_path(path) == ()


def test_field_path_dimension_propagation_is_ordered_and_complete():
    assert classify_source_conflict_field_path("components.run.quantity_observation") == (
        AffectedDimension.QUANTITY, AffectedDimension.DOSE, AffectedDimension.DECISION)
    assert classify_source_conflict_field_path("components.run.intensity_observations") == (
        AffectedDimension.INTENSITY, AffectedDimension.DOSE, AffectedDimension.DECISION)


@pytest.mark.parametrize("change", [
    {"projection_version": "tampered"}, {"projection_hash": "0" * 64},
    {"projection_hash_algorithm": "MD5"},
    {"projection_serialization_policy_id": "wrong"},
    {"through_event_sequence": 99}, {"provenance": {}},
    {"status": SourceConflictProjectionStatus.RESOLVED},
])
def test_corrupt_projection_cannot_influence_evaluation(change):
    snapshot = INTERVAL_PRESCRIPTION
    session = replace(RUN_SESSION, source_conflicts=(CONFLICT,))
    mapping = build_mapping(snapshot, session, mapping_id="projection-map", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    projection = replace(conflict_projection(()), **change)
    with pytest.raises(ValueError):
        evaluate(snapshot, session, mapping, evaluation_id="bad-projection", evaluated_at=NOW,
                 conflict_projections=(projection,))


@pytest.mark.parametrize("field,value", [
    ("evaluated_at", NOW.replace(tzinfo=None)),
    ("provenance", None), ("missing_fields", None),
    ("affected_dimensions", (AffectedDimension.IDENTITY, AffectedDimension.IDENTITY)),
    ("evaluation_version", True),
])
def test_corrupt_impact_cannot_influence_evaluation(field, value):
    snapshot = INTERVAL_PRESCRIPTION
    session = replace(RUN_SESSION, source_conflicts=(CONFLICT,))
    mapping = build_mapping(snapshot, session, mapping_id="impact-map", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    impact = evaluate_source_conflict_impact(session, mapping, CONFLICT,
        impact_evaluation_id="impact", evaluation_version="1", evaluated_at=NOW)
    with pytest.raises(ValueError):
        evaluate(snapshot, session, mapping, evaluation_id="bad-impact", evaluated_at=NOW,
                 conflict_impacts=(replace(impact, **{field: value}),))
