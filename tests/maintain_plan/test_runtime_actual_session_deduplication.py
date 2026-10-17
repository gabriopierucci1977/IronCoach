"""Regression test for Garmin live/FIT duplicate activities."""

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


def test_live_and_manual_fit_same_activity_persist_once(tmp_path):
    database = tmp_path / "maintain-plan-dedup.db"

    config = RuntimeConfig(
        maintain_plan_actual_session_enabled=True,
        maintain_plan_database_path=str(database),
        maintain_plan_timezone="Europe/Rome",
    )

    history = [
        {
            "activity_id": "garmin:24720297468",
            "source_id": "24720297468",
            "date": "2026-10-14T10:07:02Z",
            "sport": "BIKE",
            "duration_minutes": 99.25,
            "distance_km": 52.899,
            "heart_rate": {"average": 142, "max": 167},
            "power": {},
            "segments": [],
            "metadata": {
                "garmin": {
                    "activity_id": "24720297468",
                },
            },
            "raw": {
                "activity_type": "road",
            },
        },
        {
            "activity_id": FIT_HASH,
            "source_id": FIT_HASH,
            "date": "2026-10-14T10:07:02Z",
            "sport": "BIKE",
            "duration_minutes": 99.25,
            "distance_km": 52.899,
            "heart_rate": {"average": 142, "max": 167},
            "power": {},
            "segments": [],
            "metadata": {
                "garmin": {
                    "file_name": "24720297468_ACTIVITY.fit",
                    "sub_sport": "road",
                },
            },
            "raw": {
                "activity_type": "road",
            },
        },
    ]

    RuntimeActualSessionCapture().capture(
        runtime_config=config,
        athlete={"source_id": "recAthleteDedup"},
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

    payloads = [
        row[0]
        for row in db.execute(
            "SELECT payload_json FROM maintain_plan_actual_sessions"
        ).fetchall()
    ]
    db.close()

    assert count == 1
    assert any("24720297468_ACTIVITY.fit" in payload for payload in payloads)
