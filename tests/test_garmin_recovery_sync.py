import json

import pytest

from backend.importers.garmin_recovery_sync import (
    GarminRecoverySync,
    GarminRecoverySyncError,
)


class FakeGarminRecoveryClient:
    def __init__(
        self,
        *,
        fail=False,
    ):
        self.fail = fail

    def login(
        self,
        tokenstore,
    ):
        return None

    def get_sleep_data(
        self,
        cdate,
    ):
        return {
            "dailySleepDTO": {
                "calendarDate": cdate,
                "sleepTimeSeconds": None,
            }
        }

    def get_hrv_data(
        self,
        cdate,
    ):
        return {}

    def get_morning_training_readiness(
        self,
        cdate,
    ):
        return None

    def get_stress_data(
        self,
        cdate,
    ):
        if self.fail:
            raise RuntimeError(
                "Garmin temporaneamente non disponibile"
            )

        return {
            "avgStressLevel": 18,
        }

    def get_body_battery(
        self,
        startdate,
        enddate=None,
    ):
        return [
            {
                "charged": 7,
                "drained": 11,
            }
        ]

    def get_stats_and_body(
        self,
        cdate,
    ):
        return {
            "restingHeartRate": 43,
            "averageStressLevel": 18,
            "bodyBatteryMostRecentValue": 83,
            "bodyBatteryChargedValue": 7,
            "bodyBatteryDrainedValue": 11,
        }


def test_recovery_sync_writes_state_only_after_complete_success(
    tmp_path,
) -> None:
    archive_path = (
        tmp_path
        / "recovery.json"
    )
    state_path = (
        tmp_path
        / "recovery_state.json"
    )

    failing = GarminRecoverySync(
        archive_path=str(
            archive_path
        ),
        state_path=str(
            state_path
        ),
        client=FakeGarminRecoveryClient(
            fail=True
        ),
        tokenstore="unused",
    )

    with pytest.raises(
        GarminRecoverySyncError
    ):
        failing.sync(
            sync_date="2026-08-28"
        )

    assert not state_path.exists()
    assert not archive_path.exists()

    successful = GarminRecoverySync(
        archive_path=str(
            archive_path
        ),
        state_path=str(
            state_path
        ),
        client=FakeGarminRecoveryClient(),
        tokenstore="unused",
    )

    result = successful.sync(
        sync_date="2026-08-28"
    )

    assert result.record_count == 1
    assert result.inserted_count == 1
    assert result.updated_count == 0
    assert (
        result.last_observation_date
        == "2026-08-28"
    )

    state = json.loads(
        state_path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        state["source_checked_at"]
        == result.source_checked_at
    )
    assert (
        state["last_observation_date"]
        == "2026-08-28"
    )
