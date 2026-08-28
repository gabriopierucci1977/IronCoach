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

from datetime import datetime, timezone
from typing import List

import pytest

import backend.context_builder as context_builder_module
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
        latest_recovery=None,
        latest_training=None,
    ):
        self._training_history = training_history or []
        self._recovery_history = recovery_history or []
        self._performance_history = performance_history or []
        self._latest_recovery = latest_recovery or {}
        self._latest_training = latest_training or {}
        self.calls: List[str] = []

    def _record(self, name):
        self.calls.append(name)

    def get_athlete_profile(self):
        self._record("get_athlete_profile")
        return {}

    def get_latest_recovery(self):
        self._record("get_latest_recovery")
        return self._latest_recovery

    def get_latest_training(self):
        self._record("get_latest_training")
        return self._latest_training

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

    assert len(
        context["context_warnings"]
    ) == 1

    assert context[
        "context_warnings"
    ][0].startswith(
        "Allenamento: dato obsoleto"
    )


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
    ) == 2

    assert any(
        warning.startswith(
            "Archivio Garmin non disponibile:"
        )
        for warning in context[
            "context_warnings"
        ]
    )

    assert any(
        warning.startswith(
            "Allenamento: dato obsoleto"
        )
        for warning in context[
            "context_warnings"
        ]
    )

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

def test_cross_source_duplicates_are_merged() -> None:
    garmin_activity = _activity(
        source_id="9001",
        start_time="2026-07-23T16:07:34Z",
        sport="RUN",
        duration_seconds=3478.98,
        distance_meters=10500,
        training_load=226.17,
    )

    client = FakeClient(
        training_history=[
            {
                "Data allenamento": "2026-07-24",
                "Sport": "Corsa",
                "Durata minuti": 57.98,
                "Distanza km": 10.5,
                "Carico interno": 521.82,
                "RPE percepito": 9,
                "Note personali": "Seduta qualità",
            }
        ]
    )

    context = ContextBuilder(
        client,
        garmin_archive=FakeArchive(
            [
                garmin_activity
            ]
        ),
    ).build()

    assert context["history_sources"] == {
        "training_total": 1,
        "training_airtable": 1,
        "training_garmin": 1,
        "garmin_enabled": True,
    }

    assert len(
        context["training_history"]
    ) == 1

    session = context[
        "training_history"
    ][0]

    # TrainingHistory conserva i campi normalizzati necessari
    # all'analisi, ma non espone il campo tecnico "source".
    # La priorità Airtable è verificata dai valori specifici della
    # sessione Airtable, diversi da quelli Garmin.
    assert session["date"] == "2026-07-24"
    assert session["sport"] == "run"
    assert session["duration_minutes"] == 57.98
    assert session["distance_km"] == 10.5
    assert session["training_load"] == 521.82


def test_similar_sessions_are_not_merged_without_metric_match() -> None:
    garmin_activity = _activity(
        source_id="9002",
        start_time="2026-07-24T08:00:00Z",
        sport="RUN",
        duration_seconds=3600,
        distance_meters=10000,
        training_load=200,
    )

    client = FakeClient(
        training_history=[
            {
                "Data allenamento": "2026-07-24",
                "Sport": "Corsa",
                "Durata minuti": 50,
                "Distanza km": 8,
                "Carico interno": 400,
            }
        ]
    )

    context = ContextBuilder(
        client,
        garmin_archive=FakeArchive(
            [
                garmin_activity
            ]
        ),
    ).build()

    assert context["history_sources"][
        "training_total"
    ] == 2

    assert len(
        context["training_history"]
    ) == 2


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(
            2026,
            8,
            7,
            12,
            0,
            0,
            tzinfo=timezone.utc,
        )

        if tz is None:
            return value.replace(
                tzinfo=None
            )

        return value.astimezone(tz)


@pytest.fixture
def fixed_context_time(monkeypatch):
    monkeypatch.setattr(
        context_builder_module,
        "datetime",
        _FixedDateTime,
    )


