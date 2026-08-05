"""
Test goal profile influence on decision strategy.
"""

from backend.engines.decision_engine import (
    DecisionEngine,
)


def test_wellness_goal_with_fatigue_prefers_caution():
    assessments = {
        "recovery": {
            "level": "HIGH",
            "reasons": [],
        },
        "training": {
            "level": "HIGH",
            "reasons": [],
        },
        "injury": {
            "level": "LOW",
            "reasons": [],
        },
        "load": {
            "level": "HIGH",
            "reasons": [],
        },
        "goal_profile": {
            "goal_type": "BENESSERE",
            "primary_goal": "Continuità salute",
        },
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["strategy"] in (
        "REDUCE_LOAD",
        "RECOVERY",
    )


def test_event_goal_with_safe_status_can_keep_plan():
    assessments = {
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
        "load": {
            "level": "LOW",
            "reasons": [],
        },
        "goal_profile": {
            "goal_type": "EVENTO",
            "primary_goal": "Preparazione gara",
        },
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["strategy"] == "KEEP_PLAN"