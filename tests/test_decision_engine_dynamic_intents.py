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
            "risk_codes": [],
            "risk_factors": [],
            "positive_factors": [],
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


def test_adaptation_limited_prioritizes_physical_limitation():
    assessments = _safe_assessments()
    assessments["adaptation"] = {
        "adaptation_level": "LIMITED",
        "risk_codes": [
            "PHYSICAL_LIMITATION",
            "HIGH_LOAD",
        ],
        "risk_factors": [],
        "positive_factors": [],
        "reasons": [],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "ADAPTATION_LIMITED"
    assert decision["primary_intent"] == "PROTECT_INJURY"
    assert decision["supporting_intents"] == [
        "REDUCE_LOAD",
    ]


def test_adaptation_limited_prioritizes_recovery_over_load():
    assessments = _safe_assessments()
    assessments["adaptation"] = {
        "adaptation_level": "LIMITED",
        "risk_codes": [
            "HIGH_ACUTE_CHRONIC_RATIO",
            "POOR_RECOVERY",
        ],
        "risk_factors": [],
        "positive_factors": [],
        "reasons": [],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "ADAPTATION_LIMITED"
    assert decision["primary_intent"] == "RESTORE_RECOVERY"
    assert decision["supporting_intents"] == [
        "REDUCE_LOAD",
    ]


def test_adaptation_moderate_high_load_exposes_reduce_load():
    assessments = _safe_assessments()
    assessments["adaptation"] = {
        "adaptation_level": "MODERATE",
        "risk_codes": [
            "HIGH_LOAD",
        ],
        "risk_factors": [],
        "positive_factors": [],
        "reasons": [],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "ADAPTATION_MODERATE"
    assert decision["primary_intent"] == "REDUCE_LOAD"
    assert decision["supporting_intents"] == []


def test_adaptation_moderate_declining_performance_exposes_protection():
    assessments = _safe_assessments()
    assessments["adaptation"] = {
        "adaptation_level": "MODERATE",
        "risk_codes": [
            "PERFORMANCE_DECLINING",
        ],
        "risk_factors": [],
        "positive_factors": [],
        "reasons": [],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "ADAPTATION_MODERATE"
    assert decision["primary_intent"] == "PROTECT_PERFORMANCE"
    assert decision["supporting_intents"] == []


def test_multiple_moderate_injury_and_training_prioritizes_injury():
    assessments = _safe_assessments()
    assessments["injury"]["level"] = "MODERATE"
    assessments["training"]["level"] = "MODERATE"

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "MULTIPLE_MODERATE_FACTORS"
    assert decision["primary_intent"] == "PROTECT_INJURY"
    assert decision["supporting_intents"] == [
        "REDUCE_LOAD",
    ]


def test_multiple_moderate_nutrition_and_training_prioritizes_fueling():
    assessments = _safe_assessments()
    assessments["nutrition"]["level"] = "MODERATE"
    assessments["training"]["level"] = "MODERATE"

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "MULTIPLE_MODERATE_FACTORS"
    assert decision["primary_intent"] == "RESTORE_FUELING"
    assert decision["supporting_intents"] == [
        "REDUCE_LOAD",
    ]


def test_multiple_moderate_factors_follow_intent_priority_order():
    assessments = _safe_assessments()
    assessments["injury"]["level"] = "MODERATE"
    assessments["nutrition"]["level"] = "MODERATE"
    assessments["training"]["level"] = "MODERATE"

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "MULTIPLE_MODERATE_FACTORS"
    assert decision["primary_intent"] == "PROTECT_INJURY"
    assert decision["supporting_intents"] == [
        "RESTORE_FUELING",
        "REDUCE_LOAD",
    ]