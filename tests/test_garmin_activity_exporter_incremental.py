"""
Test export incrementale delle attività Garmin.

Verifica:

- caricamento e validazione dell'archivio esistente;
- aggiunta delle sole attività nuove;
- esclusione dei source_id già archiviati;
- ordinamento cronologico dell'archivio risultante;
- blocco dei conflitti di identità;
- conservazione dell'archivio originale in caso di errore.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from backend.importers.garmin_activity_exporter import (
    GarminActivityExportError,
    GarminActivityExporter,
)
from backend.models.activity import IronCoachActivity


def _activity(
    *,
    source_id: str,
    start_time: str,
    activity_id: str | None = None,
    sport: str = "RUN",
) -> IronCoachActivity:
    return IronCoachActivity(
        activity_id=activity_id or f"garmin:{source_id}",
        source="garmin",
        source_id=source_id,
        file_hash=f"hash-{source_id}",
        start_time=start_time,
        end_time=None,
        sport=sport,
        activity_type=sport.lower(),
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
            "garmin_merge": {
                "merge_status": "MERGED",
                "raw_format": "FIT",
            },
        },
    )


def _sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as source:
        for chunk in iter(
            lambda: source.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def test_incremental_export_adds_only_new_source_ids(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "activities.jsonl.gz"

    exporter = GarminActivityExporter(
        output_path=str(output_path),
    )

    existing_1001 = _activity(
        source_id="1001",
        start_time="2025-01-01T08:00:00Z",
    )
    existing_1002 = _activity(
        source_id="1002",
        start_time="2025-01-02T08:00:00Z",
        sport="BIKE",
    )

    exporter.export(
        [
            existing_1001,
            existing_1002,
        ]
    )

    duplicate_1002 = _activity(
        source_id="1002",
        start_time="2025-01-02T08:00:00Z",
        sport="BIKE",
    )
    new_1003 = _activity(
        source_id="1003",
        start_time="2025-01-03T08:00:00Z",
        sport="SWIM",
    )

    result = exporter.export_incremental(
        [
            duplicate_1002,
            new_1003,
        ]
    )

    assert result.existing_count == 2
    assert result.added_count == 1
    assert result.skipped_existing == 1
    assert result.activity_count == 3

    loaded = exporter.load()

    assert [
        activity.source_id
        for activity in loaded
    ] == [
        "1001",
        "1002",
        "1003",
    ]


def test_incremental_export_sorts_complete_archive_chronologically(
    tmp_path: Path,
) -> None:
    exporter = GarminActivityExporter(
        output_path=str(
            tmp_path / "activities.jsonl.gz"
        ),
    )

    exporter.export(
        [
            _activity(
                source_id="1002",
                start_time="2025-01-02T08:00:00Z",
            ),
            _activity(
                source_id="1003",
                start_time="2025-01-03T08:00:00Z",
            ),
        ]
    )

    result = exporter.export_incremental(
        [
            _activity(
                source_id="1001",
                start_time="2025-01-01T08:00:00Z",
            ),
        ]
    )

    assert result.existing_count == 2
    assert result.added_count == 1
    assert result.skipped_existing == 0

    assert [
        activity.source_id
        for activity in exporter.load()
    ] == [
        "1001",
        "1002",
        "1003",
    ]


def test_incremental_export_rejects_activity_id_conflict(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "activities.jsonl.gz"

    exporter = GarminActivityExporter(
        output_path=str(output_path),
    )

    exporter.export(
        [
            _activity(
                source_id="1001",
                start_time="2025-01-01T08:00:00Z",
            ),
        ]
    )

    original_hash = _sha256(output_path)
    original_manifest_hash = _sha256(
        exporter.manifest_path
    )

    conflicting = _activity(
        source_id="9999",
        activity_id="garmin:1001",
        start_time="2025-01-02T08:00:00Z",
    )

    with pytest.raises(
        GarminActivityExportError,
        match="activity_id.*conflitto",
    ):
        exporter.export_incremental(
            [
                conflicting,
            ]
        )

    assert _sha256(output_path) == original_hash
    assert _sha256(
        exporter.manifest_path
    ) == original_manifest_hash

    assert [
        activity.source_id
        for activity in exporter.load()
    ] == [
        "1001",
    ]


def test_incremental_export_rejects_source_id_conflict(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "activities.jsonl.gz"

    exporter = GarminActivityExporter(
        output_path=str(output_path),
    )

    exporter.export(
        [
            _activity(
                source_id="1001",
                start_time="2025-01-01T08:00:00Z",
            ),
        ]
    )

    original_hash = _sha256(output_path)

    conflicting = _activity(
        source_id="1001",
        activity_id="garmin:different",
        start_time="2025-01-02T08:00:00Z",
    )

    with pytest.raises(
        GarminActivityExportError,
        match="source_id.*conflitto",
    ):
        exporter.export_incremental(
            [
                conflicting,
            ]
        )

    assert _sha256(output_path) == original_hash
    assert exporter.load()[0].activity_id == "garmin:1001"


def test_incremental_export_with_no_new_activities_does_not_rewrite(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "activities.jsonl.gz"

    exporter = GarminActivityExporter(
        output_path=str(output_path),
    )

    existing = _activity(
        source_id="1001",
        start_time="2025-01-01T08:00:00Z",
    )

    initial = exporter.export(
        [
            existing,
        ]
    )

    original_output_hash = _sha256(output_path)
    original_manifest_hash = _sha256(
        exporter.manifest_path
    )

    result = exporter.export_incremental(
        [
            existing,
        ]
    )

    assert result.existing_count == 1
    assert result.added_count == 0
    assert result.skipped_existing == 1
    assert result.activity_count == 1
    assert result.sha256 == initial.sha256

    assert _sha256(output_path) == original_output_hash
    assert _sha256(
        exporter.manifest_path
    ) == original_manifest_hash
