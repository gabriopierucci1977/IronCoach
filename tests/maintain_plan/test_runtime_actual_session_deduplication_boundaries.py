"""Boundary tests for Garmin live/FIT deduplication."""

import sqlite3
from datetime import datetime, timezone

from backend.config import RuntimeConfig
from backend.maintain_plan.runtime_actual_session_capture import (
    RuntimeActualSessionCapture,
)


FIT_HASH = (
    "8307ae6bd68dc598edbeb64e3d65e79af6c0ed303db2090"
    "df72a7ae9ee6a2f4c"
)


def _activity(activity_id, date, metadata):
    return {
        "activity_id": activity_id,
        "source_id": activity_id,
        "date": date,
        "sport": "BIKE",
        "duration_minutes": 99.25,
        "distance_km": 52.899,
        "heart_rate": {"average": 142, "max": 167},
        "power": {},
        "segments": [],
        "metadata": metadata,
        "raw": {"activity_type": "road"},
    }


def test_distinct_starts_in_same_minute_are_not_deduplicated(tmp_path):
    database = tmp_path / "maintain-plan-boundaries.db"

    config = RuntimeConfig(
        maintain_plan_actual_session_enabled=True,
        maintain_plan_database_path=str(database),
        maintain_plan_timezone="Europe/Rome",
    )

    history = [
        _activity(
            "garmin:activity-100",
            "2026-10-14T10:07:02Z",
            {"garmin": {"activity_id": "activity-100"}},
        ),
        _activity(
            FIT_HASH,
            "2026-10-14T10:07:45Z",
            {
                "garmin": {
                    "file_name": "24720297468_ACTIVITY.fit",
                    "sub_sport": "road",
                }
            },
        ),
    ]

    RuntimeActualSessionCapture().capture(
        runtime_config=config,
        athlete={"source_id": "recAthleteBoundary"},
        garmin_training_history=history,
        normalized_at=datetime(
            2026,
            10,
            15,
            tzinfo=timezone.utc,
        ),
    )

    db = sqlite3.connect(database)
    count = db.execute(
        "SELECT COUNT(*) FROM maintain_plan_actual_sessions"
    ).fetchone()[0]
    db.close()

    assert count == 2
