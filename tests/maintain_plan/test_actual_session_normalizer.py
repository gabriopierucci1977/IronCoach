from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.maintain_plan.actual_session_normalizer import (
    ActualSessionInput, ActualSessionNormalizer, BlockObservationInput,
    ComponentObservationInput, RepetitionObservationInput, SourceActivityInput,
    TransitionObservationInput,
)
from backend.maintain_plan.models import BlockType, Composition, Discipline, Environment, Mode
from backend.maintain_plan.repository import MaintainPlanRepository


NOW = datetime(2026, 9, 7, 8, tzinfo=timezone.utc)


def source(identifier="activity-1"):
    return SourceActivityInput(
        "synthetic-device", identifier, {"native": identifier},
        {"source": "synthetic-device", "captured_at": NOW},
    )


def component(identifier="run", index=0, discipline=Discipline.RUN, **changes):
    values = dict(
        component_id=identifier, component_index=index, discipline=discipline,
        source_activity_refs=("activity-1",), start=NOW,
        end=NOW + timedelta(hours=1), quantity_primary_metric="active_duration",
        quantity_observation={"value": None}, quantity_unit="minutes",
        intensity_methods=("HR",), intensity_observations={"average_hr": None},
        provenance={"source": "synthetic-device"},
        missing_fields=("quantity.value", "intensity.average_hr"),
        warnings=("telemetry_missing",), data_quality={"completeness": "PARTIAL"},
    )
    values.update(changes)
    return ComponentObservationInput(**values)


def session_input(**changes):
    values = dict(
        session_id="session-1", source_activities=(source(),), start=NOW,
        end=NOW + timedelta(hours=1), timezone="UTC", composition=Composition.SINGLE,
        components=(component(),), normalized_at=NOW + timedelta(hours=2),
        completion_status="COMPLETED", data_quality={"completeness": "PARTIAL"},
        missing_fields=("components[0].quantity.value",), warnings=("telemetry_missing",),
    )
    values.update(changes)
    return ActualSessionInput(**values)


@pytest.mark.parametrize(
    ("discipline", "environment", "mode", "metric"),
    (
        (Discipline.RUN, Environment.OUTDOOR, Mode.ROAD, "active_duration"),
        (Discipline.BIKE, Environment.OUTDOOR, Mode.ROAD, "active_duration"),
        (Discipline.SWIM, Environment.INDOOR, Mode.POOL, "distance"),
        (Discipline.SWIM, Environment.OUTDOOR, Mode.OPEN_WATER, "active_duration"),
        (Discipline.STRENGTH, Environment.INDOOR, None, "sets_repetitions"),
    ),
)
def test_normalizes_single_observed_disciplines_without_evaluation(
        discipline, environment, mode, metric):
    observed = component(discipline=discipline, environment=environment, mode=mode,
                         quantity_primary_metric=metric)
    result = ActualSessionNormalizer.normalize(session_input(components=(observed,)))
    assert result.components[0].discipline is discipline
    assert result.components[0].quantity_primary_metric == metric
    assert not hasattr(result, "support_status")


def test_preserves_interval_blocks_repetitions_missingness_and_provenance():
    repetition = RepetitionObservationInput(
        "rep-1", 0, "work", {"duration_minutes": None}, {"power": None},
        source_segment_refs=("segment-1",), provenance={"source": "synthetic-device"},
        missing_fields=("power",), warnings=("power_missing",),
    )
    block = BlockObservationInput(
        "work", 0, BlockType.WORK, (repetition,),
        provenance={"source": "synthetic-device"}, missing_fields=("power",),
    )
    result = ActualSessionNormalizer.normalize(
        session_input(components=(component(blocks=(block,)),))
    )
    normalized_rep = result.components[0].blocks[0].repetitions[0]
    assert normalized_rep.quantity_observation["duration_minutes"] is None
    assert normalized_rep.intensity_observation["power"] is None
    assert normalized_rep.block_ref == "work"
    assert normalized_rep.source_segment_refs == ("segment-1",)


