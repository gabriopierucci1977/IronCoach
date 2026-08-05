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
    }


def test_athlete_profile_is_added_to_reasoning():
    assessments = _safe_assessments()
    assessments["athlete_profile"] = {
        "athlete_type": (
            "Triatleta Age Group endurance "
            "multidisciplinare"
        ),
        "strengths": [
            "Elevata esperienza sportiva",
        ],
        "limitations": [
            "Storico problematiche tendinee",
        ],
        "training_preferences": [
            "Possibilità di allenamento quotidiano",
        ],
        "injury_patterns": [
            (
                "Monitorare la risposta del tendine "
                "d'Achille al carico di corsa"
            ),
        ],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    reasoning = decision["reasoning"]

    assert (
        "Profilo atleta: "
        "Triatleta Age Group endurance "
        "multidisciplinare"
        in reasoning
    )

    assert (
        "Punto di forza atleta: "
        "Elevata esperienza sportiva"
        in reasoning
    )

    assert (
        "Limitazione atleta: "
        "Storico problematiche tendinee"
        in reasoning
    )

    assert (
        "Preferenza allenante: "
        "Possibilità di allenamento quotidiano"
        in reasoning
    )

    assert (
        "Pattern infortunio: "
        "Monitorare la risposta del tendine "
        "d'Achille al carico di corsa"
        in reasoning
    )


def test_empty_or_unknown_profile_values_are_ignored():
    assessments = _safe_assessments()
    assessments["athlete_profile"] = {
        "athlete_type": "N/D",
        "strengths": [
            "",
            "UNKNOWN",
            None,
        ],
        "limitations": [],
        "training_preferences": None,
        "injury_patterns": [
            "NON DISPONIBILE",
        ],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    reasoning = decision["reasoning"]

    assert not any(
        item.startswith(
            "Profilo atleta:"
        )
        for item in reasoning
    )

    assert not any(
        item.startswith(
            "Punto di forza atleta:"
        )
        for item in reasoning
    )

    assert not any(
        item.startswith(
            "Limitazione atleta:"
        )
        for item in reasoning
    )

    assert not any(
        item.startswith(
            "Preferenza allenante:"
        )
        for item in reasoning
    )

    assert not any(
        item.startswith(
            "Pattern infortunio:"
        )
        for item in reasoning
    )


def test_profile_reasoning_does_not_change_safe_decision():
    assessments = _safe_assessments()
    assessments["athlete_profile"] = {
        "athlete_type": "Atleta Age Group endurance",
        "strengths": [
            "Elevata esperienza sportiva",
        ],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert decision["decision"] == "CONFERMA"
    assert decision["strategy"] == "KEEP_PLAN"
    assert decision["risk_level"] == "NORMAL"