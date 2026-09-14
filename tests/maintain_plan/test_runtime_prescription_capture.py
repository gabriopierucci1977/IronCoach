"""Runtime-boundary tests for MAINTAIN_PLAN prescription capture."""

import pytest

from backend.config import (
    DEFAULT_DECISION_MEMORY_DATABASE_PATH,
    DEFAULT_MAINTAIN_PLAN_DATABASE_PATH,
    RuntimeConfig,
)
from backend.normalization.activity_normalizer import ActivityNormalizer


_MAINTAIN_PLAN_ENV = (
    "IRONCOACH_MAINTAIN_PLAN_SNAPSHOT_ENABLED",
    "IRONCOACH_MAINTAIN_PLAN_DATABASE_PATH",
    "IRONCOACH_MAINTAIN_PLAN_TIMEZONE",
)


def clear_maintain_plan_env(monkeypatch):
    for name in _MAINTAIN_PLAN_ENV:
        monkeypatch.delenv(name, raising=False)


def test_maintain_plan_capture_is_disabled_by_default(monkeypatch):
    clear_maintain_plan_env(monkeypatch)

    config = RuntimeConfig.from_env()

    assert config.maintain_plan_snapshot_enabled is False
    assert config.maintain_plan_database_path == DEFAULT_MAINTAIN_PLAN_DATABASE_PATH
    assert config.maintain_plan_database_path != DEFAULT_DECISION_MEMORY_DATABASE_PATH
    assert config.maintain_plan_timezone == ""


@pytest.mark.parametrize("raw_value", ("invalid", "2", "-1", "enabled"))
def test_invalid_snapshot_flag_values_fail_closed(monkeypatch, raw_value):
    clear_maintain_plan_env(monkeypatch)
    monkeypatch.setenv("IRONCOACH_MAINTAIN_PLAN_SNAPSHOT_ENABLED", raw_value)

    assert RuntimeConfig.from_env().maintain_plan_snapshot_enabled is False


@pytest.mark.parametrize("raw_value", ("1", "true", "TRUE", "yes", "on"))
def test_explicit_snapshot_flag_values_enable_capture(monkeypatch, raw_value):
    clear_maintain_plan_env(monkeypatch)
    monkeypatch.setenv("IRONCOACH_MAINTAIN_PLAN_SNAPSHOT_ENABLED", raw_value)
    monkeypatch.setenv(
        "IRONCOACH_MAINTAIN_PLAN_DATABASE_PATH",
        "data/test-maintain-plan.db",
    )
    monkeypatch.setenv("IRONCOACH_MAINTAIN_PLAN_TIMEZONE", "Europe/Rome")

    config = RuntimeConfig.from_env()

    assert config.maintain_plan_snapshot_enabled is True
    assert config.maintain_plan_database_path == "data/test-maintain-plan.db"
    assert config.maintain_plan_timezone == "Europe/Rome"


def test_airtable_record_id_survives_training_normalization():
    normalized = ActivityNormalizer().normalize(
        {
            "record_id": "recTraining123",
            "Data allenamento": "2026-09-14",
            "Sport": "RUN",
        },
        source="airtable",
    )

    assert normalized["source_id"] == "recTraining123"
    assert normalized["raw"]["record_id"] == "recTraining123"


def test_explicit_prescription_metadata_survives_normalization():
    normalized = ActivityNormalizer().normalize(
        {
            "Metodo intensità": "HR",
            "Unità intensità": "zone",
            "Ambiente": "OUTDOOR",
            "Modalità": "ROAD",
        },
        source="airtable",
    )

    assert normalized["intensity_method"] == "HR"
    assert normalized["intensity_unit"] == "zone"
    assert normalized["environment"] == "OUTDOOR"
    assert normalized["mode"] == "ROAD"


def test_intensity_method_and_unit_are_not_inferred_from_zone():
    normalized = ActivityNormalizer().normalize(
        {"Zona prevista": "Z2"},
        source="airtable",
    )

    assert normalized["intensity"] == "Z2"
    assert normalized["intensity_method"] is None
    assert normalized["intensity_unit"] is None


