"""Idempotency regression for repeated runtime captures."""

from datetime import datetime, timezone

from backend.config import RuntimeConfig
from backend.maintain_plan.runtime_actual_session_capture import (
    RuntimeActualSessionCapture,
)


def test_same_activity_reuses_session_with_different_normalized_at(tmp_path):
    database = tmp_path / "runtime-idempotency.db"

    config = RuntimeConfig(
        maintain_plan_actual_session_enabled=True,
        maintain_plan_database_path=str(database),
        maintain_plan_timezone="Europe/Rome",
    )

    history = [
        {
            "activity_id": "garmin:idempotency-test",
            "source_id": "idempotency-test",
            "date": "2026-10-14T10:07:02Z",
            "sport": "BIKE",
            "duration_minutes": 90,
            "distance_km": 45,
            "heart_rate": {"average": 140, "max": 160},
            "power": {},
            "segments": [],
            "metadata": {},
            "raw": {"activity_type": "road"},
        }
    ]

    capture = RuntimeActualSessionCapture()

    first = capture.capture(
        runtime_config=config,
        athlete={"source_id": "athlete-idempotency"},
        garmin_training_history=history,
        normalized_at=datetime(
            2026, 10, 18, 9, 0, tzinfo=timezone.utc
        ),
    )

    second = capture.capture(
        runtime_config=config,
        athlete={"source_id": "athlete-idempotency"},
        garmin_training_history=history,
        normalized_at=datetime(
            2026, 10, 18, 9, 1, tzinfo=timezone.utc
        ),
    )

    assert first.created
    assert second.reused == first.created
    assert second.created == ()
