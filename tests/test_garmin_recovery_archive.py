from backend.importers.garmin_recovery_adapter import (
    GarminRecoveryAdapter,
)
from backend.importers.garmin_recovery_archive import (
    GarminRecoveryArchive,
)


def test_garmin_recovery_stays_conservative_and_upserts_day(
    tmp_path,
) -> None:
    archive = GarminRecoveryArchive(
        archive_path=str(
            tmp_path
            / "recovery.json"
        )
    )

    first = GarminRecoveryAdapter.convert(
        date="2026-08-28",
        sleep={
            "dailySleepDTO": {
                "calendarDate": (
                    "2026-08-28"
                ),
                "sleepTimeSeconds": None,
            }
        },
        hrv={},
        training_readiness=None,
        stress={
            "avgStressLevel": 18,
        },
        body_battery=[
            {
                "charged": 7,
                "drained": 11,
            }
        ],
        stats={
            "restingHeartRate": 43,
            "bodyBatteryMostRecentValue": 83,
            "bodyBatteryChargedValue": 7,
            "bodyBatteryDrainedValue": 11,
        },
    )

    assert "readiness" not in first
    assert (
        first["training_readiness"]
        is None
    )
    assert first["hrv"] is None
    assert (
        first["sleep"]["hours"]
        is None
    )
    assert first["resting_hr"] == 43.0
    assert first["stress"] == 18.0
    assert (
        first["body_battery"]
        == 83.0
    )

    first_result = archive.upsert(
        [first]
    )

    assert (
        first_result.record_count
        == 1
    )
    assert (
        first_result.inserted_count
        == 1
    )

    second = GarminRecoveryAdapter.convert(
        date="2026-08-28",
        stress={
            "avgStressLevel": 20,
        },
        stats={
            "restingHeartRate": 44,
            "bodyBatteryMostRecentValue": 80,
        },
    )

    second_result = archive.upsert(
        [second]
    )

    records = archive.load()

    assert (
        second_result.record_count
        == 1
    )
    assert (
        second_result.updated_count
        == 1
    )
    assert len(records) == 1
    assert records[0]["stress"] == 20.0
    assert (
        records[0]["body_battery"]
        == 80.0
    )