def test_data_freshness_is_low_when_dates_are_current(
    fixed_context_time,
) -> None:
    context = ContextBuilder(
        FakeClient(
            latest_recovery={
                "Data": "2026-08-06",
            },
            latest_training={
                "Data allenamento": "2026-08-03",
                "Sport": "Corsa",
            },
        ),
        garmin_archive=FakeArchive(),
    ).build()

    freshness = context["data_freshness"]

    assert freshness["level"] == "LOW"
    assert freshness["reasons"] == []
    assert freshness["recovery"] == {
        "status": "CURRENT",
        "level": "LOW",
        "date": "2026-08-06",
        "age_days": 1,
        "max_age_days": 3,
        "reason": None,
    }
    assert freshness["training"] == {
        "status": "CURRENT",
        "level": "LOW",
        "date": "2026-08-03",
        "age_days": 4,
        "max_age_days": 7,
        "reason": None,
    }
    assert context["context_warnings"] == []


def test_stale_training_sets_moderate_data_freshness(
    fixed_context_time,
) -> None:
    context = ContextBuilder(
        FakeClient(
            latest_recovery={
                "Data": "2026-08-06",
            },
            latest_training={
                "Data allenamento": "2026-07-30",
                "Sport": "Corsa",
            },
        ),
        garmin_archive=FakeArchive(),
    ).build()

    freshness = context["data_freshness"]

    assert freshness["level"] == "MODERATE"
    assert freshness["training"]["status"] == "STALE"
    assert freshness["training"]["age_days"] == 8
    assert freshness["recovery"]["status"] == "CURRENT"
    assert freshness["reasons"] == [
        (
            "Allenamento: dato obsoleto di 8 giorni "
            "(data 2026-07-30, soglia 7 giorni)"
        )
    ]
    assert context["context_warnings"] == freshness["reasons"]


def test_garmin_history_sets_training_freshness_without_becoming_current_training(
    fixed_context_time,
) -> None:
    context = ContextBuilder(
        FakeClient(
            latest_recovery={
                "Data": "2026-08-06",
            },
            latest_training={},
        ),
        garmin_archive=FakeArchive(
            [
                _activity(
                    source_id="stale-garmin",
                    start_time="2026-07-30T08:00:00Z",
                )
            ]
        ),
    ).build()

    freshness = context[
        "data_freshness"
    ]

    assert context[
        "training"
    ].get(
        "date"
    ) is None

    assert freshness[
        "training"
    ][
        "status"
    ] == "STALE"

    assert freshness[
        "training"
    ][
        "date"
    ] == "2026-07-30"

    assert freshness[
        "training"
    ][
        "age_days"
    ] == 8


def test_stale_recovery_sets_high_data_freshness(
    fixed_context_time,
) -> None:
    context = ContextBuilder(
        FakeClient(
            latest_recovery={
                "Data": "2026-08-03",
            },
            latest_training={
                "Data allenamento": "2026-08-03",
                "Sport": "Corsa",
            },
        ),
        garmin_archive=FakeArchive(),
    ).build()

    freshness = context["data_freshness"]

    assert freshness["level"] == "HIGH"
    assert freshness["recovery"]["status"] == "STALE"
    assert freshness["recovery"]["age_days"] == 4
    assert freshness["training"]["status"] == "CURRENT"
    assert freshness["reasons"] == [
        (
            "Recovery: dato obsoleto di 4 giorni "
            "(data 2026-08-03, soglia 3 giorni)"
        )
    ]


def test_future_dates_are_structured_and_reported(
    fixed_context_time,
) -> None:
    context = ContextBuilder(
        FakeClient(
            latest_recovery={
                "Data": "2026-08-08",
            },
            latest_training={
                "Data allenamento": "2026-08-09",
                "Sport": "Corsa",
            },
        ),
        garmin_archive=FakeArchive(),
    ).build()

    freshness = context["data_freshness"]

    assert freshness["level"] == "HIGH"
    assert freshness["recovery"]["status"] == "FUTURE"
    assert freshness["recovery"]["age_days"] == -1
    assert freshness["training"]["status"] == "FUTURE"
    assert freshness["training"]["age_days"] == -2
    assert freshness["reasons"] == [
        "Recovery: data futura (2026-08-08)",
        "Allenamento: data futura (2026-08-09)",
    ]
    assert context["context_warnings"] == freshness["reasons"]


