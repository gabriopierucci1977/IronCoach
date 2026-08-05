"""
Test AthleteProfileEngine goal profile.

Verifica che il profilo intelligente
riconosca correttamente:
- obiettivi gara/evento;
- obiettivi performance;
- obiettivi benessere;
- fallback senza obiettivo;
- mantenimento gara target.
"""

from backend.intelligence.athlete_profile_engine import (
    AthleteProfileEngine,
)


def _analyze(athlete):
    return AthleteProfileEngine().analyze(
        {
            "athlete": athlete,
        }
    )


def test_goal_profile_recognizes_event_goal() -> None:
    profile = _analyze(
        {
            "Obiettivi principali": (
                "Preparazione Ironman "
                "con obiettivo gara"
            ),
            "Gare obiettivo": (
                "Ironman Italia 2026"
            ),
        }
    )

    assert (
        profile["goal_profile"]["goal_type"]
        == "EVENTO"
    )

    assert (
        profile["goal_profile"]["race_target"]
        == "Ironman Italia 2026"
    )


def test_goal_profile_recognizes_performance_goal() -> None:
    profile = _analyze(
        {
            "Obiettivi principali": (
                "Migliorare FTP e prestazione "
                "ciclistica"
            ),
        }
    )

    assert (
        profile["goal_profile"]["goal_type"]
        == "PERFORMANCE"
    )


def test_goal_profile_recognizes_wellness_goal() -> None:
    profile = _analyze(
        {
            "Obiettivi principali": (
                "Mantenere salute e benessere "
                "generale"
            ),
        }
    )

    assert (
        profile["goal_profile"]["goal_type"]
        == "BENESSERE"
    )


def test_goal_profile_fallback_when_goal_missing() -> None:
    profile = _analyze(
        {}
    )

    assert (
        profile["goal_profile"]["goal_type"]
        == "NON DEFINITO"
    )


def test_goal_profile_preserves_target_race_information() -> None:
    profile = _analyze(
        {
            "Gare obiettivo": (
                "Maratona di Roma 2027"
            ),
            "Obiettivi principali": (
                "Preparare la gara"
            ),
        }
    )

    assert (
        profile["goal_profile"]["race_target"]
        == "Maratona di Roma 2027"
    )