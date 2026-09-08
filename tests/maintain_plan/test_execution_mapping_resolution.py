"""Evaluator ownership regressions for distinct planned/observed namespaces."""

from dataclasses import replace

from backend.maintain_plan.execution_evaluation_service import evaluate
from backend.maintain_plan.models import *
from backend.maintain_plan.repository import MaintainPlanRepository
from tests.maintain_plan.fixtures import NOW
from tests.maintain_plan.test_execution_evaluation_corrections import interval_case


def distinct_ids():
    snapshot, session, mapping = interval_case([.8] * 10, valid=[.8] * 10)
    work = session.components[0].blocks[0]
    repetitions = tuple(replace(item, repetition_id=f"device-rep-{item.repetition_index}",
                                block_ref="device-main") for item in work.repetitions)
    work = replace(work, block_id="device-main", repetitions=repetitions)
    session = replace(session, components=(replace(session.components[0],
        blocks=(work,) + session.components[0].blocks[1:]),))
    block_mappings = tuple(replace(item, observed_block_ref=(
        ObservedBlockRef(session.session_id, session.components[0].component_id, "device-main")
        if item.planned_block_ref and item.planned_block_ref.block_id == "run-work"
        else item.observed_block_ref)) for item in mapping.block_mappings)
    repetition_mappings = tuple(replace(item, observed_repetition_ref=(
        ObservedRepetitionRef(session.session_id, session.components[0].component_id,
            "device-main", f"device-rep-{item.planned_repetition_ref.repetition_index}")
        if item.planned_repetition_ref else item.observed_repetition_ref))
        for item in mapping.repetition_mappings)
    return snapshot, session, replace(mapping, block_mappings=block_mappings,
                                      repetition_mappings=repetition_mappings)


def test_interval_resolves_distinct_block_and_repetition_ids_through_mapping():
    result = evaluate(*distinct_ids(), evaluation_id="distinct", evaluated_at=NOW)
    component = result.component_results[0]
    assert component.intensity.status is AdherenceStatus.MET
    assert component.structure.status is AdherenceStatus.MET


def test_missing_planned_repetition_mapping_is_not_replaced_by_observed_extra():
    snapshot, session, mapping = distinct_ids()
    missing = mapping.repetition_mappings[3]
    extra = RepetitionMapping(None,
        ObservedRepetitionRef(session.session_id, session.components[0].component_id,
                              "device-main", "device-rep-3"), MatchStatus.OBSERVED_ONLY)
    mappings = tuple(item for item in mapping.repetition_mappings if item is not missing) + (extra,)
    result = evaluate(snapshot, session, replace(mapping, repetition_mappings=mappings),
                      evaluation_id="missing", evaluated_at=NOW)
    assert result.component_results[0].intensity.status is AdherenceStatus.INSUFFICIENT_DATA
    assert result.component_results[0].structure.status is AdherenceStatus.NOT_MET


def test_mapping_tuple_order_does_not_change_evaluation():
    snapshot, session, mapping = distinct_ids()
    first = evaluate(snapshot, session, mapping, evaluation_id="ordered", evaluated_at=NOW)
    shuffled = replace(mapping, block_mappings=tuple(reversed(mapping.block_mappings)),
                       repetition_mappings=tuple(reversed(mapping.repetition_mappings)))
    second = evaluate(snapshot, session, shuffled, evaluation_id="ordered", evaluated_at=NOW)
    assert first == second


def test_planned_only_block_with_distinct_observed_namespace_is_not_met():
    snapshot, session, mapping = distinct_ids()
    block = mapping.block_mappings[0]
    mapping = replace(mapping, block_mappings=(replace(block,
        observed_block_ref=None, match_status=MatchStatus.PLANNED_ONLY),) + mapping.block_mappings[1:],
        repetition_mappings=())
    result = evaluate(snapshot, session, mapping, evaluation_id="planned-only", evaluated_at=NOW)
    assert result.component_results[0].intensity.status is AdherenceStatus.INSUFFICIENT_DATA
    assert result.component_results[0].structure.status is AdherenceStatus.NOT_MET


def test_distinct_namespace_mapping_round_trip_then_evaluation(tmp_path):
    snapshot, session, mapping = distinct_ids()
    repository = MaintainPlanRepository(tmp_path / "distinct.db")
    repository.create_prescription_snapshot(snapshot)
    repository.create_actual_session(session)
    repository.create_prescription_mapping(mapping)
    persisted = repository.get_prescription_mapping(mapping.mapping_id)
    result = evaluate(snapshot, session, persisted, evaluation_id="persisted", evaluated_at=NOW)
    assert result.component_results[0].intensity.status is AdherenceStatus.MET
    assert result.component_results[0].structure.status is AdherenceStatus.MET
