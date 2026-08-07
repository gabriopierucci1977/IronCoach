"""
Test incremento controllato del Garmin Activity Merger.

Verifica che le attività già presenti nell'archivio vengano escluse
prima del parsing dei file FIT/TCX/GPX.
"""

from __future__ import annotations

from pathlib import Path

from backend.importers.garmin_activity_merger import GarminActivityMerger
from backend.importers.garmin_historical_importer import (
    GarminHistoricalImporter,
)
from backend.models.activity import IronCoachActivity


def _activity(
    source_id: str,
    start_time: str,
) -> IronCoachActivity:
    return IronCoachActivity(
        activity_id=f"garmin:{source_id}",
        source="garmin",
        source_id=source_id,
        file_hash=None,
        start_time=start_time,
        end_time=None,
        sport="RUN",
        activity_type="running",
        duration_seconds=3600,
        distance_meters=10000.0,
        elevation_gain=None,
        elevation_loss=None,
        calories=None,
        avg_speed=None,
        max_speed=None,
        avg_hr=None,
        max_hr=None,
        avg_cadence=None,
        max_cadence=None,
        avg_power=None,
        normalized_power=None,
        training_load=None,
        training_effect=None,
        segments=[],
        metadata={
            "garmin_historical": {
                "import_status": "GOOD",
                "raw_file": {
                    "extension": ".fit",
                },
            },
        },
    )


def test_existing_source_ids_are_skipped_before_raw_parsing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    existing = _activity(
        source_id="1001",
        start_time="2025-01-01T08:00:00Z",
    )
    new = _activity(
        source_id="1002",
        start_time="2025-01-02T08:00:00Z",
    )

    monkeypatch.setattr(
        GarminHistoricalImporter,
        "import_activities",
        lambda self: [
            existing,
            new,
        ],
    )

    monkeypatch.setattr(
        GarminHistoricalImporter,
        "import_status",
        staticmethod(
            lambda activity: "GOOD"
        ),
    )

    merger = GarminActivityMerger(
        summary_source=str(tmp_path),
        raw_matches_csv=str(
            tmp_path / "matches.csv"
        ),
        extracted_directory=str(tmp_path),
        excluded_source_ids={
            "1001",
        },
    )

    raw_path_calls: list[str] = []
    raw_import_calls: list[str] = []

    def fake_raw_path(
        activity: IronCoachActivity,
    ) -> Path:
        source_id = str(activity.source_id)
        raw_path_calls.append(source_id)

        path = tmp_path / f"{source_id}.fit"
        path.touch()
        return path

    def fake_import_raw_activity(
        path: Path,
    ) -> IronCoachActivity:
        raw_import_calls.append(path.stem)

        return _activity(
            source_id=f"raw-{path.stem}",
            start_time="2025-01-02T08:00:00Z",
        )

    monkeypatch.setattr(
        merger,
        "_raw_path",
        fake_raw_path,
    )
    monkeypatch.setattr(
        merger,
        "_import_raw_activity",
        fake_import_raw_activity,
    )
    monkeypatch.setattr(
        merger,
        "_merge_activity",
        lambda summary_activity, raw_activity, raw_path: summary_activity,
    )

    result = merger.merge_all()

    assert [
        activity.source_id
        for activity in result.activities
    ] == [
        "1002",
    ]

    assert raw_path_calls == [
        "1002",
    ]
    assert raw_import_calls == [
        "1002",
    ]

    assert result.total == 1
    assert result.excluded_existing == 1


def test_excluded_source_ids_are_normalized(
    tmp_path: Path,
    monkeypatch,
) -> None:
    activity = _activity(
        source_id="1001",
        start_time="2025-01-01T08:00:00Z",
    )

    monkeypatch.setattr(
        GarminHistoricalImporter,
        "import_activities",
        lambda self: [
            activity,
        ],
    )

    merger = GarminActivityMerger(
        summary_source=str(tmp_path),
        raw_matches_csv=str(
            tmp_path / "matches.csv"
        ),
        extracted_directory=str(tmp_path),
        excluded_source_ids={
            " 1001 ",
            "",
        },
    )

    result = merger.merge_all()

    assert result.activities == []
    assert result.total == 0
    assert result.excluded_existing == 1
