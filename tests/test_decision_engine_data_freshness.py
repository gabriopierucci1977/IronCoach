from backend.engines.decision_engine import DecisionEngine


def _base_assessments():
    return {
        "recovery": {
            "level": "MODERATE",
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
        "nutrition": {
            "level": "HIGH",
            "reasons": [],
        },
        "load": {
            "level": "HIGH",
            "reasons": [],
        },
        "recovery_trend": {
            "trend": "DECLINING",
            "reasons": [],
        },
        "adaptation": {
            "adaptation_level": "MODERATE",
            "reasons": [],
        },
        "performance": {
            "trend": "IMPROVING",
            "reasons": [],
        },
        "athlete_profile": {},
        "goal_profile": {},
    }


def test_confidence_is_unchanged_without_freshness_warning():
    assessments = _base_assessments()
    assessments["data_freshness"] = {
        "level": "LOW",
        "reasons": [],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["confidence"] == 96


def test_stale_training_caps_confidence_at_85():
    assessments = _base_assessments()
    assessments["data_freshness"] = {
        "level": "MODERATE",
        "reasons": [
            "Allenamento: dato obsoleto di 8 giorni",
        ],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["confidence"] == 85
    assert (
        "Freschezza dati: moderato"
        in decision["reasoning"]
    )


def test_stale_recovery_caps_confidence_at_75():
    assessments = _base_assessments()
    assessments["data_freshness"] = {
        "level": "HIGH",
        "reasons": [
            "Recovery: dato obsoleto di 12 giorni",
        ],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["confidence"] == 75
    assert (
        "Freschezza dati: alto"
        in decision["reasoning"]
    )


def test_future_recovery_date_caps_confidence_at_75():
    assessments = _base_assessments()
    assessments["data_freshness"] = {
        "level": "HIGH",
        "reasons": [
            "Recovery: data futura (2026-08-10)",
        ],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["confidence"] == 75
    assert (
        "Recovery: data futura (2026-08-10)"
        in decision["reasoning"]
    )


def test_freshness_cap_never_increases_lower_confidence():
    engine = DecisionEngine()

    engine._data_freshness = {
        "level": "HIGH",
        "reasons": [],
    }

    assert (
        engine._adjust_confidence_for_data_freshness(
            72
        )
        == 72
    )