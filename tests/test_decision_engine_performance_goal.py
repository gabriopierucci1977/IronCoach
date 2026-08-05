"""
Test PERFORMANCE goal influence on DecisionEngine strategy.
"""

from backend.engines.decision_engine import (
    DecisionEngine,
)


def test_performance_goal_with_good_status_keeps_plan():
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
        "performance": {
            "trend": "IMPROVING",
            "reasons": [],
            "details": {},
        },
        "adaptation": {
            "adaptation_level": "GOOD",
            "reasons": [],
        },
        "goal_profile": {
            "goal_type": "PERFORMANCE",
            "primary_goal": "Miglioramento FTP",
        },
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        decision["strategy"]
        == "KEEP_PLAN"
    )


def test_performance_goal_with_declining_trend_adapts():
    assessments = {
        "recovery": {
            "level": "LOW",
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
        "performance": {
            "trend": "DECLINING",
            "reasons": [],
            "details": {},
        },
        "adaptation": {
            "adaptation_level": "GOOD",
            "reasons": [],
        },
        "goal_profile": {
            "goal_type": "PERFORMANCE",
            "primary_goal": "Miglioramento FTP",
        },
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        decision["strategy"]
        in (
            "ADAPT",
            "RECOVERY",
        )
    )