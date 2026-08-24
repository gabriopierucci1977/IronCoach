"""Regression tests for historical load-tolerance intelligence."""

from datetime import datetime, timedelta, timezone

from backend.coach_engine import CoachEngine
from backend.context_builder import ContextBuilder
from backend.intelligence.athlete_profile_engine import AthleteProfileEngine


def _steady_history(weeks=6, load_per_session=150.0):
    latest = datetime(2026, 8, 23, tzinfo=timezone.utc)
    sessions = []

    for week in range(weeks):
        for offset in (0, 3):
            date = latest - timedelta(
                days=(week * 7) + offset
            )
            sessions.append(
                {
                    "date": date.isoformat(),
                    "training_load": load_per_session,
                    "source": "garmin",
                }
            )

    return sessions


def test_load_tolerance_uses_historical_weekly_baseline() -> None:
    profile = AthleteProfileEngine().analyze(
        {
            "athlete": {},
            "training_history": _steady_history(),
        }
    )

    tolerance = profile["load_tolerance"]

    assert tolerance["status"] == "STIMATA"
    assert tolerance["level"] == "NORMAL"
    assert tolerance["confidence"] == "HIGH"
    assert tolerance["sessions_analyzed"] == 12
    assert tolerance["weeks_analyzed"] == 6
    assert tolerance["baseline_weekly_load"] == 300.0
    assert tolerance["mean_weekly_load"] == 300.0
    assert tolerance["peak_weekly_load"] == 300.0
    assert tolerance["latest_7d_load"] == 300.0
    assert "garmin" in tolerance["source"]


def test_load_tolerance_does_not_claim_estimate_with_sparse_history() -> None:
    sessions = _steady_history(
        weeks=2,
        load_per_session=100.0,
    )[:3]

    tolerance = AthleteProfileEngine().analyze(
        {
            "athlete": {},
            "training_history": sessions,
        }
    )["load_tolerance"]

    assert tolerance["status"] == "DATI INSUFFICIENTI"
    assert tolerance["level"] == "UNKNOWN"
    assert tolerance["confidence"] == "LOW"


class _ContextClient:
    def get_athlete_profile(self):
        return {
            "Nome atleta": "Atleta test",
            "Sport principale": "Triathlon",
        }

    def get_latest_recovery(self):
        return {}

    def get_latest_training(self):
        return {}

    def get_latest_nutrition(self):
        return {}

    def get_latest_decision(self):
        return {}

    def get_training_history(self):
        sessions = []
        for session in _steady_history():
            sessions.append(
                {
                    "Data allenamento": session["date"],
                    "Sport": "Bici",
                    "Carico interno": session["training_load"],
                }
            )
        return sessions

    def get_recovery_history(self):
        return []

    def get_performance_history(self):
        return []


def test_context_builder_derives_load_tolerance_after_loading_history() -> None:
    context = ContextBuilder(
        _ContextClient(),
        include_garmin=False,
    ).build()

    tolerance = context[
        "athlete_profile_intelligence"
    ]["load_tolerance"]

    assert tolerance["status"] == "STIMATA"
    assert tolerance["level"] == "NORMAL"
    assert tolerance["baseline_weekly_load"] == 300.0
    assert "airtable" in tolerance["source"]


def test_coach_engine_preserves_enriched_load_tolerance_in_decision() -> None:
    expected = {
        "status": "STIMATA",
        "level": "NORMAL",
        "confidence": "HIGH",
        "baseline_weekly_load": 300.0,
    }

    decision = CoachEngine().evaluate(
        {
            "athlete_profile": {},
            "athlete_profile_intelligence": {
                "load_tolerance": expected,
                "goal_profile": {
                    "goal_type": "NON DEFINITO",
                },
            },
            "recovery": {},
            "training": {},
            "nutrition": {},
            "training_history": [],
            "recovery_history": [],
            "performance_history": [],
            "data_freshness": {
                "level": "HIGH",
                "reasons": [],
            },
        }
    )

    assert (
        decision["intelligence"]
        ["athlete_profile"]
        ["load_tolerance"]
        == expected
    )
