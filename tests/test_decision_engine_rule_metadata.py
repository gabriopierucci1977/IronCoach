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


def test_injury_critical_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["injury"]["level"] = "CRITICAL"

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "INJURY_CRITICAL"


def test_recovery_critical_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["recovery"]["level"] = "CRITICAL"

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "RECOVERY_CRITICAL"


def test_recovery_moderate_high_load_declining_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["recovery"]["level"] = "MODERATE"
    assessments["load"]["level"] = "HIGH"
    assessments["recovery_trend"]["trend"] = "DECLINING"

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        decision["rule_id"]
        == "RECOVERY_MODERATE_HIGH_LOAD_DECLINING"
    )


def test_recovery_moderate_injury_high_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["recovery"]["level"] = "MODERATE"
    assessments["injury"]["level"] = "HIGH"

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        decision["rule_id"]
        == "RECOVERY_MODERATE_INJURY_HIGH"
    )


def test_recovery_moderate_training_high_nutrition_high_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["recovery"]["level"] = "MODERATE"
    assessments["training"]["level"] = "HIGH"
    assessments["nutrition"]["level"] = "HIGH"

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        decision["rule_id"]
        == "RECOVERY_MODERATE_TRAINING_HIGH_NUTRITION_HIGH"
    )


def test_recovery_favorable_training_high_load_high_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["training"]["level"] = "HIGH"
    assessments["load"]["level"] = "HIGH"

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        decision["rule_id"]
        == "RECOVERY_FAVORABLE_TRAINING_HIGH_LOAD_HIGH"
    )


def test_recovery_favorable_nutrition_high_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["nutrition"]["level"] = "HIGH"

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        decision["rule_id"]
        == "RECOVERY_FAVORABLE_NUTRITION_HIGH"
    )


def test_adaptation_limited_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["adaptation"]["adaptation_level"] = "LIMITED"

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "ADAPTATION_LIMITED"


def test_adaptation_moderate_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["adaptation"]["adaptation_level"] = "MODERATE"

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "ADAPTATION_MODERATE"


def test_performance_declining_load_high_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["performance"]["trend"] = "DECLINING"
    assessments["load"]["level"] = "HIGH"

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        decision["rule_id"]
        == "PERFORMANCE_DECLINING_LOAD_HIGH"
    )


def test_recovery_unknown_with_stress_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["recovery"]["level"] = "UNKNOWN"
    assessments["training"]["level"] = "HIGH"

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        decision["rule_id"]
        == "RECOVERY_UNKNOWN_WITH_STRESS"
    )


def test_recovery_unknown_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["recovery"]["level"] = "UNKNOWN"

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "RECOVERY_UNKNOWN"


def test_multiple_moderate_factors_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["training"]["level"] = "MODERATE"
    assessments["injury"]["level"] = "MODERATE"

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        decision["rule_id"]
        == "MULTIPLE_MODERATE_FACTORS"
    )


def test_wellbeing_high_stress_exposes_rule_id():
    assessments = _safe_assessments()
    assessments["load"]["level"] = "HIGH"
    assessments["goal_profile"] = {
        "goal_type": "BENESSERE",
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "WELLBEING_HIGH_STRESS"


def test_default_confirm_exposes_rule_id():
    decision = DecisionEngine().decide(
        _safe_assessments()
    )

    assert decision["decision"] == "CONFERMA"
    assert decision["rule_id"] == "DEFAULT_CONFIRM"