"""
Test Load Analyzer con finestre temporali recenti.

Il carico deve rappresentare lo stato allenante attuale,
non la somma dell'intera carriera.

Contratto atteso:
- finestra acuta: ultimi 7 giorni inclusivi;
- finestra cronica: ultimi 28 giorni inclusivi;
- data di riferimento opzionale in history["analysis_date"];
- in assenza di analysis_date viene usata la data più recente valida;
- attività più vecchie di 28 giorni escluse;
- carichi mancanti ignorati;
- compatibilità con le chiavi storiche già restituite.
"""

from __future__ import annotations

from backend.analyzers.load_analyzer import LoadAnalyzer


def _session(
    *,
    date: str,
    load=None,
    sport: str = "RUN",
):
    session = {
        "date": date,
        "sport": sport,
    }

    if load is not None:
        session["training_load"] = load

    return session


def _history(
    sessions,
    analysis_date: str = "2025-01-28T12:00:00Z",
):
    return {
        "analysis_date": analysis_date,
        "training_history": sessions,
    }


def test_uses_only_last_28_days() -> None:
    result = LoadAnalyzer().analyze(
        _history(
            [
                _session(
                    date="2024-12-01T08:00:00Z",
                    load=5000,
                ),
                _session(
                    date="2025-01-10T08:00:00Z",
                    load=100,
                ),
                _session(
                    date="2025-01-28T08:00:00Z",
                    load=50,
                ),
            ]
        )
    )

    assert result["total_load"] == 150.0
    assert result["chronic_load_28d"] == 150.0
    assert result["sessions_28d"] == 2


def test_calculates_acute_load_for_last_7_days() -> None:
    result = LoadAnalyzer().analyze(
        _history(
            [
                _session(
                    date="2025-01-20T08:00:00Z",
                    load=80,
                ),
                _session(
                    date="2025-01-22T08:00:00Z",
                    load=70,
                ),
                _session(
                    date="2025-01-28T08:00:00Z",
                    load=50,
                ),
            ]
        )
    )

    assert result["acute_load_7d"] == 120.0
    assert result["sessions_7d"] == 2
    assert result["chronic_load_28d"] == 200.0


def test_boundary_days_are_inclusive() -> None:
    result = LoadAnalyzer().analyze(
        _history(
            [
                _session(
                    date="2025-01-21T12:00:00Z",
                    load=40,
                ),
                _session(
                    date="2024-12-31T12:00:00Z",
                    load=60,
                ),
            ]
        )
    )

    assert result["acute_load_7d"] == 40.0
    assert result["chronic_load_28d"] == 100.0


def test_missing_and_invalid_loads_are_ignored() -> None:
    result = LoadAnalyzer().analyze(
        _history(
            [
                _session(
                    date="2025-01-25T08:00:00Z",
                    load=None,
                ),
                _session(
                    date="2025-01-26T08:00:00Z",
                    load="",
                ),
                _session(
                    date="2025-01-27T08:00:00Z",
                    load="not-a-number",
                ),
                _session(
                    date="2025-01-28T08:00:00Z",
                    load=75,
                ),
            ]
        )
    )

    assert result["sessions"] == 4
    assert result["sessions_with_load"] == 1
    assert result["acute_load_7d"] == 75.0
    assert result["chronic_load_28d"] == 75.0


def test_recent_sport_distribution_excludes_old_sessions() -> None:
    result = LoadAnalyzer().analyze(
        _history(
            [
                _session(
                    date="2024-11-01T08:00:00Z",
                    load=1000,
                    sport="RUN",
                ),
                _session(
                    date="2025-01-25T08:00:00Z",
                    load=60,
                    sport="RUN",
                ),
                _session(
                    date="2025-01-27T08:00:00Z",
                    load=90,
                    sport="BIKE",
                ),
            ]
        )
    )

    assert result["sport_distribution"] == {
        "bike": 90.0,
        "run": 60.0,
    }


