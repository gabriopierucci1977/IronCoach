from datetime import datetime, timezone

import pytest

from backend.config import RuntimeConfig
from backend.maintain_plan.repository import ActualSessionConflictError
from backend.maintain_plan.runtime_actual_session_capture import RuntimeActualSessionCapture


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
