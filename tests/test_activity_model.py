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
    )

    assert activity.sport == "RUN"
    assert activity.duration_seconds == 3600
    assert activity.avg_hr == 145


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

    assert len(activity.segments) == 3
