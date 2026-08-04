"""
Test scenario atleta completo IronCoach.

Verifica casi reali:
- recovery compromesso;
- carico elevato;
- trend performance negativo;
- adattamento limitato;
- rischio elevato;
- decisione finale coerente.

Non usa Airtable.
"""

from backend.coach_engine import CoachEngine



def _context():

    return {
        "athlete_profile": {
            "athlete_name": "Atleta Test",
            "level": "advanced",
        },

        "recovery": {
            "recovery_score": 55,
            "sleep_score": 60,
        },

        "training": {
            "planned": True,
        },

        "nutrition": {
            "status": "ADEQUATE",
        },

        "injury": {
            "status": "LOW",
        },

        "training_history": [
            {
                "date": "2026-01-01",
                "training_load": 900,
            },
            {
                "date": "2026-01-07",
                "training_load": 950,
            },
        ],

        "recovery_history": [
            {
                "date": "2026-01-01",
                "recovery_score": 75,
            },
            {
                "date": "2026-01-07",
                "recovery_score": 55,
            },
        ],

        "performance_history": [
            {
                "date": "2026-01-01",
                "metric": "ftp",
                "value": 280,
            },
            {
                "date": "2026-02-01",
                "metric": "ftp",
                "value": 265,
            },
        ],
    }



def test_complete_athlete_scenario_generates_adaptation_decision():

    decision = CoachEngine().evaluate(
        _context()
    )


    assert decision[
        "decision"
    ] == "ADATTA"


    assert decision[
        "strategy"
    ] == "ADAPT"


    assert decision[
        "risk_level"
    ] == "CAUTION"




def test_complete_scenario_keeps_performance_intelligence():

    decision = CoachEngine().evaluate(
        _context()
    )


    performance = decision[
        "intelligence"
    ][
        "performance"
    ]


    assert performance[
        "trend"
    ] == "DECLINING"


    assert performance[
        "metrics"
    ][
        "ftp"
    ] == -5.4




def test_complete_scenario_reasoning_contains_main_factors():

    decision = CoachEngine().evaluate(
        _context()
    )


    reasoning = decision[
        "reasoning"
    ]


    assert any(
        "Performance" in item
        for item in reasoning
    )


    assert any(
        "Recovery" in item
        for item in reasoning
    )




def test_high_risk_athlete_scenario_requires_recovery():

    context = _context()

    context["recovery"] = {
        "recovery_score": 35,
        "sleep_score": 40,
    }


    decision = CoachEngine().evaluate(
        context
    )


    assert decision[
        "decision"
    ] == "RECUPERA"


    assert decision[
        "strategy"
    ] == "RECOVERY"


    assert decision[
        "risk_level"
    ] == "HIGH_ALERT"




def test_high_risk_scenario_keeps_performance_decline_information():

    context = _context()

    context["recovery"] = {
        "recovery_score": 35,
        "sleep_score": 40,
    }


    decision = CoachEngine().evaluate(
        context
    )


    performance = decision[
        "intelligence"
    ][
        "performance"
    ]


    assert performance[
        "trend"
    ] == "DECLINING"


    assert performance[
        "metrics"
    ][
        "ftp"
    ] == -5.4