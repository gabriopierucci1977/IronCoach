"""
Test Garmin Activity Archive

Verifica:
- caricamento lazy dell'archivio persistente;
- conteggio e copia della lista completa;
- ricerca per activity_id e source_id;
- require_by_source_id;
- selezione delle attività più recenti;
- filtro per sport;
- filtro per intervallo temporale;
- statistiche aggregate;
- reload della cache;
- errori su file mancante e parametri non validi.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.importers.garmin_activity_archive import (
    GarminActivityArchive,
    GarminActivityArchiveError,
)
from backend.importers.garmin_activity_exporter import (
    GarminActivityExporter,
)
from backend.models.activity import IronCoachActivity
from backend.models.activity_segment import IronCoachActivitySegment


def _segment(
    sport: str = "SWIM",
) -> IronCoachActivitySegment:
    return IronCoachActivitySegment(
        sport=sport,
        activity_type=sport.lower(),
        start_time="2025-01-02T10:00:00Z",
        duration_seconds=600,
        distance_meters=500.0,
        elevation_gain=None,
        elevation_loss=None,
        avg_hr=130,
        max_hr=150,
        avg_speed=None,
        max_speed=None,
        avg_power=None,
        normalized_power=None,
        avg_cadence=None,
        max_cadence=None,
        training_load=None,
        training_effect=None,
        metadata={
            "test": True,
        },
    )


def _activity(
    *,
    source_id: str,
    start_time: str,
    sport: str,
    status: str = "MERGED",
    segments: list[IronCoachActivitySegment] | None = None,
) -> IronCoachActivity:
    return IronCoachActivity(
        activity_id=f"garmin:{source_id}",
        source="garmin",
        source_id=source_id,
        file_hash=f"hash-{source_id}",
        start_time=start_time,
        end_time=None,
        sport=sport,
        activity_type=sport.lower(),
        duration_seconds=3600,
        distance_meters=10000.0,
        elevation_gain=100.0,
        elevation_loss=90.0,
        calories=600,
        avg_speed=2.7,
        max_speed=4.5,
        avg_hr=145,
        max_hr=170,
        avg_cadence=82.0,
        max_cadence=90.0,
        avg_power=None,
        normalized_power=None,
        training_load=80.0,
        training_effect=3.5,
        segments=segments or [],
        metadata={
            "garmin_merge": {
                "merge_status": status,
                "raw_format": "FIT",
            }
        },
    )


@pytest.fixture
def archive_path(
    tmp_path: Path,
) -> Path:
    output_path = (
        tmp_path
        / "garmin_activities.jsonl.gz"
    )

    activities = [
        _activity(
            source_id="1001",
            start_time="2025-01-01T08:00:00Z",
            sport="RUN",
        ),
        _activity(
            source_id="1002",
            start_time="2025-01-02T08:00:00Z",
            sport="BIKE",
            segments=[
                _segment()
            ],
        ),
        _activity(
            source_id="1003",
            start_time="2025-01-03T08:00:00Z",
            sport="RUN",
            status="JSON_ONLY",
        ),
        _activity(
            source_id="1004",
            start_time="2025-01-04T08:00:00Z",
            sport="SWIM",
        ),
    ]

    GarminActivityExporter(
        output_path=str(
            output_path
        )
    ).export(
        activities
    )

    return output_path


def test_count_and_all(
    archive_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            archive_path
        )
    )

    assert archive.count() == 4

    first_copy = archive.all()
    second_copy = archive.all()

    assert len(first_copy) == 4
    assert first_copy == second_copy
    assert first_copy is not second_copy


def test_iter_all_is_chronological(
    archive_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            archive_path
        )
    )

    source_ids = [
        activity.source_id
        for activity in archive.iter_all()
    ]

    assert source_ids == [
        "1001",
        "1002",
        "1003",
        "1004",
    ]


def test_lookup_by_activity_and_source_id(
    archive_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            archive_path
        )
    )

    by_activity_id = archive.get_by_activity_id(
        "garmin:1002"
    )

    by_source_id = archive.get_by_source_id(
        "1002"
    )

    assert by_activity_id is not None
    assert by_source_id is not None
    assert by_activity_id == by_source_id
    assert by_source_id.sport == "BIKE"

    assert archive.get_by_activity_id("") is None
    assert archive.get_by_source_id("missing") is None


def test_require_by_source_id(
    archive_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            archive_path
        )
    )

    assert archive.require_by_source_id(
        "1001"
    ).sport == "RUN"

    with pytest.raises(
        GarminActivityArchiveError,
        match="Attività Garmin non trovata",
    ):
        archive.require_by_source_id(
            "9999"
        )


def test_latest_returns_descending_order(
    archive_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            archive_path
        )
    )

    latest = archive.latest(
        3
    )

    assert [
        activity.source_id
        for activity in latest
    ] == [
        "1004",
        "1003",
        "1002",
    ]

    assert archive.latest(
        0
    ) == []

    with pytest.raises(
        ValueError,
        match="limit",
    ):
        archive.latest(
            -1
        )


def test_latest_can_filter_sports(
    archive_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            archive_path
        )
    )

    latest_runs = archive.latest(
        limit=10,
        sports=[
            "run"
        ],
    )

    assert [
        activity.source_id
        for activity in latest_runs
    ] == [
        "1003",
        "1001",
    ]


def test_by_sport_is_case_insensitive(
    archive_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            archive_path
        )
    )

    runs = archive.by_sport(
        "run"
    )

    assert [
        activity.source_id
        for activity in runs
    ] == [
        "1001",
        "1003",
    ]

    assert archive.by_sport(
        ""
    ) == []


def test_between_uses_inclusive_boundaries(
    archive_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            archive_path
        )
    )

    selected = archive.between(
        start="2025-01-02T08:00:00Z",
        end="2025-01-03T08:00:00Z",
    )

    assert [
        activity.source_id
        for activity in selected
    ] == [
        "1002",
        "1003",
    ]


def test_between_can_filter_sports(
    archive_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            archive_path
        )
    )

    selected = archive.between(
        start="2025-01-01T00:00:00Z",
        end="2025-01-04T23:59:59Z",
        sports=[
            "RUN",
        ],
    )

    assert [
        activity.source_id
        for activity in selected
    ] == [
        "1001",
        "1003",
    ]


def test_between_rejects_invalid_range(
    archive_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            archive_path
        )
    )

    with pytest.raises(
        ValueError,
        match="start non può essere successivo",
    ):
        archive.between(
            start="2025-01-05T00:00:00Z",
            end="2025-01-01T00:00:00Z",
        )

    with pytest.raises(
        ValueError,
        match="ISO-8601",
    ):
        archive.between(
            start="not-a-date",
        )


def test_stats(
    archive_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            archive_path
        )
    )

    stats = archive.stats()

    assert stats.activity_count == 4
    assert stats.segment_count == 1
    assert stats.first_start_time == (
        "2025-01-01T08:00:00Z"
    )
    assert stats.last_start_time == (
        "2025-01-04T08:00:00Z"
    )

    assert stats.sport_counts == {
        "BIKE": 1,
        "RUN": 2,
        "SWIM": 1,
    }

    assert stats.merge_status_counts == {
        "JSON_ONLY": 1,
        "MERGED": 3,
    }


def test_reload_clears_and_rebuilds_cache(
    archive_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            archive_path
        )
    )

    first_activity = archive.get_by_source_id(
        "1001"
    )

    assert first_activity is not None

    archive.reload()

    second_activity = archive.get_by_source_id(
        "1001"
    )

    assert second_activity is not None
    assert second_activity == first_activity
    assert second_activity is not first_activity


def test_missing_archive_raises_domain_error(
    tmp_path: Path,
) -> None:
    archive = GarminActivityArchive(
        archive_path=str(
            tmp_path
            / "missing.jsonl.gz"
        )
    )

    with pytest.raises(
        GarminActivityArchiveError,
        match="Impossibile caricare",
    ):
        archive.count()