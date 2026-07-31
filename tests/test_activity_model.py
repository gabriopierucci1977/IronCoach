"""
Basic tests for IronCoachActivity model.
"""

from backend.models.activity import IronCoachActivity


def test_activity_creation():

    activity = IronCoachActivity(
        activity_id="TEST001",
        source="garmin",
        sport="RUN",
        duration_seconds=3600,
        distance_meters=10000,
        avg_hr=145,
        max_hr=160,
    )

    assert activity.sport == "RUN"
    assert activity.duration_seconds == 3600
    assert activity.distance_meters == 10000
    assert activity.avg_hr == 145
    assert activity.max_hr == 160


def test_multisport_creation():

    activity = IronCoachActivity(
        activity_id="TEST002",
        source="garmin",
        sport="MULTISPORT",
        segments=[
            {"sport": "SWIM"},
            {"sport": "BIKE"},
            {"sport": "RUN"},
        ],
    )

    assert activity.sport == "MULTISPORT"
    assert len(activity.segments) == 3
    assert activity.segments[0]["sport"] == "SWIM"
    assert activity.segments[1]["sport"] == "BIKE"
    assert activity.segments[2]["sport"] == "RUN"


def test_extended_metrics():

    activity = IronCoachActivity(
        activity_id="TEST003",
        source="garmin",
        sport="BIKE",
        avg_power=190,
        normalized_power=200,
        training_load=44.5,
        training_effect=3.1,
        avg_cadence=85,
        max_cadence=102,
    )

    assert activity.sport == "BIKE"
    assert activity.avg_power == 190
    assert activity.normalized_power == 200
    assert activity.training_load == 44.5
    assert activity.training_effect == 3.1
    assert activity.avg_cadence == 85
    assert activity.max_cadence == 102