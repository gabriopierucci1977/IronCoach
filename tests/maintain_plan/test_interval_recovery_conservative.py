"""Approved beta 0.4 conservative interval-recovery semantics."""

from dataclasses import replace

import pytest

from backend.maintain_plan.execution_evaluation_service import evaluate
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