def test_missing_dates_keep_unknown_details_without_warning(
    fixed_context_time,
) -> None:
    context = ContextBuilder(
        FakeClient(),
        garmin_archive=FakeArchive(),
    ).build()

    freshness = context["data_freshness"]

    assert freshness["level"] == "LOW"
    assert freshness["reasons"] == []
    assert freshness["recovery"]["status"] == "UNKNOWN"
    assert freshness["training"]["status"] == "UNKNOWN"
    assert context["context_warnings"] == []


def test_freshness_threshold_days_are_still_current(
    fixed_context_time,
) -> None:
    context = ContextBuilder(
        FakeClient(
            latest_recovery={
                "Data": "2026-08-04",
            },
            latest_training={
                "Data allenamento": "2026-07-31",
                "Sport": "Corsa",
            },
        ),
        garmin_archive=FakeArchive(),
    ).build()

    freshness = context["data_freshness"]

    assert freshness["level"] == "LOW"
    assert freshness["recovery"]["status"] == "CURRENT"
    assert freshness["recovery"]["age_days"] == 3
    assert freshness["training"]["status"] == "CURRENT"
    assert freshness["training"]["age_days"] == 7
    assert freshness["reasons"] == []
    assert context["context_warnings"] == []


def test_freshness_one_day_over_threshold_is_stale(
    fixed_context_time,
) -> None:
    context = ContextBuilder(
        FakeClient(
            latest_recovery={
                "Data": "2026-08-03",
            },
            latest_training={
                "Data allenamento": "2026-07-30",
                "Sport": "Corsa",
            },
        ),
        garmin_archive=FakeArchive(),
    ).build()

    freshness = context["data_freshness"]

    assert freshness["level"] == "HIGH"
    assert freshness["recovery"]["status"] == "STALE"
    assert freshness["recovery"]["age_days"] == 4
    assert freshness["training"]["status"] == "STALE"
    assert freshness["training"]["age_days"] == 8
    assert freshness["reasons"] == [
        (
            "Recovery: dato obsoleto di 4 giorni "
            "(data 2026-08-03, soglia 3 giorni)"
        ),
        (
            "Allenamento: dato obsoleto di 8 giorni "
            "(data 2026-07-30, soglia 7 giorni)"
        ),
    ]



def test_current_garmin_source_is_distinct_from_last_activity(
    tmp_path,
    fixed_context_time,
) -> None:
    state_path = (
        tmp_path
        / "garmin_live_sync_state.json"
    )

    state_path.write_text(
        (
            '{"source_checked_at": '
            '"2026-08-07T11:00:00Z", '
            '"last_activity_at": '
            '"2025-01-02T08:00:00Z"}'
        ),
        encoding="utf-8",
    )

    archive = FakeArchive(
        [
            _activity(
                source_id="1001",
                start_time=(
                    "2025-01-02T08:00:00Z"
                ),
            )
        ]
    )

    context = ContextBuilder(
        FakeClient(),
        garmin_archive=archive,
        garmin_source_state_path=str(
            state_path
        ),
    ).build()

    training_freshness = (
        context["data_freshness"][
            "training"
        ]
    )

    assert training_freshness[
        "status"
    ] == "CURRENT"

    assert training_freshness[
        "basis"
    ] == "source_checked_at"

    assert training_freshness[
        "source_checked_at"
    ] == "2026-08-07T11:00:00Z"

    assert training_freshness[
        "last_activity_at"
    ] == "2025-01-02T08:00:00Z"

    assert training_freshness[
        "window_complete"
    ] is True

    assert context["history_sources"][
        "garmin_source_status"
    ] == "CURRENT"

    assert not any(
        warning.startswith(
            "Allenamento: dato obsoleto"
        )
        for warning in context[
            "context_warnings"
        ]
    )
