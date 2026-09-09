"""Approved beta 0.4 conservative interval-recovery semantics."""

from dataclasses import replace

import pytest

from backend.maintain_plan.execution_evaluation_service import (
    _observed_block_collection_is_incomplete, evaluate)
from backend.maintain_plan.matching_service import build_mapping
from backend.maintain_plan.models import *
from tests.maintain_plan.fixtures import NOW
from tests.maintain_plan.test_execution_evaluation_corrections import interval_case


WARNING = "required interval recovery target is not evaluable by the beta 0.4 policy"


def required_case(*, recovery=True, quantity=None, intensity=None, incomplete=False):
    snapshot, session, mapping = interval_case(
        [.8] * 6, valid=[.8] * 6, include_recovery=recovery,
        recovery_required=True)
    if recovery:
        recovery_block = replace(session.components[0].blocks[1],
            quantity_observation=quantity, intensity_observation=intensity)
        session = replace(session, components=(replace(session.components[0],
            blocks=(session.components[0].blocks[0], recovery_block),
            missing_fields=("structure.blocks",) if incomplete else ()),))
        mapping = build_mapping(snapshot, session, mapping_id="recovery-map",
            created_at=NOW, resolution_method=ResolutionMethod.AUTOMATIC)
    elif incomplete:
        session = replace(session, components=(replace(session.components[0],
            missing_fields=("structure.blocks",)),))
    return snapshot, session, mapping


@pytest.mark.parametrize("quantity,intensity", [
    (None, None), ({"value": 90}, None), (None, {"value": 90}),
    ({"duration": 90}, {"average_hr": 90}),
])
def test_required_recovery_never_interprets_generic_observations(quantity, intensity):
    snapshot, session, mapping = required_case(quantity=quantity, intensity=intensity)
    result = evaluate(snapshot, session, mapping,
        evaluation_id="required-recovery", evaluated_at=NOW)
    component = result.component_results[0]
    assert component.intensity.status is AdherenceStatus.INSUFFICIENT_DATA
    assert component.intensity.direction is component.intensity.band is None
    assert component.intensity.missing_fields == (
        "prescription_snapshot.snapshot-1.components.run.blocks.run-work.recovery.evidence",)
    assert component.intensity.warnings == (WARNING,)
    assert component.structure.status is AdherenceStatus.INSUFFICIENT_DATA
    assert component.dose.status is DoseStatus.INSUFFICIENT_DATA
    assert result.intensity_aggregate.status is AdherenceStatus.INSUFFICIENT_DATA
    assert result.dose_aggregate.status is DoseStatus.INSUFFICIENT_DATA
    assert result.overall is OverallStatus.INSUFFICIENT_DATA


def test_required_recovery_absent_complete_vs_incomplete_block_set():
    complete = evaluate(*required_case(recovery=False),
        evaluation_id="absent-complete", evaluated_at=NOW)
    incomplete = evaluate(*required_case(recovery=False, incomplete=True),
        evaluation_id="absent-incomplete", evaluated_at=NOW)
    assert complete.component_results[0].structure.status is AdherenceStatus.NOT_MET
    assert incomplete.component_results[0].structure.status is AdherenceStatus.INSUFFICIENT_DATA
    assert complete.component_results[0].intensity.status is AdherenceStatus.INSUFFICIENT_DATA


def test_observed_only_recovery_and_mapping_order_do_not_create_association():
    snapshot, session, mapping = required_case()
    assert any(item.match_status is MatchStatus.OBSERVED_ONLY
               for item in mapping.block_mappings)
    first = evaluate(snapshot, session, mapping, evaluation_id="ordered", evaluated_at=NOW)
    second = evaluate(snapshot, session, replace(mapping,
        block_mappings=tuple(reversed(mapping.block_mappings))),
        evaluation_id="ordered", evaluated_at=NOW)
    assert first == second
    assert first.component_results[0].structure.status is AdherenceStatus.INSUFFICIENT_DATA


def test_not_applicable_recovery_has_no_effect():
    result = evaluate(*interval_case([.8] * 10, valid=[.8] * 10,
        include_recovery=False, recovery_required=False),
        evaluation_id="not-applicable", evaluated_at=NOW)
    component = result.component_results[0]
    assert component.intensity.status is AdherenceStatus.MET
    assert component.structure.status is AdherenceStatus.MET
    assert component.dose.status is DoseStatus.EVALUATED
    assert result.overall is OverallStatus.IN_LINE


