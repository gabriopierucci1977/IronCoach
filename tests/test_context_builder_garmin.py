"""
Test integrazione Garmin in ContextBuilder.

Verifica:
- caricamento dello storico Garmin;
- fusione Garmin + Airtable;
- ordinamento cronologico;
- conversione durata e distanza;
- disattivazione tramite include_garmin=False;
- tolleranza ad archivio Garmin non disponibile;
- nessuna scrittura tramite il client;
- mantenimento degli storici recovery e performance.
"""

from __future__ import annotations

from typing import List

import pytest

from backend.context_builder import ContextBuilder
from backend.importers.garmin_activity_archive import (
    GarminActivityArchiveError,
)
from backend.models.activity import IronCoachActivity


class FakeClient:
    def __init__(
        self,
        training_history=None,
        recovery_history=None,
        performance_history=None,
    ):
        self._training_history = training_history or []
        self._recovery_history = recovery_history or []
        self._performance_history = performance_history or []
        self.calls: List[str] = []

    def _record(self, name):
        self.calls.append(name)

    def get_athlete_profile(self):
        self._record("get_athlete_profile")
        return {}

    def get_latest_recovery(self):
        self._record("get_latest_recovery")
        return {}

    def get_latest_training(self):
        self._record("get_latest_training")
        return {}

    def get_latest_nutrition(self):
        self._record("get_latest_nutrition")
        return {}

    def get_latest_decision(self):
        self._record("get_latest_decision")
        return {}

    def get_training_history(self):
        self._record("get_training_history")
        return self._training_history

    def get_recovery_history(self):
        self._record("get_recovery_history")
        return self._recovery_history

    def get_performance_history(self):
        self._record("get_performance_history")
        return self._performance_history


class FakeArchive:
    def __init__(
        self,
        activities=None,
        error=None,
    ):
        self.activities = activities or []
        self.error = error
        self.iteration_count = 0

    def iter_all(self):
        self.iteration_count += 1

        if self.error is not None:
            raise self.error

        return iter(self.activities)


def _activity(
    *,
    source_id: str,
    start_time: str,
    sport: str = "RUN",
    duration_seconds: float = 3600.0,
    distance_meters: float = 10000.0,
    training_load: float = 80.0,
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
        duration_seconds=duration_seconds,
        distance_meters=distance_meters,
        elevation_gain=None,
        elevation_loss=None,
        calories=None,
        avg_speed=None,
        max_speed=None,
        avg_hr=145,
        max_hr=170,
        avg_cadence=None,
        max_cadence=None,
        avg_power=250,
        normalized_power=265,
        training_load=training_load,
        training_effect=None,
        segments=[],
        metadata={
            "garmin_merge": {
                "merge_status": "MERGED",
            }
        },
    )


def test_context_loads_garmin_history() -> None:
    archive = FakeArchive(
        [
            _activity(
                source_id="1001",
                start_time="2025-01-01T08:00:00Z",
            ),
            _activity(
                source_id="1002",
                start_time="2025-01-02T08:00:00Z",
                sport="BIKE",
            ),
        ]
    )

    context = ContextBuilder(
        FakeClient(),
        garmin_archive=archive,
    ).build()

    assert context["history_sources"] == {
        "training_total": 2,
        "training_airtable": 0,
        "training_garmin": 2,
        "garmin_enabled": True,
    }

    assert len(
        context["garmin_training_history"]
    ) == 2

    assert [
        session["raw"]["source_id"]
        for session in context["training_history"]
    ] == [
        "1001",
        "1002",
    ]

    assert context["context_warnings"] == []


def test_garmin_conversion_preserves_core_metrics() -> None:
    archive = FakeArchive(
        [
            _activity(
                source_id="2001",
                start_time="2025-02-01T10:00:00Z",
                sport="RUN",
                duration_seconds=5400,
                distance_meters=21097.5,
                training_load=123.4,
            )
        ]
    )

    context = ContextBuilder(
        FakeClient(),
        garmin_archive=archive,
    ).build()

    session = context[
        "garmin_training_history"
    ][0]

    assert session["source"] == "garmin"
    assert session["source_id"] == "2001"
    assert session["activity_id"] == "garmin:2001"
    assert session["date"] == "2025-02-01T10:00:00Z"
    assert session["sport"] == "RUN"
    assert session["duration_minutes"] == 90.0
    assert session["distance_km"] == 21.1
    assert session["training_load"] == 123.4
    assert session["heart_rate"] == {
        "average": 145,
        "max": 170,
    }
    assert session["power"] == {
        "average": 250,
        "normalized": 265,
    }


