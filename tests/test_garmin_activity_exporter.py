"""
Test Garmin Activity Exporter

Verifica:
- esportazione JSON Lines;
- manifest con conteggi e SHA-256;
- round-trip completo delle attività;
- segmenti multisport;
- supporto gzip;
- duplicati activity_id e source_id;
- export vuoto;
- manifest mancante o alterato;
- JSON Lines non valido;
- campi sconosciuti;
- numeri non finiti.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from backend.importers.garmin_activity_exporter import (
    GarminActivityExportError,
    GarminActivityExporter,
)
from backend.models.activity import IronCoachActivity
from backend.models.activity_segment import IronCoachActivitySegment


def _activity(
    *,
    activity_id: str = "garmin:1001",
    source_id: str = "1001",
    sport: str = "RUN",
    status: str = "MERGED",
    segments: list[IronCoachActivitySegment] | None = None,
) -> IronCoachActivity:
    return IronCoachActivity(
        activity_id=activity_id,
        source="garmin",
        source_id=source_id,
        file_hash="abc123",
        start_time="2025-01-01T10:00:00Z",
        end_time="2025-01-01T11:00:00Z",
        sport=sport,
        activity_type="running",
        duration_seconds=3600,
        distance_meters=10000.0,
        elevation_gain=120.0,
        elevation_loss=118.0,
        calories=650,
        avg_speed=2.777778,
        max_speed=5.2,
        avg_hr=150,
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
                "name": "Test activity",
            },
            "garmin_merge": {
                "merge_status": status,
                "raw_format": "FIT",
                "fields_from_raw": [
                    "file_hash"
                ],
            },
        },
    )


def _segment(
    *,
    sport: str = "SWIM",
    duration_seconds: int = 1200,
    distance_meters: float = 1500.0,
) -> IronCoachActivitySegment:
    return IronCoachActivitySegment(
        sport=sport,
        activity_type=sport.lower(),
        start_time="2025-01-01T10:00:00Z",
        duration_seconds=duration_seconds,
        distance_meters=distance_meters,
        elevation_gain=None,
        elevation_loss=None,
        avg_hr=140,
        max_hr=160,
        avg_speed=None,
        max_speed=None,
        avg_power=None,
        normalized_power=None,
        avg_cadence=None,
        max_cadence=None,
        training_load=None,
        training_effect=None,
        metadata={
            "garmin": {
                "segment": True,
            }
        },
    )


def _sha256(
    path: Path,
) -> str:
    sha = hashlib.sha256()

    with path.open(
        "rb"
    ) as source:
        for chunk in iter(
            lambda: source.read(
                1024 * 1024
            ),
            b"",
        ):
            sha.update(
                chunk
            )

    return sha.hexdigest()


def test_export_creates_jsonl_and_manifest(
    tmp_path: Path,
) -> None:
    output_path = (
        tmp_path
        / "activities.jsonl"
    )

    exporter = GarminActivityExporter(
        output_path=str(
            output_path
        )
    )

    result = exporter.export(
        [
            _activity(),
            _activity(
                activity_id="garmin:1002",
                source_id="1002",
                sport="BIKE",
            ),
        ]
    )

    assert output_path.exists()
    assert Path(
        result.manifest_path
    ).exists()

    assert result.activity_count == 2
    assert result.segment_count == 0
    assert result.byte_count == output_path.stat().st_size
    assert result.sha256 == _sha256(
        output_path
    )
    assert result.compressed is False

    lines = output_path.read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(lines) == 2

    first = json.loads(
        lines[0]
    )

    assert first["activity_id"] == "garmin:1001"
    assert first["source_id"] == "1001"


def test_manifest_contains_expected_counts(
    tmp_path: Path,
) -> None:
    output_path = (
        tmp_path
        / "activities.jsonl"
    )

    exporter = GarminActivityExporter(
        output_path=str(
            output_path
        )
    )

    exporter.export(
        [
            _activity(
                status="MERGED",
                sport="RUN",
            ),
            _activity(
                activity_id="garmin:1002",
                source_id="1002",
                status="JSON_ONLY",
                sport="SWIM",
            ),
        ]
    )

    manifest = json.loads(
        exporter.manifest_path.read_text(
            encoding="utf-8"
        )
    )

    assert manifest["format"] == (
        "ironcoach-garmin-activities-jsonl"
    )

    assert manifest["format_version"] == 1
    assert manifest["activity_count"] == 2

    assert manifest[
        "merge_status_counts"
    ] == {
        "JSON_ONLY": 1,
        "MERGED": 1,
    }

    assert manifest[
        "sport_counts"
    ] == {
        "RUN": 1,
        "SWIM": 1,
    }

    assert manifest[
        "raw_format_counts"
    ] == {
        "FIT": 2,
    }


def test_round_trip_preserves_activity_and_segments(
    tmp_path: Path,
) -> None:
    segments = [
        _segment(),
        _segment(
            sport="BIKE",
            duration_seconds=3600,
            distance_meters=40000.0,
        ),
    ]

    original = _activity(
        sport="MULTISPORT",
        segments=segments,
    )

    exporter = GarminActivityExporter(
        output_path=str(
            tmp_path
            / "activities.jsonl"
        )
    )

    result = exporter.export(
        [
            original
        ]
    )

    assert result.segment_count == 2

    loaded = exporter.load()

    assert len(loaded) == 1
    assert loaded[0] == original
    assert len(
        loaded[0].segments
    ) == 2
    assert loaded[0].segments[0].sport == "SWIM"
    assert loaded[0].segments[1].sport == "BIKE"


def test_iter_activities_reads_one_record_at_a_time(
    tmp_path: Path,
) -> None:
    exporter = GarminActivityExporter(
        output_path=str(
            tmp_path
            / "activities.jsonl"
        )
    )

    exporter.export(
        [
            _activity(),
            _activity(
                activity_id="garmin:1002",
                source_id="1002",
            ),
        ]
    )

    source_ids = [
        activity.source_id
        for activity in exporter.iter_activities()
    ]

    assert source_ids == [
        "1001",
        "1002",
    ]


def test_gzip_export_and_load(
    tmp_path: Path,
) -> None:
    output_path = (
        tmp_path
        / "activities.jsonl.gz"
    )

    exporter = GarminActivityExporter(
        output_path=str(
            output_path
        )
    )

    result = exporter.export(
        [
            _activity()
        ]
    )

    assert result.compressed is True

    with gzip.open(
        output_path,
        mode="rt",
        encoding="utf-8",
    ) as source:
        payload = json.loads(
            source.readline()
        )

    assert payload["source_id"] == "1001"

    loaded = exporter.load()

    assert loaded[0].source_id == "1001"


def test_duplicate_activity_id_raises_error(
    tmp_path: Path,
) -> None:
    exporter = GarminActivityExporter(
        output_path=str(
            tmp_path
            / "activities.jsonl"
        )
    )

    first = _activity()

    second = _activity(
        source_id="1002",
    )

    with pytest.raises(
        GarminActivityExportError,
        match="activity_id duplicato",
    ):
        exporter.export(
            [
                first,
                second,
            ]
        )


def test_duplicate_source_id_raises_error(
    tmp_path: Path,
) -> None:
    exporter = GarminActivityExporter(
        output_path=str(
            tmp_path
            / "activities.jsonl"
        )
    )

    first = _activity()

    second = _activity(
        activity_id="garmin:1002",
    )

    with pytest.raises(
        GarminActivityExportError,
        match="source_id duplicato",
    ):
        exporter.export(
            [
                first,
                second,
            ]
        )


def test_empty_export_raises_error(
    tmp_path: Path,
) -> None:
    exporter = GarminActivityExporter(
        output_path=str(
            tmp_path
            / "activities.jsonl"
        )
    )

    with pytest.raises(
        GarminActivityExportError,
        match="Nessuna attività",
    ):
        exporter.export(
            []
        )

    assert not exporter.output_path.exists()
    assert not exporter.manifest_path.exists()


def test_missing_manifest_raises_file_not_found(
    tmp_path: Path,
) -> None:
    output_path = (
        tmp_path
        / "activities.jsonl"
    )

    output_path.write_text(
        "{}\n",
        encoding="utf-8",
    )

    exporter = GarminActivityExporter(
        output_path=str(
            output_path
        )
    )

    with pytest.raises(
        FileNotFoundError,
        match="manifest",
    ):
        exporter.validate_manifest()


def test_modified_export_fails_manifest_validation(
    tmp_path: Path,
) -> None:
    exporter = GarminActivityExporter(
        output_path=str(
            tmp_path
            / "activities.jsonl"
        )
    )

    exporter.export(
        [
            _activity()
        ]
    )

    with exporter.output_path.open(
        "a",
        encoding="utf-8",
    ) as output:
        output.write(
            "{}\n"
        )

    with pytest.raises(
        GarminActivityExportError,
        match="Dimensione export Garmin non valida",
    ):
        exporter.validate_manifest()


def test_invalid_json_line_raises_error(
    tmp_path: Path,
) -> None:
    output_path = (
        tmp_path
        / "activities.jsonl"
    )

    output_path.write_text(
        "{not-json}\n",
        encoding="utf-8",
    )

    exporter = GarminActivityExporter(
        output_path=str(
            output_path
        )
    )

    with pytest.raises(
        GarminActivityExportError,
        match="JSON Lines non valido",
    ):
        list(
            exporter.iter_activities(
                validate_manifest=False
            )
        )


def test_unknown_activity_field_raises_error() -> None:
    payload = GarminActivityExporter.activity_to_dict(
        _activity()
    )

    payload["unknown_field"] = 123

    with pytest.raises(
        GarminActivityExportError,
        match="Campi attività non supportati",
    ):
        GarminActivityExporter.activity_from_dict(
            payload
        )


def test_non_finite_number_raises_error(
    tmp_path: Path,
) -> None:
    activity = _activity()

    activity.metadata[
        "invalid"
    ] = float(
        "nan"
    )

    exporter = GarminActivityExporter(
        output_path=str(
            tmp_path
            / "activities.jsonl"
        )
    )

    with pytest.raises(
        GarminActivityExportError,
        match="non finito",
    ):
        exporter.export(
            [
                activity
            ]
        )