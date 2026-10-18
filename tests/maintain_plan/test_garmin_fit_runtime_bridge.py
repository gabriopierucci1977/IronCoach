"""Tests for the Garmin FIT runtime bridge."""

import pytest
from types import SimpleNamespace

from backend.importers.garmin_fit_runtime_bridge import (
    source_activity_to_runtime_payload,
)


def test_source_activity_is_converted_to_runtime_payload():
    activity = SimpleNamespace(
        source_id="fit-hash-123",
        start_time="2026-10-14 10:07:02",
        end_time=None,
        sport="BIKE",
        activity_type="road",
        duration_seconds=5955,
        distance_meters=52899.44,
        avg_hr=142,
        max_hr=167,
        avg_power=None,
        normalized_power=None,
        segments=[],
        metadata={
            "garmin": {
                "file_name": "24720297468_ACTIVITY.fit",
                "sub_sport": "road",
            }
        },
    )

    payload = source_activity_to_runtime_payload(
        activity,
        "fit-hash-123",
    )

    assert payload["activity_id"] == "fit-hash-123"
    assert payload["source_id"] == "fit-hash-123"
    assert payload["file_hash"] == "fit-hash-123"
    assert payload["date"] == "2026-10-14T10:07:02Z"
    assert payload["sport"] == "BIKE"
    assert payload["duration_minutes"] == 99.25
    assert payload["distance_km"] == pytest.approx(52.89944)
    assert payload["heart_rate"] == {"average": 142, "max": 167}
    assert payload["power"] == {}
    assert payload["raw"]["activity_type"] == "road"
    assert payload["metadata"]["garmin"]["sub_sport"] == "road"
