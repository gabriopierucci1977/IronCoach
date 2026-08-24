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


def test_injury_critical_exposes_protect_injury_intent():
    assessments = _safe_assessments()
    assessments["injury"]["level"] = "CRITICAL"

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "INJURY_CRITICAL"
    assert decision["primary_intent"] == "PROTECT_INJURY"
    assert decision["supporting_intents"] == []


def test_recovery_critical_exposes_restore_recovery_intent():
    assessments = _safe_assessments()
    assessments["recovery"]["level"] = "CRITICAL"

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "RECOVERY_CRITICAL"
    assert decision["primary_intent"] == "RESTORE_RECOVERY"
    assert decision["supporting_intents"] == []


def test_recovery_moderate_high_load_declining_exposes_intents():
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
    assert decision["primary_intent"] == "RESTORE_RECOVERY"
    assert decision["supporting_intents"] == [
        "REDUCE_LOAD",
    ]


def test_recovery_moderate_injury_high_exposes_intents():
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
    assert decision["primary_intent"] == "PROTECT_INJURY"
    assert decision["supporting_intents"] == [
        "RESTORE_RECOVERY",
    ]


def test_recovery_moderate_training_high_nutrition_high_exposes_intents():
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
    assert decision["primary_intent"] == "RESTORE_FUELING"
    assert decision["supporting_intents"] == [
        "RESTORE_RECOVERY",
        "REDUCE_LOAD",
    ]


def test_recovery_favorable_training_high_load_high_exposes_intents():
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
    assert decision["primary_intent"] == "REDUCE_LOAD"
    assert decision["supporting_intents"] == [
        "PROTECT_PERFORMANCE",
    ]


def test_recovery_favorable_nutrition_high_exposes_restore_fueling_intent():
    assessments = _safe_assessments()
    assessments["nutrition"]["level"] = "HIGH"

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        decision["rule_id"]
        == "RECOVERY_FAVORABLE_NUTRITION_HIGH"
    )
    assert decision["primary_intent"] == "RESTORE_FUELING"
    assert decision["supporting_intents"] == []


def test_performance_declining_load_high_exposes_intents():
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
    assert decision["primary_intent"] == "PROTECT_PERFORMANCE"
    assert decision["supporting_intents"] == [
        "REDUCE_LOAD",
    ]


def test_recovery_unknown_with_training_stress_exposes_intents():
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
    assert decision["primary_intent"] == "MANAGE_UNCERTAINTY"
    assert decision["supporting_intents"] == [
        "REDUCE_LOAD",
    ]


def test_recovery_unknown_without_stress_exposes_manage_uncertainty_intent():
    assessments = _safe_assessments()
    assessments["recovery"]["level"] = "UNKNOWN"

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "RECOVERY_UNKNOWN"
    assert decision["primary_intent"] == "MANAGE_UNCERTAINTY"
    assert decision["supporting_intents"] == []


def test_wellbeing_high_stress_exposes_reduce_load_intent():
    assessments = _safe_assessments()
    assessments["load"]["level"] = "HIGH"
    assessments["goal_profile"] = {
        "goal_type": "BENESSERE",
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["rule_id"] == "WELLBEING_HIGH_STRESS"
    assert decision["primary_intent"] == "REDUCE_LOAD"
    assert decision["supporting_intents"] == []


def test_default_confirm_exposes_maintain_plan_intent():
    decision = DecisionEngine().decide(
        _safe_assessments()
    )

    assert decision["rule_id"] == "DEFAULT_CONFIRM"
    assert decision["primary_intent"] == "MAINTAIN_PLAN"
    assert decision["supporting_intents"] == []