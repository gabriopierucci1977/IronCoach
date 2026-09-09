from dataclasses import replace

import pytest

from backend.maintain_plan.execution_evaluation_service import (
    evaluate, evaluate_source_conflict_impact)
from backend.maintain_plan.matching_service import build_mapping
from backend.maintain_plan.models import *
from tests.maintain_plan.fixtures import NOW, RUN_PRESCRIPTION, RUN_SESSION


def canonical_run():
    observed = replace(RUN_SESSION.components[0], environment=Environment.OUTDOOR,
        mode=Mode.ROAD, quantity_primary_metric="active_duration",
        quantity_unit="minutes", quantity_observation={"value": 60},
        blocks=(ObservedBlock("run-main", 0, block_type=BlockType.MAIN_SET),),
        intensity_methods=("RPE",), intensity_observations={
            "valid_coverage": .9, "time_in_target": .85,
            "time_above": .05, "time_below": .1})
    session = replace(RUN_SESSION, components=(observed,))
    mapping = build_mapping(RUN_PRESCRIPTION, session, mapping_id="evaluated-mapping",
        created_at=NOW, resolution_method=ResolutionMethod.AUTOMATIC)
    return session, mapping


def test_evaluates_simple_session_deterministically():
    session, mapping = canonical_run()
    result = evaluate(RUN_PRESCRIPTION, session, mapping,
        evaluation_id="evaluation-new", evaluated_at=NOW)
    assert result.overall is OverallStatus.IN_LINE
    assert result.component_results[0].dose.direction is Direction.IN_LINE
    assert result.prescription_mapping_ref == mapping.mapping_id


def test_planned_and_observed_only_are_retained_exactly_once():
    session, _ = canonical_run()
    session = replace(session, composition=Composition.MULTISPORT,
        components=session.components + (replace(session.components[0], component_id="extra", component_index=1),))
    snapshot = replace(RUN_PRESCRIPTION, composition=Composition.MULTISPORT,
        components=RUN_PRESCRIPTION.components + (
        replace(RUN_PRESCRIPTION.components[0], component_id="missing", component_index=1),))
    mapping = build_mapping(snapshot, session, mapping_id="mixed-mapping", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    # Positional matching intentionally preserves deviations; construct explicit missing/extra mapping.
    mapping = replace(mapping, component_mappings=(mapping.component_mappings[0],
        ComponentMapping(PlannedComponentRef("snapshot-1", "missing"), None,
                         Requiredness.REQUIRED, SupportStatus.SUPPORTED,
                         snapshot.components[1].capability_policy, MatchStatus.PLANNED_ONLY),
        ComponentMapping(None, ObservedComponentRef("session-1", "extra"), None,
                         SupportStatus.SUPPORTED, snapshot.components[0].capability_policy,
                         MatchStatus.OBSERVED_ONLY)), block_mappings=(
        BlockMapping(PlannedBlockRef("snapshot-1", "run", "run-main"),
                     ObservedBlockRef("session-1", "run", "run-main"), MatchStatus.MATCHED),
        BlockMapping(PlannedBlockRef("snapshot-1", "missing", "run-main"), None, MatchStatus.PLANNED_ONLY),
        BlockMapping(None, ObservedBlockRef("session-1", "extra", "run-main"), MatchStatus.OBSERVED_ONLY)),
        repetition_mappings=())
    result = evaluate(snapshot, session, mapping, evaluation_id="evaluation-mixed", evaluated_at=NOW)
    assert [x.match_status for x in result.component_results] == [
        MatchStatus.MATCHED, MatchStatus.PLANNED_ONLY, MatchStatus.OBSERVED_ONLY]
    assert result.session_composition_result.extra_observed_component_refs


def test_conflict_impact_is_exact_and_ghost_is_rejected():
    session, mapping = canonical_run()
    conflict = {"conflict_id": "c1", "schema_version": "maintain-plan-source-conflict/1.0.0-draft",
                "field_path": "components.run.quantity_observation", "values": ({"value": 59, "source": "Garmin"}, {"value": 60, "source": "Strava"}),
                "provenance": {}, "captured_at": NOW, "missing_fields": (), "warnings": ()}
    session = replace(session, source_conflicts=(conflict,))
    impact = evaluate_source_conflict_impact(session, mapping, conflict,
        impact_evaluation_id="impact-1", evaluation_version="1", evaluated_at=NOW)
    assert impact.affected_dimensions == (
        AffectedDimension.QUANTITY, AffectedDimension.DOSE, AffectedDimension.DECISION)
    with pytest.raises(ValueError, match="ghost"):
        evaluate_source_conflict_impact(session, mapping, {**conflict, "conflict_id": "ghost"},
            impact_evaluation_id="impact-2", evaluation_version="1", evaluated_at=NOW)
