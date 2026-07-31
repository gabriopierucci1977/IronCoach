"""
Tests for Garmin FIT importer.
"""

from backend.importers.garmin_fit_importer import GarminFitImporter


TEST_FILE = "data/garmin_raw/4872731416_ACTIVITY.fit"


def test_import_garmin_bike_activity():

    activity = GarminFitImporter(
        TEST_FILE
    ).import_activity()

    assert activity.source == "garmin"

    assert activity.sport == "BIKE"

    assert activity.distance_meters > 0

    assert activity.duration_seconds > 0

    assert activity.avg_hr == 130

    assert activity.avg_power == 190

    assert activity.file_hash is not None


def test_metadata_creation():

    activity = GarminFitImporter(
        TEST_FILE
    ).import_activity()

    assert "garmin" in activity.metadata

    assert (
        activity.metadata["garmin"]["sub_sport"]
        == "virtual_activity"
    )