"""
Tests for Garmin multisport FIT import.
"""

from backend.importers.garmin_fit_importer import GarminFitImporter


TEST_TRIATHLON_FILE = (
    "data/garmin_raw/14891176843_ACTIVITY.fit"
)


def test_garmin_triathlon_import():

    activity = GarminFitImporter(
        TEST_TRIATHLON_FILE
    ).import_activity()


    assert activity.source == "garmin"

    assert activity.sport == "MULTISPORT"

    assert len(activity.segments) == 5


    assert activity.segments[0].sport == "SWIM"

    assert activity.segments[1].sport == "TRANSITION"

    assert activity.segments[2].sport == "BIKE"

    assert activity.segments[3].sport == "TRANSITION"

    assert activity.segments[4].sport == "RUN"



def test_garmin_triathlon_distances():

    activity = GarminFitImporter(
        TEST_TRIATHLON_FILE
    ).import_activity()


    assert activity.segments[2].distance_meters == 47428.93

    assert activity.segments[4].distance_meters == 7538.92



def test_garmin_triathlon_duration():

    activity = GarminFitImporter(
        TEST_TRIATHLON_FILE
    ).import_activity()


    assert activity.segments[2].duration_seconds == 5127

    assert activity.segments[4].duration_seconds == 1954