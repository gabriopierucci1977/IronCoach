"""
Test Garmin Historical Importer

Verifica:
- unione tra summarizedActivities JSON e raw matches CSV;
- classificazione SAFE, REVIEW e JSON_ONLY;
- metadati del file grezzo;
- filtri per stato;
- conteggi per stato;
- validazione delle colonne richieste;
- rilevamento di activityId duplicati nel CSV.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from backend.importers.garmin_historical_importer import (
    GarminHistoricalImportError,
    GarminHistoricalImporter,
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


def _write_matches_csv(
    path: Path,
    rows: list[dict],
) -> None:
    fieldnames = [
        "activity_id",
        "activity_name",
        "activity_type",
        "activity_start_utc",
        "activity_duration_seconds",
        "activity_distance_meters",
        "archive",
        "member_name",
        "extension",
        "size_bytes",
        "raw_start_utc",
        "raw_duration_seconds",
        "raw_distance_meters",
        "time_difference_seconds",
        "duration_difference_percent",
        "distance_difference_percent",
        "match_score",
        "match_quality",
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output:
        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def _summary_activities() -> list[dict]:
    return [
        {
            "activityId": 1001,
            "name": "Excellent Run",
            "activityType": "running",
            "sportType": "RUNNING",
            "beginTimestamp": 1704067200000,
            "duration": 3600000.0,
            "distance": 1000000.0,
        },
        {
            "activityId": 1002,
            "name": "Good Bike",
            "activityType": "road_biking",
            "sportType": "CYCLING",
            "beginTimestamp": 1704153600000,
            "duration": 5400000.0,
            "distance": 5000000.0,
        },
        {
            "activityId": 1003,
            "name": "Possible Swim",
            "activityType": "lap_swimming",
            "sportType": "SWIMMING",
            "beginTimestamp": 1704240000000,
            "duration": 3000000.0,
            "distance": 200000.0,
        },
        {
            "activityId": 1004,
            "name": "JSON Only Strength",
            "activityType": "strength_training",
            "sportType": "STRENGTH_TRAINING",
            "beginTimestamp": 1704326400000,
            "duration": 1800000.0,
        },
    ]


def _match_rows() -> list[dict]:
    return [
        {
            "activity_id": "1001",
            "activity_name": "Excellent Run",
            "activity_type": "running",
            "activity_start_utc": "2024-01-01T00:00:00Z",
            "activity_duration_seconds": "3600",
            "activity_distance_meters": "10000",
            "archive": "UploadedFiles_0-_Part1.zip",
            "member_name": "folder/run.fit",
            "extension": ".fit",
            "size_bytes": "123456",
            "raw_start_utc": "2024-01-01T00:00:02Z",
            "raw_duration_seconds": "3599.5",
            "raw_distance_meters": "9999.8",
            "time_difference_seconds": "2",
            "duration_difference_percent": "0.014",
            "distance_difference_percent": "0.002",
            "match_score": "0.5",
            "match_quality": "EXCELLENT",
        },
        {
            "activity_id": "1002",
            "activity_name": "Good Bike",
            "activity_type": "road_biking",
            "activity_start_utc": "2024-01-02T00:00:00Z",
            "activity_duration_seconds": "5400",
            "activity_distance_meters": "50000",
            "archive": "UploadedFiles_0-_Part2.zip",
            "member_name": "folder/bike.tcx",
            "extension": ".tcx",
            "size_bytes": "654321",
            "raw_start_utc": "2024-01-02T00:00:20Z",
            "raw_duration_seconds": "5398",
            "raw_distance_meters": "50010",
            "time_difference_seconds": "20",
            "duration_difference_percent": "0.037",
            "distance_difference_percent": "0.02",
            "match_score": "8.5",
            "match_quality": "GOOD",
        },
        {
            "activity_id": "1003",
            "activity_name": "Possible Swim",
            "activity_type": "lap_swimming",
            "activity_start_utc": "2024-01-03T00:00:00Z",
            "activity_duration_seconds": "3000",
            "activity_distance_meters": "2000",
            "archive": "UploadedFiles_0-_Part3.zip",
            "member_name": "folder/swim.gpx",
            "extension": ".gpx",
            "size_bytes": "32100",
            "raw_start_utc": "2024-01-03T00:00:00Z",
            "raw_duration_seconds": "",
            "raw_distance_meters": "",
            "time_difference_seconds": "0",
            "duration_difference_percent": "",
            "distance_difference_percent": "",
            "match_score": "20",
            "match_quality": "POSSIBLE",
        },
    ]


def _build_importer(
    tmp_path: Path,
) -> GarminHistoricalImporter:
    summary_path = (
        tmp_path
        / "gabpie_0_summarizedActivities.json"
    )

    matches_path = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    _write_summary_file(
        summary_path,
        _summary_activities(),
    )

    _write_matches_csv(
        matches_path,
        _match_rows(),
    )

    return GarminHistoricalImporter(
        summary_source=str(
            summary_path
        ),
        raw_matches_csv=str(
            matches_path
        ),
    )


def test_enriches_safe_activity_with_raw_metadata(
    tmp_path: Path,
) -> None:
    importer = _build_importer(
        tmp_path
    )

    activities = (
        importer.import_activities()
    )

    activity = next(
        item
        for item in activities
        if item.source_id == "1001"
    )

    historical = activity.metadata[
        "garmin_historical"
    ]

    assert historical["import_status"] == "SAFE"
    assert historical["has_raw_file"] is True
    assert historical["match_quality"] == "EXCELLENT"

    assert historical["raw_file"] == {
        "archive": "UploadedFiles_0-_Part1.zip",
        "member_name": "folder/run.fit",
        "extension": ".fit",
        "size_bytes": 123456,
    }

    assert historical["validation"]["match_score"] == 0.5
    assert (
        historical["validation"][
            "time_difference_seconds"
        ]
        == 2.0
    )
    assert (
        historical["validation"][
            "raw_duration_seconds"
        ]
        == 3599.5
    )


def test_good_match_is_safe(
    tmp_path: Path,
) -> None:
    importer = _build_importer(
        tmp_path
    )

    activity = next(
        item
        for item in importer.import_activities()
        if item.source_id == "1002"
    )

    historical = activity.metadata[
        "garmin_historical"
    ]

    assert historical["import_status"] == "SAFE"
    assert historical["match_quality"] == "GOOD"
    assert historical["raw_file"]["extension"] == ".tcx"


def test_possible_match_requires_review(
    tmp_path: Path,
) -> None:
    importer = _build_importer(
        tmp_path
    )

    activity = next(
        item
        for item in importer.import_activities()
        if item.source_id == "1003"
    )

    historical = activity.metadata[
        "garmin_historical"
    ]

    assert historical["import_status"] == "REVIEW"
    assert historical["match_quality"] == "POSSIBLE"
    assert historical["raw_file"]["extension"] == ".gpx"
    assert (
        historical["validation"][
            "raw_duration_seconds"
        ]
        is None
    )


def test_activity_without_match_is_json_only(
    tmp_path: Path,
) -> None:
    importer = _build_importer(
        tmp_path
    )

    activity = next(
        item
        for item in importer.import_activities()
        if item.source_id == "1004"
    )

    historical = activity.metadata[
        "garmin_historical"
    ]

    assert historical == {
        "import_status": "JSON_ONLY",
        "has_raw_file": False,
        "match_quality": None,
    }


def test_status_filters_return_expected_activities(
    tmp_path: Path,
) -> None:
    importer = _build_importer(
        tmp_path
    )

    assert [
        activity.source_id
        for activity in importer.import_safe_activities()
    ] == [
        "1001",
        "1002",
    ]

    assert [
        activity.source_id
        for activity in importer.import_review_activities()
    ] == [
        "1003",
    ]

    assert [
        activity.source_id
        for activity in importer.import_json_only_activities()
    ] == [
        "1004",
    ]


def test_counts_by_status(
    tmp_path: Path,
) -> None:
    importer = _build_importer(
        tmp_path
    )

    assert importer.counts_by_status() == {
        "SAFE": 2,
        "REVIEW": 1,
        "JSON_ONLY": 1,
    }


def test_without_matches_csv_all_activities_are_json_only(
    tmp_path: Path,
) -> None:
    summary_path = (
        tmp_path
        / "gabpie_0_summarizedActivities.json"
    )

    _write_summary_file(
        summary_path,
        _summary_activities(),
    )

    importer = GarminHistoricalImporter(
        summary_source=str(
            summary_path
        )
    )

    assert importer.counts_by_status() == {
        "SAFE": 0,
        "REVIEW": 0,
        "JSON_ONLY": 4,
    }


def test_missing_required_csv_columns_raises_error(
    tmp_path: Path,
) -> None:
    summary_path = (
        tmp_path
        / "gabpie_0_summarizedActivities.json"
    )

    matches_path = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    _write_summary_file(
        summary_path,
        _summary_activities(),
    )

    matches_path.write_text(
        "activity_id,match_quality\n"
        "1001,EXCELLENT\n",
        encoding="utf-8",
    )

    importer = GarminHistoricalImporter(
        summary_source=str(
            summary_path
        ),
        raw_matches_csv=str(
            matches_path
        ),
    )

    with pytest.raises(
        GarminHistoricalImportError,
        match="colonne richieste",
    ):
        importer.import_activities()


def test_duplicate_activity_id_in_matches_csv_raises_error(
    tmp_path: Path,
) -> None:
    summary_path = (
        tmp_path
        / "gabpie_0_summarizedActivities.json"
    )

    matches_path = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    _write_summary_file(
        summary_path,
        _summary_activities(),
    )

    rows = _match_rows()
    rows.append(
        dict(
            rows[0]
        )
    )

    _write_matches_csv(
        matches_path,
        rows,
    )

    importer = GarminHistoricalImporter(
        summary_source=str(
            summary_path
        ),
        raw_matches_csv=str(
            matches_path
        ),
    )

    with pytest.raises(
        GarminHistoricalImportError,
        match="duplicato",
    ):
        importer.import_activities()


def test_unsupported_match_quality_raises_error(
    tmp_path: Path,
) -> None:
    summary_path = (
        tmp_path
        / "gabpie_0_summarizedActivities.json"
    )

    matches_path = (
        tmp_path
        / "garmin_raw_matches.csv"
    )

    _write_summary_file(
        summary_path,
        _summary_activities(),
    )

    rows = _match_rows()
    rows[0]["match_quality"] = "UNKNOWN"

    _write_matches_csv(
        matches_path,
        rows,
    )

    importer = GarminHistoricalImporter(
        summary_source=str(
            summary_path
        ),
        raw_matches_csv=str(
            matches_path
        ),
    )

    with pytest.raises(
        GarminHistoricalImportError,
        match="non supportata",
    ):
        importer.import_activities()