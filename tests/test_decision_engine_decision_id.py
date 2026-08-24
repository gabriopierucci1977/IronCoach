from uuid import UUID

from backend.engines.decision_engine import DecisionEngine


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
            "athlete_type": "Triatleta Age Group endurance",
        },
        "goal_profile": {},
    }


def test_decision_engine_generates_uuid4_decision_id():
    decision = DecisionEngine().decide(
        _safe_assessments()
    )

    parsed = UUID(
        decision["decision_id"],
        version=4,
    )

    assert str(parsed) == decision["decision_id"]


def test_decision_engine_generates_distinct_decision_ids():
    engine = DecisionEngine()

    first = engine.decide(
        _safe_assessments()
    )
    second = engine.decide(
        _safe_assessments()
    )

    assert first["decision_id"] != second["decision_id"]