def test_without_valid_load_returns_unknown() -> None:
    result = LoadAnalyzer().analyze(
        _history(
            [
                _session(
                    date="2025-01-27T08:00:00Z",
                    load=None,
                )
            ]
        )
    )

    assert result["level"] == "UNKNOWN"
    assert result["sessions_with_load"] == 0
    assert result["total_load"] == 0.0
    assert result["reasons"] == [
        "Dati di carico recente insufficienti"
    ]


def test_without_analysis_date_uses_latest_session_date() -> None:
    result = LoadAnalyzer().analyze(
        {
            "training_history": [
                _session(
                    date="2025-01-01T08:00:00Z",
                    load=30,
                ),
                _session(
                    date="2025-02-01T08:00:00Z",
                    load=70,
                ),
            ]
        }
    )

    assert result["analysis_date"] == "2025-02-01T08:00:00Z"
    assert result["acute_load_7d"] == 70.0
    assert result["chronic_load_28d"] == 70.0


def test_preserves_legacy_output_keys() -> None:
    result = LoadAnalyzer().analyze(
        _history(
            [
                _session(
                    date="2025-01-28T08:00:00Z",
                    load=100,
                )
            ]
        )
    )

    for key in (
        "level",
        "total_load",
        "sessions",
        "sessions_with_load",
        "sport_distribution",
        "reasons",
    ):
        assert key in result


def test_level_uses_recent_load_not_career_total() -> None:
    result = LoadAnalyzer().analyze(
        _history(
            [
                _session(
                    date="2020-01-01T08:00:00Z",
                    load=10000,
                ),
                _session(
                    date="2025-01-28T08:00:00Z",
                    load=80,
                ),
            ]
        )
    )

    assert result["level"] == "LOW"
    assert result["total_load"] == 80.0



def test_complete_window_without_recent_activity_is_low() -> None:
    result = LoadAnalyzer().analyze(
        {
            "analysis_date": "2025-02-28T12:00:00Z",
            "training_window_complete": True,
            "training_history": [
                _session(
                    date="2025-01-01T08:00:00Z",
                    load=100,
                )
            ],
        }
    )

    assert result["level"] == "LOW"
    assert result["sessions_28d"] == 0
    assert result["sessions_with_load"] == 0
    assert result["total_load"] == 0.0
    assert result["reasons"] == [
        "Nessuna attività registrata negli ultimi 28 giorni"
    ]



def test_reliable_personal_baseline_prevents_false_high_load() -> None:
    sessions = [
        _session(
            date="2025-01-07T08:00:00Z",
            load=600,
        ),
        _session(
            date="2025-01-14T08:00:00Z",
            load=600,
        ),
        _session(
            date="2025-01-21T08:00:00Z",
            load=600,
        ),
        _session(
            date="2025-01-28T08:00:00Z",
            load=600,
        ),
    ]

    reliable = LoadAnalyzer().analyze(
        {
            "analysis_date": (
                "2025-01-28T12:00:00Z"
            ),
            "training_history": sessions,
            "load_tolerance": {
                "status": "STIMATA",
                "confidence": "HIGH",
                "baseline_weekly_load": 800.0,
            },
        }
    )

    assert reliable["absolute_level"] == "HIGH"
    assert reliable["level"] == "NORMAL"
    assert (
        reliable["classification_basis"]
        == "PERSONAL_BASELINE"
    )
    assert (
        reliable["personal_baseline_weekly_load"]
        == 800.0
    )
    assert reliable["acute_load_7d"] == 600.0
    assert reliable["reasons"] == [
        (
            "Carico assoluto elevato ma coerente "
            "con la baseline personale"
        )
    ]

    unreliable = LoadAnalyzer().analyze(
        {
            "analysis_date": (
                "2025-01-28T12:00:00Z"
            ),
            "training_history": sessions,
            "load_tolerance": {
                "status": "STIMATA",
                "confidence": "LOW",
                "baseline_weekly_load": 800.0,
            },
        }
    )

    assert unreliable["absolute_level"] == "HIGH"
    assert unreliable["level"] == "HIGH"
    assert (
        unreliable["classification_basis"]
        == "ABSOLUTE_THRESHOLDS"
    )
