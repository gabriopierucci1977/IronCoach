"""
Test DecisionEngine goal profile reasoning.

Verifica che il DecisionEngine utilizzi
gli obiettivi atleta nel reasoning senza
modificare la logica decisionale.
"""

from backend.engines.decision_engine import (
    DecisionEngine,
)


def _safe_assessments():
    return {
        "recovery": {
            "level": "LOW",
            "reasons": [],
        },
        "training": {
            "level": "LOW",
            "reasons": [],
        },
        "injury": {
            "level": "LOW",
            "reasons": [],
        },
        "nutrition": {
            "level": "LOW",
            "reasons": [],
        },
        "load": {
            "level": "LOW",
            "reasons": [],
        },
        "recovery_trend": {
            "trend": "STABLE",
            "reasons": [],
        },
        "adaptation": {
            "adaptation_level": "GOOD",
            "reasons": [],
        },
        "performance": {
            "trend": "STABLE",
            "reasons": [],
            "details": {},
        },
        "athlete_profile": {
            "athlete_type": (
                "Triatleta Age Group endurance"
            ),
        },
    }


def test_event_goal_is_added_to_reasoning():
    assessments = _safe_assessments()

    assessments["goal_profile"] = {
        "goal_type": "EVENTO",
        "primary_goal": (
            "Preparazione Ironman"
        ),
        "race_target": (
            "Ironman Italia 2026"
        ),
    }

    decision = DecisionEngine().decide(
        assessments
    )

    reasoning = decision["reasoning"]

    assert (
        "Obiettivo atleta: "
        "Preparazione Ironman"
        in reasoning
    )

    assert (
        "Gara obiettivo: "
        "Ironman Italia 2026"
        in reasoning
    )


def test_event_goal_personalizes_reason():
    assessments = _safe_assessments()

    assessments["goal_profile"] = {
        "goal_type": "EVENTO",
        "race_target": (
            "Ironman Italia 2026"
        ),
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        "La gestione considera la preparazione "
        "dell'obiettivo gara Ironman Italia 2026."
        in decision["reason"]
    )


def test_performance_goal_is_added_to_reasoning():
    assessments = _safe_assessments()

    assessments["goal_profile"] = {
        "goal_type": "PERFORMANCE",
        "primary_goal": (
            "Migliorare FTP"
        ),
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        "Obiettivo atleta: Migliorare FTP"
        in decision["reasoning"]
    )

    assert (
        "La strategia considera l'obiettivo "
        "di miglioramento prestativo."
        in decision["reason"]
    )


def test_unknown_goal_does_not_add_reasoning():
    assessments = _safe_assessments()

    assessments["goal_profile"] = {
        "goal_type": "NON DEFINITO",
        "primary_goal": "",
        "race_target": "",
    }

    decision = DecisionEngine().decide(
        assessments
    )

    reasoning = decision["reasoning"]

    assert not any(
        item.startswith(
            "Obiettivo atleta:"
        )
        for item in reasoning
    )

    assert not any(
        item.startswith(
            "Gara obiettivo:"
        )
        for item in reasoning
    )


def test_goal_profile_does_not_change_safe_decision():
    assessments = _safe_assessments()

    assessments["goal_profile"] = {
        "goal_type": "EVENTO",
        "primary_goal": (
            "Preparazione gara"
        ),
        "race_target": (
            "Triathlon 2026"
        ),
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["decision"] == "CONFERMA"
    assert decision["strategy"] == "KEEP_PLAN"
    assert decision["risk_level"] == "NORMAL"