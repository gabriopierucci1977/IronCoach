"""
Test integrazione Decision Memory Learning con DecisionEngine.

La memoria storica può arricchire l'intelligence della
decisione, ma non deve sostituire la regola deterministica
che ha prodotto la decisione.
"""

from backend.engines.decision_engine import (
    DecisionEngine,
)


def test_decision_includes_learning_evidence_for_selected_rule():
    rule_id = (
        "PERFORMANCE_DECLINING_LOAD_HIGH"
    )

    historical_evidence = {
        "positive_count": 2,
        "neutral_count": 1,
        "negative_count": 0,
        "insufficient_data_count": 1,
        "evaluable_count": 3,
        "positive_rate": 2 / 3,
        "sufficient_evidence": True,
    }

    assessments = {
        "recovery": {
            "level": "LOW",
        },
        "training": {
            "level": "LOW",
        },
        "injury": {
            "level": "LOW",
        },
        "nutrition": {
            "level": "LOW",
        },
        "load": {
            "level": "HIGH",
        },
        "recovery_trend": {
            "trend": "STABLE",
        },
        "adaptation": {
            "adaptation_level": "NORMAL",
        },
        "performance": {
            "trend": "DECLINING",
        },
        "data_freshness": {
            "level": "LOW",
        },
        "decision_memory": {
            rule_id: historical_evidence,
        },
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["decision"] == "ADATTA"
    assert decision["rule_id"] == rule_id

    assert (
        decision["intelligence"]
        ["decision_memory"]
        ["rule_id"]
        == rule_id
    )

    assert (
        decision["intelligence"]
        ["decision_memory"]
        ["evidence"]
        == historical_evidence
    )
