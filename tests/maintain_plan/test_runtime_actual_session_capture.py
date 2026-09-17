from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.config import RuntimeConfig
from backend.maintain_plan.repository import ActualSessionConflictError
from backend.maintain_plan.runtime_actual_session_capture import RuntimeActualSessionCapture
from backend.maintain_plan.runtime_actual_session_adapter import RuntimeActivityValidationError
from backend.maintain_plan.repository import MaintainPlanRepository


NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)


def activity(source_id="source-1"):
    return {"activity_id": "garmin:1", "source_id": source_id,
            "date": "2026-09-15T08:00:00Z", "sport": "RUN",
            "duration_minutes": 30, "distance_km": 5, "heart_rate": {}, "power": {},
            "segments": [], "metadata": {},
            "raw": {"activity_type": "running", "distance_km": 5}}


def config(path, enabled=True):
    return RuntimeConfig(maintain_plan_actual_session_enabled=enabled,
                         maintain_plan_database_path=str(path))


def test_disabled_does_not_initialize_repository(tmp_path):
    path = tmp_path / "absent.db"
    assert RuntimeActualSessionCapture().capture(
        runtime_config=config(path, False), athlete=None,
        garmin_training_history=None, normalized_at=NOW) is None
    assert not path.exists()


@pytest.mark.parametrize(("raw", "expected"), [
    ("true", True), ("TRUE", True), ("TrUe", True), ("false", False),
    ("FALSE", False), ("", False), ("invalid", False),
])
def test_dedicated_config_flag_is_fail_closed(monkeypatch, raw, expected):
    monkeypatch.setenv("IRONCOACH_MAINTAIN_PLAN_ACTUAL_SESSION_ENABLED", raw)
    assert RuntimeConfig.from_env().maintain_plan_actual_session_enabled is expected


def test_insert_retry_and_conflict(tmp_path):
    service = RuntimeActualSessionCapture()
    cfg = config(tmp_path / "sessions.db")
    first = service.capture(runtime_config=cfg, athlete={"source_id": "athlete"},
                            garmin_training_history=[activity()], normalized_at=NOW)
    second = service.capture(runtime_config=cfg, athlete={"source_id": "athlete"},
                             garmin_training_history=[activity()], normalized_at=NOW)
    assert len(first.created) == len(second.reused) == 1
    with pytest.raises(ActualSessionConflictError):
        service.capture(runtime_config=cfg, athlete={"source_id": "athlete"},
                        garmin_training_history=[activity("different")], normalized_at=NOW)


def test_unsupported_is_explicit(tmp_path):
    value = activity()
    value["raw"]["activity_type"] = "strength_training"
    result = RuntimeActualSessionCapture().capture(
        runtime_config=config(tmp_path / "sessions.db"),
        athlete={"source_id": "athlete"}, garmin_training_history=[value],
        normalized_at=NOW)
    assert result.unsupported == (0,)


def test_late_conflict_rolls_back_complete_batch(tmp_path):
    service = RuntimeActualSessionCapture()
    cfg = config(tmp_path / "sessions.db")
    conflict = activity()
    conflict["activity_id"] = "conflict"
    conflict["duration_minutes"] = conflict["raw"]["duration_minutes"] = 1
    service.capture(runtime_config=cfg, athlete={"source_id": "athlete"},
                    garmin_training_history=[conflict], normalized_at=NOW)
    new = activity()
    new["activity_id"] = "new"
    divergent = activity()
    divergent["activity_id"] = "conflict"
    divergent["duration_minutes"] = divergent["raw"]["duration_minutes"] = 2

    with pytest.raises(ActualSessionConflictError):
        service.capture(runtime_config=cfg, athlete={"source_id": "athlete"},
                        garmin_training_history=[new, divergent], normalized_at=NOW)

    from backend.maintain_plan.runtime_actual_session_adapter import runtime_actual_session_id
    assert MaintainPlanRepository(cfg.maintain_plan_database_path).get_actual_session(
        runtime_actual_session_id("athlete", "new")) is None
    # A rollback must release the IMMEDIATE lock without waiting.
    service.capture(runtime_config=cfg, athlete={"source_id": "athlete"},
                    garmin_training_history=[new], normalized_at=NOW)


def test_independent_connections_serialize_equivalent_batches(tmp_path):
    cfg = config(tmp_path / "sessions.db")
    # Migrations happen before the competing capture calls, exactly as they do
    # during application startup; each capture still opens its own connection.
    MaintainPlanRepository(cfg.maintain_plan_database_path)
    batch = [activity()]
    def capture():
        return RuntimeActualSessionCapture().capture(
            runtime_config=cfg, athlete={"source_id": "athlete"},
            garmin_training_history=batch, normalized_at=NOW)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: capture(), range(2)))
    assert sum(len(item.created) for item in results) == 1
    assert sum(len(item.reused) for item in results) == 1