def test_multiple_required_recoveries_are_reported_separately_and_sorted():
    snapshot, session, _ = required_case()
    first = snapshot.components[0].structure.blocks[0]
    second = replace(first, block_id="run-work-2", block_index=1)
    component = replace(snapshot.components[0], structure=replace(
        snapshot.components[0].structure, blocks=(second, first)))
    snapshot = replace(snapshot, components=(component,))
    observed_first = session.components[0].blocks[0]
    observed_second = replace(observed_first, block_id="device-work-2", block_index=1,
        repetitions=tuple(replace(rep, repetition_id=f"second-{rep.repetition_id}",
                                  block_ref="device-work-2")
                          for rep in observed_first.repetitions))
    observed = replace(session.components[0], blocks=(observed_second, observed_first))
    session = replace(session, components=(observed,))
    mapping = build_mapping(snapshot, session, mapping_id="two-work-blocks", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    result = evaluate(snapshot, session, mapping, evaluation_id="two-recoveries", evaluated_at=NOW)
    assert result.component_results[0].intensity.missing_fields == (
        "prescription_snapshot.snapshot-1.components.run.blocks.run-work-2.recovery.evidence",
        "prescription_snapshot.snapshot-1.components.run.blocks.run-work.recovery.evidence",
    )
    assert result.component_results[0].intensity.warnings == (WARNING,)


@pytest.mark.parametrize("marker", [
    "weather.blocking_clouds", "notes.structure_comment", "roadblock_note",
    "notes.structure", "weather.blocks", "block", "blocks_extra",
    "structure_blocks", "structure.blocks_extra", "structure.blocks.comment",
    " structure.blocks", "structure.blocks ", "STRUCTURE.BLOCKS",
    "recovery.evidence", "quantity_observation", "intensity_observation",
])
def test_unrelated_or_fuzzy_missing_marker_does_not_change_absent_recovery(marker):
    snapshot, session, mapping = required_case(recovery=False)
    session = replace(session, components=(replace(session.components[0],
        missing_fields=(marker,)),))
    result = evaluate(snapshot, session, mapping,
                      evaluation_id="unrelated-missing", evaluated_at=NOW)
    assert result.component_results[0].structure.status is AdherenceStatus.NOT_MET


def test_block_collection_marker_is_exact_component_scoped_and_order_independent():
    component = required_case(recovery=False)[1].components[0]
    assert _observed_block_collection_is_incomplete(replace(
        component, missing_fields=("structure.blocks",)))
    assert _observed_block_collection_is_incomplete(replace(
        component, missing_fields=("weather.blocking_clouds", "structure.blocks")))
    assert _observed_block_collection_is_incomplete(replace(
        component, missing_fields=("structure.blocks", "weather.blocking_clouds")))
    assert not _observed_block_collection_is_incomplete(replace(
        component, missing_fields=("components.other.structure.blocks",)))
    # Duplicate markers have one deterministic truth value at the pure boundary;
    # the full ActualSession validator independently rejects duplicates.
    assert _observed_block_collection_is_incomplete(replace(
        component, missing_fields=("structure.blocks", "structure.blocks")))


def test_missing_field_inside_present_block_does_not_mark_collection_incomplete():
    snapshot, session, mapping = required_case(recovery=False)
    work = replace(session.components[0].blocks[0],
                   missing_fields=("intensity_observation", "structure.blocks"))
    session = replace(session, components=(replace(session.components[0], blocks=(work,)),))
    result = evaluate(snapshot, session, mapping,
                      evaluation_id="block-local", evaluated_at=NOW)
    assert result.component_results[0].structure.status is AdherenceStatus.NOT_MET


def absent_work_case(*, component_missing=(), session_missing=(), block_missing=()):
    snapshot, session, _ = required_case(recovery=False)
    blocks = (() if not block_missing else
              (ObservedBlock("unrelated", 0, block_type=BlockType.RECOVERY,
                             missing_fields=block_missing),))
    observed = replace(session.components[0], blocks=blocks,
                       missing_fields=component_missing)
    session = replace(session, components=(observed,), missing_fields=session_missing)
    mapping = build_mapping(snapshot, session, mapping_id="absent-work", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    return evaluate(snapshot, session, mapping, evaluation_id="absent-work", evaluated_at=NOW)


def test_exact_component_marker_precedes_planned_only_work_absence():
    result = absent_work_case(component_missing=("structure.blocks",))
    assert result.component_results[0].structure.status is AdherenceStatus.INSUFFICIENT_DATA


@pytest.mark.parametrize("component_missing", [
    (), ("weather.blocking_clouds",), ("notes.structure_comment",),
    ("components.other.structure.blocks",),
])
def test_complete_or_unrelated_marker_keeps_planned_only_work_not_met(component_missing):
    result = absent_work_case(component_missing=component_missing)
    assert result.component_results[0].structure.status is AdherenceStatus.NOT_MET


def test_session_or_present_block_marker_does_not_override_planned_only_work():
    session_marker = absent_work_case(session_missing=("structure.blocks",))
    block_marker = absent_work_case(block_missing=("structure.blocks",))
    assert session_marker.component_results[0].structure.status is AdherenceStatus.NOT_MET
    assert block_marker.component_results[0].structure.status is AdherenceStatus.NOT_MET


def test_mapping_order_does_not_change_incomplete_planned_only_result():
    snapshot, session, _ = required_case(recovery=False)
    session = replace(session, components=(replace(session.components[0], blocks=(),
        missing_fields=("structure.blocks",)),))
    mapping = build_mapping(snapshot, session, mapping_id="ordered-absence", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    first = evaluate(snapshot, session, mapping, evaluation_id="same", evaluated_at=NOW)
    second = evaluate(snapshot, session, replace(mapping,
        block_mappings=tuple(reversed(mapping.block_mappings))),
        evaluation_id="same", evaluated_at=NOW)
    assert first == second


def test_exact_block_marker_does_not_override_missing_required_repetition():
    snapshot, session, _ = interval_case([.8] * 6, valid=[.8] * 6,
        include_recovery=False, recovery_required=False)
    work = replace(session.components[0].blocks[0],
                   repetitions=session.components[0].blocks[0].repetitions[:-1])
    session = replace(session, components=(replace(session.components[0], blocks=(work,),
        missing_fields=("structure.blocks",)),))
    mapping = build_mapping(snapshot, session, mapping_id="missing-repetition", created_at=NOW,
                            resolution_method=ResolutionMethod.AUTOMATIC)
    result = evaluate(snapshot, session, mapping,
                      evaluation_id="missing-repetition", evaluated_at=NOW)
    assert result.component_results[0].structure.status is AdherenceStatus.NOT_MET