@pytest.mark.parametrize("composition", (Composition.BRICK, Composition.MULTISPORT))
def test_preserves_composed_session_component_order_transition_and_observed_extra(composition):
    bike = component("bike", 0, Discipline.BIKE)
    run = component("run", 1, Discipline.RUN)
    strength = component("extra-strength", 2, Discipline.STRENGTH)
    transition = TransitionObservationInput(
        "transition-1", "bike", "run", NOW + timedelta(minutes=30),
        NOW + timedelta(minutes=35), 5, {"source": "synthetic-device"},
    )
    result = ActualSessionNormalizer.normalize(session_input(
        composition=composition, components=(bike, run, strength), transitions=(transition,),
    ))
    assert [item.component_id for item in result.components] == ["bike", "run", "extra-strength"]
    assert result.transitions[0].from_component_ref == "bike"
    assert result.transitions[0].to_component_ref == "run"


def test_preserves_interruption_safety_multiple_sources_conflict_and_original_ids():
    second = source("activity-2")
    observed = component(source_activity_refs=("activity-1", "activity-2"))
    conflict = {"conflict_id": "conflict-1", "field_path": "components.run.quantity",
                "values": ({"value": 10, "source": "synthetic-device"},
                           {"value": 12, "source": "synthetic-manual"})}
    result = ActualSessionNormalizer.normalize(session_input(
        source_activities=(source(), second), components=(observed,),
        completion_status="INTERRUPTED", interruption_reason="SAFETY_PAIN",
        safety_interruption=True, source_conflicts=(conflict,),
    ))
    assert [item.original_activity_id for item in result.source_activities] == ["activity-1", "activity-2"]
    assert result.completion.interruption_reason == "SAFETY_PAIN"
    assert result.source_conflicts[0]["values"][0]["value"] == 10


def test_output_is_defensively_copied_deeply_immutable_and_deterministic():
    raw_ids = {"nested": ["original"]}
    value = session_input(source_activities=(replace(source(), raw_ids=raw_ids),))
    first = ActualSessionNormalizer.normalize(value)
    second = ActualSessionNormalizer.normalize(value)
    raw_ids["nested"].append("changed")
    assert first == second
    assert first.source_activities[0].raw_ids["nested"] == ("original",)
    with pytest.raises(FrozenInstanceError):
        first.session_id = "changed"
    with pytest.raises(TypeError):
        first.source_activities[0].raw_ids["new"] = True
    with pytest.raises(AttributeError):
        first.source_activities[0].raw_ids["nested"].append("changed")


@pytest.mark.parametrize(
    "invalid",
    (
        session_input(start=datetime(2026, 9, 7, 8)),
        session_input(session_id=""),
        session_input(source_activities=(source(), source())),
        session_input(components=(component("one", 0), component("two", 0)),
                      composition=Composition.MULTISPORT),
        session_input(components=(component(blocks=(
            BlockObservationInput("same", 0, BlockType.WORK),
            BlockObservationInput("same", 1, BlockType.RECOVERY),
        )),)),
        session_input(components=(component(blocks=(BlockObservationInput(
            "work", 0, BlockType.WORK,
            (RepetitionObservationInput("rep", 0, "wrong"),),
        ),)),)),
        session_input(transitions=(TransitionObservationInput("transition", "run", "missing"),)),
        session_input(warnings=("duplicate", "duplicate")),
        session_input(data_quality={"distance": float("nan")}),
        session_input(data_quality={"planned_target": 10}),
    ),
)
def test_rejects_invalid_observations(invalid):
    with pytest.raises(ValueError):
        ActualSessionNormalizer.normalize(invalid)


def test_repository_round_trip_uses_only_explicit_tmp_database(tmp_path):
    result = ActualSessionNormalizer.normalize(session_input())
    repository = MaintainPlanRepository(tmp_path / "maintain-plan.db")
    repository.create_actual_session(result)
    assert repository.get_actual_session(result.session_id) == result


def test_is_not_imported_by_runtime_and_contains_no_prescription_fields():
    backend = Path(__file__).parents[2] / "backend"
    runtime = [path for path in backend.rglob("*.py") if "maintain_plan" not in path.parts]
    module = "backend.maintain_plan.actual_session_normalizer"
    assert not [path for path in runtime if module in path.read_text(encoding="utf-8")]
    result = ActualSessionNormalizer.normalize(session_input())
    assert not any(word in vars(result) for word in ("prescription", "mapping", "evaluation", "outcome"))
