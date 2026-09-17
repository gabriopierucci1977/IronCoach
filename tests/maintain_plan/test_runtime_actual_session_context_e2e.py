from datetime import datetime, timezone

import pytest

from backend.context_builder import ContextBuilder, GarminActivityProjectionError
from backend.models.activity import IronCoachActivity
from backend.normalization.activity_normalizer import ActivityNormalizer
from backend.maintain_plan.runtime_actual_session_adapter import (
    RuntimeActivityValidationError, build_actual_session,
)


NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)


def convert(duration=None, distance=None, end_time=None):
    activity = IronCoachActivity(
        activity_id="garmin:1", source="garmin", source_id="source:1",
        start_time="2026-09-15T08:00:00Z", sport="RUN",
        activity_type="running", duration_seconds=duration,
        distance_meters=distance, end_time=end_time,
    )
    builder = ContextBuilder.__new__(ContextBuilder)
    builder.activity_normalizer = ActivityNormalizer()
    projected = builder._garmin_activity_to_session(activity)
    return projected, build_actual_session(projected, "athlete", normalized_at=NOW)


@pytest.mark.parametrize(("duration", "distance", "expected"), [
    (None, None, []),
    (0, 0, [("duration", 0.0), ("distance", 0.0)]),
    (1800, 5000, [("duration", 30.0), ("distance", 5.0)]),
])
def test_source_missingness_survives_context_and_adapter(duration, distance, expected):
    projected, session = convert(duration, distance)
    metrics = [(item["metric"], item["value"])
               for item in session.components[0].secondary_metrics]
    assert metrics == expected
    assert projected["raw"]["duration_minutes"] == (
        None if duration is None else duration / 60)
    assert projected["raw"]["distance_km"] == (
        None if distance is None else distance / 1000)


@pytest.mark.parametrize(("duration", "distance"), [("bad", None), (None, "bad")])
def test_invalid_source_numbers_fail_deterministically(duration, distance):
    with pytest.raises(GarminActivityProjectionError):
        convert(duration, distance)


def test_adapter_preserves_explicit_duration_but_not_synthetic_distance():
    projected, _ = convert(None, None)
    projected["duration_minutes"] = projected["distance_km"] = 0.0
    session = build_actual_session(projected, "athlete", normalized_at=NOW)
    assert [(item["metric"], item["value"])
            for item in session.components[0].secondary_metrics] == [("duration", 0.0)]


def test_garmin_without_end_time_keeps_actual_session_end_absent():
    projected, session = convert(1800, 5000)

    assert projected["end"] is None
    assert session.end is None
    assert session.components[0].end is None


def test_importer_derived_end_time_is_not_projected_as_observed():
    projected, session = convert(
        1800, 5000, end_time="2026-09-15T08:30:00Z",
    )

    assert projected["end"] is None
    assert session.end is None
    assert session.components[0].end is None
    assert [(item["metric"], item["value"], item["unit"])
            for item in session.components[0].secondary_metrics] == [
                ("duration", 30.0, "min"),
                ("distance", 5.0, "km"),
            ]
    assert session.components[0].discipline.value == "RUN"
