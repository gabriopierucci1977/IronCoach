"""
Test Garmin Summary Importer

Verifica:
- lettura dei file summarizedActivities Garmin;
- conversione delle unità;
- normalizzazione sport;
- metriche Garmin nei metadata;
- importazione di una singola attività;
- rilevamento duplicati;
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.importers.garmin_summary_importer import (
    GarminSummaryImportError,
    GarminSummaryImporter,
)


def _write_summary_file(
    path: Path,
    activities: list[dict],
) -> None:
    payload = [
        {
            "summarizedActivitiesExport": activities
        }
    ]

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_imports_and_normalizes_running_activity(
    tmp_path: Path,
) -> None:
    source = (
        tmp_path
        / "gabpie_0_summarizedActivities.json"
    )

    _write_summary_file(
        source,
        [
            {
                "activityId": 123456789,
                "name": "Test Run",
                "activityType": "running",
                "sportType": "RUNNING",
                "beginTimestamp": 1704067200000,
                "startTimeLocal": 1704070800000,
                "duration": 3600500.0,
                "elapsedDuration": 3650000.0,
                "movingDuration": 3590000.0,
                "distance": 1000000.0,
                "elevationGain": 12500.0,
                "elevationLoss": 12000.0,
                "avgSpeed": 0.2777778,
                "maxSpeed": 0.5,
                "avgHr": 150.0,
                "maxHr": 175.0,
                "minHr": 90.0,
                "avgRunCadence": 86.0,
                "maxRunCadence": 94.0,
                "calories": 2092.0,
                "activityTrainingLoad": 123.4,
                "aerobicTrainingEffect": 4.1,
                "anaerobicTrainingEffect": 1.2,
                "trainingEffectLabel": "THRESHOLD",
                "vO2MaxValue": 58.0,
                "steps": 9000.0,
                "lapCount": 10,
                "manufacturer": "GARMIN",
                "deviceId": 42,
                "locationName": "Test City",
                "workoutRpe": 70,
                "workoutFeel": 80,
                "hrTimeInZone_0": 1000,
                "hrTimeInZone_1": 2000,
            }
        ],
    )

    activities = GarminSummaryImporter(
        str(source)
    ).import_activities()

    assert len(activities) == 1

    activity = activities[0]

    assert activity.activity_id == (
        "garmin:123456789"
    )
    assert activity.source == "garmin"
    assert activity.source_id == "123456789"
    assert activity.file_hash is None

    assert activity.start_time == (
        "2024-01-01T00:00:00Z"
    )
    assert activity.end_time == (
        "2024-01-01T01:00:00Z"
    )

    assert activity.sport == "RUN"
    assert activity.activity_type == "running"

    assert activity.duration_seconds == 3600
    assert activity.distance_meters == 10000.0
    assert activity.elevation_gain == 125.0
    assert activity.elevation_loss == 120.0

    assert activity.avg_speed == pytest.approx(
        2.777778
    )
    assert activity.max_speed == pytest.approx(
        5.0
    )

    assert activity.avg_hr == 150
    assert activity.max_hr == 175
    assert activity.avg_cadence == 86.0
    assert activity.max_cadence == 94.0

    assert activity.training_load == 123.4
    assert activity.training_effect == 4.1

    assert activity.calories == 500
    assert activity.segments == []

    garmin = activity.metadata["garmin"]

    assert garmin["name"] == "Test Run"
    assert garmin["min_hr"] == 90
    assert garmin["anaerobic_training_effect"] == 1.2
    assert garmin["training_effect_label"] == "THRESHOLD"
    assert garmin["vo2_max"] == 58.0
    assert garmin["steps"] == 9000
    assert garmin["lap_count"] == 10
    assert garmin["manufacturer"] == "GARMIN"
    assert garmin["device_id"] == 42
    assert garmin["location_name"] == "Test City"
    assert garmin["workout_rpe"] == 70.0
    assert garmin["workout_feel"] == 80.0
    assert garmin["hr_time_in_zone_ms"] == {
        "0": 1000,
        "1": 2000,
    }


def test_imports_indoor_cycling_power_metrics(
    tmp_path: Path,
) -> None:
    source = (
        tmp_path
        / "gabpie_2002_summarizedActivities.json"
    )

    _write_summary_file(
        source,
        [
            {
                "activityId": 987654321,
                "activityType": "indoor_cycling",
                "sportType": "CYCLING",
                "beginTimestamp": 1704153600000,
                "duration": 1800000.0,
                "distance": 1500000.0,
                "avgPower": 188.0,
                "maxPower": 325.0,
                "normPower": 200.0,
                "avgBikeCadence": 79.0,
                "maxBikeCadence": 92.0,
                "trainingStressScore": 44.5,
                "intensityFactor": 0.948,
            }
        ],
    )

    activity = GarminSummaryImporter(
        str(source)
    ).import_activities()[0]

    assert activity.sport == "BIKE"
    assert activity.avg_power == 188.0
    assert activity.normalized_power == 200.0
    assert activity.avg_cadence == 79.0
    assert activity.max_cadence == 92.0

    garmin = activity.metadata["garmin"]

    assert garmin["max_power"] == 325.0
    assert garmin["training_stress_score"] == 44.5
    assert garmin["intensity_factor"] == 0.948


def test_imports_swimming_metrics(
    tmp_path: Path,
) -> None:
    source = (
        tmp_path
        / "gabpie_3003_summarizedActivities.json"
    )

    _write_summary_file(
        source,
        [
            {
                "activityId": 555555555,
                "activityType": "lap_swimming",
                "sportType": "SWIMMING",
                "beginTimestamp": 1704240000000,
                "duration": 3000000.0,
                "distance": 200000.0,
                "poolLength": 5000.0,
                "activeLengths": 40.0,
                "avgSwolf": 68.0,
                "avgSwimCadence": 29.0,
                "maxSwimCadence": 34.0,
            }
        ],
    )

    activity = GarminSummaryImporter(
        str(source)
    ).import_activities()[0]

    assert activity.sport == "SWIM"
    assert activity.distance_meters == 2000.0
    assert activity.avg_cadence == 29.0
    assert activity.max_cadence == 34.0

    garmin = activity.metadata["garmin"]

    assert garmin["pool_length_meters"] == 50.0
    assert garmin["active_lengths"] == 40
    assert garmin["avg_swolf"] == 68.0


def test_imports_all_files_from_directory_in_time_order(
    tmp_path: Path,
) -> None:
    first = (
        tmp_path
        / "gabpie_0_summarizedActivities.json"
    )
    second = (
        tmp_path
        / "gabpie_2002_summarizedActivities.json"
    )

    _write_summary_file(
        first,
        [
            {
                "activityId": 2,
                "activityType": "running",
                "beginTimestamp": 1704153600000,
            }
        ],
    )

    _write_summary_file(
        second,
        [
            {
                "activityId": 1,
                "activityType": "road_biking",
                "beginTimestamp": 1704067200000,
            }
        ],
    )

    activities = GarminSummaryImporter(
        str(tmp_path)
    ).import_activities()

    assert [
        activity.source_id
        for activity in activities
    ] == [
        "1",
        "2",
    ]


def test_import_activity_returns_requested_id(
    tmp_path: Path,
) -> None:
    source = (
        tmp_path
        / "gabpie_4004_summarizedActivities.json"
    )

    _write_summary_file(
        source,
        [
            {
                "activityId": 111,
                "activityType": "running",
                "beginTimestamp": 1704067200000,
            },
            {
                "activityId": 222,
                "activityType": "strength_training",
                "beginTimestamp": 1704153600000,
            },
        ],
    )

    activity = GarminSummaryImporter(
        str(source)
    ).import_activity(
        "222"
    )

    assert activity.source_id == "222"
    assert activity.sport == "STRENGTH"


def test_duplicate_activity_id_raises_error(
    tmp_path: Path,
) -> None:
    first = (
        tmp_path
        / "gabpie_0_summarizedActivities.json"
    )
    second = (
        tmp_path
        / "gabpie_2002_summarizedActivities.json"
    )

    duplicate = {
        "activityId": 999,
        "activityType": "running",
        "beginTimestamp": 1704067200000,
    }

    _write_summary_file(
        first,
        [duplicate],
    )

    _write_summary_file(
        second,
        [duplicate],
    )

    with pytest.raises(
        GarminSummaryImportError,
        match="duplicato",
    ):
        GarminSummaryImporter(
            str(tmp_path)
        ).import_activities()


def test_missing_source_path_raises_file_not_found() -> None:
    with pytest.raises(
        FileNotFoundError
    ):
        GarminSummaryImporter(
            "missing/garmin/path"
        ).import_activities()


def test_missing_activity_id_raises_error(
    tmp_path: Path,
) -> None:
    source = (
        tmp_path
        / "gabpie_0_summarizedActivities.json"
    )

    _write_summary_file(
        source,
        [
            {
                "activityType": "running",
                "beginTimestamp": 1704067200000,
            }
        ],
    )

    with pytest.raises(
        GarminSummaryImportError,
        match="activityId",
    ):
        GarminSummaryImporter(
            str(source)
        ).import_activities()