def test_structural_error_is_not_reported_as_unsupported_and_opens_no_db(tmp_path):
    path = tmp_path / "sessions.db"
    malformed = activity()
    malformed.pop("activity_id")
    with pytest.raises(ValueError, match="activity_id"):
        RuntimeActualSessionCapture().capture(
            runtime_config=config(path), athlete={"source_id": "athlete"},
            garmin_training_history=[activity(), malformed], normalized_at=NOW)
    assert not path.exists()


@pytest.mark.parametrize(("field", "value"), [
    ("normalized_at", datetime(2026, 9, 16)),
    ("captured_at", datetime(2026, 9, 16)),
    ("normalized_at", "2026-09-16T00:00:00Z"),
    ("captured_at", 1),
])
def test_invalid_process_timestamp_raises_validation_error_before_database(
        tmp_path, field, value):
    path = tmp_path / "sessions.db"
    arguments = {"runtime_config": config(path), "athlete": {"source_id": "athlete"},
                 "garmin_training_history": [activity()], "normalized_at": NOW,
                 "captured_at": NOW}
    arguments[field] = value
    with pytest.raises(RuntimeActivityValidationError, match=field):
        RuntimeActualSessionCapture().capture(**arguments)
    assert not path.exists()


def test_aware_process_timestamps_are_accepted(tmp_path):
    result = RuntimeActualSessionCapture().capture(
        runtime_config=config(tmp_path / "sessions.db"),
        athlete={"source_id": "athlete"}, garmin_training_history=[activity()],
        normalized_at=NOW, captured_at=NOW)
    assert len(result.created) == 1


def test_late_malformed_classifier_prevents_any_database_creation(tmp_path):
    path = tmp_path / "sessions.db"
    malformed = activity()
    malformed["activity_id"] = "garmin:2"
    malformed["segments"] = [{"sport": []}]
    with pytest.raises(RuntimeActivityValidationError):
        RuntimeActualSessionCapture().capture(
            runtime_config=config(path), athlete={"source_id": "athlete"},
            garmin_training_history=[activity(), malformed], normalized_at=NOW)
    assert not path.exists()


@pytest.mark.parametrize("invalid", [True, "30", float("nan"), float("inf"), -1])
@pytest.mark.parametrize("location", ["top-level", "raw"])
def test_invalid_duration_prevents_database_initialization(tmp_path, location, invalid):
    path = tmp_path / "sessions.db"
    malformed = activity()
    malformed["raw"]["duration_minutes"] = 30
    if location == "top-level":
        malformed["duration_minutes"] = invalid
    else:
        malformed["raw"]["duration_minutes"] = invalid

    with pytest.raises(RuntimeActivityValidationError, match="duration_minutes"):
        RuntimeActualSessionCapture().capture(
            runtime_config=config(path), athlete={"source_id": "athlete"},
            garmin_training_history=[malformed], normalized_at=NOW)
    assert not path.exists()


def test_concurrent_conflicting_batches_never_persist_prefixes(tmp_path):
    cfg = config(tmp_path / "sessions.db")
    service = RuntimeActualSessionCapture()
    stored = activity()
    stored["activity_id"] = "conflict"
    stored["duration_minutes"] = stored["raw"]["duration_minutes"] = 1
    service.capture(runtime_config=cfg, athlete={"source_id": "athlete"},
                    garmin_training_history=[stored], normalized_at=NOW)

    def conflicting(prefix):
        new = activity()
        new["activity_id"] = prefix
        conflict = activity()
        conflict["activity_id"] = "conflict"
        conflict["duration_minutes"] = conflict["raw"]["duration_minutes"] = 2
        with pytest.raises(ActualSessionConflictError):
            RuntimeActualSessionCapture().capture(
                runtime_config=cfg, athlete={"source_id": "athlete"},
                garmin_training_history=[new, conflict], normalized_at=NOW)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(conflicting, ("new-a", "new-b")))

    from backend.maintain_plan.runtime_actual_session_adapter import runtime_actual_session_id
    repository = MaintainPlanRepository(cfg.maintain_plan_database_path)
    assert repository.get_actual_session(runtime_actual_session_id("athlete", "new-a")) is None
    assert repository.get_actual_session(runtime_actual_session_id("athlete", "new-b")) is None
