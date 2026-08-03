"""
Test Garmin Activity Merger

Verifica:
- fusione dei campi mancanti dal file grezzo;
- conservazione dell'identità JSON;
- conservazione dei segmenti multisport FIT;
- gestione JSON_ONLY e REVIEW;
- file grezzo mancante;
- errori di parsing;
- modalità strict;
- parsing TCX;
- parsing GPX;
- ricerca di una singola attività.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.importers import garmin_activity_merger
from backend.importers.garmin_activity_merger import (
    GarminActivityMergeError,
    GarminActivityMerger,
)
from backend.models.activity import IronCoachActivity
from backend.models.activity_segment import IronCoachActivitySegment


def _summary_activity(
    *,
    source_id: str = "1001",
    status: str = "SAFE",
    extension: str = ".fit",
    avg_hr: int | None = None,
    distance_meters: float | None = 10000.0,
    duration_seconds: int | None = 3600,
) -> IronCoachActivity:
    return IronCoachActivity(
        activity_id=f"garmin:{source_id}",
        source="garmin",
        source_id=source_id,
        file_hash=None,
        start_time="2025-01-01T10:00:00Z",
        end_time=None,
        sport="RUN",
        activity_type="running",
        duration_seconds=duration_seconds,
        distance_meters=distance_meters,
        elevation_gain=None,
        elevation_loss=None,
        calories=None,
        avg_speed=None,
        max_speed=None,
        avg_hr=avg_hr,
        max_hr=None,
        avg_cadence=None,
        max_cadence=None,
        avg_power=None,
        normalized_power=None,
        training_load=None,
        training_effect=None,
        segments=[],
        metadata={
            "garmin": {
                "name": "Test activity",
            },
            "garmin_historical": {
                "import_status": status,
                "has_raw_file": status != "JSON_ONLY",
                "match_quality": (
                    "EXCELLENT"
                    if status == "SAFE"
                    else (
                        "POSSIBLE"
                        if status == "REVIEW"
                        else None
                    )
                ),
                "raw_file": {
                    "extension": extension,
                },
            },
        },
    )


def _raw_activity(
    *,
    file_hash: str = "rawhash",
    duration_seconds: int | None = 3590,
    distance_meters: float | None = 9990.0,
    avg_hr: int | None = 150,
    segments: list[IronCoachActivitySegment] | None = None,
) -> IronCoachActivity:
    return IronCoachActivity(
        activity_id=file_hash,
        source="garmin",
        source_id=file_hash,
        file_hash=file_hash,
        start_time="2025-01-01T10:00:05Z",
        end_time="2025-01-01T10:59:55Z",
        sport="RUN",
        activity_type="running",
        duration_seconds=duration_seconds,
        distance_meters=distance_meters,
        elevation_gain=120.0,
        elevation_loss=118.0,
        calories=650,
        avg_speed=2.78,
        max_speed=5.1,
        avg_hr=avg_hr,
        max_hr=178,
        avg_cadence=84.0,
        max_cadence=92.0,
        avg_power=250.0,
        normalized_power=265.0,
        training_load=90.0,
        training_effect=4.1,
        segments=segments or [],
        metadata={
            "garmin": {
                "file_name": "1001.fit",
            }
        },
    )


def _patch_historical(
    monkeypatch: pytest.MonkeyPatch,
    activities: list[IronCoachActivity],
) -> None:
    class FakeHistoricalImporter:
        def __init__(
            self,
            summary_source: str,
            raw_matches_csv: str,
        ):
            self.summary_source = summary_source
            self.raw_matches_csv = raw_matches_csv

        def import_activities(
            self,
        ) -> list[IronCoachActivity]:
            return activities

        @staticmethod
        def import_status(
            activity: IronCoachActivity,
        ) -> str:
            return activity.metadata[
                "garmin_historical"
            ][
                "import_status"
            ]

    monkeypatch.setattr(
        garmin_activity_merger,
        "GarminHistoricalImporter",
        FakeHistoricalImporter,
    )


def test_merge_preserves_summary_identity_and_fills_missing_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    summary = _summary_activity(
        avg_hr=None,
    )

    raw_file = tmp_path / "1001.fit"
    raw_file.write_bytes(
        b"fake-fit"
    )

    raw = _raw_activity()

    _patch_historical(
        monkeypatch,
        [summary],
    )

    monkeypatch.setattr(
        GarminActivityMerger,
        "_import_raw_activity",
        lambda self, path: raw,
    )

    result = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
    ).merge_all()

    assert result.total == 1
    assert result.merged == 1
    assert result.parse_errors == 0

    merged = result.activities[0]

    assert merged.activity_id == "garmin:1001"
    assert merged.source_id == "1001"
    assert merged.sport == "RUN"
    assert merged.activity_type == "running"
    assert merged.duration_seconds == 3600
    assert merged.distance_meters == 10000.0
    assert merged.avg_hr == 150
    assert merged.max_hr == 178
    assert merged.elevation_gain == 120.0
    assert merged.file_hash == "rawhash"

    merge_metadata = merged.metadata[
        "garmin_merge"
    ]

    assert merge_metadata[
        "merge_status"
    ] == "MERGED"

    assert merge_metadata[
        "summary_identity_preserved"
    ] is True

    assert "avg_hr" in merge_metadata[
        "fields_from_raw"
    ]

    assert "duration_seconds" not in merge_metadata[
        "fields_from_raw"
    ]


def test_existing_summary_value_is_not_overwritten(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    summary = _summary_activity(
        avg_hr=145,
    )

    (
        tmp_path
        / "1001.fit"
    ).write_bytes(
        b"fake-fit"
    )

    _patch_historical(
        monkeypatch,
        [summary],
    )

    monkeypatch.setattr(
        GarminActivityMerger,
        "_import_raw_activity",
        lambda self, path: _raw_activity(
            avg_hr=160
        ),
    )

    merged = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
    ).merge_all().activities[0]

    assert merged.avg_hr == 145
    assert "avg_hr" not in merged.metadata[
        "garmin_merge"
    ][
        "fields_from_raw"
    ]


def test_multisport_segments_are_added(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    summary = replace(
        _summary_activity(),
        sport="MULTISPORT",
        activity_type="triathlon",
    )

    segments = [
        IronCoachActivitySegment(
            sport="SWIM",
            activity_type="lap_swimming",
            start_time="2025-01-01T10:00:00Z",
            duration_seconds=1200,
            distance_meters=1500.0,
            metadata={},
        ),
        IronCoachActivitySegment(
            sport="BIKE",
            activity_type="cycling",
            start_time="2025-01-01T10:20:00Z",
            duration_seconds=3600,
            distance_meters=40000.0,
            metadata={},
        ),
    ]

    (
        tmp_path
        / "1001.fit"
    ).write_bytes(
        b"fake-fit"
    )

    _patch_historical(
        monkeypatch,
        [summary],
    )

    monkeypatch.setattr(
        GarminActivityMerger,
        "_import_raw_activity",
        lambda self, path: _raw_activity(
            segments=segments
        ),
    )

    merged = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
    ).merge_all().activities[0]

    assert len(
        merged.segments
    ) == 2

    assert merged.segments[
        0
    ].sport == "SWIM"

    assert "segments" in merged.metadata[
        "garmin_merge"
    ][
        "fields_from_raw"
    ]


def test_json_only_is_kept_without_raw_merge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    activity = _summary_activity(
        status="JSON_ONLY",
    )

    _patch_historical(
        monkeypatch,
        [activity],
    )

    result = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
    ).merge_all()

    assert result.json_only == 1
    assert result.merged == 0

    merged = result.activities[0]

    assert merged.metadata[
        "garmin_merge"
    ][
        "merge_status"
    ] == "JSON_ONLY"


def test_review_is_skipped_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    activity = _summary_activity(
        status="REVIEW",
    )

    _patch_historical(
        monkeypatch,
        [activity],
    )

    result = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
    ).merge_all()

    assert result.skipped_review == 1
    assert result.merged == 0

    assert result.activities[
        0
    ].metadata[
        "garmin_merge"
    ][
        "merge_status"
    ] == "SKIPPED_REVIEW"


def test_review_can_be_included(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    activity = _summary_activity(
        status="REVIEW",
    )

    (
        tmp_path
        / "1001.fit"
    ).write_bytes(
        b"fake-fit"
    )

    _patch_historical(
        monkeypatch,
        [activity],
    )

    monkeypatch.setattr(
        GarminActivityMerger,
        "_import_raw_activity",
        lambda self, path: _raw_activity(),
    )

    result = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
        include_review=True,
    ).merge_all()

    assert result.merged == 1
    assert result.skipped_review == 0


def test_missing_raw_file_is_reported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    activity = _summary_activity()

    _patch_historical(
        monkeypatch,
        [activity],
    )

    result = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
    ).merge_all()

    assert result.missing_raw_files == 1
    assert result.merged == 0

    assert result.activities[
        0
    ].metadata[
        "garmin_merge"
    ][
        "merge_status"
    ] == "MISSING_RAW_FILE"


def test_strict_mode_raises_for_missing_raw_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_historical(
        monkeypatch,
        [
            _summary_activity()
        ],
    )

    merger = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
        strict=True,
    )

    with pytest.raises(
        FileNotFoundError,
        match="File grezzo estratto non trovato",
    ):
        merger.merge_all()


def test_parse_error_is_recorded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (
        tmp_path
        / "1001.fit"
    ).write_bytes(
        b"invalid"
    )

    _patch_historical(
        monkeypatch,
        [
            _summary_activity()
        ],
    )

    def fail_import(
        self: GarminActivityMerger,
        path: Path,
    ) -> IronCoachActivity:
        raise ValueError(
            "invalid raw file"
        )

    monkeypatch.setattr(
        GarminActivityMerger,
        "_import_raw_activity",
        fail_import,
    )

    result = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
    ).merge_all()

    assert result.parse_errors == 1

    assert result.activities[
        0
    ].metadata[
        "garmin_merge"
    ][
        "merge_status"
    ] == "PARSE_ERROR"


def test_tcx_parser_sums_all_laps(
    tmp_path: Path,
) -> None:
    tcx = tmp_path / "activity.tcx"

    tcx.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities>
    <Activity Sport="Running">
      <Lap StartTime="2025-01-01T10:00:00Z">
        <TotalTimeSeconds>600</TotalTimeSeconds>
        <DistanceMeters>2000</DistanceMeters>
        <Calories>150</Calories>
        <AverageHeartRateBpm><Value>140</Value></AverageHeartRateBpm>
        <MaximumHeartRateBpm><Value>160</Value></MaximumHeartRateBpm>
      </Lap>
      <Lap StartTime="2025-01-01T10:10:00Z">
        <TotalTimeSeconds>900</TotalTimeSeconds>
        <DistanceMeters>3000</DistanceMeters>
        <Calories>220</Calories>
        <AverageHeartRateBpm><Value>150</Value></AverageHeartRateBpm>
        <MaximumHeartRateBpm><Value>170</Value></MaximumHeartRateBpm>
      </Lap>
    </Activity>
  </Activities>
</TrainingCenterDatabase>
""",
        encoding="utf-8",
    )

    merger = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
    )

    activity = merger._import_tcx(
        tcx
    )

    assert activity.sport == "RUN"
    assert activity.duration_seconds == 1500
    assert activity.distance_meters == 5000.0
    assert activity.calories == 370
    assert activity.avg_hr == 145
    assert activity.max_hr == 170