def _runtime_training(**overrides):
    value = {
        "source": "airtable",
        "source_id": "recTraining123",
        "date": "2026-09-15",
        "sport": "RUN",
        "workout_name": "Corsa aerobica",
        "session_type": "continuous",
        "duration_minutes": 60,
        "intensity": 140,
        "intensity_method": "HR",
        "intensity_unit": "bpm",
        "environment": "OUTDOOR",
        "mode": "ROAD",
        "raw": {
            "Zona prevista": "Z2",
            "analyzer_legacy": "must-not-be-used",
        },
    }
    value.update(overrides)
    return value


def _runtime_decision(**overrides):
    value = {
        "decision_id": "decision-123",
        "primary_intent": "MAINTAIN_PLAN",
        "strategy": "KEEP_PLAN",
        "modified_workout": {
            "free_text": "must not define the prescription",
        },
    }
    value.update(overrides)
    return value


def _build_runtime_prescription(
    training=None,
    decision=None,
    *,
    communicated_at=None,
    timezone_name="Europe/Rome",
):
    from datetime import datetime, timezone

    from backend.maintain_plan.runtime_prescription_adapter import (
        build_communicated_prescription,
    )

    return build_communicated_prescription(
        training if training is not None else _runtime_training(),
        decision if decision is not None else _runtime_decision(),
        communicated_at=(
            communicated_at
            if communicated_at is not None
            else datetime(2026, 9, 14, 10, tzinfo=timezone.utc)
        ),
        timezone_name=timezone_name,
    )


def test_runtime_adapter_builds_valid_continuous_prescription():
    from backend.maintain_plan.models import (
        Applicability,
        BlockType,
        Composition,
        Discipline,
        Environment,
        EvaluationWindow,
        IntensityMethod,
        Mode,
        ObjectiveEvaluability,
        QuantityMetric,
        Requiredness,
        SessionType,
        SupportStatus,
    )
    from backend.maintain_plan.prescription_snapshot_service import (
        CommunicatedPrescription,
    )
    from backend.maintain_plan.validators import validate_prescription

    communicated = _build_runtime_prescription()
    assert type(communicated) is CommunicatedPrescription

    snapshot = communicated.snapshot
    assert validate_prescription(snapshot) == ()
    assert snapshot.prescription_snapshot_id == "maintain-plan:decision-123"
    assert snapshot.workout_id == "recTraining123"
    assert snapshot.decision_id == "decision-123"
    assert snapshot.composition is Composition.SINGLE
    assert snapshot.scheduled_window.timezone == "Europe/Rome"
    assert snapshot.scheduled_window.derived_from_date_only is True
    assert snapshot.scheduled_window.start.date().isoformat() == "2026-09-15"
    assert snapshot.scheduled_window.start.hour == 0
    assert snapshot.scheduled_window.end.date().isoformat() == "2026-09-15"
    assert snapshot.scheduled_window.end.hour == 23

    assert len(snapshot.components) == 1
    component = snapshot.components[0]
    assert component.component_id == "primary"
    assert component.discipline is Discipline.RUN
    assert component.environment is Environment.OUTDOOR
    assert component.mode is Mode.ROAD
    assert component.requiredness is Requiredness.REQUIRED
    assert component.support_status is SupportStatus.SUPPORTED
    assert component.applicability is Applicability.REQUIRED

    assert component.quantity.primary_metric is QuantityMetric.ACTIVE_DURATION
    assert component.quantity.target.value == 60
    assert component.quantity.unit == "minutes"
    assert component.intensity.primary_method is IntensityMethod.HR
    assert component.intensity.target.value == 140
    assert component.intensity.unit == "bpm"
    assert component.structure.session_type is SessionType.CONTINUOUS

    block = component.structure.blocks[0]
    assert block.block_type is BlockType.MAIN_SET
    assert block.intensity_target.value == 140
    assert block.method is IntensityMethod.HR
    assert block.evaluation_window is EvaluationWindow.WHOLE_BLOCK
    assert snapshot.objective.evaluability is ObjectiveEvaluability.CONTEXT_ONLY
    assert snapshot.objective.context_text == "Corsa aerobica"


@pytest.mark.parametrize(
    ("sport", "expected"),
    [
        ("RUN", "RUN"),
        ("BIKE", "BIKE"),
        ("SWIM", "SWIM"),
    ],
)
def test_runtime_adapter_supports_explicit_continuous_endurance_sports(
    sport,
    expected,
):
    result = _build_runtime_prescription(
        training=_runtime_training(
            sport=sport,
            environment=None,
            mode=None,
        )
    )
    assert result.snapshot.components[0].discipline.value == expected


