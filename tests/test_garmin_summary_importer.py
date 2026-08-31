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
from backend.importers.garmin_live_activity_adapter import (
    GarminLiveActivityAdapter,
)
from backend.importers.garmin_live_sync import (
    GarminLiveSync,
)
from backend.importers.garmin_activity_exporter import (
    GarminActivityExporter,
)
from backend.models.activity import IronCoachActivity


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

def test_live_activity_adapter_preserves_live_units() -> None:
    activity = GarminLiveActivityAdapter.convert(
        {
            "activityId": 24134063811,
            "activityName": "Live Test",
            "activityType": {
                "typeKey": "indoor_cycling",
            },
            "startTimeGMT": "2026-08-27 09:00:42",
            "startTimeLocal": "2026-08-27 11:00:42",
            "duration": 3603.52099609375,
            "elapsedDuration": 3603.52099609375,
            "movingDuration": 3598.72998046875,
            "distance": 30329.140625,
            "calories": 523.0,
            "averageHR": 118.0,
            "maxHR": 143.0,
            "averageSpeed": 8.416999816894531,
            "maxSpeed": 14.97599983215332,
            "activityTrainingLoad": 56.946868896484375,
            "aerobicTrainingEffect": 2.5,
            "anaerobicTrainingEffect": 0.0,
            "vO2MaxValue": 55.0,
        }
    )

    assert activity.activity_id == (
        "garmin:24134063811"
    )
    assert activity.source_id == "24134063811"
    assert activity.sport == "BIKE"
    assert activity.activity_type == "indoor_cycling"

    assert activity.start_time == (
        "2026-08-27T09:00:42Z"
    )
    assert activity.duration_seconds == 3604

    # L'API live restituisce già metri e m/s:
    # questi valori NON devono essere riconvertiti
    # come quelli dell'export storico.
    assert activity.distance_meters == pytest.approx(
        30329.140625
    )
    assert activity.avg_speed == pytest.approx(
        8.416999816894531
    )

    assert activity.calories == 523
    assert activity.avg_hr == 118
    assert activity.max_hr == 143
    assert activity.training_load == pytest.approx(
        56.946868896484375
    )
    assert activity.training_effect == 2.5

    assert activity.metadata[
        "garmin_live"
    ][
        "start_time_local"
    ] == "2026-08-27 11:00:42"

    assert activity.metadata[
        "garmin_live"
    ][
        "vo2_max"
    ] == pytest.approx(55.0)


def test_live_sync_updates_archive_and_records_source_check(
    tmp_path: Path,
    monkeypatch,
) -> None:
    archive_path = (
        tmp_path
        / "garmin_activities_merged.jsonl.gz"
    )
    state_path = (
        tmp_path
        / "garmin_live_sync_state.json"
    )

    existing = IronCoachActivity(
        activity_id="garmin:100",
        source="garmin",
        source_id="100",
        start_time="2026-07-30T04:10:16Z",
        sport="RUN",
        activity_type="running",
        duration_seconds=3600,
        training_load=100.0,
    )

    GarminActivityExporter(
        output_path=str(
            archive_path
        )
    ).export(
        [existing]
    )

    class FakeGarmin:
        def __init__(self):
            self.login_tokenstore = None
            self.fetch_args = None

        def login(
            self,
            tokenstore=None,
        ):
            self.login_tokenstore = tokenstore

        def get_activities_by_date(
            self,
            startdate,
            enddate=None,
            activitytype=None,
            sortorder=None,
        ):
            self.fetch_args = {
                "startdate": startdate,
                "enddate": enddate,
                "sortorder": sortorder,
            }

            return [
                {
                    "activityId": 100,
                    "activityType": {
                        "typeKey": "running",
                    },
                    "startTimeGMT": (
                        "2026-07-30 04:10:16"
                    ),
                    "duration": 3600.0,
                    "vO2MaxValue": 57.0,
                },
                {
                    "activityId": 101,
                    "activityType": {
                        "typeKey": "indoor_cycling",
                    },
                    "startTimeGMT": (
                        "2026-08-01 09:00:00"
                    ),
                    "duration": 1800.0,
                    "distance": 15000.0,
                    "activityTrainingLoad": 50.0,
                },
            ]

    client = FakeGarmin()

    monkeypatch.setattr(
        GarminLiveSync,
        "_utc_now",
        staticmethod(
            lambda: "2026-08-28T07:30:00Z"
        ),
    )

    result = GarminLiveSync(
        archive_path=str(
            archive_path
        ),
        state_path=str(
            state_path
        ),
        tokenstore=str(
            tmp_path / "auth"
        ),
        client=client,
    ).sync(
        end_date="2026-08-28"
    )

    assert client.fetch_args == {
        "startdate": "2026-07-30",
        "enddate": "2026-08-28",
        "sortorder": "asc",
    }

    assert result.fetched_count == 2
    assert result.existing_count == 1
    assert result.added_count == 1
    assert result.skipped_existing == 1
    assert result.activity_count == 2

    assert result.source_checked_at == (
        "2026-08-28T07:30:00Z"
    )
    assert result.last_activity_at == (
        "2026-08-01T09:00:00Z"
    )

    state = json.loads(
        state_path.read_text(
            encoding="utf-8"
        )
    )

    assert state[
        "source_checked_at"
    ] == "2026-08-28T07:30:00Z"

    assert state[
        "last_activity_at"
    ] == "2026-08-01T09:00:00Z"

    archived = GarminActivityExporter(
        output_path=str(
            archive_path
        )
    ).load(
        validate_manifest=True
    )

    assert [
        activity.source_id
        for activity in archived
    ] == [
        "100",
        "101",
    ]

    # Il duplicato resta skipped dall'export incrementale,
    # ma può essere arricchito con metadata live più recenti.
    existing_after_sync = archived[0]

    assert existing_after_sync.activity_id == (
        "garmin:100"
    )
    assert existing_after_sync.source_id == "100"
    assert existing_after_sync.training_load == 100.0

    assert existing_after_sync.metadata[
        "garmin_live"
    ][
        "vo2_max"
    ] == pytest.approx(57.0)