def test_gpx_parser_calculates_distance_and_duration(
    tmp_path: Path,
) -> None:
    gpx = tmp_path / "activity.gpx"

    gpx.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="IronCoach" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>Test</name>
    <trkseg>
      <trkpt lat="45.0000" lon="7.0000">
        <ele>100</ele>
        <time>2025-01-01T10:00:00Z</time>
      </trkpt>
      <trkpt lat="45.0010" lon="7.0000">
        <ele>110</ele>
        <time>2025-01-01T10:01:00Z</time>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
""",
        encoding="utf-8",
    )

    merger = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
    )

    activity = merger._import_gpx(
        gpx
    )

    assert activity.duration_seconds == 60
    assert activity.distance_meters is not None
    assert 110.0 <= activity.distance_meters <= 112.5
    assert activity.elevation_gain == 10.0
    assert activity.elevation_loss == 0.0


def test_merge_activity_returns_requested_activity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = _summary_activity(
        source_id="1001",
        status="JSON_ONLY",
    )

    second = _summary_activity(
        source_id="1002",
        status="JSON_ONLY",
    )

    _patch_historical(
        monkeypatch,
        [
            first,
            second,
        ],
    )

    merger = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
    )

    activity = merger.merge_activity(
        "1002"
    )

    assert activity.source_id == "1002"


def test_merge_activity_missing_id_raises_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_historical(
        monkeypatch,
        [],
    )

    merger = GarminActivityMerger(
        summary_source="summary",
        raw_matches_csv="matches.csv",
        extracted_directory=str(
            tmp_path
        ),
    )

    with pytest.raises(
        GarminActivityMergeError,
        match="non trovata",
    ):
        merger.merge_activity(
            "9999"
        )