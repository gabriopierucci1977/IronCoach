"""
Test PERFORMANCE goal reasoning in DecisionEngine.
"""

from backend.engines.decision_engine import (
    DecisionEngine,
)


def _base_assessments():
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
        "adaptation": {
            "adaptation_level": "GOOD",
            "reasons": [],
        },
        "performance": {
            "trend": "IMPROVING",
            "reasons": [],
            "details": {},
        },
        "athlete_profile": {
            "athlete_type": (
                "Triatleta Age Group endurance"
            ),
        },
    }


def test_performance_goal_is_added_to_reasoning():
    assessments = _base_assessments()

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


def test_performance_goal_personalizes_reason():
    assessments = _base_assessments()

    assessments["goal_profile"] = {
        "goal_type": "PERFORMANCE",
        "primary_goal": (
            "Aumentare prestazione ciclistica"
        ),
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        "La strategia considera l'obiettivo "
        "di miglioramento prestativo."
        in decision["reason"]
    )


def test_performance_goal_does_not_override_risk_logic():
    assessments = _base_assessments()

    assessments["goal_profile"] = {
        "goal_type": "PERFORMANCE",
        "primary_goal": (
            "Massima performance"
        ),
    }

    assessments["injury"] = {
        "level": "CRITICAL",
        "reasons": [],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        decision["strategy"]
        == "RECOVERY"
    )