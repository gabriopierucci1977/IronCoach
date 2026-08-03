"""
Test Adaptation Analyzer.

La capacità di adattamento non deve dipendere dal solo carico totale.
Il risultato combina:
- profilo atleta e limitazioni note;
- carico recente;
- rapporto acuto/cronico;
- trend prestativo;
- recupero, quando disponibile.

Il formato resta compatibile con l'output storico:
{
    "adaptation_level": "",
    "risk_factors": [],
    "positive_factors": [],
    "reasons": [],
}
"""

from backend.analyzers.adaptation_analyzer import AdaptationAnalyzer


def _context(
    *,
    profile=None,
    load=None,
    performance=None,
    recovery=None,
):
    return {
        "athlete_profile": profile or {},
        "load_analysis": load or {},
        "performance_analysis": performance or {},
        "recovery_analysis": recovery or {},
    }


def test_unknown_without_meaningful_data() -> None:
    result = AdaptationAnalyzer().analyze(
        {}
    )

    assert result["adaptation_level"] == "UNKNOWN"
    assert result["risk_factors"] == []
    assert result["positive_factors"] == []
    assert result["reasons"] == [
        "Dati insufficienti per valutare l'adattamento"
    ]


def test_good_with_normal_load_and_improving_performance() -> None:
    result = AdaptationAnalyzer().analyze(
        _context(
            profile={
                "limitations": [],
            },
            load={
                "level": "NORMAL",
                "total_load": 900,
                "acute_chronic_ratio": 1.0,
                "sessions_with_load": 12,
            },
            performance={
                "trend": "IMPROVING",
            },
        )
    )

    assert result["adaptation_level"] == "GOOD"
    assert "Performance in crescita" in result[
        "positive_factors"
    ]
    assert result["risk_factors"] == []


def test_high_load_alone_is_moderate_not_limited() -> None:
    result = AdaptationAnalyzer().analyze(
        _context(
            load={
                "level": "HIGH",
                "total_load": 2200,
                "acute_chronic_ratio": 1.1,
                "sessions_with_load": 20,
            },
            performance={
                "trend": "STABLE",
            },
        )
    )

    assert result["adaptation_level"] == "MODERATE"
    assert "Carico recente elevato" in result[
        "risk_factors"
    ]


def test_high_load_with_limitations_is_limited() -> None:
    result = AdaptationAnalyzer().analyze(
        _context(
            profile={
                "limitations": [
                    "Dolore al ginocchio"
                ],
            },
            load={
                "level": "HIGH",
                "total_load": 2200,
                "acute_chronic_ratio": 1.2,
                "sessions_with_load": 20,
            },
        )
    )

    assert result["adaptation_level"] == "LIMITED"
    assert "Dolore al ginocchio" in result[
        "risk_factors"
    ]


def test_high_acute_chronic_ratio_is_risk_factor() -> None:
    result = AdaptationAnalyzer().analyze(
        _context(
            load={
                "level": "NORMAL",
                "total_load": 1000,
                "acute_chronic_ratio": 1.7,
                "sessions_with_load": 10,
            },
            performance={
                "trend": "STABLE",
            },
        )
    )

    assert result["adaptation_level"] == "MODERATE"
    assert "Rapporto acuto/cronico elevato" in result[
        "risk_factors"
    ]


def test_declining_performance_reduces_adaptation() -> None:
    result = AdaptationAnalyzer().analyze(
        _context(
            load={
                "level": "NORMAL",
                "total_load": 900,
                "acute_chronic_ratio": 1.0,
                "sessions_with_load": 12,
            },
            performance={
                "trend": "DECLINING",
            },
        )
    )

    assert result["adaptation_level"] == "MODERATE"
    assert "Performance in calo" in result[
        "risk_factors"
    ]


def test_poor_recovery_with_high_load_is_limited() -> None:
    result = AdaptationAnalyzer().analyze(
        _context(
            load={
                "level": "HIGH",
                "total_load": 2300,
                "acute_chronic_ratio": 1.4,
                "sessions_with_load": 18,
            },
            recovery={
                "state": "ROSSO",
                "level": "CRITICAL",
            },
        )
    )

    assert result["adaptation_level"] == "LIMITED"
    assert "Recupero insufficiente" in result[
        "risk_factors"
    ]


def test_good_recovery_is_positive_factor() -> None:
    result = AdaptationAnalyzer().analyze(
        _context(
            load={
                "level": "NORMAL",
                "total_load": 800,
                "acute_chronic_ratio": 0.9,
                "sessions_with_load": 10,
            },
            recovery={
                "state": "VERDE",
                "level": "LOW",
            },
        )
    )

    assert result["adaptation_level"] == "GOOD"
    assert "Recupero adeguato" in result[
        "positive_factors"
    ]


def test_string_limitation_is_not_split_into_characters() -> None:
    result = AdaptationAnalyzer().analyze(
        _context(
            profile={
                "limitations": "Tendinopatia",
            },
            load={
                "level": "LOW",
                "total_load": 300,
                "sessions_with_load": 5,
            },
        )
    )

    assert "Tendinopatia" in result[
        "risk_factors"
    ]
    assert "T" not in result[
        "risk_factors"
    ]


def test_numeric_strings_are_supported() -> None:
    result = AdaptationAnalyzer().analyze(
        _context(
            load={
                "level": "NORMAL",
                "total_load": "900",
                "acute_chronic_ratio": "1,0",
                "sessions_with_load": "12",
            },
            performance={
                "trend": "STABLE",
            },
        )
    )

    assert result["adaptation_level"] == "GOOD"


def test_unknown_load_does_not_become_good_from_zero_default() -> None:
    result = AdaptationAnalyzer().analyze(
        _context(
            profile={
                "limitations": [],
            },
            load={
                "level": "UNKNOWN",
                "total_load": 0,
                "sessions_with_load": 0,
            },
        )
    )

    assert result["adaptation_level"] == "UNKNOWN"


def test_preserves_output_contract() -> None:
    result = AdaptationAnalyzer().analyze(
        {}
    )

    assert set(result) == {
        "adaptation_level",
        "risk_factors",
        "positive_factors",
        "reasons",
    }