def test_runtime_adapter_is_deterministic_deeply_frozen_and_non_mutating():
    from copy import deepcopy
    from dataclasses import FrozenInstanceError

    training = _runtime_training()
    decision = _runtime_decision()
    original_training = deepcopy(training)
    original_decision = deepcopy(decision)

    first = _build_runtime_prescription(
        training=training,
        decision=decision,
    )
    second = _build_runtime_prescription(
        training=training,
        decision=decision,
    )

    assert first == second
    assert training == original_training
    assert decision == original_decision
    assert type(first.snapshot.components) is tuple
    assert type(first.snapshot.components[0].structure.blocks) is tuple

    with pytest.raises(FrozenInstanceError):
        first.snapshot.workout_id = "changed"


@pytest.mark.parametrize(
    "training",
    [
        _runtime_training(intensity_method=None),
        _runtime_training(intensity_unit=None),
        _runtime_training(intensity_method="ZONE"),
        _runtime_training(session_type="intervals"),
        _runtime_training(sport="STRENGTH"),
        _runtime_training(duration_minutes=True),
        _runtime_training(duration_minutes=0),
        _runtime_training(duration_minutes=float("nan")),
        _runtime_training(intensity=True),
        _runtime_training(source_id=""),
        _runtime_training(date="15/09/2026"),
        _runtime_training(environment="GARAGE"),
        _runtime_training(mode="ELLIPTICAL"),
    ],
)
def test_runtime_adapter_rejects_incomplete_or_unsupported_training(training):
    from backend.maintain_plan.runtime_prescription_adapter import (
        RuntimePrescriptionError,
    )

    with pytest.raises(RuntimePrescriptionError):
        _build_runtime_prescription(training=training)


@pytest.mark.parametrize(
    "decision",
    [
        _runtime_decision(decision_id=None),
        _runtime_decision(primary_intent="RECOVERY"),
        _runtime_decision(strategy="ADAPT"),
        _runtime_decision(strategy="REDUCE_LOAD"),
        _runtime_decision(strategy="RECOVERY"),
    ],
)
def test_runtime_adapter_rejects_unsupported_decisions(decision):
    from backend.maintain_plan.runtime_prescription_adapter import (
        RuntimePrescriptionError,
    )

    with pytest.raises(RuntimePrescriptionError):
        _build_runtime_prescription(decision=decision)


@pytest.mark.parametrize(
    ("training", "decision"),
    [
        ("raw", _runtime_decision()),
        ({}, _runtime_decision()),
        (_runtime_training(), "raw"),
        (_runtime_training(), {}),
    ],
)
def test_runtime_adapter_rejects_wrong_primary_input_types(
    training,
    decision,
):
    from backend.maintain_plan.runtime_prescription_adapter import (
        RuntimePrescriptionError,
    )

    with pytest.raises(RuntimePrescriptionError):
        _build_runtime_prescription(
            training=training,
            decision=decision,
        )


def test_runtime_adapter_rejects_naive_timestamp_and_invalid_timezone():
    from datetime import datetime

    from backend.maintain_plan.runtime_prescription_adapter import (
        RuntimePrescriptionError,
    )

    with pytest.raises(RuntimePrescriptionError, match="timezone-aware"):
        _build_runtime_prescription(
            communicated_at=datetime(2026, 9, 14, 10),
        )

    with pytest.raises(RuntimePrescriptionError, match="IANA timezone"):
        _build_runtime_prescription(
            timezone_name="Not/A_Timezone",
        )


def test_runtime_adapter_never_infers_intensity_metadata_from_zone_or_text():
    from backend.maintain_plan.runtime_prescription_adapter import (
        RuntimePrescriptionError,
    )

    training = _runtime_training(
        intensity_method=None,
        intensity_unit=None,
        intensity="Z2",
        workout_name="Corsa facile in zona cardiaca 2",
        raw={
            "Zona prevista": "Z2",
            "Metodo intensità legacy": "HR",
            "Unità intensità legacy": "bpm",
        },
    )
    decision = _runtime_decision(
        modified_workout={
            "intensity": "Z2",
            "method": "HR",
            "unit": "bpm",
        }
    )

    with pytest.raises(RuntimePrescriptionError):
        _build_runtime_prescription(
            training=training,
            decision=decision,
        )