def test_context_merges_garmin_and_airtable_in_date_order() -> None:
    client = FakeClient(
        training_history=[
            {
                "Record ID": "airtable-1",
                "Data allenamento": "2025-01-03T08:00:00Z",
                "Sport": "Corsa",
                "Durata minuti": 45,
                "Distanza km": 8,
            }
        ]
    )

    archive = FakeArchive(
        [
            _activity(
                source_id="1002",
                start_time="2025-01-02T08:00:00Z",
            ),
            _activity(
                source_id="1001",
                start_time="2025-01-01T08:00:00Z",
            ),
        ]
    )

    context = ContextBuilder(
        client,
        garmin_archive=archive,
    ).build()

    assert context["history_sources"] == {
        "training_total": 3,
        "training_airtable": 1,
        "training_garmin": 2,
        "garmin_enabled": True,
    }

    assert [
        session["date"]
        for session in context["training_history"]
    ] == [
        "2025-01-01T08:00:00Z",
        "2025-01-02T08:00:00Z",
        "2025-01-03T08:00:00Z",
    ]


def test_include_garmin_false_skips_archive() -> None:
    archive = FakeArchive(
        [
            _activity(
                source_id="1001",
                start_time="2025-01-01T08:00:00Z",
            )
        ]
    )

    context = ContextBuilder(
        FakeClient(),
        include_garmin=False,
        garmin_archive=archive,
    ).build()

    assert archive.iteration_count == 0
    assert context[
        "garmin_training_history"
    ] == []

    assert context["history_sources"] == {
        "training_total": 0,
        "training_airtable": 0,
        "training_garmin": 0,
        "garmin_enabled": False,
    }


def test_missing_garmin_archive_adds_warning_and_continues() -> None:
    archive = FakeArchive(
        error=GarminActivityArchiveError(
            "missing archive"
        )
    )

    context = ContextBuilder(
        FakeClient(
            training_history=[
                {
                    "Record ID": "airtable-1",
                    "Data allenamento": "2025-01-01",
                    "Sport": "Corsa",
                }
            ]
        ),
        garmin_archive=archive,
    ).build()

    assert context[
        "history_sources"
    ]["training_total"] == 1

    assert context[
        "history_sources"
    ]["training_airtable"] == 1

    assert context[
        "history_sources"
    ]["training_garmin"] == 0

    assert len(
        context["context_warnings"]
    ) == 1

    assert (
        "Archivio Garmin non disponibile"
        in context["context_warnings"][0]
    )


def test_context_builder_never_calls_write_methods() -> None:
    client = FakeClient()

    ContextBuilder(
        client,
        garmin_archive=FakeArchive(),
    ).build()

    assert client.calls == [
        "get_athlete_profile",
        "get_latest_recovery",
        "get_latest_training",
        "get_latest_nutrition",
        "get_latest_decision",
        "get_training_history",
        "get_recovery_history",
        "get_performance_history",
    ]


def test_recovery_and_performance_history_are_preserved() -> None:
    client = FakeClient(
        recovery_history=[
            {
                "Data": "2025-01-01",
                "Recovery Score": 70,
            }
        ],
        performance_history=[
            {
                "date": "2025-01-01",
                "metric": "vo2max",
                "value": 55,
            }
        ],
    )

    context = ContextBuilder(
        client,
        garmin_archive=FakeArchive(),
    ).build()

    assert len(
        context["recovery_history"]
    ) == 1

    assert len(
        context["performance_history"]
    ) == 1

    assert context["context_warnings"] == []


def test_airtable_training_error_is_non_fatal() -> None:
    class FailingClient(FakeClient):
        def get_training_history(self):
            self._record("get_training_history")
            raise RuntimeError(
                "airtable unavailable"
            )

    context = ContextBuilder(
        FailingClient(),
        garmin_archive=FakeArchive(
            [
                _activity(
                    source_id="1001",
                    start_time="2025-01-01T08:00:00Z",
                )
            ]
        ),
    ).build()

    assert context[
        "history_sources"
    ]["training_total"] == 1

    assert context[
        "history_sources"
    ]["training_garmin"] == 1

    assert (
        "Storico allenamenti Airtable non disponibile"
        in context["context_warnings"][0]
    )