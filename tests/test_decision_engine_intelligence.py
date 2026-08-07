"""
Test DecisionEngine con intelligence di adattamento e performance.

Verifica che le informazioni già prodotte dagli analyzer incidano
realmente sulla decisione finale e sul reasoning.
"""

from backend.config import RuntimeConfig
from backend.engines.decision_engine import DecisionEngine


def _assessment(
    *,
    recovery_level="LOW",
    training_level="LOW",
    injury_level="LOW",
    nutrition_level="LOW",
    load_level="NORMAL",
    recovery_trend="STABLE",
    adaptation_level="GOOD",
    performance_trend="STABLE",
    data_freshness_level="LOW",
):
    return {
        "recovery": {
            "level": recovery_level,
            "reasons": [],
        },
        "training": {
            "level": training_level,
            "reasons": [],
        },
        "injury": {
            "level": injury_level,
            "reasons": [],
        },
        "nutrition": {
            "level": nutrition_level,
            "reasons": [],
        },
        "load": {
            "level": load_level,
            "reasons": [],
        },
        "recovery_trend": {
            "trend": recovery_trend,
            "reasons": [],
        },
        "adaptation": {
            "adaptation_level": adaptation_level,
            "reasons": [],
        },
        "performance": {
            "trend": performance_trend,
            "reasons": [],
        },
        "data_freshness": {
            "level": data_freshness_level,
            "reasons": [],
        },
    }


def test_limited_adaptation_requires_recovery_decision() -> None:
    result = DecisionEngine().decide(
        _assessment(
            adaptation_level="LIMITED",
        )
    )

    assert result["decision"] == "RECUPERA"
    assert result["strategy"] == "RECOVERY"
    assert result["risk_level"] == "HIGH_ALERT"


def test_moderate_adaptation_requires_plan_adjustment() -> None:
    result = DecisionEngine().decide(
        _assessment(
            adaptation_level="MODERATE",
        )
    )

    assert result["decision"] == "ADATTA"
    assert result["strategy"] == "ADAPT"
    assert result["risk_level"] == "CAUTION"


def test_declining_performance_with_high_load_requires_adjustment() -> None:
    result = DecisionEngine().decide(
        _assessment(
            load_level="HIGH",
            adaptation_level="GOOD",
            performance_trend="DECLINING",
        )
    )

    assert result["decision"] == "ADATTA"
    assert result["strategy"] == "ADAPT"


def test_improving_performance_and_good_adaptation_confirm_plan() -> None:
    result = DecisionEngine().decide(
        _assessment(
            adaptation_level="GOOD",
            performance_trend="IMPROVING",
        )
    )

    assert result["decision"] == "CONFERMA"
    assert result["strategy"] == "KEEP_PLAN"


def test_performance_is_included_in_reasoning() -> None:
    result = DecisionEngine().decide(
        _assessment(
            performance_trend="DECLINING",
        )
    )

    assert "Performance: in peggioramento" in result[
        "reasoning"
    ]


def test_performance_details_are_included_in_reasoning() -> None:
    assessment = _assessment(
        performance_trend="DECLINING",
    )

    assessment["performance"] = {
        "trend": "DECLINING",
        "details": {
            "ftp": {
                "start": 280,
                "end": 267.4,
                "change_percent": -4.5,
            }
        },
        "reasons": [],
    }

    result = DecisionEngine().decide(
        assessment
    )

    assert (
        "FTP: 280 -> 267.4 (-4.5%)"
        in result["reasoning"]
    )


def test_adaptation_prevents_confirmation_despite_green_recovery() -> None:
    result = DecisionEngine().decide(
        _assessment(
            recovery_level="LOW",
            adaptation_level="LIMITED",
            performance_trend="DECLINING",
        )
    )

    assert result["decision"] != "CONFERMA"


def test_unknown_adaptation_does_not_force_recovery() -> None:
    result = DecisionEngine().decide(
        _assessment(
            adaptation_level="UNKNOWN",
            performance_trend="STABLE",
        )
    )

    assert result["decision"] == "CONFERMA"


def test_high_risk_combination_has_priority_over_moderate_adaptation() -> None:
    result = DecisionEngine().decide(
        _assessment(
            recovery_level="MODERATE",
            load_level="HIGH",
            recovery_trend="DECLINING",
            adaptation_level="MODERATE",
            performance_trend="UNKNOWN",
        )
    )

    assert result["decision"] == "RECUPERA"
    assert result["strategy"] == "RECOVERY"
    assert result["risk_level"] == "HIGH_ALERT"
    assert result["confidence"] == 96


def test_default_high_freshness_cap_is_applied() -> None:
    result = DecisionEngine().decide(
        _assessment(
            injury_level="CRITICAL",
            data_freshness_level="HIGH",
        )
    )

    assert result["confidence"] == 75


def test_default_moderate_freshness_cap_is_applied() -> None:
    result = DecisionEngine().decide(
        _assessment(
            injury_level="CRITICAL",
            data_freshness_level="MODERATE",
        )
    )

    assert result["confidence"] == 85


def test_runtime_config_customizes_high_freshness_cap() -> None:
    config = RuntimeConfig(
        freshness_high_confidence_cap=68,
        freshness_moderate_confidence_cap=82,
    )

    result = DecisionEngine(
        runtime_config=config,
    ).decide(
        _assessment(
            injury_level="CRITICAL",
            data_freshness_level="HIGH",
        )
    )

    assert result["confidence"] == 68


def test_runtime_config_customizes_moderate_freshness_cap() -> None:
    config = RuntimeConfig(
        freshness_high_confidence_cap=68,
        freshness_moderate_confidence_cap=82,
    )

    result = DecisionEngine(
        runtime_config=config,
    ).decide(
        _assessment(
            injury_level="CRITICAL",
            data_freshness_level="MODERATE",
        )
    )

    assert result["confidence"] == 82


def test_freshness_cap_never_increases_confidence() -> None:
    config = RuntimeConfig(
        freshness_high_confidence_cap=90,
        freshness_moderate_confidence_cap=95,
    )

    result = DecisionEngine(
        runtime_config=config,
    ).decide(
        _assessment(
            recovery_level="UNKNOWN",
            data_freshness_level="HIGH",
        )
    )

    assert result["confidence"] == 72